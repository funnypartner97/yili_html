import asyncio
from uuid import uuid7

import pytest
from sqlalchemy import select

from src.db.models import ArtifactVersion, Job
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


def setup_confirmed(client, session):
    artifact_id = client.post('/v1/artifacts', json={'title': 'Report'}).json()['id']
    add_source(session, artifact_id)
    planner = Planner(session, FakeProvider())
    plan = asyncio.run(planner.create_plan(artifact_id, '生成管理层汇报', {}))
    job = planner.confirm_plan(artifact_id, plan.id)
    return artifact_id, plan, job


def test_document_not_ready_until_first_version_exists(client, session):
    artifact_id, plan, job = setup_confirmed(client, session)
    response = client.get(f'/v1/artifacts/{artifact_id}/document')
    assert response.status_code == 409 and response.json()['code'] == 'document_not_ready'
    asyncio.run(Generator(session, FakeProvider()).generate(plan.id))
    document = client.get(f'/v1/artifacts/{artifact_id}/document')
    assert document.status_code == 200, document.text
    body = document.json()
    assert body['schemaVersion'] == '1.0.0'
    assert body['artifactId'] == artifact_id
    assert body['sections'] and body['outputModes'] == ['document']
    assert body['sections'][0]['blocks'][0]['sourceRefs'][0]['sourceId']


def test_job_polling_reports_progress_then_terminal_state(client, session):
    artifact_id, plan, job = setup_confirmed(client, session)
    first = client.get(f'/v1/jobs/{job.id}')
    assert first.status_code == 200, first.text
    assert first.json()['status'] == 'queued' and first.json()['progress'] == 0
    assert first.json()['stage'] is None and first.json()['error'] is None
    asyncio.run(Generator(session, FakeProvider()).generate(plan.id))
    done = client.get(f'/v1/jobs/{job.id}')
    body = done.json()
    assert body['status'] == 'succeeded' and body['progress'] == 100
    assert body['stage'] == 'completed' and body['error'] is None
    assert len(session.scalars(select(ArtifactVersion)).all()) == 1


def test_job_failure_payload_is_pollable(client, session):
    artifact_id, plan, job = setup_confirmed(client, session)

    class Fabricating(FakeProvider):
        async def create_document(self, request):
            result = await super().create_document(request)
            raw = result.value.model_dump(by_alias=True, mode='json')
            raw['sections'][0]['blocks'][0]['sourceRefs'] = [{'sourceId': str(uuid7()), 'locator': 'x'}]
            return type(result)(raw, result.audit)

    with pytest.raises(Exception):
        asyncio.run(Generator(session, Fabricating()).generate(plan.id))
    failed = client.get(f'/v1/jobs/{job.id}')
    body = failed.json()
    assert body['status'] == 'failed'
    assert body['error'] == {'code': 'citation_source_missing',
                             'message': body['error']['message'], 'stage': 'validating_document'}
    blocked = client.get(f'/v1/artifacts/{artifact_id}/document')
    assert blocked.status_code == 409 and blocked.json()['code'] == 'document_not_ready'


def test_unknown_job_and_artifact_return_not_found(client):
    missing_job = client.get(f'/v1/jobs/{uuid7()}')
    assert missing_job.status_code == 404 and missing_job.json()['code'] == 'job_not_found'
    missing_document = client.get(f'/v1/artifacts/{uuid7()}/document')
    assert missing_document.status_code == 404 and missing_document.json()['code'] == 'artifact_not_found'
