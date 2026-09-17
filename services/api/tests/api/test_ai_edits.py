import asyncio
from datetime import timedelta
from uuid import uuid7

import pytest
from sqlalchemy import select

from src.db.models import Artifact, ArtifactVersion, EditPreview, utc_now
from src.generation.fake_provider import FakeProvider
from src.generation.generator import Generator
from src.generation.planner import Planner
from src.generation.provider import get_provider
from src.main import app
from tests.generation.test_planner import add_source


@pytest.fixture(autouse=True)
def fake_provider():
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_provider] = FakeProvider
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def _generate(client, session, title="Report", sources=1):
    artifact_id = client.post("/v1/artifacts", json={"title": title}).json()["id"]
    for index in range(sources):
        add_source(session, artifact_id, title=f"材料 {index + 1}")
    planner = Planner(session, FakeProvider())
    plan = asyncio.run(planner.create_plan(artifact_id, "生成管理层汇报", {}))
    planner.confirm_plan(artifact_id, plan.id)
    asyncio.run(Generator(session, FakeProvider()).generate(plan.id))
    return artifact_id


@pytest.fixture
def editable(client, session):
    return _generate(client, session)


def _preview(client, artifact_id, instruction="改写执行摘要", block_ids=None):
    body = {"instruction": instruction}
    if block_ids is not None:
        body["blockIds"] = block_ids
    response = client.post(f"/v1/artifacts/{artifact_id}/edits/preview", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _text_of(document):
    return document["sections"][0]["blocks"][0]["text"]


def test_preview_proposes_commands_without_mutating_the_artifact(client, session, editable):
    body = _preview(client, editable, "更专业的执行摘要")
    assert body["baseVersion"] == 1
    assert body["commands"][0]["kind"] == "replaceText"
    assert body["commands"][0]["text"] == "更专业的执行摘要"
    assert body["affectedBlockIds"] and body["summary"]
    assert body["expiresAt"]
    session.expire_all()
    assert session.get(Artifact, editable).latest_version == 1


def test_preview_requires_an_instruction(client, editable):
    response = client.post(f"/v1/artifacts/{editable}/edits/preview", json={"instruction": ""})
    assert response.status_code == 422


def test_preview_targets_a_selected_block(client, session):
    artifact_id = _generate(client, session, sources=2)
    document = session.scalar(select(ArtifactVersion).where(ArtifactVersion.artifact_id == artifact_id)).document
    second_block = document["sections"][1]["blocks"][0]["id"]
    body = _preview(client, artifact_id, "只改这一段", block_ids=[second_block])
    assert body["commands"][0]["blockId"] == second_block
    assert body["affectedBlockIds"] == [second_block]


def test_apply_persists_an_ai_version(client, session, editable):
    body = _preview(client, editable, "全新的执行摘要")
    response = client.post(f"/v1/artifacts/{editable}/edits/{body['previewId']}/apply")
    assert response.status_code == 200, response.text
    assert response.json()["versionNumber"] == 2
    session.expire_all()
    versions = session.scalars(select(ArtifactVersion).order_by(ArtifactVersion.version_number)).all()
    assert [v.version_number for v in versions] == [1, 2]
    assert versions[1].origin == "ai"
    assert _text_of(versions[1].document) == "全新的执行摘要"
    # The prior version is immutable.
    assert _text_of(versions[0].document) != "全新的执行摘要"


def test_apply_is_idempotent_and_rejects_reuse(client, editable):
    body = _preview(client, editable, "第一次修改")
    first = client.post(f"/v1/artifacts/{editable}/edits/{body['previewId']}/apply")
    assert first.status_code == 200
    second = client.post(f"/v1/artifacts/{editable}/edits/{body['previewId']}/apply")
    assert second.status_code == 409
    assert second.json()["code"] == "preview_already_applied"


def test_apply_rejects_a_stale_base_version(client, session, editable):
    body = _preview(client, editable, "并发的修改")
    # A concurrent manual save advances the artifact beyond the preview's base.
    document = session.scalar(select(ArtifactVersion).where(
        ArtifactVersion.artifact_id == editable, ArtifactVersion.version_number == 1)).document
    manual = client.put(f"/v1/artifacts/{editable}/document", headers={"If-Match": "1"}, json=document)
    assert manual.status_code == 200
    response = client.post(f"/v1/artifacts/{editable}/edits/{body['previewId']}/apply")
    assert response.status_code == 409
    assert response.json()["code"] == "version_conflict"
    assert response.json()["details"]["latestVersion"] == 2


def test_apply_rejects_an_expired_preview(client, session, editable):
    body = _preview(client, editable, "过期的修改")
    preview = session.get(EditPreview, body["previewId"])
    preview.expires_at = utc_now() - timedelta(minutes=1)
    session.commit()
    response = client.post(f"/v1/artifacts/{editable}/edits/{body['previewId']}/apply")
    assert response.status_code == 409
    assert response.json()["code"] == "preview_expired"


def test_apply_unknown_preview_is_not_found(client, editable):
    response = client.post(f"/v1/artifacts/{editable}/edits/{uuid7()}/apply")
    assert response.status_code == 404
    assert response.json()["code"] == "preview_not_found"


def test_preview_requires_a_generated_document(client):
    empty_id = client.post("/v1/artifacts", json={"title": "Empty"}).json()["id"]
    response = client.post(f"/v1/artifacts/{empty_id}/edits/preview", json={"instruction": "改写"})
    assert response.status_code == 409
    assert response.json()["code"] == "document_not_ready"


def test_versions_list_and_restore_previous_version(client, session, editable):
    _preview_and_apply(client, editable, "AI 修改后的内容")
    listing = client.get(f"/v1/artifacts/{editable}/versions")
    assert listing.status_code == 200
    versions = listing.json()["versions"]
    assert [item["versionNumber"] for item in versions] == [2, 1]
    assert versions[0]["origin"] == "ai" and versions[1]["origin"] == "generation"

    # Undo: restore version 1 as a new immutable 'restore' version.
    restore = client.post(f"/v1/artifacts/{editable}/versions/1/restore")
    assert restore.status_code == 200
    assert restore.json()["versionNumber"] == 3
    session.expire_all()
    rows = session.scalars(select(ArtifactVersion).order_by(ArtifactVersion.version_number)).all()
    assert rows[2].origin == "restore"
    assert _text_of(rows[2].document) == _text_of(rows[0].document)


def test_restore_unknown_version_is_not_found(client, editable):
    response = client.post(f"/v1/artifacts/{editable}/versions/99/restore")
    assert response.status_code == 404
    assert response.json()["code"] == "version_not_found"


def _preview_and_apply(client, artifact_id, instruction):
    body = _preview(client, artifact_id, instruction)
    response = client.post(f"/v1/artifacts/{artifact_id}/edits/{body['previewId']}/apply")
    assert response.status_code == 200, response.text
    return response.json()
