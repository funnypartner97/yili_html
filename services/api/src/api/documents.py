from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import Field, UUID7
from sqlalchemy import select

from src.api.schemas import APIModel
from src.core.errors import DomainError
from src.db.models import ArtifactVersion
from src.db.repositories import ArtifactRepository
from src.db.session import SessionDep
from src.documents.contracts import DocumentGraphModel
from src.documents.service import DocumentService

router = APIRouter(prefix='/v1/artifacts', tags=['documents'])


class DocumentSaveResponse(APIModel):
    version_number: int = Field(ge=1)
    saved_at: datetime


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


@router.put('/{artifactId}/document', response_model=DocumentSaveResponse)
def save_document(artifactId: UUID7, request: Request, document: DocumentGraphModel,
                  session: SessionDep) -> DocumentSaveResponse:
    version = DocumentService(session).save_document(str(artifactId), document, request.headers.get('If-Match'))
    return DocumentSaveResponse(version_number=version.version_number, saved_at=version.created_at)
