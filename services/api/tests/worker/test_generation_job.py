import asyncio
from uuid import uuid7

import pytest
from arq import Retry
from sqlalchemy import select

from src.core.errors import DomainError
from src.db.models import Artifact, ArtifactVersion, Job
from src.db.repositories import ArtifactRepository
from src.generation.fake_provider import FakeProvider
from src.generation.planner import Planner
from src.worker import jobs
from tests.generation.test_planner import add_source


@pytest.fixture(autouse=True)
def worker_engine(engine):
    jobs.configure(engine=engine, provider_factory=FakeProvider)
    yield
    jobs.configure(engine=None, provider_factory=jobs.get_provider)


def setup_confirmed(session):
    artifact = ArtifactRepository(session).create_artifact('Report')
    add_source(session, artifact.id)
    planner = Planner(session, FakeProvider())
    plan = asyncio.run(planner.create_plan(artifact.id, '生成管理层汇报', {}))
    return artifact, planner.confirm_plan(artifact.id, plan.id)


def run(job_id, job_try=1):
    return asyncio.run(jobs.generate_document_job({'job_try': job_try}, job_id))


def test_worker_completes_job_and_saves_document(session):
    artifact, job = setup_confirmed(session)
    run(job.id)
    session.expire_all()
    assert session.get(Job, job.id).status == 'succeeded'
    assert session.get(Artifact, artifact.id).status == 'editable'
    versions = session.scalars(select(ArtifactVersion)).all()
    assert len(versions) == 1 and versions[0].origin == 'generation'


def test_worker_retries_transient_provider_failure_with_backoff(session):
    artifact, job = setup_confirmed(session)

    class Unavailable(FakeProvider):
        async def create_document(self, request):
            raise DomainError('provider_unavailable', 'The model provider is temporarily unavailable.', status_code=503)

    jobs.configure(provider_factory=Unavailable)
    with pytest.raises(Retry):
        run(job.id, job_try=1)
    session.expire_all()
    assert session.get(Job, job.id).status == 'running'
    assert session.get(Artifact, artifact.id).status == 'generating'


def test_worker_exhausted_retries_mark_job_and_artifact_failed(session):
    artifact, job = setup_confirmed(session)

    class Unavailable(FakeProvider):
        async def create_document(self, request):
            raise DomainError('provider_unavailable', 'The model provider is temporarily unavailable.', status_code=503)

    jobs.configure(provider_factory=Unavailable)
    run(job.id, job_try=3)
    session.expire_all()
    failed = session.get(Job, job.id)
    assert failed.status == 'failed'
    assert failed.error['code'] == 'provider_unavailable'
    assert failed.error['stage'] == 'generating_content'
    assert session.get(Artifact, artifact.id).status == 'failed'


def test_worker_non_retryable_failure_marks_failed_without_raising(session):
    artifact, job = setup_confirmed(session)

    class Fabricating(FakeProvider):
        async def create_document(self, request):
            result = await super().create_document(request)
            raw = result.value.model_dump(by_alias=True, mode='json')
            raw['sections'][0]['blocks'][0]['sourceRefs'][0]['sourceId'] = str(uuid7())
            return type(result)(raw, result.audit)

    jobs.configure(provider_factory=Fabricating)
    run(job.id)
    session.expire_all()
    failed = session.get(Job, job.id)
    assert failed.status == 'failed'
    assert failed.error['code'] == 'citation_source_missing'
    assert session.get(Artifact, artifact.id).status == 'failed'
    assert session.scalars(select(ArtifactVersion)).all() == []


def test_worker_rejects_unknown_job(engine):
    with pytest.raises(DomainError) as error:
        run(str(uuid7()))
    assert error.value.code == 'job_not_found'
