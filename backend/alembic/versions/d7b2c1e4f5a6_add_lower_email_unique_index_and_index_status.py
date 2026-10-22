"""add unique index on lower email and index status

Revision ID: d7b2c1e4f5a6
Revises: c6a171aa4414
Create Date: 2026-10-22 16:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd7b2c1e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'c6a171aa4414'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1. Add index_status column to documents if not already present
    doc_cols = [c['name'] for c in insp.get_columns('documents')]
    if 'index_status' not in doc_cols:
        op.add_column(
            'documents',
            sa.Column('index_status', sa.String(20), nullable=False, server_default='building')
        )

    # 2. Create unique index on LOWER(email)
    op.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_lower_email "
        "ON users (LOWER(email));"
    ))


def downgrade() -> None:
    bind = op.get_bind()

    op.execute(sa.text("DROP INDEX IF EXISTS ix_users_lower_email;"))

    insp = sa.inspect(bind)
    doc_cols = [c['name'] for c in insp.get_columns('documents')]
    if 'index_status' in doc_cols:
        op.drop_column('documents', 'index_status')

