from fastapi import APIRouter
from pydantic import UUID7

from src.api.schemas import ArtifactCreate, ArtifactResponse
from src.db.repositories import ArtifactRepository
from src.db.session import SessionDep

router = APIRouter(prefix="/v1/artifacts", tags=["artifacts"])


@router.post("", response_model=ArtifactResponse, status_code=201)
def create_artifact(payload: ArtifactCreate, session: SessionDep) -> ArtifactResponse:
    artifact = ArtifactRepository(session).create_artifact(payload.title)
    return ArtifactResponse.from_model(artifact, source_count=0)


@router.get("/{artifactId}", response_model=ArtifactResponse)
def get_artifact(artifactId: UUID7, session: SessionDep) -> ArtifactResponse:
    repository = ArtifactRepository(session)
    artifact = repository.get_artifact(str(artifactId))
    return ArtifactResponse.from_model(artifact, repository.source_count(artifact.id))
