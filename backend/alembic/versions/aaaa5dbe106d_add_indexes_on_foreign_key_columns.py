"""add indexes on foreign key columns

Revision ID: aaaa5dbe106d
Revises: a979431ca0d1
Create Date: 2026-10-16 20:42:01.474515

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aaaa5dbe106d'
down_revision: Union[str, Sequence[str], None] = 'a979431ca0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add indexes on foreign key columns."""
    with op.batch_alter_table('dependent_profiles') as batch_op:
        batch_op.create_index('ix_dependent_profiles_user_id', ['user_id'], unique=False)

    with op.batch_alter_table('documents') as batch_op:
        batch_op.create_index('ix_documents_user_id', ['user_id'], unique=False)

    with op.batch_alter_table('chats') as batch_op:
        batch_op.create_index('ix_chats_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_chats_document_id', ['document_id'], unique=False)

    with op.batch_alter_table('audit_logs') as batch_op:
        batch_op.create_index('ix_audit_logs_user_id', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema: drop indexes on foreign key columns."""
    with op.batch_alter_table('audit_logs') as batch_op:
        batch_op.drop_index('ix_audit_logs_user_id')

    with op.batch_alter_table('chats') as batch_op:
        batch_op.drop_index('ix_chats_document_id')
        batch_op.drop_index('ix_chats_user_id')

    with op.batch_alter_table('documents') as batch_op:
        batch_op.drop_index('ix_documents_user_id')

    with op.batch_alter_table('dependent_profiles') as batch_op:
        batch_op.drop_index('ix_dependent_profiles_user_id')
