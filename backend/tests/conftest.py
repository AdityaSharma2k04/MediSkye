import os
import inspect
from passlib.context import CryptContext

# Set test environment variables before modules are loaded
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test_jwt_secret_key_at_least_32_characters_long_for_unit_tests!"
)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ENV", "test")

# Shared test password — must be ≤72 bytes for bcrypt compatibility across OSes.
TEST_PASSWORD = "TestPassword123!"

# Disable remote GCS bucket calls in tests (tests testing GCS mock it explicitly)
from app.core.config import settings
settings.GCS_INDEX_BUCKET = None

# Fast-fail external Firebase network calls for synthetic test emails
import firebase_admin.auth
_orig_get_user = firebase_admin.auth.get_user_by_email

def _fast_get_user_by_email(email, app=None):
    if any(email.endswith(dom) for dom in ("@example.com", "@test.com", "@mediskye-test.local")) or "delete" in email or "e2e" in email:
        raise firebase_admin.auth.UserNotFoundError(f"Test user not in remote Firebase: {email}")
    return _orig_get_user(email, app=app)

firebase_admin.auth.get_user_by_email = _fast_get_user_by_email

# Fast-fail slow OCR subprocess execution in unit tests (tests testing OCR mock it explicitly)
import app.rag.loader as rl_mod
rl_mod._extract_with_ocr = lambda *args, **kwargs: []

# Fast-hash passwords in tests: minimum bcrypt cost (rounds=4) takes ~1ms instead of ~250ms
import app.core.auth as auth_mod
auth_mod.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=4)

import pytest
import pytest_asyncio
from sqlalchemy import event, text, inspect as sa_inspect
from app.db.database import Base, engine

# Module-level flag to ensure schema DDL runs only once across the test session
_SCHEMA_INITIALIZED = False


@event.listens_for(engine.sync_engine, "connect")
def _set_test_sqlite_pragmas(dbapi_conn, connection_record):
    """Disable disk syncing and store journal in memory for fast SQLite execution."""
    try:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA synchronous = OFF;")
        cursor.execute("PRAGMA journal_mode = MEMORY;")
        cursor.close()
    except Exception:
        pass


@pytest_asyncio.fixture(autouse=True)
async def setup_test_database(request):
    """
    Create all tables in the test database once per session.
    Skip DB setup/teardown entirely for pure synchronous unit tests.
    Only clean up tables if the test actually wrote data to the database.
    """
    global _SCHEMA_INITIALIZED

    # Skip DB setup & teardown entirely for pure synchronous unit tests (e.g. regex, ranges, safety)
    node_obj = getattr(request.node, "obj", None)
    if not inspect.iscoroutinefunction(node_obj):
        yield
        return

    # Ensure aiosqlite connection mutex belongs to the current event loop and is unlocked
    pool = getattr(engine.sync_engine, "pool", None)
    if pool is not None and "connection" in getattr(pool, "__dict__", {}):
        rec = pool.connection
        dbapi_conn = getattr(rec, "dbapi_connection", None)
        if dbapi_conn is not None and hasattr(dbapi_conn, "_execute_mutex"):
            import asyncio
            dbapi_conn._execute_mutex = asyncio.Lock()

    if not _SCHEMA_INITIALIZED:
        async with engine.begin() as conn:
            def _init_sqlite(sync_conn):
                if sync_conn.dialect.name == "sqlite":
                    sync_conn.execute(text("PRAGMA synchronous = OFF;"))
                    sync_conn.execute(text("PRAGMA journal_mode = MEMORY;"))

            await conn.run_sync(_init_sqlite)
            await conn.run_sync(Base.metadata.create_all)

            def _ensure_document_cache_columns(sync_conn):
                inspector = sa_inspect(sync_conn)
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

                if "users" in inspector.get_table_names():
                    existing_user_cols = {c["name"] for c in inspector.get_columns("users")}
                    if "token_invalid_before" not in existing_user_cols:
                        if dialect == "postgresql":
                            sync_conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_invalid_before TIMESTAMP WITH TIME ZONE"))
                        else:
                            sync_conn.execute(text("ALTER TABLE users ADD COLUMN token_invalid_before DATETIME"))

                if "chats" in inspector.get_table_names():
                    existing_chat_cols = {c["name"] for c in inspector.get_columns("chats")}
                    if "dependent_id" not in existing_chat_cols:
                        if dialect == "postgresql":
                            sync_conn.execute(text("ALTER TABLE chats ADD COLUMN IF NOT EXISTS dependent_id UUID REFERENCES dependent_profiles(id) ON DELETE CASCADE"))
                            sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chats_dependent_id ON chats(dependent_id)"))
                        else:
                            sync_conn.execute(text("ALTER TABLE chats ADD COLUMN dependent_id CHAR(32)"))
                            sync_conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chats_dependent_id ON chats(dependent_id)"))

            await conn.run_sync(_ensure_document_cache_columns)
        _SCHEMA_INITIALIZED = True

    # Record total_changes before test execution to detect if any writes happen
    def _get_changes(sync_conn):
        try:
            raw = sync_conn.connection.dbapi_connection
            underlying = getattr(raw, "_connection", raw)
            return getattr(underlying, "total_changes", -1)
        except Exception:
            return -1

    try:
        async with engine.connect() as conn:
            start_changes = await conn.run_sync(_get_changes)
    except Exception:
        start_changes = -1

    yield

    # Clean up and drain any background tasks spawned during the test
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

    # Clean up tables after test
    need_cleanup = True
    if start_changes != -1:
        try:
            async with engine.connect() as conn:
                end_changes = await conn.run_sync(_get_changes)
                if end_changes == start_changes:
                    need_cleanup = False
        except Exception:
            need_cleanup = True

    if need_cleanup:
        try:
            async with engine.begin() as conn:
                for table in reversed(Base.metadata.sorted_tables):
                    await conn.execute(table.delete())
        except Exception:
            pass


@pytest.fixture(autouse=True)
def fast_gemini_retry(request, monkeypatch):
    """
    Zero out retry backoff sleeps so retry tests don't spend seconds waiting.
    Skip for tests that explicitly assert retry duration/timing.
    """
    timing_tests = {
        "test_metrics_retry_recovers_on_second_attempt",
        "test_extract_metrics_retry_with_asyncio_sleep",
        "test_call_gemini_retry_does_not_block_event_loop",
    }
    if request.node.name in timing_tests:
        yield
        return

    import app.llm.gemini_client as gc
    import app.llm.embeddings_client as ec
    import app.rag.loader as rl
    import app.rag.intent_router as ir
    import app.api.v1.endpoints.metrics as em
    import app.services.fact_extractor as fe

    orig_call = gc.call_gemini_with_retry
    orig_embed = ec.embed_content_with_retry

    async def _fast_call(*args, **kwargs):
        if len(args) < 9 and "backoff_delays" not in kwargs:
            kwargs["backoff_delays"] = [0.01, 0.02]
        # Fast-fail real external Gemini network calls in unmocked unit tests
        client = kwargs.get("client")
        if client is None:
            try:
                client = gc.get_genai_client()
            except Exception:
                client = None
        from unittest.mock import MagicMock, AsyncMock
        if not isinstance(client, (MagicMock, AsyncMock)):
            if len(args) < 5 and "timeout" not in kwargs:
                kwargs["timeout"] = 0.1
            if "fallback_models" not in kwargs:
                kwargs["fallback_models"] = [settings.GEMINI_MODEL]
            if len(args) < 4 and "max_attempts" not in kwargs:
                kwargs["max_attempts"] = 1
        return await orig_call(*args, **kwargs)

    async def _fast_embed(*args, **kwargs):
        if len(args) < 8 and "backoff_delays" not in kwargs:
            kwargs["backoff_delays"] = [0.01, 0.02]
        client = kwargs.get("client")
        if client is None:
            try:
                client = gc.get_genai_client()
            except Exception:
                client = None
        from unittest.mock import MagicMock, AsyncMock
        if not isinstance(client, (MagicMock, AsyncMock)):
            if len(args) < 4 and "timeout" not in kwargs:
                kwargs["timeout"] = 0.1
            if len(args) < 3 and "max_attempts" not in kwargs:
                kwargs["max_attempts"] = 1
        return await orig_embed(*args, **kwargs)

    monkeypatch.setattr(gc, "call_gemini_with_retry", _fast_call)
    monkeypatch.setattr(ec, "embed_content_with_retry", _fast_embed)
    if hasattr(rl, "call_gemini_with_retry"):
        monkeypatch.setattr(rl, "call_gemini_with_retry", _fast_call)
    if hasattr(ir, "call_gemini_with_retry"):
        monkeypatch.setattr(ir, "call_gemini_with_retry", _fast_call)
    if hasattr(em, "call_gemini_with_retry"):
        monkeypatch.setattr(em, "call_gemini_with_retry", _fast_call)
    if hasattr(fe, "call_gemini_with_retry"):
        monkeypatch.setattr(fe, "call_gemini_with_retry", _fast_call)

    yield


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
    gc.get_genai_client.cache_clear()
    yield
    gc._llm_dead_until = 0.0
    gc.get_genai_client.cache_clear()


@pytest.fixture(autouse=True)
def reset_token_cache_each_test():
    """Ensure in-memory auth token cache does not leak across test cases."""
    from app.core.auth import clear_token_cache, _INFLIGHT_RESOLUTIONS
    clear_token_cache()
    _INFLIGHT_RESOLUTIONS.clear()
    yield
    clear_token_cache()
    _INFLIGHT_RESOLUTIONS.clear()
