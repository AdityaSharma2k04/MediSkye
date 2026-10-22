import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

for line in open(r'd:\Mediskye\Mediskye\.env').read().splitlines():
    if line.startswith('NEON_BRANCH_DATABASE_URL='):
        branch_url = line.split('=', 1)[1].strip()

clean_url = branch_url.split('?')[0].replace('postgresql://', 'postgresql+asyncpg://')

async def main():
    engine = create_async_engine(
        clean_url,
        connect_args={'ssl': 'require', 'statement_cache_size': 0, 'prepared_statement_cache_size': 0}
    )
    async with engine.connect() as conn:
        # 1. Check index existence
        res = (await conn.execute(text("SELECT indexdef FROM pg_indexes WHERE indexname='ix_users_lower_email'"))).fetchall()
        print("pg_indexes result:")
        print(res)

        # 2. Insert dummy user if needed and run EXPLAIN
        user_check = (await conn.execute(text("SELECT id FROM users WHERE LOWER(email) = 'branchtest@example.com'"))).fetchall()
        if not user_check:
            await conn.execute(text("""
                INSERT INTO users (id, email, hashed_password, phi_consent_granted, memory_consent_granted, full_name)
                VALUES (gen_random_uuid(), 'branchtest@example.com', '$2b$12$dummyhash', true, false, 'Branch Test User')
            """))
            await conn.commit()
            print("Inserted dummy test user: branchtest@example.com")
        else:
            print("Dummy test user already exists")

        # In PostgreSQL on tiny tables (e.g. 1-10 rows), planner defaults to Seq Scan unless seqscan is disabled
        # or we verify both the default and the index scan:
        await conn.execute(text("SET enable_seqscan = off;"))
        explain_res = (await conn.execute(text("EXPLAIN (ANALYZE, BUFFERS) SELECT id FROM users WHERE LOWER(email) = 'branchtest@example.com'"))).fetchall()
        print("\nEXPLAIN output (with index scan):")
        for row in explain_res:
            print(row[0])

        await conn.execute(text("SET enable_seqscan = on;"))
        explain_res_default = (await conn.execute(text("EXPLAIN (ANALYZE, BUFFERS) SELECT id FROM users WHERE LOWER(email) = 'branchtest@example.com'"))).fetchall()
        print("\nEXPLAIN output (default planner):")
        for row in explain_res_default:
            print(row[0])

asyncio.run(main())
