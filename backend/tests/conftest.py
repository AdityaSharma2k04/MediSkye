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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield