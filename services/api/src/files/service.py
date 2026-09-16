import hashlib
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import UploadFile
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.core.errors import DomainError
from src.core.ids import new_id
from src.db.models import Artifact, SourceFile, utc_now
from src.db.repositories import ArtifactRepository
from src.db.validation import validate_persistence_text
from src.files.parsers.base import CONTENT_TYPES, MAX_FILE_BYTES, finalize, inspect_file, safe_filename
from src.files.storage import ObjectStorage
from src.files.types import ParsedSource

logger = logging.getLogger(__name__)
PARSE_ERRORS = {
    'source_parse_failed': 'The file could not be parsed. Upload a valid, unencrypted file.',
    'source_limit_exceeded': 'The source exceeds supported parsing limits.',
    'source_integrity_failed': 'The stored file could not be verified. Upload the file again.',
    'source_storage_unavailable': 'The stored file is temporarily unavailable. Try again later.',
}


class FileService:
    """Dedicated-session units of work, with compensating object deletion.

    An artifact UPDATE locks admission until the source row is committed. This
    serializes PostgreSQL and SQLite uploads, including independent API processes.
    Parse hooks are synchronous integration points; worker scheduling is separate.
    """
    def __init__(self, session: Session, storage: ObjectStorage, *, temp_root: Path | None = None):
        self.session = session
        self.storage = storage
        self.temp_root = temp_root
        self.repository = ArtifactRepository(session)

    def list_files(self, artifact_id: str) -> list[SourceFile]:
        self.repository.get_artifact(artifact_id)
        return list(self.session.scalars(select(SourceFile).where(SourceFile.artifact_id == artifact_id)
                                        .order_by(SourceFile.created_at, SourceFile.id)))

    def upload(self, artifact_id: str, upload: UploadFile) -> SourceFile:
        self.repository.get_artifact(artifact_id)
        filename = safe_filename(upload.filename)
        source_id = new_id()
        # IDs come from persisted artifact identity/server UUIDv7; only the safe basename is user-derived.
        key = f'artifacts/{artifact_id}/sources/{source_id}/{filename}'
        object_attempted = False
        phase = 'persistence'
        try:
            with TemporaryDirectory(prefix='source-', dir=self.temp_root) as directory:
                # Temp path is entirely generated, never built from the supplied filename.
                path = Path(directory) / ('payload' + Path(filename).suffix.lower())
                digest = hashlib.sha256()
                size = 0
                with path.open('xb') as output:
                    while chunk := upload.file.read(1024 * 1024):
                        size += len(chunk)
                        if size > MAX_FILE_BYTES:
                            raise DomainError('file_too_large', 'Files must be no larger than 50 MiB.', status_code=413)
                        digest.update(chunk)
                        output.write(chunk)
                kind = inspect_file(path, filename)
                locked = self.session.scalar(update(Artifact).where(Artifact.id == artifact_id)
                    .values(updated_at=utc_now()).returning(Artifact.id))
                if locked is None:
                    raise self.repository._not_found(artifact_id)
                if self.repository.source_count(artifact_id) >= 10:
                    raise DomainError('source_count_limit', 'An artifact can contain at most 10 source files.')
                row = SourceFile(id=source_id, artifact_id=artifact_id, filename=filename,
                    content_type=CONTENT_TYPES[kind], size_bytes=size, sha256=digest.hexdigest(),
                    storage_key=key, parse_status='queued')
                self.session.add(row)
                self.session.flush()
                phase = 'storage'
                object_attempted = True
                self.storage.put_file(key, path, row.content_type)
                phase = 'persistence'
            # Finish temp cleanup before committing so cleanup failure can still
            # roll back the row and compensate the object as one failed upload.
            # Detach the response to avoid a post-commit database round-trip.
            self.session.expunge(row)
            self.session.commit()
            return row
        except Exception as error:
            self.session.rollback()
            if object_attempted:
                try:
                    self.storage.delete(key)
                except Exception:
                    # Distributed compensation can fail; retain key in operator logs for reconciliation.
                    logger.error('Source object cleanup failed: %s', key)
            if isinstance(error, DomainError):
                raise
            code = 'source_storage_unavailable' if phase == 'storage' else 'source_persistence_failed'
            raise DomainError(code, 'The file could not be saved. Try again later.', status_code=503) from error

    def get_source(self, artifact_id: str, source_id: str) -> SourceFile:
        row = self.session.scalar(select(SourceFile).where(SourceFile.id == source_id,
                                                         SourceFile.artifact_id == artifact_id))
        if row is None:
            raise DomainError('source_not_found', 'Source file was not found.', status_code=404)
        return row

    def _transition(self, artifact_id: str, source_id: str, allowed: tuple[str, ...], **values) -> None:
        self.get_source(artifact_id, source_id)
        try:
            changed = self.session.scalar(update(SourceFile).where(SourceFile.id == source_id,
                SourceFile.artifact_id == artifact_id, SourceFile.parse_status.in_(allowed))
                .values(**values, updated_at=utc_now()).returning(SourceFile.id))
            if changed is None:
                raise DomainError('source_state_conflict', 'The file parse state has already changed.', status_code=409)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def mark_parsed(self, artifact_id: str, source_id: str, parsed: ParsedSource) -> None:
        validated = finalize(ParsedSource.model_validate(parsed.model_dump(mode='python')))
        payload = validated.model_dump(by_alias=True, mode='json')
        validate_persistence_text(payload)
        self._transition(artifact_id, source_id, ('queued', 'parsing'), parse_status='parsed', parsed_content=payload, error=None)

    def mark_failed(self, artifact_id: str, source_id: str, code: str = 'source_parse_failed') -> None:
        if code not in PARSE_ERRORS:
            raise ValueError('Unknown public parse error code')
        self._transition(artifact_id, source_id, ('queued', 'parsing'), parse_status='failed', parsed_content=None,
                         error={'code': code, 'message': PARSE_ERRORS[code], 'details': {}})

    def parse_source(self, artifact_id: str, source_id: str) -> None:
        """Download, verify and parse one source; no job queue or worker orchestration."""
        from src.files.parsers.docx import DocxParser
        from src.files.parsers.image import ImageParser
        from src.files.parsers.pdf import PdfParser
        from src.files.parsers.pptx import PptxParser
        from src.files.parsers.spreadsheet import SpreadsheetParser

        self._transition(artifact_id, source_id, ('queued', 'failed'), parse_status='parsing', parsed_content=None, error=None)
        row = self.get_source(artifact_id, source_id)
        code = 'source_storage_unavailable'
        try:
            with TemporaryDirectory(prefix='source-', dir=self.temp_root) as directory:
                path = Path(directory) / ('payload' + Path(row.filename).suffix.lower())
                self.storage.download_file(row.storage_key, path, max_bytes=MAX_FILE_BYTES)
                code = 'source_integrity_failed'
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                if path.stat().st_size != row.size_bytes or digest != row.sha256:
                    raise ValueError('Stored content mismatch')
                code = 'source_parse_failed'
                kind = inspect_file(path, row.filename)
                parsers = {'pdf': PdfParser, 'docx': DocxParser, 'pptx': PptxParser,
                           'xlsx': SpreadsheetParser, 'csv': SpreadsheetParser, 'png': ImageParser, 'jpeg': ImageParser}
                parsed = parsers[kind]().parse(path)
                parsed.title = Path(row.filename).stem
                if kind == 'csv':
                    parsed.tables[0].name = parsed.title
                    parsed.tables[0].locator.sheet = parsed.title
        except Exception as error:
            if isinstance(error, DomainError) and error.code == 'source_limit_exceeded':
                code = error.code
            self.mark_failed(artifact_id, source_id, code)
            return
        # Persistence failures are not parser failures and must remain retryable/visible to callers.
        self.mark_parsed(artifact_id, source_id, parsed)
