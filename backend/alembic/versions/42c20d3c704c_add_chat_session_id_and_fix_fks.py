"""add_chat_session_id_and_fix_fks

Revision ID: 42c20d3c704c
Revises: d7b2c1e4f5a6
Create Date: 2026-11-05 21:57:08.303034

"""
import logging
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from cryptography.fernet import Fernet
from app.core.config import settings

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = '42c20d3c704c'
down_revision: Union[str, Sequence[str], None] = 'd7b2c1e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1. Add session_id and session_title to chats
    chat_cols = [c['name'] for c in insp.get_columns('chats')]
    if 'session_id' not in chat_cols:
        op.add_column('chats', sa.Column('session_id', sa.String(64), nullable=True))
        op.create_index('ix_chats_session_id', 'chats', ['session_id'])

    if 'session_title' not in chat_cols:
        op.add_column('chats', sa.Column('session_title', sa.String(255), nullable=True))

    # 2. Backfill existing chats rows where session_id IS NULL
    op.execute(sa.text("""
        UPDATE chats
        SET session_id = 'doc-' || CAST(document_id AS VARCHAR)
        WHERE session_id IS NULL AND document_id IS NOT NULL;
    """))
    op.execute(sa.text("""
        UPDATE chats
        SET session_id = 'legacy-' || CAST(user_id AS VARCHAR)
        WHERE session_id IS NULL;
    """))

    # 3. Encrypt legacy plaintext chat messages in chats table
    try:
        fernet = Fernet(settings.FERNET_KEY.encode() if isinstance(settings.FERNET_KEY, str) else settings.FERNET_KEY)
        rows = bind.execute(sa.text("SELECT id, message FROM chats")).fetchall()
        for row in rows:
            cid, msg = row[0], row[1]
            if msg and not msg.startswith("gAAAAA"):
                try:
                    encrypted = fernet.encrypt(msg.encode('utf-8')).decode('utf-8')
                    bind.execute(
                        sa.text("UPDATE chats SET message = :enc WHERE id = :cid"),
                        {"enc": encrypted, "cid": cid}
                    )
                except Exception as enc_err:
                    logger.warning("Could not encrypt chat row %s: %s", cid, enc_err)
    except Exception as e:
        logger.warning("Chat encryption backfill encountered an issue: %s", e)

    # 4. Sanitize orphaned dependent_id values
    op.execute(sa.text("""
        UPDATE documents
        SET dependent_id = NULL
        WHERE dependent_id IS NOT NULL
          AND dependent_id NOT IN (SELECT id FROM dependent_profiles);
    """))
    op.execute(sa.text("""
        UPDATE audit_logs
        SET dependent_id = NULL
        WHERE dependent_id IS NOT NULL
          AND dependent_id NOT IN (SELECT id FROM dependent_profiles);
    """))

    # 5. Add missing foreign key constraints
    if bind.dialect.name == "postgresql":
        doc_fks = [fk['name'] for fk in insp.get_foreign_keys('documents')]
        if 'fk_documents_dependent_id_dependent_profiles' not in doc_fks:
            op.create_foreign_key(
                'fk_documents_dependent_id_dependent_profiles',
                'documents',
                'dependent_profiles',
                ['dependent_id'],
                ['id'],
                ondelete='SET NULL'
            )

        audit_fks = [fk['name'] for fk in insp.get_foreign_keys('audit_logs')]
        if 'fk_audit_logs_dependent_id_dependent_profiles' not in audit_fks:
            op.create_foreign_key(
                'fk_audit_logs_dependent_id_dependent_profiles',
                'audit_logs',
                'dependent_profiles',
                ['dependent_id'],
                ['id'],
                ondelete='SET NULL'
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if bind.dialect.name == "postgresql":
        audit_fks = [fk['name'] for fk in insp.get_foreign_keys('audit_logs')]
        if 'fk_audit_logs_dependent_id_dependent_profiles' in audit_fks:
            op.drop_constraint('fk_audit_logs_dependent_id_dependent_profiles', 'audit_logs', type_='foreignkey')

        doc_fks = [fk['name'] for fk in insp.get_foreign_keys('documents')]
        if 'fk_documents_dependent_id_dependent_profiles' in doc_fks:
            op.drop_constraint('fk_documents_dependent_id_dependent_profiles', 'documents', type_='foreignkey')

    chat_indices = [idx['name'] for idx in insp.get_indexes('chats')]
    if 'ix_chats_session_id' in chat_indices:
        op.drop_index('ix_chats_session_id', table_name='chats')

    chat_cols = [c['name'] for c in insp.get_columns('chats')]
    if 'session_title' in chat_cols:
        op.drop_column('chats', 'session_title')
    if 'session_id' in chat_cols:
        op.drop_column('chats', 'session_id')
