import sqlite3
import pytest
from sqlalchemy import text
from app.db.database import AsyncSessionLocal
# Import models so Base.metadata is fully populated for test database creation
from app.db import models  # noqa: F401


@pytest.mark.asyncio
async def test_expected_foreign_key_indexes_exist():
    """Verify that indexes exist on critical foreign key columns via PRAGMA index_list."""
    expected_indexes = {
        "documents": {"ix_documents_user_id"},
        "chats": {"ix_chats_user_id", "ix_chats_document_id"},
        "dependent_profiles": {"ix_dependent_profiles_user_id"},
        "audit_logs": {"ix_audit_logs_user_id"},
    }

    async with AsyncSessionLocal() as session:
        for table, expected in expected_indexes.items():
            result = await session.execute(text(f"PRAGMA index_list('{table}')"))
            rows = result.fetchall()
            # row format: (seq, name, unique, origin, partial)
            found_indexes = {row[1] for row in rows}
            for expected_index in expected:
                assert (
                    expected_index in found_indexes
                ), f"Expected index '{expected_index}' on table '{table}', found: {found_indexes}"


@pytest.mark.asyncio
async def test_queries_use_foreign_key_indexes():
    """Verify that filtering by foreign key columns utilizes the created indexes."""
    test_queries = [
        "SELECT * FROM documents WHERE user_id = 'test-id'",
        "SELECT * FROM chats WHERE user_id = 'test-id'",
        "SELECT * FROM chats WHERE document_id = 'test-id'",
        "SELECT * FROM dependent_profiles WHERE user_id = 'test-id'",
        "SELECT * FROM audit_logs WHERE user_id = 'test-id'",
    ]

    async with AsyncSessionLocal() as session:
        for query in test_queries:
            plan_res = await session.execute(text(f"EXPLAIN QUERY PLAN {query}"))
            plan_rows = plan_res.fetchall()
            plan_text = " ".join(str(r[-1]) for r in plan_rows)
            assert (
                "USING INDEX" in plan_text or "COVERING INDEX" in plan_text
            ), f"Query '{query}' did not use index in execution plan: {plan_text}"


def test_sqlite_file_foreign_key_indexes_exist():
    """Verify directly via sqlite3 on mediskye.db that migration created the indexes."""
    import os
    if not os.path.exists("mediskye.db"):
        pytest.skip("mediskye.db not found (running in pure memory CI)")

    conn = sqlite3.connect("mediskye.db")
    cur = conn.cursor()
    expected_indexes = {
        "documents": {"ix_documents_user_id"},
        "chats": {"ix_chats_user_id", "ix_chats_document_id"},
        "dependent_profiles": {"ix_dependent_profiles_user_id"},
        "audit_logs": {"ix_audit_logs_user_id"},
    }
    for table, expected in expected_indexes.items():
        cur.execute(f"PRAGMA index_list('{table}')")
        rows = cur.fetchall()
        found = {r[1] for r in rows}
        for idx in expected:
            assert idx in found, f"Missing index {idx} on {table} in mediskye.db"
    conn.close()
