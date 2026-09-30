import os

# Set test environment variables before modules are loaded
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test_jwt_secret_key_at_least_32_characters_long_for_unit_tests!"
)

import pytest
import pytest_asyncio


@pytest_asyncio.fixture(autouse=True, scope="session")
async def setup_test_database():
    """
    Create all tables in the test database before any test runs.
    
    This is required for CI where the database is an empty in-memory SQLite.
    Locally, the file-based mediskye.db might already have these tables, which
    is why tests pass locally but fail in CI.
    """
    from app.db.database import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Optional: drop tables after the session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)