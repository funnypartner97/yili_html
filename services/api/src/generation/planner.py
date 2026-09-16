"""Mandatory source-grounded, append-only production planning.

Dedicated-session transactions, as in ArtifactRepository. Slow inference runs
outside database locks; a fresh locked source manifest/revision check precedes
persistence. Confirmation linearizes on the artifact row, then snapshots and
queues in one commit. A confirmed plan's ID is its permanent idempotency key.
"""
from copy import deepcopy
from typing import Literal

from pydantic import Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.core.errors import DomainError
from src.db.models import Artifact, GenerationPlan, Job, SourceFile, utc_now
from src.db.repositories import ArtifactRepository
from src.db.validation import validate_persistence_text
from src.documents.contracts import GenerationPlanModel
from src.files.types import ParsedSource, StrictModel
from src.generation.provider import GenerationProvider, PlanProviderRequest, SourceInput, digest


class PlanParameters(StrictModel):
    output_modes: list[Literal['document', 'presentation']] = Field(default_factory=lambda: ['document'], min_length=1, max_length=2)
    audience: str | None = Field(default=None, min_length=1, max_length=300)
    length_preset: Literal['short', 'standard', 'long'] = 'standard'
    density: Literal['sparse', 'balanced', 'dense'] = 'balanced'
    output_spec: Literal['responsive', 'fixed'] = 'responsive'
    emphasis: list[str] = Field(default_factory=list, max_length=30)

    @field_validator('output_modes')
    @classmethod
    def unique_modes(cls, value):
        if len(set(value)) != len(value):
            raise ValueError('Duplicate output modes')
        return value

    @field_validator('audience')
    @classmethod
    def audience_text(cls, value):
        if value is not None and not value.strip():
            raise ValueError('Blank audience')
        return value.strip() if value else value

    @field_validator('emphasis')
    @classmethod
    def emphasis_text(cls, value):
        if any(not text.strip() or len(text) > 1000 for text in value):
            raise ValueError('Invalid emphasis')
        return [text.strip() for text in value]


def _invalid():
    return DomainError('validation_error', 'The plan request is invalid.')


def _modes(raw):
    modes = raw.get('outputModes', raw.get('output_modes', [])) if isinstance(raw, dict) else []
    if isinstance(modes, list) and any(mode in ('data', 'dashboard') for mode in modes):
        raise DomainError('output_mode_not_enabled', 'Data and dashboard output are not enabled.')


class Planner:
    def __init__(self, session: Session, provider: GenerationProvider):
        self.session = session
        self.provider = provider
        self.repository = ArtifactRepository(session)

    def _sources(self, artifact_id, *, lock=False):
        query = select(SourceFile).where(SourceFile.artifact_id == artifact_id).order_by(SourceFile.created_at, SourceFile.id)
        if lock:
            query = query.with_for_update()
        rows = list(self.session.scalars(query.execution_options(populate_existing=True)))
        sources = []
        for row in rows:
            if row.parse_status != 'parsed':
                continue
            try:
                parsed = ParsedSource.model_validate(row.parsed_content).model_dump(by_alias=True, mode='json')
                validate_persistence_text(parsed)
            except (ValueError, DomainError):
                raise DomainError('source_invalid', 'A parsed source is invalid. Parse the source again.', status_code=409) from None
            sources.append(SourceInput(row.id, row.sha256, digest(parsed), parsed))
        if not sources:
            raise DomainError('source_required', 'At least one successfully parsed source is required.')
        return sources, sum(row.parse_status == 'failed' for row in rows)

    def _lock_artifact(self, artifact_id):
        # UPDATE provides the same serialization boundary on SQLite and PostgreSQL.
        found = self.session.scalar(update(Artifact).where(Artifact.id == artifact_id)
            .values(updated_at=utc_now()).returning(Artifact.id))
        if found is None:
            raise self.repository._not_found(artifact_id)
        return self.session.scalar(select(Artifact).where(Artifact.id == artifact_id)
                                   .execution_options(populate_existing=True))

    def _get_plan(self, artifact_id, plan_id):
        plan = self.session.scalar(select(GenerationPlan).where(GenerationPlan.id == plan_id,
            GenerationPlan.artifact_id == artifact_id).execution_options(populate_existing=True))
        if plan is None:
            raise DomainError('plan_not_found', 'The generation plan was not found.', status_code=404)
        return plan

    @staticmethod
    def _validate_plan(raw, artifact_id, sources, failed, *, parameters=None, provider=False):
        try:
            if hasattr(raw, 'model_dump'):
                raw = raw.model_dump(by_alias=True, mode='json')
            _modes(raw)
            plan = GenerationPlanModel.model_validate(raw)
            wire = plan.model_dump(by_alias=True, mode='json')
            validate_persistence_text(wire)
            if plan.artifact_id != artifact_id or not plan.audience.strip():
                raise ValueError('Artifact or audience mismatch')
            if plan.source_summary.parsed != len(sources) or plan.source_summary.failed != failed:
                raise ValueError('Source counts mismatch')
            if any(not item.title.strip() or not item.id.strip() for item in plan.outline):
                raise ValueError('Empty outline')
            if any(not item.strip() for item in plan.emphasis):
                raise ValueError('Empty emphasis')
            if parameters and any(wire[key] != value for key, value in parameters.items()):
                raise ValueError('Parameters mismatch')
            return wire
        except (ValueError, DomainError):
            if provider:
                raise DomainError('provider_output_invalid', 'The model response failed validation.', status_code=502) from None
            raise _invalid() from None

    def _check_sources(self, artifact_id, manifest, failed):
        sources, current_failed = self._sources(artifact_id, lock=True)
        if [source.version() for source in sources] != manifest or current_failed != failed:
            raise DomainError('plan_sources_changed', 'Sources changed. Create a new generation plan.', status_code=409)
        return sources

    def _append(self, artifact, payload, instruction, manifest, audit):
        artifact.plan_revision += 1
        if artifact.status != 'generating':
            artifact.status = 'plan_ready'
        row = GenerationPlan(artifact_id=artifact.id, revision=artifact.plan_revision,
            status='ready', payload=deepcopy(payload), instruction=instruction,
            source_manifest=deepcopy(manifest), invocation_audit=deepcopy(audit))
        self.session.add(row)
        self.session.flush()
        # Detach before commit to avoid an unneeded response SELECT after commit.
        self.session.expunge(row)
        self.session.commit()
        return row

    async def create_plan(self, artifact_id: str, instruction: str, parameters: dict) -> GenerationPlan:
        _modes(parameters)
        try:
            if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 20000:
                raise ValueError('Invalid instruction')
            params = PlanParameters.model_validate(parameters).model_dump(by_alias=True, mode='json', exclude_none=True)
            validate_persistence_text([instruction, params])
        except (ValueError, DomainError):
            raise _invalid() from None
        artifact = self.repository.get_artifact(artifact_id)
        revision = artifact.plan_revision
        sources, failed = self._sources(artifact_id)
        manifest = [source.version() for source in sources]
        # Release the read transaction while waiting for inference.
        self.session.rollback()
        result = await self.provider.create_plan(PlanProviderRequest(artifact_id, instruction.strip(), params, sources, failed))
        wire = self._validate_plan(result.value, artifact_id, sources, failed, parameters=params, provider=True)
        try:
            artifact = self._lock_artifact(artifact_id)
            if artifact.plan_revision != revision:
                raise DomainError('plan_revision_stale', 'The plan changed. Reload the latest revision.', status_code=409)
            self._check_sources(artifact_id, manifest, failed)
            return self._append(artifact, wire, instruction.strip(), manifest, result.audit)
        except Exception:
            self.session.rollback()
            raise

    def update_plan(self, artifact_id: str, plan_id: str, raw: dict) -> GenerationPlan:
        _modes(raw)
        try:
            artifact = self._lock_artifact(artifact_id)
            prior = self._get_plan(artifact_id, plan_id)
            if prior.revision != artifact.plan_revision:
                raise DomainError('plan_revision_stale', 'The plan changed. Reload the latest revision.', status_code=409)
            sources = self._check_sources(artifact_id, prior.source_manifest, prior.payload['sourceSummary']['failed'])
            wire = self._validate_plan(raw, artifact_id, sources, prior.payload['sourceSummary']['failed'])
            return self._append(artifact, wire, prior.instruction, prior.source_manifest, prior.invocation_audit)
        except Exception:
            self.session.rollback()
            raise

    def confirm_plan(self, artifact_id: str, plan_id: str) -> Job:
        try:
            artifact = self._lock_artifact(artifact_id)
            plan = self._get_plan(artifact_id, plan_id)
            job = self.session.scalar(select(Job).where(Job.plan_id == plan_id, Job.artifact_id == artifact_id))
            if plan.status == 'confirmed' and job is not None:
                self.session.expunge(job)
                self.session.rollback()
                return job
            if plan.status != 'ready' or not plan.source_manifest or not plan.instruction:
                raise DomainError('plan_not_ready', 'The generation plan is not ready for confirmation.', status_code=409)
            if plan.revision != artifact.plan_revision:
                raise DomainError('plan_revision_stale', 'The plan changed. Reload the latest revision.', status_code=409)
            if artifact.status == 'generating':
                raise DomainError('generation_in_progress', 'A generation is already in progress.', status_code=409)
            sources = self._check_sources(artifact_id, plan.source_manifest, plan.payload['sourceSummary']['failed'])
            wire = self._validate_plan(plan.payload, artifact_id, sources, plan.payload['sourceSummary']['failed'])
            plan.status, plan.confirmed_at = 'confirmed', utc_now()
            artifact.status = 'generating'
            job = Job(artifact_id=artifact_id, plan_id=plan.id, kind='generate_document', status='queued',
                payload={'planId': plan.id, 'planRevision': plan.revision, 'plan': deepcopy(wire),
                    'instruction': plan.instruction, 'sourceManifest': deepcopy(plan.source_manifest),
                    'invocationAudit': deepcopy(plan.invocation_audit)})
            self.session.add(job)
            self.session.flush()
            self.session.expunge(job)
            self.session.commit()
            return job
        except Exception:
            self.session.rollback()
            raise
