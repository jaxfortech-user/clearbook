import asyncio
import asyncpg
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def reset():
    conn = await asyncpg.connect(
        host="clearbook-db.cr8ykokaa92o.ap-south-1.rds.amazonaws.com",
        port=5432,
        user="clearbook_user",
        password="ClearbookDB2024Secure",
        database="clearbook",
        ssl="require"
    )
    new_password = "Admin@1234"
    hashed = pwd_context.hash(new_password)
    await conn.execute(
        "UPDATE users SET hashed_password = $1 WHERE email = 'admin@clearbook.ae'",
        hashed
    )
    print(f"Password reset to: {new_password}")
    await conn.close()

asyncio.run(reset())