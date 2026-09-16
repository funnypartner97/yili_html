"""Persist artifacts, uploaded sources, plans, jobs, and document versions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def identity_columns():
    return [sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)]


def artifact_column():
    return sa.Column("artifact_id", sa.String(36),
                     sa.ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False)


def json_type():
    return sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table("artifacts", *identity_columns(),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("latest_version", sa.Integer(), nullable=False),
        sa.Column("plan_revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('draft','planning','plan_ready','generating','editable','failed')", name="ck_artifacts_status"),
        sa.CheckConstraint("length(trim(title)) BETWEEN 1 AND 300", name="ck_artifacts_title"),
        sa.CheckConstraint("latest_version >= 0", name="ck_artifacts_latest_version"),
        sa.CheckConstraint("plan_revision >= 0", name="ck_artifacts_plan_revision"),
    )
    op.create_index("ix_artifacts_status", "artifacts", ["status"])
    op.create_table("source_files", *identity_columns(), artifact_column(),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("parse_status", sa.String(20), nullable=False),
        sa.Column("parsed_content", json_type(), nullable=True),
        sa.Column("error", json_type(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("storage_key"),
        sa.CheckConstraint("parse_status IN ('queued','parsing','parsed','failed')", name="ck_source_files_parse_status"),
        sa.CheckConstraint("size_bytes >= 0 AND size_bytes <= 52428800", name="ck_source_files_size"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_source_files_sha256"),
    )
    op.create_index("ix_source_files_artifact_id", "source_files", ["artifact_id"])
    op.create_index("ix_source_files_parse_status", "source_files", ["parse_status"])
    op.create_table("generation_plans", *identity_columns(), artifact_column(),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", json_type(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("artifact_id", "revision", name="uq_generation_plans_artifact_revision"),
        sa.CheckConstraint("revision > 0", name="ck_generation_plans_revision"),
        sa.CheckConstraint("status IN ('ready','confirmed')", name="ck_generation_plans_status"),
    )
    op.create_index("ix_generation_plans_artifact_id", "generation_plans", ["artifact_id"])
    op.create_table("jobs", *identity_columns(), artifact_column(),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(100), nullable=True),
        sa.Column("payload", json_type(), nullable=True),
        sa.Column("error", json_type(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('queued','running','succeeded','failed')", name="ck_jobs_status"),
        sa.CheckConstraint("progress BETWEEN 0 AND 100", name="ck_jobs_progress"),
    )
    op.create_index("ix_jobs_artifact_id", "jobs", ["artifact_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_table("artifact_versions", *identity_columns(), artifact_column(),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("document", json_type(), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.UniqueConstraint("artifact_id", "version_number", name="uq_artifact_versions_artifact_version"),
        sa.CheckConstraint("version_number > 0", name="ck_artifact_versions_number"),
        sa.CheckConstraint("origin IN ('generation','manual','ai','restore')", name="ck_artifact_versions_origin"),
    )
    op.create_index("ix_artifact_versions_artifact_id", "artifact_versions", ["artifact_id"])


def downgrade() -> None:
    for table in ("artifact_versions", "jobs", "generation_plans", "source_files", "artifacts"):
        op.drop_table(table)
