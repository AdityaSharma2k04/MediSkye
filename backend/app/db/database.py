from app.core.config import normalize_async_database_url, settings
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool

# For in-memory SQLite (used in tests), we must use StaticPool to share a single
# connection across all sessions. Without this, each new connection gets a fresh
# empty database, so tables created by one session are invisible to the next.
_engine_kwargs = {}
normalized_db_url = normalize_async_database_url(settings.DATABASE_URL)

if ":memory:" in normalized_db_url:
    _engine_kwargs = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }
elif "postgresql" in normalized_db_url:
    # ssl=require for Neon; statement_cache_size=0 disables asyncpg's prepared
    # statement cache, which is incompatible with PgBouncer (Neon pooler) in
    # transaction mode. pool_pre_ping handles scale-to-zero reconnects.
    # pool_recycle=300 ensures idle connections are recycled before serverless PgBouncer drops them.
    # timeout=10 in connect_args ensures stale serverless connections fail-fast without hanging container boot.
    _engine_kwargs = {
        "connect_args": {
            "ssl": "require",
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "command_timeout": 60,
            "timeout": 10,
        },
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
    }

engine = create_async_engine(
    normalized_db_url,
    echo=settings.DEBUG,
    future=True,
    **_engine_kwargs,
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    """Enforce foreign key constraints on SQLite.

    SQLite does not enforce ON DELETE actions unless PRAGMA foreign_keys is ON.
    Without this, the ondelete="CASCADE" declarations are silently ignored and
    deleting a user would leave orphaned child rows.
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db():
    session = AsyncSessionLocal()
    try:
        yield session
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            await session.close()
        except Exception:
            pass