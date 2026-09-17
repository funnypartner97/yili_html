from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import Field, UUID7
from sqlalchemy import select

from src.api.schemas import APIModel
from src.core.errors import DomainError
from src.db.models import GenerationPlan
from src.db.session import SessionDep
from src.documents.contracts import GenerationPlanModel
from src.generation.planner import Planner
from src.generation.provider import GenerationProvider, get_provider

router = APIRouter(prefix='/v1/artifacts', tags=['plans'])
ProviderDep = Annotated[GenerationProvider, Depends(get_provider)]


class PlanCreate(APIModel):
    instruction: str = Field(strict=True, min_length=1, max_length=20000)
    parameters: dict = Field(default_factory=dict)


class PlanUpdate(APIModel):
    plan: dict


class PlanResponse(APIModel):
    id: UUID7
    artifact_id: UUID7
    revision: int
    status: Literal['ready', 'confirmed']
    plan: GenerationPlanModel
    created_at: datetime
    confirmed_at: datetime | None

    @classmethod
    def from_row(cls, row):
        return cls(id=row.id, artifact_id=row.artifact_id, revision=row.revision, status=row.status,
            plan=row.payload, created_at=row.created_at, confirmed_at=row.confirmed_at)


class ConfirmationResponse(APIModel):
    job_id: UUID7
    plan_id: UUID7
    status: Literal['queued', 'running', 'succeeded', 'failed']


@router.post('/{artifactId}/plans', status_code=201, response_model=PlanResponse)
async def create_plan(artifactId: UUID7, request: PlanCreate, session: SessionDep, provider: ProviderDep):
    return PlanResponse.from_row(await Planner(session, provider).create_plan(str(artifactId), request.instruction, request.parameters))


@router.put('/{artifactId}/plans/{planId}', status_code=201, response_model=PlanResponse)
def update_plan(artifactId: UUID7, planId: UUID7, request: PlanUpdate, session: SessionDep, provider: ProviderDep):
    return PlanResponse.from_row(Planner(session, provider).update_plan(str(artifactId), str(planId), request.plan))


@router.get('/{artifactId}/plans/{planId}', response_model=PlanResponse)
def get_plan(artifactId: UUID7, planId: UUID7, session: SessionDep) -> PlanResponse:
    plan = session.scalar(select(GenerationPlan).where(GenerationPlan.id == str(planId),
        GenerationPlan.artifact_id == str(artifactId)))
    if plan is None:
        raise DomainError('plan_not_found', 'The generation plan was not found.', status_code=404)
    return PlanResponse.from_row(plan)


@router.post('/{artifactId}/plans/{planId}/confirm', status_code=202, response_model=ConfirmationResponse)
def confirm_plan(artifactId: UUID7, planId: UUID7, session: SessionDep, provider: ProviderDep):
    job = Planner(session, provider).confirm_plan(str(artifactId), str(planId))
    return ConfirmationResponse(job_id=job.id, plan_id=job.plan_id, status=job.status)
