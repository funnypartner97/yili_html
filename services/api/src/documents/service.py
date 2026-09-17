"""Manual document saves with optimistic concurrency and full graph validation.

A save never overwrites an earlier version row: the If-Match precondition must
equal the latest version number, and every citation must still resolve to an
uploaded source before a new `manual` version is appended.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.errors import DomainError
from src.db.models import Artifact, SourceFile
from src.db.repositories import ArtifactRepository
from src.db.validation import validate_persistence_text
from src.documents.contracts import DocumentGraphModel


class DocumentService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = ArtifactRepository(session)

    def save_document(self, artifact_id: str, graph: DocumentGraphModel, if_match: str | None):
        artifact = self.repository.get_artifact(artifact_id)
        if if_match is None:
            raise DomainError('version_precondition_required',
                              'Send the current version number in the If-Match header.', status_code=428)
        try:
            expected_version = int(if_match)
        except ValueError:
            raise DomainError('version_precondition_required',
                              'The If-Match header must be a version number.', status_code=428) from None
        if artifact.status == 'generating':
            raise DomainError('generation_in_progress',
                              'A generation is running; retry once it finishes.', status_code=409)
        if artifact.latest_version == 0:
            raise DomainError('document_not_ready', 'The document has not been generated yet.', status_code=409)
        if expected_version != artifact.latest_version:
            raise DomainError('version_conflict', 'The document has a newer version.',
                              status_code=409, details={'latestVersion': artifact.latest_version})
        if graph.artifact_id != artifact_id:
            raise DomainError('artifact_id_mismatch', 'The document belongs to another artifact.', status_code=409)

        wire = graph.model_dump(by_alias=True, mode='json')
        validate_persistence_text(wire)
        known_sources = {row.id for row in self.session.scalars(select(SourceFile).where(
            SourceFile.artifact_id == artifact_id))}
        for section in wire['sections']:
            for block in section['blocks']:
                for reference in block['sourceRefs']:
                    if reference['sourceId'] not in known_sources:
                        raise DomainError('citation_source_missing',
                                          'A citation does not match an uploaded source.', status_code=502)
        return self.repository.save_document(wire, 'manual')
