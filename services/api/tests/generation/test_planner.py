import asyncio
from uuid import uuid7

import pytest
from sqlalchemy import select

from src.core.errors import DomainError
from src.db.models import Artifact, GenerationPlan, SourceFile
from src.db.repositories import ArtifactRepository
from src.generation.fake_provider import FakeProvider
from src.generation.planner import Planner


def add_source(session, artifact_id, status='parsed', title='Quarterly results'):
    row = SourceFile(artifact_id=artifact_id, filename='report.csv', content_type='text/csv',
        size_bytes=10, sha256='a' * 64, storage_key=str(uuid7()),
        parse_status=status, parsed_content={'kind': 'csv', 'title': title, 'segments': [],
        'tables': [{'name': 'Revenue', 'locator': {'sheet': 'Revenue'}, 'rows': [['Q1', 20]]}],
        'images': [], 'metadata': {}} if status == 'parsed' else None)
    session.add(row)
    session.commit()
    return row


def create(planner, artifact_id, instruction='生成管理层汇报', parameters=None):
    return asyncio.run(planner.create_plan(artifact_id, instruction, parameters or {}))


def test_planner_rejects_artifact_without_parsed_sources(session):
    artifact = ArtifactRepository(session).create_artifact('Report')
    add_source(session, artifact.id, 'queued')
    with pytest.raises(DomainError) as error:
        create(Planner(session, FakeProvider()), artifact.id)
    assert error.value.code == 'source_required'
    assert session.scalars(select(GenerationPlan)).all() == []


def test_planner_passes_every_parsed_source_and_persists_audit(session):
    repo = ArtifactRepository(session)
    artifact = repo.create_artifact('Report')
    first = add_source(session, artifact.id)
    second = add_source(session, artifact.id, title='Costs')
    add_source(session, artifact.id, 'failed')
    add_source(session, artifact.id, 'queued')
    other = repo.create_artifact('Foreign')
    add_source(session, other.id, title='Secret')

    class RecordingProvider(FakeProvider):
        async def create_plan(self, request):
            self.request = request
            return await super().create_plan(request)

    provider = RecordingProvider()
    row = create(Planner(session, provider), artifact.id, parameters={
        'outputModes': ['document', 'presentation'], 'audience': 'Board',
        'lengthPreset': 'long', 'density': 'dense', 'outputSpec': 'fixed', 'emphasis': ['Revenue']})
    assert [s.source_id for s in provider.request.sources] == [first.id, second.id]
    assert provider.request.sources[0].content['tables'][0]['rows'] == [['Q1', 20]]
    assert row.payload['outputModes'] == ['document', 'presentation']
    assert row.payload['audience'] == 'Board'
    assert row.payload['sourceSummary'] == {'parsed': 2, 'failed': 1, 'conflicts': []}
    assert row.status == 'ready' and row.revision == 1
    assert row.invocation_audit['provider'] == 'fake'
    assert row.invocation_audit['model'] == 'deterministic-v1'
    assert row.invocation_audit['promptVersion'] == 'plan-v1'
    assert len(row.invocation_audit['sources']) == 2
    assert row.source_manifest[0]['parsedSha256']
    assert 'Quarterly results' not in str(row.invocation_audit)
    assert session.get(Artifact, artifact.id).status == 'plan_ready'


@pytest.mark.parametrize('instruction,parameters,code', [
    ('   ', {}, 'validation_error'), ('ok', {'outputModes': ['data']}, 'output_mode_not_enabled'),
    ('ok', {'outputModes': ['document', 'dashboard']}, 'output_mode_not_enabled'),
    ('ok', {'outputModes': []}, 'validation_error'),
    ('ok', {'outputModes': ['document', 'document']}, 'validation_error'),
    ('ok', {'materialRange': []}, 'validation_error'), ('ok', {'model': 'gpt-4'}, 'validation_error'),
    ('ok', {'audience': '   '}, 'validation_error'), ('ok\x00', {}, 'validation_error'),
])
def test_planner_rejects_invalid_inputs_before_provider(session, instruction, parameters, code):
    artifact = ArtifactRepository(session).create_artifact('Report')
    add_source(session, artifact.id)
    class NeverCalled(FakeProvider):
        async def create_plan(self, request):
            pytest.fail('Invalid input reached provider')
    with pytest.raises(DomainError) as error:
        create(Planner(session, NeverCalled()), artifact.id, instruction, parameters)
    assert error.value.code == code
    assert session.get(Artifact, artifact.id).plan_revision == 0


@pytest.mark.parametrize('mutation', ['artifact', 'modes', 'count', 'schema', 'nul'])
def test_nonconforming_provider_output_never_persists(session, mutation):
    artifact = ArtifactRepository(session).create_artifact('Report')
    add_source(session, artifact.id)
    class Broken(FakeProvider):
        async def create_plan(self, request):
            result = await super().create_plan(request)
            raw = result.value.model_dump(by_alias=True, mode='json')
            if mutation == 'artifact': raw['artifactId'] = str(uuid7())
            if mutation == 'modes': raw['outputModes'] = ['presentation']
            if mutation == 'count': raw['sourceSummary']['parsed'] = 9
            if mutation == 'schema': raw['executableHtml'] = '<script>secret</script>'
            if mutation == 'nul': raw['audience'] = 'secret\x00'
            return type(result)(raw, result.audit)
    with pytest.raises(DomainError) as error:
        create(Planner(session, Broken()), artifact.id)
    assert error.value.code == 'provider_output_invalid'
    assert 'secret' not in str(error.value)
    assert session.scalars(select(GenerationPlan)).all() == []
    assert session.get(Artifact, artifact.id).plan_revision == 0


def test_source_change_during_provider_call_rejects_stale_result(session):
    artifact = ArtifactRepository(session).create_artifact('Report')
    add_source(session, artifact.id)
    class Changing(FakeProvider):
        async def create_plan(self, request):
            result = await super().create_plan(request)
            add_source(session, artifact.id, title='Late source')
            return result
    with pytest.raises(DomainError) as error:
        create(Planner(session, Changing()), artifact.id)
    assert error.value.code == 'plan_sources_changed'
    assert session.scalars(select(GenerationPlan)).all() == []


def test_plan_insert_failure_rolls_back_revision_and_preserves_old_state(session):
    from sqlalchemy import event
    from sqlalchemy.exc import IntegrityError
    artifact = ArtifactRepository(session).create_artifact('Report')
    artifact_id = artifact.id
    add_source(session, artifact_id)
    def fail(mapper, connection, target):
        target.revision = None
    event.listen(GenerationPlan, 'before_insert', fail)
    try:
        with pytest.raises(IntegrityError):
            create(Planner(session, FakeProvider()), artifact_id)
    finally:
        event.remove(GenerationPlan, 'before_insert', fail)
    assert session.get(Artifact, artifact_id).plan_revision == 0
    assert session.get(Artifact, artifact_id).status == 'draft'
    assert create(Planner(session, FakeProvider()), artifact_id).revision == 1


def test_provider_failure_leaves_prior_ready_plan_untouched(session):
    artifact = ArtifactRepository(session).create_artifact('Report')
    artifact_id = artifact.id
    add_source(session, artifact_id)
    first = create(Planner(session, FakeProvider()), artifact_id)
    class FailedProvider(FakeProvider):
        async def create_plan(self, request):
            raise DomainError('provider_unavailable', 'Unavailable', status_code=503)
    with pytest.raises(DomainError):
        create(Planner(session, FailedProvider()), artifact_id)
    rows = session.scalars(select(GenerationPlan)).all()
    assert len(rows) == 1 and rows[0].id == first.id
    assert session.get(Artifact, artifact_id).status == 'plan_ready'
