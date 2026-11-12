import asyncio
import uuid
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://clearbook_user:ClearbookDB2024Secure@clearbook-db.cr8ykokaa92o.ap-south-1.rds.amazonaws.com:5432/clearbook?ssl=require"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def seed():
    async with AsyncSessionLocal() as db:
        # Check if user already exists
        result = await db.execute(text("SELECT id FROM users WHERE email = 'admin@clearbook.ae'"))
        existing_user = result.fetchone()

        if not existing_user:
            user_id = str(uuid.uuid4())
            hashed_password = pwd_context.hash("Admin@1234")
            await db.execute(text("""
                INSERT INTO users (id, email, hashed_password, full_name, role, is_active, created_at, updated_at)
                VALUES (:id, :email, :password, :name, :role, true, NOW(), NOW())
            """), {
                "id": user_id,
                "email": "admin@clearbook.ae",
                "password": hashed_password,
                "name": "Admin User",
                "role": "admin",
            })
            print(f"✓ Created user: admin@clearbook.ae / Admin@1234")
        else:
            print(f"✓ User already exists: admin@clearbook.ae")

        # Check if client already exists
        result = await db.execute(text("SELECT id FROM clients WHERE name = 'ABC Trading LLC'"))
        existing_client = result.fetchone()

        if not existing_client:
            client_id = str(uuid.uuid4())
            await db.execute(text("""
                INSERT INTO clients (id, name, trn, email, is_active, created_at, updated_at)
                VALUES (:id, :name, :trn, :email, true, NOW(), NOW())
            """), {
                "id": client_id,
                "name": "ABC Trading LLC",
                "trn": "100234567890123",
                "email": "accounts@abctrading.ae",
            })
            print(f"✓ Created client: ABC Trading LLC")
            print(f"  Client ID: {client_id}")
        else:
            client_id = existing_client[0]
            print(f"✓ Client already exists: ABC Trading LLC")
            print(f"  Client ID: {client_id}")

        await db.commit()
        print("\nDone! Use the Client ID above when uploading documents.")

    await engine.dispose()


asyncio.run(seed())