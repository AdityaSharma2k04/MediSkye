import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

for line in open(r'd:\Mediskye\Mediskye\.env').read().splitlines():
    if line.startswith('NEON_BRANCH_DATABASE_URL='):
        branch_url = line.split('=', 1)[1].strip()

clean_url = branch_url.split('?')[0].replace('postgresql://', 'postgresql+asyncpg://')

async def main():
    e = create_async_engine(clean_url, connect_args={'ssl': 'require', 'statement_cache_size': 0, 'prepared_statement_cache_size': 0})
    async with e.connect() as c:
        await c.execute(text("DELETE FROM users WHERE email='branchtest@example.com'"))
        await c.commit()
        print("Cleaned up branchtest user")

asyncio.run(main())
