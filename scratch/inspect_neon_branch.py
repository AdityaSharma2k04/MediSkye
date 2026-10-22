import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

branch_url = None
for line in open(r'd:\Mediskye\Mediskye\.env').read().splitlines():
    if line.startswith('NEON_BRANCH_DATABASE_URL='):
        branch_url = line.split('=', 1)[1].strip()

# Clean URL for asyncpg
clean_url = branch_url.split('?')[0].replace('postgresql://', 'postgresql+asyncpg://')
print("Using branch URL:", clean_url[:40] + "...")

async def check():
    engine = create_async_engine(
        clean_url,
        connect_args={"ssl": "require", "statement_cache_size": 0, "prepared_statement_cache_size": 0}
    )
    async with engine.connect() as conn:
        tables = (await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))).fetchall()
        print("Tables in public schema:", [t[0] for t in tables])
        try:
            versions = (await conn.execute(text("SELECT version_num FROM alembic_version"))).fetchall()
            print("Alembic version table contains:", versions)
        except Exception as e:
            print("alembic_version check failed:", e)

        indexes = (await conn.execute(text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename='users'"))).fetchall()
        print("Existing indexes on users:")
        for name, defn in indexes:
            print(f"  - {name}: {defn}")

asyncio.run(check())
