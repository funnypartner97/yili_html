"""Persist expiring AI edit previews awaiting explicit apply."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0004_edit_previews'
down_revision = '0003_plan_confirmation'
branch_labels = None
depends_on = None


def json_type():
    return sa.JSON().with_variant(JSONB(), 'postgresql')


def upgrade() -> None:
    op.create_table(
        'edit_previews',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('artifact_id', sa.String(36),
                  sa.ForeignKey('artifacts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('base_version', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('instruction', sa.Text(), nullable=False),
        sa.Column('commands', json_type(), nullable=False),
        sa.Column('summary', json_type(), nullable=False),
        sa.Column('affected_block_ids', json_type(), nullable=False),
        sa.Column('result_document', json_type(), nullable=False),
        sa.Column('invocation_audit', json_type(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('base_version > 0', name='ck_edit_previews_base_version'),
        sa.CheckConstraint("status IN ('pending','applied')", name='ck_edit_previews_status'),
    )
    op.create_index('ix_edit_previews_artifact_id', 'edit_previews', ['artifact_id'])


def downgrade() -> None:
    op.drop_index('ix_edit_previews_artifact_id', table_name='edit_previews')
    op.drop_table('edit_previews')
