import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

for line in open(r'd:\Mediskye\Mediskye\.env').read().splitlines():
    if line.startswith('NEON_BRANCH_DATABASE_URL='):
        branch_url = line.split('=', 1)[1].strip()

clean_url = branch_url.split('?')[0].replace('postgresql://', 'postgresql+asyncpg://')

async def check():
    engine = create_async_engine(
        clean_url,
        connect_args={"ssl": "require", "statement_cache_size": 0, "prepared_statement_cache_size": 0}
    )
    async with engine.connect() as conn:
        doc_cols = (await conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='documents'"))).fetchall()
        print("Documents columns:", [c[0] for c in doc_cols])
        
        user_cols = (await conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='users'"))).fetchall()
        print("Users columns:", [c[0] for c in user_cols])

        indexes = (await conn.execute(text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename='users'"))).fetchall()
        print("Users indexes:")
        for name, defn in indexes:
            print(f"  {name}: {defn}")

asyncio.run(check())
