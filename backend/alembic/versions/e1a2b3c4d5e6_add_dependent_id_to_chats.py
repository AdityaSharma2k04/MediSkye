"""add_dependent_id_to_chats

Revision ID: e1a2b3c4d5e6
Revises: 985d8b426bbd
Create Date: 2026-11-08 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = '985d8b426bbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        op.add_column(
            'chats',
            sa.Column('dependent_id', postgresql.UUID(as_uuid=True), nullable=True)
        )
        op.create_foreign_key(
            'fk_chats_dependent_id_dependent_profiles',
            'chats',
            'dependent_profiles',
            ['dependent_id'],
            ['id'],
            ondelete='CASCADE'
        )
        op.create_index('ix_chats_dependent_id', 'chats', ['dependent_id'])
        # Backfill from documents
        conn.execute(sa.text(
            "UPDATE chats SET dependent_id = d.dependent_id FROM documents d "
            "WHERE chats.document_id = d.id AND d.dependent_id IS NOT NULL"
        ))
    else:
        op.add_column('chats', sa.Column('dependent_id', sa.UUID(), nullable=True))
        op.create_index('ix_chats_dependent_id', 'chats', ['dependent_id'])
        try:
            conn.execute(sa.text(
                "UPDATE chats SET dependent_id = (SELECT dependent_id FROM documents WHERE documents.id = chats.document_id) "
                "WHERE document_id IS NOT NULL"
            ))
        except Exception:
            pass


def downgrade() -> None:
    op.drop_index('ix_chats_dependent_id', table_name='chats')
    op.drop_column('chats', 'dependent_id')
