import asyncio
import asyncpg

async def check():
    conn = await asyncpg.connect(
        host="clearbook-db.cr8ykokaa92o.ap-south-1.rds.amazonaws.com",
        port=5432,
        user="clearbook_user",
        password="ClearbookDB2024Secure",
        database="clearbook",
        ssl="require"
    )
    rows = await conn.fetch("SELECT id, email, full_name, is_active, created_at FROM users")
    if rows:
        for r in rows:
            print(f"Email: {r['email']} | Name: {r['full_name']} | Active: {r['is_active']}")
    else:
        print("No users found.")
    await conn.close()

asyncio.run(check())