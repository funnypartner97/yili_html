"""Give source parsing attempts exclusive, expiring ownership."""
from alembic import op
import sqlalchemy as sa

revision = '0002_source_parse_lease'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('source_files', sa.Column('parse_attempt_id', sa.String(36), nullable=True))
    op.add_column('source_files', sa.Column('parse_lease_expires_at', sa.DateTime(timezone=True), nullable=True))
    # Old parsing rows had no ownership/recovery protocol. Migrate with parsers
    # stopped; they can then be claimed by the new implementation.
    op.execute("UPDATE source_files SET parse_status = 'queued', parsed_content = NULL, error = NULL "
               "WHERE parse_status = 'parsing'")


def downgrade() -> None:
    op.drop_column('source_files', 'parse_lease_expires_at')
    op.drop_column('source_files', 'parse_attempt_id')
