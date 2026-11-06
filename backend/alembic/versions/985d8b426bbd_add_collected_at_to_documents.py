"""add_collected_at_to_documents

Revision ID: 985d8b426bbd
Revises: 204cb7f58e36
Create Date: 2026-11-06 20:12:08.897059

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '985d8b426bbd'
down_revision: Union[str, Sequence[str], None] = '204cb7f58e36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema and backfill collected_at if detectable."""
    op.add_column('documents', sa.Column('collected_at', sa.String(length=64), nullable=True))
    
    conn = op.get_bind()
    import re
    try:
        results = conn.execute(sa.text("SELECT id, title, filename, cached_summary FROM documents")).fetchall()
        date_regex = re.compile(r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|\d{4}-\d{2}-\d{2})\b', re.IGNORECASE)
        for row in results:
            doc_id, title, filename, cached_summary = row[0], row[1] or "", row[2] or "", row[3] or ""
            matched_date = None
            for text in [title, filename, cached_summary]:
                m = date_regex.search(text)
                if m:
                    matched_date = m.group(1).strip()
                    break
            if matched_date:
                conn.execute(
                    sa.text("UPDATE documents SET collected_at = :dt WHERE id = :id"),
                    {"dt": matched_date, "id": doc_id}
                )
    except Exception:
        pass


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('documents', 'collected_at')
