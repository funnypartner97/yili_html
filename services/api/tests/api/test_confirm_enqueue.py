import asyncio

import pytest
from sqlalchemy import select

from src.db.models import Job
from src.generation.fake_provider import FakeProvider
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


def _ready_plan(client, session):
    artifact_id = client.post("/v1/artifacts", json={"title": "Report"}).json()["id"]
    add_source(session, artifact_id)
    plan = asyncio.run(Planner(session, FakeProvider()).create_plan(artifact_id, "生成管理层汇报", {}))
    return artifact_id, plan.id, f"/v1/artifacts/{artifact_id}/plans/{plan.id}/confirm"


def test_confirm_enqueues_the_generation_job(client, session, enqueuer):
    _, _, confirm_url = _ready_plan(client, session)
    response = client.post(confirm_url)
    assert response.status_code == 202, response.text
    job_id = response.json()["jobId"]
    assert response.json()["status"] == "queued"
    assert enqueuer.enqueued == [job_id]


def test_reconfirmation_reuses_the_same_job_id(client, session, enqueuer):
    _, _, confirm_url = _ready_plan(client, session)
    first = client.post(confirm_url).json()["jobId"]
    second = client.post(confirm_url).json()["jobId"]
    assert first == second
    # ARQ dedupes on _job_id, so re-enqueueing the same id is safe.
    assert set(enqueuer.enqueued) == {first}


def test_queue_unavailable_is_recoverable_and_keeps_the_job_queued(client, session, enqueuer):
    artifact_id, _, confirm_url = _ready_plan(client, session)
    enqueuer.raise_on_enqueue = True
    failed = client.post(confirm_url)
    assert failed.status_code == 503
    assert failed.json()["code"] == "queue_unavailable"

    # The durable job row survives the failed enqueue and is still queued.
    job = session.scalar(select(Job).where(Job.artifact_id == artifact_id))
    assert job is not None and job.status == "queued"

    # Confirming again retries the enqueue and succeeds once the queue recovers.
    enqueuer.raise_on_enqueue = False
    recovered = client.post(confirm_url)
    assert recovered.status_code == 202
    assert recovered.json()["jobId"] == job.id
    assert enqueuer.enqueued == [job.id]
