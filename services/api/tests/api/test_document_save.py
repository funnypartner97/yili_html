import asyncio
from copy import deepcopy
from uuid import uuid7

import pytest
from sqlalchemy import select

from src.core.errors import DomainError
from src.db.models import Artifact, ArtifactVersion
from src.db.repositories import ArtifactRepository
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


@pytest.fixture
def editable(client, session):
    artifact_id = client.post('/v1/artifacts', json={'title': 'Report'}).json()['id']
    add_source(session, artifact_id)
    planner = Planner(session, FakeProvider())
    plan = asyncio.run(planner.create_plan(artifact_id, '生成管理层汇报', {}))
    planner.confirm_plan(artifact_id, plan.id)
    version = asyncio.run(Generator(session, FakeProvider()).generate(plan.id))
    return artifact_id, version


def test_save_rejects_stale_version(client, session, editable):
    artifact_id, version = editable
    response = client.put(f'/v1/artifacts/{artifact_id}/document',
        headers={'If-Match': '0'}, json=version.document)
    assert response.status_code == 409
    body = response.json()
    assert body['code'] == 'version_conflict'
    assert body['details']['latestVersion'] == 1
    assert session.get(Artifact, artifact_id).latest_version == 1


def test_save_requires_if_match_header(client, editable):
    artifact_id, version = editable
    response = client.put(f'/v1/artifacts/{artifact_id}/document', json=version.document)
    assert response.status_code == 428
    assert response.json()['code'] == 'version_precondition_required'


def test_save_validates_graph_and_creates_manual_version(client, session, editable):
    artifact_id, version = editable
    document = deepcopy(version.document)
    document['sections'][0]['blocks'] = [
        {'id': str(uuid7()), 'order': 0, 'kind': 'richText', 'text': '手工编辑后的执行摘要。',
         'sourceRefs': document['sections'][0]['blocks'][0]['sourceRefs']}]
    response = client.put(f'/v1/artifacts/{artifact_id}/document',
        headers={'If-Match': '1'}, json=document)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['versionNumber'] == 2 and body['savedAt']
    session.expire_all()
    artifact = session.get(Artifact, artifact_id)
    assert artifact.latest_version == 2
    versions = session.scalars(select(ArtifactVersion).order_by(ArtifactVersion.version_number)).all()
    assert [v.version_number for v in versions] == [1, 2]
    assert versions[1].origin == 'manual'
    assert versions[1].document['sections'][0]['blocks'][0]['text'] == '手工编辑后的执行摘要。'
    assert versions[0].document['sections'][0]['blocks'][0]['text'] != '手工编辑后的执行摘要。'


def test_save_rejects_invalid_graph_without_versioning(client, session, editable):
    artifact_id, version = editable
    document = deepcopy(version.document)
    document['sections'][0]['blocks'][0]['sourceRefs'] = [{'sourceId': '00000000-0000-7000-8000-000000000000', 'locator': 'x'}]
    response = client.put(f'/v1/artifacts/{artifact_id}/document',
        headers={'If-Match': '1'}, json=document)
    assert response.status_code == 502 and response.json()['code'] == 'citation_source_missing'
    assert session.get(Artifact, artifact_id).latest_version == 1
    document['schemaVersion'] = '9.9.9'
    broken = client.put(f'/v1/artifacts/{artifact_id}/document',
        headers={'If-Match': '1'}, json=document)
    assert broken.status_code == 422


def test_save_rejects_foreign_or_mismatched_graph(client, editable):
    artifact_id, version = editable
    response = client.put(f'/v1/artifacts/{uuid7()}/document',
        headers={'If-Match': '1'}, json=version.document)
    assert response.status_code == 404
    mismatched = deepcopy(version.document)
    mismatched['artifactId'] = str(uuid7())
    response = client.put(f'/v1/artifacts/{artifact_id}/document',
        headers={'If-Match': '1'}, json=mismatched)
    assert response.status_code == 409 and response.json()['code'] == 'artifact_id_mismatch'


def test_save_blocks_missing_document(client, session, editable):
    artifact_id, version = editable
    empty_id = client.post('/v1/artifacts', json={'title': 'Empty'}).json()['id']
    document = deepcopy(version.document)
    document['artifactId'] = empty_id
    response = client.put(f'/v1/artifacts/{empty_id}/document',
        headers={'If-Match': '0'}, json=document)
    assert response.status_code == 409 and response.json()['code'] == 'document_not_ready'
    assert session.get(Artifact, empty_id).latest_version == 0
