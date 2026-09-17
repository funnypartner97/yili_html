from fastapi import APIRouter
from pydantic import UUID7

from src.core.errors import DomainError
from src.db.models import ArtifactVersion
from src.db.repositories import ArtifactRepository
from src.db.session import SessionDep
from src.documents.contracts import DocumentGraphModel
from sqlalchemy import select

router = APIRouter(prefix='/v1/artifacts', tags=['documents'])


@router.get('/{artifactId}/document', response_model=DocumentGraphModel)
def get_document(artifactId: UUID7, session: SessionDep) -> dict:
    repository = ArtifactRepository(session)
    artifact = repository.get_artifact(str(artifactId))
    version = session.scalar(select(ArtifactVersion).where(
        ArtifactVersion.artifact_id == artifact.id,
        ArtifactVersion.version_number == artifact.latest_version))
    if artifact.latest_version == 0 or version is None:
        raise DomainError('document_not_ready', 'The document has not been generated yet.', status_code=409)
    return version.document
