"""add patient memory, personalization, multi-doc support

Revision ID: 4c6654c33c56
Revises: c9e1f2a3b4d5
Create Date: 2026-10-01 01:41:19.286191

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '4c6654c33c56'
down_revision: Union[str, Sequence[str], None] = 'c9e1f2a3b4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1. Add fields to users table
    user_cols = [c['name'] for c in insp.get_columns('users')]
    with op.batch_alter_table('users') as batch_op:
        if 'memory_consent_granted' not in user_cols:
            batch_op.add_column(sa.Column('memory_consent_granted', sa.Boolean(), server_default='0', nullable=False))
        if 'height_cm' not in user_cols:
            batch_op.add_column(sa.Column('height_cm', sa.Float(), nullable=True))
        if 'diet_type' not in user_cols:
            batch_op.add_column(sa.Column('diet_type', sa.String(), nullable=True))
        if 'activity_level' not in user_cols:
            batch_op.add_column(sa.Column('activity_level', sa.String(), nullable=True))
        if 'occupation' not in user_cols:
            batch_op.add_column(sa.Column('occupation', sa.String(), nullable=True))

    # 2. Add fields to dependent_profiles table
    dep_cols = [c['name'] for c in insp.get_columns('dependent_profiles')]
    with op.batch_alter_table('dependent_profiles') as batch_op:
        if 'height_cm' not in dep_cols:
            batch_op.add_column(sa.Column('height_cm', sa.Float(), nullable=True))
        if 'diet_type' not in dep_cols:
            batch_op.add_column(sa.Column('diet_type', sa.String(), nullable=True))
        if 'activity_level' not in dep_cols:
            batch_op.add_column(sa.Column('activity_level', sa.String(), nullable=True))
        if 'occupation' not in dep_cols:
            batch_op.add_column(sa.Column('occupation', sa.String(), nullable=True))

    existing_tables = insp.get_table_names()

    # 3. Create patient_facts table
    if 'patient_facts' not in existing_tables:
        op.create_table(
            'patient_facts',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('dependent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dependent_profiles.id', ondelete='CASCADE'), nullable=True),
            sa.Column('fact_type', sa.String(), nullable=False),
            sa.Column('fact_text', sa.String(), nullable=False),
            sa.Column('confidence', sa.Float(), server_default='1.0', nullable=False),
            sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
            sa.Column('is_user_verified', sa.Boolean(), server_default='0', nullable=False),
            sa.Column('source_type', sa.String(), server_default='chat', nullable=False),
            sa.Column('source_id', sa.String(), nullable=True),
            sa.Column('source_excerpt', sa.String(), nullable=True),
            sa.Column('first_seen_at', sa.DateTime(), nullable=False),
            sa.Column('last_seen_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
        op.create_index(op.f('ix_patient_facts_user_id'), 'patient_facts', ['user_id'])
        op.create_index(op.f('ix_patient_facts_dependent_id'), 'patient_facts', ['dependent_id'])
        op.create_index(op.f('ix_patient_facts_fact_type'), 'patient_facts', ['fact_type'])
        op.create_index('ix_patient_facts_user_dep_active', 'patient_facts', ['user_id', 'dependent_id', 'is_active'])

    # 4. Create chat_chunks table
    if 'chat_chunks' not in existing_tables:
        op.create_table(
            'chat_chunks',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('dependent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('dependent_profiles.id', ondelete='CASCADE'), nullable=True),
            sa.Column('chat_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chats.id', ondelete='CASCADE'), nullable=False),
            sa.Column('chunk_text', sa.String(), nullable=False),
            sa.Column('chunk_index', sa.Integer(), server_default='0', nullable=False),
            sa.Column('embedding', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
        op.create_index(op.f('ix_chat_chunks_user_id'), 'chat_chunks', ['user_id'])
        op.create_index(op.f('ix_chat_chunks_dependent_id'), 'chat_chunks', ['dependent_id'])
        op.create_index(op.f('ix_chat_chunks_chat_id'), 'chat_chunks', ['chat_id'])
        op.create_index('ix_chat_chunks_user_chat', 'chat_chunks', ['user_id', 'chat_id'])

    # 5. Create chat_documents table
    if 'chat_documents' not in existing_tables:
        op.create_table(
            'chat_documents',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('chat_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chats.id', ondelete='CASCADE'), nullable=False),
            sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
            sa.Column('added_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('chat_id', 'document_id', name='uq_chat_document'),
        )
        op.create_index(op.f('ix_chat_documents_chat_id'), 'chat_documents', ['chat_id'])
        op.create_index(op.f('ix_chat_documents_document_id'), 'chat_documents', ['document_id'])

    # 6. Task A4: Clean fake specialist rows if any exist
    try:
        bind.execute(sa.text(
            "DELETE FROM specialists WHERE contact_info LIKE '%555-%' OR contact_info LIKE '%@mediskye.org' "
            "OR name LIKE '%Sarah Chen%' OR name LIKE '%Marcus Johnson%' OR name LIKE '%Emily Patel%' "
            "OR name LIKE '%Michael Chang%' OR name LIKE '%Rachel Green%' OR name LIKE '%David Smith%' "
            "OR name LIKE '%Elena Rodriguez%' OR name LIKE '%James Wilson%'"
        ))
    except Exception:
        pass


def downgrade() -> None:
    op.drop_table('chat_documents')
    op.drop_table('chat_chunks')
    op.drop_table('patient_facts')

    with op.batch_alter_table('dependent_profiles') as batch_op:
        batch_op.drop_column('occupation')
        batch_op.drop_column('activity_level')
        batch_op.drop_column('diet_type')
        batch_op.drop_column('height_cm')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('occupation')
        batch_op.drop_column('activity_level')
        batch_op.drop_column('diet_type')
        batch_op.drop_column('height_cm')
        batch_op.drop_column('memory_consent_granted')
