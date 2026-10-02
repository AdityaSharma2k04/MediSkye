"""add cascade deletes

Revision ID: 3ee652733cc5
Revises: 4c6654c33c56
Create Date: 2026-10-02 23:34:26.225751

GDPR/HIPAA cleanup: deleting a user (or a parent row) must cascade to child
rows instead of leaving orphans. ``audit_logs.user_id`` is deliberately
``ON DELETE SET NULL`` so the compliance trail survives the account deletion.

Dialect notes
-------------
SQLite cannot ALTER foreign keys in place, so Alembic batch mode recreates the
table (``recreate="always"``). The pre-existing FK constraints are unnamed in
SQLite, so a naming convention is supplied to give the reflected constraints a
deterministic name that can be targeted by ``drop_constraint``. PostgreSQL (and
other backends) drop/recreate the constraint directly using the reflected name.

Several FKs already carried ``ON DELETE CASCADE`` from earlier migrations
(``dependent_profiles.user_id``, ``patient_facts.*``, ``chat_chunks.*``,
``chat_documents.*``), so only the drifted constraints are touched here.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ee652733cc5'
down_revision: Union[str, Sequence[str], None] = '4c6654c33c56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Deterministic FK names so unnamed SQLite constraints can be addressed.
FK_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def _fk_name(table: str, column: str, referred_table: str) -> str:
    return f"fk_{table}_{column}_{referred_table}"


# table -> [(child column, referred table, ondelete), ...]
# ondelete=None restores the original SQL "NO ACTION" behaviour (downgrade).
CASCADE_FKS = {
    "documents": [("user_id", "users", "CASCADE")],
    "chats": [
        ("user_id", "users", "CASCADE"),
        # chats.document_id is nullable; a deleted document must not orphan it.
        ("document_id", "documents", "SET NULL"),
    ],
    "audit_logs": [("user_id", "users", "SET NULL")],
}

RESTORE_FKS = {
    "documents": [("user_id", "users", None)],
    "chats": [
        ("user_id", "users", None),
        ("document_id", "documents", None),
    ],
    "audit_logs": [("user_id", "users", None)],
}


def _reflected_fk_name(inspector, table: str, column: str):
    """Return the DB's existing FK constraint name for ``table.column`` (or None)."""
    for fk in inspector.get_foreign_keys(table):
        if fk.get("constrained_columns") == [column]:
            return fk.get("name")
    return None


def _apply(table: str, changes) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # Recreate the table once with all FK changes applied together.
        with op.batch_alter_table(
            table, naming_convention=FK_CONVENTION, recreate="always"
        ) as batch_op:
            for column, referred_table, ondelete in changes:
                name = _fk_name(table, column, referred_table)
                batch_op.drop_constraint(name, type_="foreignkey")
                batch_op.create_foreign_key(
                    name, referred_table, [column], ["id"], ondelete=ondelete
                )
    else:
        inspector = sa.inspect(bind)
        for column, referred_table, ondelete in changes:
            existing_name = _reflected_fk_name(inspector, table, column)
            if existing_name:
                op.drop_constraint(existing_name, table, type_="foreignkey")
            op.create_foreign_key(
                _fk_name(table, column, referred_table),
                table,
                referred_table,
                [column],
                ["id"],
                ondelete=ondelete,
            )


def upgrade() -> None:
    """Add ON DELETE CASCADE (and SET NULL for audit_logs) to drifted FKs."""
    for table, changes in CASCADE_FKS.items():
        _apply(table, changes)


def downgrade() -> None:
    """Restore the original FK behaviour (no ON DELETE action)."""
    for table, changes in RESTORE_FKS.items():
        _apply(table, changes)
