from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import UUID7

from src.api.schemas import APIModel
from src.db.session import SessionDep
from src.files.service import FileService
from src.files.storage import ObjectStorage, get_storage

router = APIRouter(prefix='/v1/artifacts', tags=['files'])
StorageDep = Annotated[ObjectStorage, Depends(get_storage)]


class FileQueued(APIModel):
    source_id: UUID7
    parse_status: Literal['queued'] = 'queued'


class FileResponse(APIModel):
    source_id: UUID7
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    parse_status: Literal['queued', 'parsing', 'parsed', 'failed']
    error: dict | None
    created_at: datetime
    updated_at: datetime


@router.post('/{artifactId}/files', status_code=202, response_model=FileQueued)
def upload_file(artifactId: UUID7, session: SessionDep, storage: StorageDep,
                file: Annotated[UploadFile, File()]) -> FileQueued:
    row = FileService(session, storage).upload(str(artifactId), file)
    return FileQueued(source_id=row.id)


@router.get('/{artifactId}/files', response_model=list[FileResponse])
def list_files(artifactId: UUID7, session: SessionDep, storage: StorageDep) -> list[FileResponse]:
    return [FileResponse(source_id=row.id, filename=row.filename, content_type=row.content_type,
        size_bytes=row.size_bytes, sha256=row.sha256, parse_status=row.parse_status, error=row.error,
        created_at=row.created_at, updated_at=row.updated_at)
        for row in FileService(session, storage).list_files(str(artifactId))]
