from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, UUID7
from pydantic.alias_generators import to_camel

from src.db.models import Artifact, ArtifactStatus


class APIModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class ArtifactCreate(APIModel):
    title: Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=300)]


class ArtifactResponse(APIModel):
    id: UUID7
    title: str
    status: ArtifactStatus
    source_count: int = Field(ge=0)
    latest_version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, artifact: Artifact, source_count: int) -> "ArtifactResponse":
        return cls(id=artifact.id, title=artifact.title, status=artifact.status,
                   source_count=source_count, latest_version=artifact.latest_version,
                   created_at=artifact.created_at, updated_at=artifact.updated_at)
