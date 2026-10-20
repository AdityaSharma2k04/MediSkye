"""add cached metrics and summary to documents

Revision ID: c6a171aa4414
Revises: b1e2f3a4c5d6
Create Date: 2026-10-21 04:30:45.428685

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6a171aa4414'
down_revision: Union[str, Sequence[str], None] = 'b1e2f3a4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add cached_metrics and cached_summary columns to documents."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c['name'] for c in insp.get_columns('documents')]
    if 'cached_metrics' not in cols:
        op.add_column('documents', sa.Column('cached_metrics', sa.JSON(), nullable=True))
    if 'cached_summary' not in cols:
        op.add_column('documents', sa.Column('cached_summary', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove cached_metrics and cached_summary columns from documents."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c['name'] for c in insp.get_columns('documents')]
    if 'cached_summary' in cols:
        op.drop_column('documents', 'cached_summary')
    if 'cached_metrics' in cols:
        op.drop_column('documents', 'cached_metrics')

