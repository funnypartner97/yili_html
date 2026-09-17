"""AI edit orchestration: preview (no mutation) and explicit apply (new version).

Preview calls the provider, validates and applies the returned commands to a copy
of the current document, and persists an expiring proposal. Nothing about the
artifact changes until the user explicitly applies a preview. Apply is a pure
persistence step guarded by the preview's base-version precondition, so it never
re-invokes the model and can never silently merge concurrent graphs.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import DomainError
from src.db.models import ArtifactVersion, EditPreview, SourceFile, utc_now
from src.db.repositories import ArtifactRepository
from src.db.validation import validate_persistence_text
from src.documents.commands import affected_block_ids, apply_commands
from src.documents.contracts import DocumentGraphModel
from src.files.types import ParsedSource
from src.generation.provider import EditProviderRequest, GenerationProvider, SourceInput, digest

PREVIEW_TTL = timedelta(minutes=30)
MAX_SELECTED_BLOCKS = 50


class Editor:
    def __init__(self, session: Session, provider: GenerationProvider):
        self.session = session
        self.provider = provider
        self.repository = ArtifactRepository(session)

    # --- loading helpers -------------------------------------------------
    def _known_source_ids(self, artifact_id: str) -> set[str]:
        return {row.id for row in self.session.scalars(
            select(SourceFile).where(SourceFile.artifact_id == artifact_id))}

    def _parsed_sources(self, artifact_id: str) -> list[SourceInput]:
        rows = self.session.scalars(select(SourceFile).where(
            SourceFile.artifact_id == artifact_id, SourceFile.parse_status == "parsed")
            .order_by(SourceFile.created_at, SourceFile.id))
        sources: list[SourceInput] = []
        for row in rows:
            parsed = ParsedSource.model_validate(row.parsed_content).model_dump(by_alias=True, mode="json")
            sources.append(SourceInput(row.id, row.sha256, digest(parsed), parsed))
        return sources

    def _current_document(self, artifact_id: str) -> tuple[dict, int]:
        artifact = self.repository.get_artifact(artifact_id)
        if artifact.status == "generating":
            raise DomainError("generation_in_progress", "A generation is running; retry once it finishes.",
                              status_code=409)
        if artifact.latest_version == 0:
            raise DomainError("document_not_ready", "The document has not been generated yet.", status_code=409)
        version = self.session.scalar(select(ArtifactVersion).where(
            ArtifactVersion.artifact_id == artifact_id,
            ArtifactVersion.version_number == artifact.latest_version))
        if version is None:
            raise DomainError("document_not_ready", "The document has not been generated yet.", status_code=409)
        return deepcopy(version.document), artifact.latest_version

    def _check_citations(self, document: dict, artifact_id: str) -> None:
        known = self._known_source_ids(artifact_id)
        for section in document["sections"]:
            for block in section["blocks"]:
                for reference in block["sourceRefs"]:
                    if reference["sourceId"] not in known:
                        raise DomainError("citation_source_missing",
                                          "A citation does not match an uploaded source.", status_code=502)

    def _finalize(self, document: dict, artifact_id: str) -> dict:
        validate_persistence_text(document)
        wire = DocumentGraphModel.model_validate(document).model_dump(by_alias=True, mode="json")
        if wire["artifactId"] != artifact_id:
            raise DomainError("artifact_id_mismatch", "The document belongs to another artifact.", status_code=409)
        self._check_citations(wire, artifact_id)
        return wire

    # --- preview / apply -------------------------------------------------
    async def preview(self, artifact_id: str, instruction: str, block_ids: list[str] | None) -> EditPreview:
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 20000:
            raise DomainError("validation_error", "An edit instruction is required.", status_code=422)
        selected = tuple(dict.fromkeys(block_ids or []))
        if len(selected) > MAX_SELECTED_BLOCKS or any(not isinstance(item, str) for item in selected):
            raise DomainError("validation_error", "Too many or invalid selected blocks.", status_code=422)

        document, base_version = self._current_document(artifact_id)
        sources = self._parsed_sources(artifact_id)
        result = await self.provider.create_edit_commands(EditProviderRequest(
            document=document, instruction=instruction.strip(), sources=sources,
            task="complex_edit", selected_block_ids=selected))
        commands = [command.model_dump(by_alias=True, mode="json") for command in result.value]
        if not commands:
            raise DomainError("provider_output_invalid", "The model proposed no edits.", status_code=502)
        try:
            updated, diffs = apply_commands(document, commands)
        except DomainError as error:
            raise DomainError("provider_output_invalid", "The proposed edits are not applicable.",
                              status_code=502, details={"code": error.code}) from None
        wire = self._finalize(updated, artifact_id)

        preview = EditPreview(
            artifact_id=artifact_id, base_version=base_version, status="pending",
            instruction=instruction.strip(), commands=commands, summary=diffs,
            affected_block_ids=affected_block_ids(diffs), result_document=wire,
            invocation_audit=result.audit, expires_at=utc_now() + PREVIEW_TTL)
        try:
            self.session.add(preview)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(preview)
        return preview

    def apply_preview(self, artifact_id: str, preview_id: str) -> ArtifactVersion:
        preview = self.session.get(EditPreview, preview_id)
        if preview is None or preview.artifact_id != artifact_id:
            raise DomainError("preview_not_found", "The edit preview was not found.", status_code=404)
        if preview.status == "applied":
            raise DomainError("preview_already_applied", "This preview has already been applied.", status_code=409)
        if preview.expires_at <= utc_now():
            raise DomainError("preview_expired", "The edit preview expired. Request a new one.", status_code=409)
        artifact = self.repository.get_artifact(artifact_id)
        if artifact.status == "generating":
            raise DomainError("generation_in_progress", "A generation is running; retry once it finishes.",
                              status_code=409)
        if artifact.latest_version != preview.base_version:
            raise DomainError("version_conflict", "The document has a newer version.", status_code=409,
                              details={"latestVersion": artifact.latest_version})
        document = self._finalize(deepcopy(preview.result_document), artifact_id)
        preview.status = "applied"
        # save_document commits the atomic unit, including the applied flag.
        return self.repository.save_document(document, "ai")

    # --- versions / restore ---------------------------------------------
    def versions(self, artifact_id: str) -> list[ArtifactVersion]:
        return self.repository.get_versions(artifact_id)

    def restore(self, artifact_id: str, version_number: int) -> ArtifactVersion:
        self.repository.get_artifact(artifact_id)
        target = self.session.scalar(select(ArtifactVersion).where(
            ArtifactVersion.artifact_id == artifact_id,
            ArtifactVersion.version_number == version_number))
        if target is None:
            raise DomainError("version_not_found", "That document version does not exist.", status_code=404)
        document = self._finalize(deepcopy(target.document), artifact_id)
        return self.repository.save_document(document, "restore")
