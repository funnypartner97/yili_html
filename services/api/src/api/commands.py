from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import Field, UUID7

from src.api.documents import DocumentSaveResponse
from src.api.schemas import APIModel
from src.db.session import SessionDep
from src.generation.editor import Editor
from src.generation.provider import GenerationProvider, get_provider

router = APIRouter(prefix="/v1/artifacts", tags=["edits"])
ProviderDep = Annotated[GenerationProvider, Depends(get_provider)]


class EditPreviewCreate(APIModel):
    instruction: str = Field(strict=True, min_length=1, max_length=20000)
    block_ids: list[str] = Field(default_factory=list, max_length=50)


class EditPreviewResponse(APIModel):
    preview_id: UUID7
    base_version: int = Field(ge=1)
    commands: list[dict]
    summary: list[dict]
    affected_block_ids: list[str]
    expires_at: datetime

    @classmethod
    def from_row(cls, row) -> "EditPreviewResponse":
        return cls(preview_id=row.id, base_version=row.base_version, commands=row.commands,
                   summary=row.summary, affected_block_ids=row.affected_block_ids, expires_at=row.expires_at)


class VersionResponse(APIModel):
    version_number: int = Field(ge=1)
    origin: Literal["generation", "manual", "ai", "restore"]
    created_at: datetime

    @classmethod
    def from_row(cls, row) -> "VersionResponse":
        return cls(version_number=row.version_number, origin=row.origin, created_at=row.created_at)


class VersionListResponse(APIModel):
    versions: list[VersionResponse]


@router.post("/{artifactId}/edits/preview", status_code=201, response_model=EditPreviewResponse)
async def preview_edit(artifactId: UUID7, request: EditPreviewCreate, session: SessionDep, provider: ProviderDep):
    row = await Editor(session, provider).preview(str(artifactId), request.instruction, request.block_ids)
    return EditPreviewResponse.from_row(row)


@router.post("/{artifactId}/edits/{previewId}/apply", response_model=DocumentSaveResponse)
def apply_edit(artifactId: UUID7, previewId: UUID7, session: SessionDep, provider: ProviderDep):
    version = Editor(session, provider).apply_preview(str(artifactId), str(previewId))
    return DocumentSaveResponse(version_number=version.version_number, saved_at=version.created_at)


@router.get("/{artifactId}/versions", response_model=VersionListResponse)
def list_versions(artifactId: UUID7, session: SessionDep, provider: ProviderDep) -> VersionListResponse:
    rows = Editor(session, provider).versions(str(artifactId))
    return VersionListResponse(versions=[VersionResponse.from_row(row) for row in rows])


@router.post("/{artifactId}/versions/{version}/restore", response_model=DocumentSaveResponse)
def restore_version(artifactId: UUID7, version: int, session: SessionDep, provider: ProviderDep):
    row = Editor(session, provider).restore(str(artifactId), version)
    return DocumentSaveResponse(version_number=row.version_number, saved_at=row.created_at)
