import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Add ?ssl=disable at the end
DATABASE_URL = "postgresql+asyncpg://clearbook_user:ClearbookDB2024Secure@clearbook-db.cr8ykokaa92o.ap-south-1.rds.amazonaws.com:5432/clearbook?ssl=require"

engine = create_async_engine(DATABASE_URL)

sql = """
ALTER TABLE vouchers
    ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'AED',
    ADD COLUMN IF NOT EXISTS approved_entries JSON,
    ADD COLUMN IF NOT EXISTS approved_by VARCHAR(255),
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT,
    ADD COLUMN IF NOT EXISTS tally_voucher_id VARCHAR(100),
    ADD COLUMN IF NOT EXISTS tally_company VARCHAR(255);
"""

async def run():
    async with engine.begin() as conn:
        await conn.execute(text(sql))
    print("Migration done.")
    await engine.dispose()

asyncio.run(run())