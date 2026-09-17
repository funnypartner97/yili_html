import asyncio
from uuid import uuid7

import pytest
from sqlalchemy import select

from src.core.errors import DomainError
from src.db.models import Artifact, ArtifactVersion, GenerationPlan, Job, SourceFile
from src.db.repositories import ArtifactRepository
from src.generation.fake_provider import FakeProvider
from src.generation.generator import Generator
from src.generation.planner import Planner
from tests.generation.test_planner import add_source


def prepare(session, *, confirm=True):
    artifact = ArtifactRepository(session).create_artifact('Report')
    add_source(session, artifact.id)
    planner = Planner(session, FakeProvider())
    plan = asyncio.run(planner.create_plan(artifact.id, '生成管理层汇报', {}))
    job = planner.confirm_plan(artifact.id, plan.id) if confirm else None
    return artifact, plan, job


def generate(generator, plan_id):
    return asyncio.run(generator.generate(plan_id))


def test_generation_requires_confirmed_plan(session):
    artifact, plan, _ = prepare(session, confirm=False)
    with pytest.raises(DomainError) as error:
        generate(Generator(session, FakeProvider()), plan.id)
    assert error.value.code == 'plan_confirmation_required'
    assert session.scalars(select(ArtifactVersion)).all() == []


def test_generation_succeeds_with_stages_and_saves_version(session, monkeypatch):
    artifact, plan, job = prepare(session)
    stages = []
    original = Generator._report

    def spy(self, job, progress, stage, *, status=None):
        stages.append((progress, stage, status))
        return original(self, job, progress, stage, status=status)

    monkeypatch.setattr(Generator, '_report', spy)
    version = generate(Generator(session, FakeProvider()), plan.id)
    assert [(progress, stage) for progress, stage, _ in stages] == [
        (10, 'loading_sources'), (30, 'generating_structure'), (60, 'generating_content'),
        (85, 'validating_document'), (95, 'saving_version'), (100, 'completed')]
    assert session.get(Artifact, artifact.id).status == 'editable'
    assert session.get(Artifact, artifact.id).latest_version == 1
    assert version.version_number == 1 and version.origin == 'generation'
    assert version.document['artifactId'] == artifact.id
    assert version.document['sections'][0]['blocks'][0]['sourceRefs'][0]['sourceId']
    completed = session.get(Job, job.id)
    assert completed.status == 'succeeded' and completed.progress == 100 and completed.stage == 'completed'
    assert completed.error is None


def test_generation_is_idempotent_after_success(session):
    artifact, plan, job = prepare(session)
    first = generate(Generator(session, FakeProvider()), plan.id)
    second = generate(Generator(session, FakeProvider()), plan.id)
    assert second.version_number == first.version_number == 1
    assert len(session.scalars(select(ArtifactVersion)).all()) == 1


def test_generation_passes_confirmed_plan_snapshot_and_sources(session):
    artifact, plan, job = prepare(session)

    class RecordingProvider(FakeProvider):
        async def create_document(self, request):
            self.request = request
            return await super().create_document(request)

    provider = RecordingProvider()
    generate(Generator(session, provider), plan.id)
    assert provider.request.plan['artifactId'] == artifact.id
    assert [source.source_id for source in provider.request.sources] == [
        row.id for row in session.scalars(select(SourceFile).where(SourceFile.artifact_id == artifact.id))]


def test_unknown_citation_fails_job_and_artifact_without_retry(session):
    artifact, plan, job = prepare(session)

    class Fabricating(FakeProvider):
        async def create_document(self, request):
            result = await super().create_document(request)
            raw = result.value.model_dump(by_alias=True, mode='json')
            raw['sections'][0]['blocks'][0]['sourceRefs'] = [{'sourceId': str(uuid7()), 'locator': 'x'}]
            return type(result)(raw, result.audit)

    with pytest.raises(DomainError) as error:
        generate(Generator(session, Fabricating()), plan.id)
    assert error.value.code == 'citation_source_missing'
    assert 'secret' not in str(error.value)
    failed = session.get(Job, job.id)
    assert failed.status == 'failed'
    assert failed.error == {'code': 'citation_source_missing', 'message': error.value.message,
                            'stage': 'validating_document'}
    assert session.get(Artifact, artifact.id).status == 'failed'
    assert session.get(GenerationPlan, plan.id).status == 'confirmed'
    assert session.scalars(select(ArtifactVersion)).all() == []


def test_nonconforming_provider_document_fails_without_retry(session):
    artifact, plan, job = prepare(session)

    class Broken(FakeProvider):
        async def create_document(self, request):
            result = await super().create_document(request)
            raw = result.value.model_dump(by_alias=True, mode='json')
            raw['artifactId'] = str(uuid7())
            return type(result)(raw, result.audit)

    with pytest.raises(DomainError) as error:
        generate(Generator(session, Broken()), plan.id)
    assert error.value.code == 'provider_output_invalid'
    assert session.get(Job, job.id).status == 'failed'
    assert session.get(Job, job.id).error['stage'] == 'validating_document'
    assert session.get(Artifact, artifact.id).status == 'failed'
    assert session.scalars(select(ArtifactVersion)).all() == []


def test_provider_unavailable_is_retryable_and_keeps_job_alive(session):
    artifact, plan, job = prepare(session)

    class Unavailable(FakeProvider):
        async def create_document(self, request):
            raise DomainError('provider_unavailable', 'The model provider is temporarily unavailable.', status_code=503)

    with pytest.raises(DomainError) as error:
        generate(Generator(session, Unavailable()), plan.id)
    assert error.value.code == 'provider_unavailable'
    retrying = session.get(Job, job.id)
    assert retrying.status == 'running'
    assert retrying.stage == 'generating_content'
    assert retrying.error is None
    assert session.get(Artifact, artifact.id).status == 'generating'
    assert session.get(GenerationPlan, plan.id).status == 'confirmed'


def test_sources_removed_after_confirmation_fail_cleanly(session):
    artifact, plan, job = prepare(session)
    session.query(SourceFile).filter(SourceFile.artifact_id == artifact.id).delete()
    session.commit()
    with pytest.raises(DomainError) as error:
        generate(Generator(session, FakeProvider()), plan.id)
    assert error.value.code == 'generation_sources_changed'
    failed = session.get(Job, job.id)
    assert failed.status == 'failed'
    assert failed.error['stage'] == 'loading_sources'
    assert session.get(Artifact, artifact.id).status == 'failed'
