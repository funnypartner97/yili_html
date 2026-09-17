"""Standalone HTML export: run the quality gate, then produce a deterministic ZIP.

Only `独立 HTML` is enabled in this slice. Error-severity diagnostics block the
export and expose their repair actions; `review` diagnostics require explicit
acknowledgement. The archive is stored in object storage and returned through a
15-minute signed download URL.
"""
from __future__ import annotations

import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import Field, UUID7

from src.api.schemas import APIModel
from src.core.errors import DomainError
from src.db.models import utc_now
from src.exports.assets import StorageAssetResolver
from src.exports.html import HtmlExporter
from src.files.storage import ObjectStorage, get_storage
from src.generation.editor import Editor
from src.generation.provider import GenerationProvider, get_provider
from src.db.session import SessionDep
from src.quality.pipeline import QualityPipeline

router = APIRouter(prefix="/v1/artifacts", tags=["exports"])
StorageDep = Annotated[ObjectStorage, Depends(get_storage)]
ProviderDep = Annotated[GenerationProvider, Depends(get_provider)]

DOWNLOAD_TTL_SECONDS = 900


class ExportResponse(APIModel):
    download_url: str
    expires_at: str
    content_hash: str
    document_version: int = Field(ge=0)
    passed_layers: list[str]
    diagnostics: list[dict]


def _diagnostics(report) -> list[dict]:
    return [item.model_dump(by_alias=True, mode="json") for item in report.diagnostics]


@router.post("/{artifactId}/exports/html", response_model=ExportResponse)
def export_html(artifactId: UUID7, session: SessionDep, storage: StorageDep,
                provider: ProviderDep, acknowledgeReview: bool = False) -> ExportResponse:
    editor = Editor(session, provider)
    document, version_number = editor.current_document(str(artifactId))

    report = QualityPipeline().run_static_layers(document, document_version=version_number)
    if report.blocks_export():
        raise DomainError("quality_gate_failed", "文档未通过质量校验，无法导出。", status_code=422,
                          details={"diagnostics": _diagnostics(report), "passedLayers": report.passed_layers})
    if report.review and not acknowledgeReview:
        raise DomainError("quality_review_required", "存在需要确认的质量问题。", status_code=409,
                          details={"diagnostics": _diagnostics(report)})

    archive = HtmlExporter(StorageAssetResolver(storage)).export(document, document_version=version_number)
    key = f"exports/{artifactId}/{version_number}/{archive.content_hash()}.zip"
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "export.zip"
        path.write_bytes(archive.to_bytes())
        storage.put_file(key, path, "application/zip")
    download_url = storage.presign_get(key, DOWNLOAD_TTL_SECONDS)
    expires_at = utc_now() + timedelta(seconds=DOWNLOAD_TTL_SECONDS)
    return ExportResponse(download_url=download_url, expires_at=expires_at.isoformat(),
                          content_hash=archive.content_hash(), document_version=version_number,
                          passed_layers=report.passed_layers, diagnostics=_diagnostics(report))
