"""Durable generation jobs executed by the ARQ worker.

Transient provider outages retry with exponential backoff up to the configured
attempt budget; exhausted retries and validation failures mark both the job and
its artifact failed while retaining the confirmed plan and parsed sources.
"""
from arq import Retry
from sqlalchemy.orm import Session

from src.core.errors import DomainError
from src.db.models import Artifact, Job
from src.db.session import create_db_engine
from src.generation.generator import RETRYABLE_CODES, Generator
from src.generation.provider import GenerationProvider, get_provider
from src.worker.settings import WorkerSettings

_state: dict = {'engine': None, 'provider_factory': get_provider}


def configure(engine=None, provider_factory: type[GenerationProvider] | None = None) -> None:
    """Test seam: swap the engine or provider without touching process config."""
    if engine is not None:
        _state['engine'] = engine
    if provider_factory is not None:
        _state['provider_factory'] = provider_factory


def _new_session() -> Session:
    if _state['engine'] is None:
        _state['engine'] = create_db_engine(WorkerSettings().database_url)
    return Session(_state['engine'])


def _mark_failed(session: Session, job_id: str, error: DomainError) -> None:
    job = session.get(Job, job_id)
    if job is None or job.status == 'succeeded':
        return
    job.status = 'failed'
    job.error = {'code': error.code, 'message': error.message, 'stage': job.stage}
    artifact = session.get(Artifact, job.artifact_id)
    if artifact is not None and artifact.status == 'generating':
        artifact.status = 'failed'
    session.commit()


async def generate_document_job(ctx: dict, job_id: str) -> None:
    settings = WorkerSettings()
    with _new_session() as session:
        job = session.get(Job, job_id)
        if job is None or not job.plan_id:
            raise DomainError('job_not_found', 'The job was not found.', status_code=404)
        try:
            await Generator(session, _state['provider_factory']()).generate(job.plan_id)
        except DomainError as error:
            tries = int(ctx.get('job_try', 1))
            if error.code in RETRYABLE_CODES and tries < settings.max_tries:
                raise Retry(defer=settings.retry_base_delay * 2 ** (tries - 1)) from error
            _mark_failed(session, job_id, error)
