from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.errors import DomainError
from src.db.models import Artifact, GenerationPlan, Job
from src.db.repositories import ArtifactRepository
from src.generation.fake_provider import FakeProvider
from src.generation.planner import Planner
from src.generation.provider import get_provider
from src.main import app
from tests.generation.test_planner import add_source, create


@pytest.fixture(autouse=True)
def fake_provider():
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_provider] = FakeProvider
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def setup_plan(client, session):
    artifact_id = client.post('/v1/artifacts', json={'title': 'Report'}).json()['id']
    add_source(session, artifact_id)
    url = f'/v1/artifacts/{artifact_id}/plans'
    response = client.post(url, json={'instruction': '生成报告', 'parameters': {'outputModes': ['document', 'presentation']}})
    assert response.status_code == 201, response.text
    return artifact_id, url, response.json()


def test_create_edit_confirm_are_explicit_append_only_and_idempotent(client, session):
    artifact_id, url, first = setup_plan(client, session)
    assert first['status'] == 'ready' and first['revision'] == 1
    assert session.scalars(select(Job)).all() == []
    edited = deepcopy(first['plan'])
    edited['audience'] = '董事会'
    edited['outline'][0]['title'] = '关键经营结论'
    response = client.put(f"{url}/{first['id']}", json={'plan': edited})
    assert response.status_code == 201, response.text
    second = response.json()
    assert second['id'] != first['id'] and second['revision'] == 2
    assert client.post(f"{url}/{first['id']}/confirm").json()['code'] == 'plan_revision_stale'
    confirm_url = f"{url}/{second['id']}/confirm"
    confirmation = client.post(confirm_url)
    assert confirmation.status_code == 202, confirmation.text
    again = client.post(confirm_url)
    assert again.json()['jobId'] == confirmation.json()['jobId']
    session.expire_all()
    jobs = session.scalars(select(Job)).all()
    assert len(jobs) == 1 and jobs[0].status == 'queued'
    assert jobs[0].payload['plan'] == edited
    assert jobs[0].payload['planId'] == second['id']
    assert session.get(Artifact, artifact_id).status == 'generating'
    edited['audience'] = 'Internal'
    third = client.put(f"{url}/{second['id']}", json={'plan': edited})
    assert third.status_code == 201
    session.expire_all()
    assert session.get(GenerationPlan, second['id']).payload['audience'] == '董事会'
    assert session.get(Job, jobs[0].id).payload['plan']['audience'] == '董事会'
    assert session.get(Artifact, artifact_id).status == 'generating'
    blocked = client.post(f"{url}/{third.json()['id']}/confirm")
    assert blocked.status_code == 409 and blocked.json()['code'] == 'generation_in_progress'


def test_artifact_scoping_invalid_fields_and_source_guard(client, session):
    artifact_id, url, plan = setup_plan(client, session)
    foreign = client.post('/v1/artifacts', json={'title': 'Other'}).json()['id']
    for method, suffix, body in [('put', '', {'plan': plan['plan']}), ('post', '/confirm', None)]:
        response = getattr(client, method)(f"/v1/artifacts/{foreign}/plans/{plan['id']}{suffix}", json=body) if body else client.post(f"/v1/artifacts/{foreign}/plans/{plan['id']}{suffix}")
        assert response.status_code == 404 and response.json()['code'] == 'plan_not_found'
    for body in [{'instruction': ' '}, {'instruction': 'ok', 'provider': 'openai'},
                 {'instruction': 'ok', 'parameters': {'baseUrl': 'http://localhost'}},
                 {'instruction': 'ok', 'parameters': {'materialRange': []}}]:
        assert client.post(url, json=body).status_code == 422
    assert client.post(f'/v1/artifacts/{foreign}/plans', json={'instruction': 'ok'}).json()['code'] == 'source_required'
    add_source(session, artifact_id, title='New source')
    response = client.post(f"{url}/{plan['id']}/confirm")
    assert response.status_code == 409 and response.json()['code'] == 'plan_sources_changed'
    assert session.scalars(select(Job)).all() == []


def test_confirmation_has_one_atomic_winner_across_sessions(session, engine):
    artifact = ArtifactRepository(session).create_artifact('Concurrent')
    artifact_id = artifact.id
    add_source(session, artifact_id)
    plan_id = create(Planner(session, FakeProvider()), artifact_id).id
    session.rollback()
    barrier = Barrier(2)
    def confirm():
        with Session(engine) as independent:
            barrier.wait()
            return Planner(independent, FakeProvider()).confirm_plan(artifact_id, plan_id).id
    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(lambda _: confirm(), range(2)))
    assert ids[0] == ids[1]
    assert len(session.scalars(select(Job)).all()) == 1


def test_failed_job_insert_rolls_back_confirmation_and_can_retry(session):
    artifact = ArtifactRepository(session).create_artifact('Atomic')
    add_source(session, artifact.id)
    planner = Planner(session, FakeProvider())
    row = create(planner, artifact.id)
    def fail(mapper, connection, target):
        target.kind = None
    event.listen(Job, 'before_insert', fail)
    try:
        with pytest.raises(IntegrityError):
            planner.confirm_plan(artifact.id, row.id)
    finally:
        event.remove(Job, 'before_insert', fail)
    session.expire_all()
    assert row.status == 'ready' and row.confirmed_at is None
    assert artifact.status == 'plan_ready'
    assert session.scalars(select(Job)).all() == []
    assert planner.confirm_plan(artifact.id, row.id).status == 'queued'


def test_confirm_rejects_unready_and_untracked_legacy_plan(session):
    artifact = ArtifactRepository(session).create_artifact('Legacy')
    add_source(session, artifact.id)
    row = create(Planner(session, FakeProvider()), artifact.id)
    row = session.get(GenerationPlan, row.id)
    row.status = 'confirmed'
    session.commit()
    with pytest.raises(DomainError) as error:
        Planner(session, FakeProvider()).confirm_plan(artifact.id, row.id)
    assert error.value.code == 'plan_not_ready'
    assert session.scalars(select(Job)).all() == []


def test_confirmation_rejects_changed_parsed_content_with_same_source_id(client, session):
    from src.db.models import SourceFile
    artifact_id, url, plan = setup_plan(client, session)
    source = session.scalar(select(SourceFile).where(SourceFile.artifact_id == artifact_id))
    content = deepcopy(source.parsed_content)
    content['tables'][0]['rows'] = [['Q1', 999]]
    source.parsed_content = content
    session.commit()
    response = client.post(f"{url}/{plan['id']}/confirm")
    assert response.status_code == 409 and response.json()['code'] == 'plan_sources_changed'
    assert session.scalars(select(Job)).all() == []
