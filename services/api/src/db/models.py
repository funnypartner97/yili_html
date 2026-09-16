from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, validates
from sqlalchemy.types import TypeDecorator

from src.core.ids import new_id

ArtifactStatus = Literal["draft", "planning", "plan_ready", "generating", "editable", "failed"]
ARTIFACT_STATUSES = ("draft", "planning", "plan_ready", "generating", "editable", "failed")
VERSION_ORIGINS = ("generation", "manual", "ai", "restore")
JSON_PAYLOAD = JSON().with_variant(JSONB(), "postgresql")


def utc_now() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Keep UTC-aware timestamps even when a test dialect drops timezone metadata."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Timestamp must include a timezone")
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


class IdentityTimestamp:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class Artifact(IdentityTimestamp, Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint("status IN ('draft','planning','plan_ready','generating','editable','failed')", name="ck_artifacts_status"),
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 300", name="ck_artifacts_title"),
        CheckConstraint("latest_version >= 0", name="ck_artifacts_latest_version"),
        CheckConstraint("plan_revision >= 0", name="ck_artifacts_plan_revision"),
    )
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    latest_version: Mapped[int] = mapped_column(Integer, default=0)
    plan_revision: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    @validates("status")
    def validate_status(self, key, value):
        if value not in ARTIFACT_STATUSES:
            raise ValueError(f"Invalid artifact status: {value}")
        return value


class SourceFile(IdentityTimestamp, Base):
    __tablename__ = "source_files"
    __table_args__ = (
        CheckConstraint("parse_status IN ('queued','parsing','parsed','failed')", name="ck_source_files_parse_status"),
        CheckConstraint("size_bytes >= 0 AND size_bytes <= 52428800", name="ck_source_files_size"),
        CheckConstraint("length(sha256) = 64", name="ck_source_files_sha256"),
    )
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(Text, unique=True)
    parse_status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    parse_attempt_id: Mapped[str | None] = mapped_column(String(36))
    parse_lease_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    parsed_content: Mapped[dict[str, Any] | None] = mapped_column(JSON_PAYLOAD)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON_PAYLOAD)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class GenerationPlan(IdentityTimestamp, Base):
    __tablename__ = "generation_plans"
    __table_args__ = (
        UniqueConstraint("artifact_id", "revision", name="uq_generation_plans_artifact_revision"),
        CheckConstraint("revision > 0", name="ck_generation_plans_revision"),
        CheckConstraint("status IN ('ready','confirmed')", name="ck_generation_plans_status"),
    )
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="ready")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    instruction: Mapped[str | None] = mapped_column(Text)
    source_manifest: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON_PAYLOAD)
    invocation_audit: Mapped[dict[str, Any] | None] = mapped_column(JSON_PAYLOAD)


class Job(IdentityTimestamp, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("status IN ('queued','running','succeeded','failed')", name="ck_jobs_status"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_jobs_progress"),
    )
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[str | None] = mapped_column(ForeignKey('generation_plans.id'), unique=True)
    kind: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str | None] = mapped_column(String(100))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_PAYLOAD)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON_PAYLOAD)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class ArtifactVersion(IdentityTimestamp, Base):
    __tablename__ = "artifact_versions"
    __table_args__ = (
        UniqueConstraint("artifact_id", "version_number", name="uq_artifact_versions_artifact_version"),
        CheckConstraint("version_number > 0", name="ck_artifact_versions_number"),
        CheckConstraint("origin IN ('generation','manual','ai','restore')", name="ck_artifact_versions_origin"),
    )
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    document: Mapped[dict[str, Any]] = mapped_column(JSON_PAYLOAD)
    origin: Mapped[str] = mapped_column(String(20))
