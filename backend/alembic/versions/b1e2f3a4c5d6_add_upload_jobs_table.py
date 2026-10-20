"""add upload_jobs table
Revision ID: b1e2f3a4c5d6
Revises: aaaa5dbe106d
Create Date: 2026-10-21 01:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b1e2f3a4c5d6'
down_revision: Union[str, Sequence[str], None] = 'aaaa5dbe106d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = insp.get_table_names()

    if 'upload_jobs' not in existing_tables:
        op.create_table(
            'upload_jobs',
            sa.Column('id', sa.String(length=64), primary_key=True),
            sa.Column('user_id', sa.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
            sa.Column('document_id', sa.String(length=64), nullable=True),
            sa.Column('error', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_upload_jobs_user_id', 'upload_jobs', ['user_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = insp.get_table_names()

    if 'upload_jobs' in existing_tables:
        op.drop_index('ix_upload_jobs_user_id', table_name='upload_jobs')
        op.drop_table('upload_jobs')
