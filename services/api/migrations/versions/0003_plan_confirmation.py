"""Persist source/audit snapshots and enforce one generation job per plan."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0003_plan_confirmation'
down_revision = '0002_source_parse_lease'
branch_labels = None
depends_on = None


def upgrade():
    payload = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')
    op.add_column('generation_plans', sa.Column('instruction', sa.Text(), nullable=True))
    op.add_column('generation_plans', sa.Column('source_manifest', payload, nullable=True))
    op.add_column('generation_plans', sa.Column('invocation_audit', payload, nullable=True))
    with op.batch_alter_table('jobs') as batch:
        batch.add_column(sa.Column('plan_id', sa.String(36), nullable=True))
        batch.create_foreign_key('fk_jobs_plan_id', 'generation_plans', ['plan_id'], ['id'])
        batch.create_unique_constraint('uq_jobs_plan_id', ['plan_id'])


def downgrade():
    with op.batch_alter_table('jobs') as batch:
        batch.drop_constraint('uq_jobs_plan_id', type_='unique')
        batch.drop_constraint('fk_jobs_plan_id', type_='foreignkey')
        batch.drop_column('plan_id')
    op.drop_column('generation_plans', 'invocation_audit')
    op.drop_column('generation_plans', 'source_manifest')
    op.drop_column('generation_plans', 'instruction')
