"""
Demo seed: creates 3 realistic UAE clients + sample vouchers for CA demo.
Run with:  venv/Scripts/python seed_demo_data.py
"""
import asyncio
import uuid
from datetime import datetime, date, timedelta
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

# Load .env
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

CLIENTS = [
    {
        "name": "Al Noor Medical Supplies LLC",
        "trn": "100234567890123",
        "entity_type": "LLC",
        "industry": "Healthcare",
        "contact_name": "Ahmed Al Mansouri",
        "contact_email": "accounts@alnoormed.ae",
        "contact_phone": "+971 4 345 6789",
    },
    {
        "name": "Gulf Tech Solutions FZE",
        "trn": "100987654321098",
        "entity_type": "FZE",
        "industry": "Technology",
        "contact_name": "Priya Sharma",
        "contact_email": "finance@gulftechfze.ae",
        "contact_phone": "+971 4 567 8901",
    },
    {
        "name": "Desert Rose Trading LLC",
        "trn": "100456789012345",
        "entity_type": "LLC",
        "industry": "Trading",
        "contact_name": "Omar Al Rashidi",
        "contact_email": "omar@desertrose.ae",
        "contact_phone": "+971 50 123 4567",
    },
]

VOUCHER_TEMPLATES = [
    {"voucher_type": "purchase", "narration": "Office rent — {month} 2024", "amount": 15000, "status": "approved"},
    {"voucher_type": "purchase", "narration": "Electricity bill — DEWA {month}", "amount": 2850, "status": "approved"},
    {"voucher_type": "payment",  "narration": "Salary payment — {month} 2024", "amount": 85000, "status": "approved"},
    {"voucher_type": "receipt",  "narration": "Invoice INV-2024-{n} — Sales", "amount": 48500, "status": "pending_approval"},
    {"voucher_type": "journal",  "narration": "VAT adjustment — {month} 2024", "amount": 7250,  "status": "draft"},
    {"voucher_type": "purchase", "narration": "Internet & IT services — {month}", "amount": 1200, "status": "approved"},
]

MONTHS = ["Oct", "Nov", "Dec", "Jan"]


async def seed():
    async with AsyncSessionLocal() as db:
        # ── Admin user ────────────────────────────────────────────────────────
        result = await db.execute(text("SELECT id FROM users WHERE email = 'admin@clearbook.ae'"))
        if not result.fetchone():
            await db.execute(text("""
                INSERT INTO users (id, email, hashed_password, full_name, role, is_active, created_at, updated_at)
                VALUES (:id, :email, :pw, :name, 'admin', true, NOW(), NOW())
            """), {"id": str(uuid.uuid4()), "email": "admin@clearbook.ae",
                   "pw": pwd_context.hash("Admin@1234"), "name": "CA Admin"})
            print("[OK] Created user: admin@clearbook.ae / Admin@1234")
        else:
            print("[OK] User exists: admin@clearbook.ae")

        # ── Clients ───────────────────────────────────────────────────────────
        client_ids = []
        for c in CLIENTS:
            result = await db.execute(text("SELECT id FROM clients WHERE trn = :trn"), {"trn": c["trn"]})
            row = result.fetchone()
            if row:
                client_ids.append(row[0])
                print(f"  -> Client exists: {c['name']}")
            else:
                cid = str(uuid.uuid4())
                await db.execute(text("""
                    INSERT INTO clients
                        (id, name, trn, entity_type, industry, contact_name, contact_email, contact_phone,
                         is_active, created_at, updated_at)
                    VALUES
                        (:id, :name, :trn, :et, :ind, :cn, :ce, :cp, true, NOW(), NOW())
                """), {
                    "id": cid, "name": c["name"], "trn": c["trn"],
                    "et": c["entity_type"], "ind": c["industry"],
                    "cn": c["contact_name"], "ce": c["contact_email"], "cp": c["contact_phone"],
                })
                client_ids.append(cid)
                print(f"[OK] Created client: {c['name']}")

        # ── Vouchers (3 per client, varied months/statuses) ───────────────────
        total_created = 0
        for i, cid in enumerate(client_ids):
            for j, tmpl in enumerate(VOUCHER_TEMPLATES[:4]):
                month = MONTHS[j % len(MONTHS)]
                vid = str(uuid.uuid4())
                vdate = date(2024, 10 + (j % 3), 1 + (j * 5))
                narration = tmpl["narration"].format(month=month, n=f"0{i+1}{j+1}")
                await db.execute(text("""
                    INSERT INTO vouchers
                        (id, client_id, voucher_type, narration, amount, tax_amount, currency,
                         voucher_date, status, created_at, updated_at)
                    VALUES
                        (:id, :cid, :vtype, :narr, :amt, 0, 'AED', :vdate, :status, NOW(), NOW())
                    ON CONFLICT (id) DO NOTHING
                """), {
                    "id": vid, "cid": cid, "vtype": tmpl["voucher_type"],
                    "narr": narration, "amt": tmpl["amount"] + (i * 1000),
                    "vdate": vdate, "status": tmpl["status"],
                })
                total_created += 1

        # ── Audit logs ────────────────────────────────────────────────────────
        for cid in client_ids:
            await db.execute(text("""
                INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, client_id, details, created_at)
                VALUES (:lid, 'document', :eid, 'extraction_complete', 'system', :cid,
                        '{"document_type": "purchase_invoice", "confidence": 0.94}'::jsonb, NOW() - INTERVAL '2 hours')
                ON CONFLICT (id) DO NOTHING
            """), {"lid": str(uuid.uuid4()), "eid": str(uuid.uuid4()), "cid": cid})

        await db.commit()
        print(f"\n[OK] Seeded {len(client_ids)} clients, {total_created} vouchers")
        print("\n---------------------------------------------------")
        print("  Demo login: admin@clearbook.ae  /  Admin@1234")
        print("---------------------------------------------------")

    await engine.dispose()


asyncio.run(seed())
