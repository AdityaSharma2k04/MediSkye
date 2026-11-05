"""harden_dependent_cascade_and_token_revocation

Revision ID: 204cb7f58e36
Revises: 42c20d3c704c
Create Date: 2026-11-06 00:01:41.612437

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '204cb7f58e36'
down_revision: Union[str, Sequence[str], None] = '42c20d3c704c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1. Add token_invalid_before to users table
    user_cols = [c['name'] for c in insp.get_columns('users')]
    if 'token_invalid_before' not in user_cols:
        op.add_column('users', sa.Column('token_invalid_before', sa.DateTime(timezone=True), nullable=True))

    # 2. Update foreign key on documents.dependent_id to ON DELETE CASCADE
    if bind.dialect.name == "postgresql":
        doc_fks = insp.get_foreign_keys('documents')
        for fk in doc_fks:
            if 'dependent_id' in fk.get('constrained_columns', []):
                fk_name = fk.get('name')
                if fk_name:
                    op.drop_constraint(fk_name, 'documents', type_='foreignkey')

        op.create_foreign_key(
            'fk_documents_dependent_id_dependent_profiles',
            'documents',
            'dependent_profiles',
            ['dependent_id'],
            ['id'],
            ondelete='CASCADE'
        )
    else:
        with op.batch_alter_table('documents') as batch_op:
            batch_op.create_foreign_key(
                'fk_documents_dependent_id_dependent_profiles',
                'dependent_profiles',
                ['dependent_id'],
                ['id'],
                ondelete='CASCADE'
            )

    # 3. Sanitize the 22 historical dangling PatientFact rows where source_type='chat'
    op.execute(sa.text("""
        DELETE FROM patient_facts
        WHERE source_type = 'chat'
          AND source_id IS NOT NULL
          AND source_id NOT IN (SELECT id::text FROM chats);
    """))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if bind.dialect.name == "postgresql":
        doc_fks = insp.get_foreign_keys('documents')
        for fk in doc_fks:
            if 'dependent_id' in fk.get('constrained_columns', []):
                fk_name = fk.get('name')
                if fk_name:
                    op.drop_constraint(fk_name, 'documents', type_='foreignkey')

        op.create_foreign_key(
            'fk_documents_dependent_id_dependent_profiles',
            'documents',
            'dependent_profiles',
            ['dependent_id'],
            ['id'],
            ondelete='SET NULL'
        )

    user_cols = [c['name'] for c in insp.get_columns('users')]
    if 'token_invalid_before' in user_cols:
        op.drop_column('users', 'token_invalid_before')
