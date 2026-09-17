from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import UUID7

from src.api.schemas import APIModel
from src.core.errors import DomainError
from src.db.models import Job
from src.db.session import SessionDep

router = APIRouter(prefix='/v1/jobs', tags=['jobs'])


class JobResponse(APIModel):
    id: UUID7
    artifact_id: UUID7
    status: Literal['queued', 'running', 'succeeded', 'failed']
    progress: int
    stage: str | None
    error: dict | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, job: Job) -> "JobResponse":
        return cls(id=job.id, artifact_id=job.artifact_id, status=job.status, progress=job.progress,
                   stage=job.stage, error=job.error, created_at=job.created_at, updated_at=job.updated_at)


@router.get('/{jobId}', response_model=JobResponse)
def get_job(jobId: UUID7, session: SessionDep) -> JobResponse:
    job = session.get(Job, str(jobId))
    if job is None:
        raise DomainError('job_not_found', 'The job was not found.', status_code=404)
    return JobResponse.from_row(job)
