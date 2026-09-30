"""Add document.title and make chat.document_id nullable

Revision ID: c9e1f2a3b4d5
Revises: 0404983f4599
Create Date: 2026-10-01 00:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e1f2a3b4d5'
down_revision: Union[str, Sequence[str], None] = '8e18e2020590'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add title column to documents; make chat.document_id nullable."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c['name'] for c in insp.get_columns('documents')]
    if 'title' not in cols:
        op.add_column(
            'documents',
            sa.Column('title', sa.String(60), nullable=True)
        )
    with op.batch_alter_table('chats') as batch_op:
        batch_op.alter_column(
            'document_id',
            existing_type=sa.UUID(),
            nullable=True
        )


def downgrade() -> None:
    """Remove title column from documents; restore chat.document_id as non-nullable."""
    with op.batch_alter_table('chats') as batch_op:
        batch_op.alter_column(
            'document_id',
            existing_type=sa.UUID(),
            nullable=False
        )
    op.drop_column('documents', 'title')
