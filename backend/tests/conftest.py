import os

# Set test environment variables before modules are loaded
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test_jwt_secret_key_at_least_32_characters_long_for_unit_tests!"
)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ENV", "test")

# Shared test password — must be ≤72 bytes for bcrypt compatibility across OSes.
TEST_PASSWORD = "TestPassword123!"

import pytest
import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def setup_test_database():
    """
    Create all tables in the test database before each test.

    Function-scoped (not session-scoped) to match pytest-asyncio's default
    function-scoped event loop. Combined with StaticPool in database.py, the
    in-memory SQLite DB shares one connection across the whole test session,
    so re-running create_all is idempotent and safe.

    Local file-based SQLite already has tables, so create_all is a no-op there.
    CI uses :memory: with StaticPool, so this is what actually creates the schema.
    """
    from app.db.database import Base, engine
    from sqlalchemy import inspect, text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def _ensure_document_cache_columns(sync_conn):
            inspector = inspect(sync_conn)
            if "documents" in inspector.get_table_names():
                existing_cols = {c["name"] for c in inspector.get_columns("documents")}
                dialect = sync_conn.dialect.name
                if "cached_metrics" not in existing_cols:
                    if dialect == "postgresql":
                        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS cached_metrics JSON"))
                    else:
                        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN cached_metrics JSON"))
                if "cached_summary" not in existing_cols:
                    if dialect == "postgresql":
                        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS cached_summary TEXT"))
                    else:
                        sync_conn.execute(text("ALTER TABLE documents ADD COLUMN cached_summary TEXT"))

        await conn.run_sync(_ensure_document_cache_columns)

    yield

    # Clean up and drain any background tasks spawned during the test
    # before pytest-asyncio destroys this test's event loop.
    try:
        import asyncio
        from app.api.v1.endpoints.upload import _background_warm_tasks
        from app.api.v1.endpoints.query import _background_tasks

        pending = [t for t in (_background_warm_tasks | _background_tasks) if not t.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        _background_warm_tasks.clear()
        _background_tasks.clear()
    except Exception:
        pass

    try:
        await engine.dispose()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def reset_rate_limits_each_test():
    """Ensure in-memory rate limiter counts do not leak across test cases."""
    from app.core.limiter import limiter
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def reset_gemini_cooldown_each_test():
    """Ensure in-memory Gemini cooldown does not leak across test cases."""
    import app.llm.gemini_client as gc
    gc._llm_dead_until = 0.0
    yield
    gc._llm_dead_until = 0.0