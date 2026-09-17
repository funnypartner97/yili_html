"""Staged document generation for confirmed plans inside durable jobs.

The job row is the single progress ledger: every stage transition commits
immediately so polling clients observe progress. Transient provider outages
propagate for worker-level retry; every other failure marks both the job and
the artifact failed while retaining the confirmed plan and parsed sources.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import DomainError
from src.db.models import Artifact, ArtifactVersion, GenerationPlan, Job, SourceFile
from src.db.repositories import ArtifactRepository
from src.db.validation import validate_persistence_text
from src.documents.contracts import DocumentGraphModel
from src.files.types import ParsedSource
from src.generation.provider import DocumentProviderRequest, GenerationProvider, SourceInput, digest

RETRYABLE_CODES = frozenset({'provider_unavailable'})


class Generator:
    def __init__(self, session: Session, provider: GenerationProvider):
        self.session = session
        self.provider = provider
        self.repository = ArtifactRepository(session)

    def _report(self, job: Job, progress: int, stage: str, *, status: str | None = None) -> None:
        job.progress = progress
        job.stage = stage
        if status is not None:
            job.status = status
        self.session.commit()

    def _load_sources(self, job: Job) -> list[SourceInput]:
        self._report(job, 10, 'loading_sources', status='running')
        rows = {row.id: row for row in self.session.scalars(select(SourceFile).where(
            SourceFile.artifact_id == job.artifact_id))}
        sources = []
        for entry in job.payload['sourceManifest']:
            row = rows.get(entry['sourceId'])
            if row is None or row.parse_status != 'parsed' or row.sha256 != entry['sha256']:
                raise DomainError('generation_sources_changed', 'The parsed sources changed.', status_code=409)
            parsed = ParsedSource.model_validate(row.parsed_content).model_dump(by_alias=True, mode='json')
            if digest(parsed) != entry['parsedSha256']:
                raise DomainError('generation_sources_changed', 'The parsed sources changed.', status_code=409)
            sources.append(SourceInput(row.id, row.sha256, digest(parsed), parsed))
        if not sources:
            raise DomainError('generation_sources_changed', 'The parsed sources changed.', status_code=409)
        return sources

    def _validate(self, value, artifact_id: str, sources: list[SourceInput]) -> dict:
        try:
            raw = value.model_dump(by_alias=True, mode='json') if hasattr(value, 'model_dump') else value
            graph = DocumentGraphModel.model_validate(raw)
            wire = graph.model_dump(by_alias=True, mode='json')
            validate_persistence_text(wire)
            if graph.artifact_id != artifact_id:
                raise ValueError('Artifact mismatch')
            known = {source.source_id for source in sources}
            for section in wire['sections']:
                for block in section['blocks']:
                    for reference in block['sourceRefs']:
                        if reference['sourceId'] not in known:
                            raise DomainError('citation_source_missing',
                                              'A citation does not match an uploaded source.', status_code=502)
            return wire
        except DomainError:
            raise
        except Exception:
            raise DomainError('provider_output_invalid', 'The model response failed validation.', status_code=502) from None

    def _existing_version(self, artifact_id: str) -> ArtifactVersion:
        artifact = self.repository.get_artifact(artifact_id)
        version = self.session.scalar(select(ArtifactVersion).where(
            ArtifactVersion.artifact_id == artifact_id,
            ArtifactVersion.version_number == artifact.latest_version))
        if version is None:
            raise DomainError('document_not_ready', 'The document has not been generated yet.', status_code=409)
        return version

    def _fail(self, job_id: str, artifact_id: str, error: DomainError) -> None:
        job = self.session.get(Job, job_id)
        if job is not None and job.status != 'succeeded':
            job.status = 'failed'
            job.error = {'code': error.code, 'message': error.message, 'stage': job.stage}
        artifact = self.session.get(Artifact, artifact_id)
        if artifact is not None and artifact.status == 'generating':
            artifact.status = 'failed'
        self.session.commit()

    async def generate(self, plan_id: str) -> ArtifactVersion:
        plan = self.session.get(GenerationPlan, plan_id)
        if plan is None:
            raise DomainError('plan_not_found', 'The generation plan was not found.', status_code=404)
        job = self.session.scalar(select(Job).where(Job.plan_id == plan_id))
        if plan.status != 'confirmed' or job is None:
            raise DomainError('plan_confirmation_required', 'Confirm the plan before generating.', status_code=409)
        if job.status == 'succeeded':
            return self._existing_version(plan.artifact_id)
        if job.status == 'failed':
            raise DomainError('generation_failed', 'The generation failed. Confirm a new plan.', status_code=409)
        try:
            sources = self._load_sources(job)
            self._report(job, 30, 'generating_structure')
            request = DocumentProviderRequest(plan=job.payload['plan'], sources=sources)
            self._report(job, 60, 'generating_content')
            result = await self.provider.create_document(request)
            self._report(job, 85, 'validating_document')
            document = self._validate(result.value, plan.artifact_id, sources)
            self._report(job, 95, 'saving_version')
            version = self.repository.save_document(document, 'generation')
            self._report(job, 100, 'completed', status='succeeded')
            return version
        except DomainError as error:
            self.session.rollback()
            if error.code in RETRYABLE_CODES:
                raise
            self._fail(job.id, plan.artifact_id, error)
            raise
