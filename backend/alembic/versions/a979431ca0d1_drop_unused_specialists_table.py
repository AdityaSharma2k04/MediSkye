"""drop unused specialists table

Revision ID: a979431ca0d1
Revises: 3ee652733cc5
Create Date: 2026-10-03 08:01:51.036048

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a979431ca0d1'
down_revision: Union[str, Sequence[str], None] = '3ee652733cc5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('specialists')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table('specialists',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('specialty', sa.String(), nullable=False),
    sa.Column('keywords', sa.JSON(), nullable=False),
    sa.Column('contact_info', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
