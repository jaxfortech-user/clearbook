import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://clearbook_user:ClearbookDB2024Secure@clearbook-db.cr8ykokaa92o.ap-south-1.rds.amazonaws.com:5432/clearbook?ssl=require"

engine = create_async_engine(DATABASE_URL)

async def run():
    async with engine.begin() as conn:
        # Delete vouchers linked to these documents first (FK constraint)
        await conn.execute(text("DELETE FROM vouchers WHERE document_id IN (SELECT id FROM documents)"))
        
        # Delete all documents
        result = await conn.execute(text("DELETE FROM documents RETURNING id"))
        deleted = result.fetchall()
        print(f"Deleted {len(deleted)} documents and their linked vouchers.")

    await engine.dispose()

asyncio.run(run())