import asyncio
import asyncpg

async def check():
    try:
        conn = await asyncpg.connect(
            host="clearbook-db.cr8ykokaa92o.ap-south-1.rds.amazonaws.com",
            port=5432,
            user="clearbook_user",
            password="ClearbookDB2024Secure",
            database="clearbook",
            ssl="require"
        )
        rows = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        print("Connected! Tables:", [r["table_name"] for r in rows])
        await conn.close()
    except Exception as e:
        print("Error:", e)

asyncio.run(check())