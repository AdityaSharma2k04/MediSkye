"""add_dependent_profiles_and_user_fields

Revision ID: 8e18e2020590
Revises: 0404983f4599
Create Date: 2026-09-30 20:03:03.075440

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e18e2020590'
down_revision: Union[str, Sequence[str], None] = '0404983f4599'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create dependent_profiles table
    op.create_table(
        'dependent_profiles',
        sa.Column('id', sa.UUID(), primary_key=True, nullable=False),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relationship', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('biological_sex', sa.String(), nullable=True),
        sa.Column('blood_type', sa.String(), nullable=True),
        sa.Column('pre_existing_conditions', sa.String(), nullable=True),
        sa.Column('known_allergies', sa.String(), nullable=True),
        sa.Column('current_medications', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # 2. Add current_medications and language_preference to users
    op.add_column('users', sa.Column('current_medications', sa.String(), nullable=True))
    op.add_column('users', sa.Column('language_preference', sa.String(), server_default='English', nullable=True))
    
    # 3. Add dependent_id to documents
    op.add_column('documents', sa.Column('dependent_id', sa.UUID(), nullable=True))
    
    # 4. Add dependent_id to audit_logs
    op.add_column('audit_logs', sa.Column('dependent_id', sa.UUID(), nullable=True))


def downgrade() -> None:
    op.drop_column('audit_logs', 'dependent_id')
    op.drop_column('documents', 'dependent_id')
    op.drop_column('users', 'language_preference')
    op.drop_column('users', 'current_medications')
    op.drop_table('dependent_profiles')
