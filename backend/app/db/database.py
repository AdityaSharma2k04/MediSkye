from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool

from app.core.config import settings

# For in-memory SQLite (used in tests), we must use StaticPool to share a single
# connection across all sessions. Without this, each new connection gets a fresh
# empty database, so tables created by one session are invisible to the next.
_engine_kwargs = {}
if ":memory:" in settings.DATABASE_URL:
    _engine_kwargs = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }

engine = create_async_engine(
    settings.DATABASE_URL,
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
    async with AsyncSessionLocal() as session:
        yield session