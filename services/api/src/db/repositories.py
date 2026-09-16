from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.core.errors import DomainError
from src.core.ids import new_id
from src.db.models import Artifact, ArtifactVersion, GenerationPlan, SourceFile, VERSION_ORIGINS, utc_now
from src.db.validation import validate_persistence_text
from src.documents.contracts import DocumentGraphModel, GenerationPlanModel


class ArtifactRepository:
    """Write methods commit an atomic unit; failures roll back before propagating.

    Each save allocates a counter with UPDATE ... RETURNING, serializing writers
    on the artifact row in PostgreSQL. Historical snapshots are append-only here.
    """
    def __init__(self, session: Session):
        self.session = session

    def create_artifact(self, title: str) -> Artifact:
        validate_persistence_text(title)
        artifact = Artifact(id=new_id(), title=title, status="draft")
        try:
            self.session.add(artifact)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(artifact)
        return artifact

    def get_artifact(self, artifact_id: str) -> Artifact:
        artifact = self.session.get(Artifact, artifact_id)
        if artifact is None:
            raise self._not_found(artifact_id)
        return artifact

    def source_count(self, artifact_id: str) -> int:
        return self.session.scalar(select(func.count()).select_from(SourceFile).where(
            SourceFile.artifact_id == artifact_id)) or 0

    def save_plan(self, plan: GenerationPlanModel | dict[str, Any]) -> GenerationPlan:
        # Revalidate even model instances: callers can have mutated nested values.
        raw = plan.model_dump(by_alias=True, mode="json") if isinstance(plan, GenerationPlanModel) else plan
        validated = GenerationPlanModel.model_validate(raw)
        payload = validated.model_dump(by_alias=True, mode="json")
        validate_persistence_text(payload)
        try:
            revision = self.session.scalar(update(Artifact).where(
                Artifact.id == validated.artifact_id).values(
                plan_revision=Artifact.plan_revision + 1, status="plan_ready", updated_at=utc_now()
            ).returning(Artifact.plan_revision))
            if revision is None:
                raise self._not_found(validated.artifact_id)
            row = GenerationPlan(artifact_id=validated.artifact_id, revision=revision,
                                 status="ready", payload=payload)
            self.session.add(row)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(row)
        return row

    def save_document(self, graph: DocumentGraphModel | dict[str, Any], origin: str) -> ArtifactVersion:
        if origin not in VERSION_ORIGINS:
            raise ValueError(f"Invalid version origin: {origin}")
        raw = graph.model_dump(by_alias=True, mode="json") if isinstance(graph, DocumentGraphModel) else graph
        validated = DocumentGraphModel.model_validate(raw)
        document = validated.model_dump(by_alias=True, mode="json")
        validate_persistence_text(document)
        try:
            version = self.session.scalar(update(Artifact).where(
                Artifact.id == validated.artifact_id).values(
                latest_version=Artifact.latest_version + 1, status="editable", updated_at=utc_now()
            ).returning(Artifact.latest_version))
            if version is None:
                raise self._not_found(validated.artifact_id)
            row = ArtifactVersion(artifact_id=validated.artifact_id, version_number=version,
                                  origin=origin, document=document)
            self.session.add(row)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(row)
        return row

    def get_versions(self, artifact_id: str) -> list[ArtifactVersion]:
        self.get_artifact(artifact_id)
        return list(self.session.scalars(select(ArtifactVersion).where(
            ArtifactVersion.artifact_id == artifact_id).order_by(ArtifactVersion.version_number.desc())))

    @staticmethod
    def _not_found(artifact_id: str) -> DomainError:
        return DomainError("artifact_not_found", "Artifact was not found.", status_code=404,
                           details={"artifactId": artifact_id})
