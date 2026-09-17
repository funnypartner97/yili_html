import asyncio
from datetime import UTC, datetime

import pytest

from src.files.storage import MemoryStorage, get_storage
from src.generation.fake_provider import FakeProvider
from src.generation.generator import Generator
from src.generation.planner import Planner
from src.generation.provider import get_provider
from src.main import app
from tests.generation.test_planner import add_source


@pytest.fixture
def storage():
    memory = MemoryStorage()
    previous_provider = app.dependency_overrides.get(get_provider)
    previous_storage = app.dependency_overrides.get(get_storage)
    app.dependency_overrides[get_provider] = FakeProvider
    app.dependency_overrides[get_storage] = lambda: memory
    yield memory
    app.dependency_overrides.pop(get_provider, None)
    app.dependency_overrides.pop(get_storage, None)
    if previous_provider:
        app.dependency_overrides[get_provider] = previous_provider
    if previous_storage:
        app.dependency_overrides[get_storage] = previous_storage


@pytest.fixture
def editable(client, session):
    artifact_id = client.post("/v1/artifacts", json={"title": "Report"}).json()["id"]
    add_source(session, artifact_id)
    planner = Planner(session, FakeProvider())
    plan = asyncio.run(planner.create_plan(artifact_id, "生成管理层汇报", {}))
    planner.confirm_plan(artifact_id, plan.id)
    asyncio.run(Generator(session, FakeProvider()).generate(plan.id))
    return artifact_id


def test_export_produces_a_signed_self_contained_archive(client, storage, editable):
    response = client.post(f"/v1/artifacts/{editable}/exports/html")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["downloadUrl"].startswith("/v1/exports/memory/exports/")
    assert body["documentVersion"] == 1
    assert body["passedLayers"] == ["schema", "semantic", "layout"]
    assert body["diagnostics"] == []
    assert body["contentHash"]
    expires = datetime.fromisoformat(body["expiresAt"])
    assert (expires - datetime.now(UTC)).total_seconds() == pytest.approx(900, abs=30)

    # The deterministic ZIP is stored in object storage under a content-addressed key.
    key = next(iter(storage.objects))
    assert key.endswith(".zip") and body["contentHash"] in key
    assert storage.objects[key][:2] == b"PK"


def test_export_is_deterministic_across_calls(client, storage, editable):
    first = client.post(f"/v1/artifacts/{editable}/exports/html").json()["contentHash"]
    second = client.post(f"/v1/artifacts/{editable}/exports/html").json()["contentHash"]
    assert first == second
    # Same content hash means the same object key; no duplicate archives accumulate.
    assert len([key for key in storage.objects if key.endswith(".zip")]) == 1


def test_export_requires_a_generated_document(client, storage):
    empty_id = client.post("/v1/artifacts", json={"title": "Empty"}).json()["id"]
    response = client.post(f"/v1/artifacts/{empty_id}/exports/html")
    assert response.status_code == 409
    assert response.json()["code"] == "document_not_ready"
