"""
Bank reconciliation: upload bank statement → extract transactions → match against Tally ledger.
"""
import os
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.models.client import Client
from app.models.bank_reconciliation import BankReconciliation, BankTransaction

router = APIRouter()


# ── Demo transactions (used when a real statement isn't parsed yet) ───────────

DEMO_BANK_TRANSACTIONS = [
    {"date": "2024-11-01", "description": "Opening Balance b/f",               "amount": 120000,  "is_matched": True,  "tally_ref": "Opening Balance"},
    {"date": "2024-11-03", "description": "TRANSFER FROM XYZ TRADING INV-089", "amount": 25000,   "is_matched": True,  "tally_ref": "Sales Receipt – XYZ Trading"},
    {"date": "2024-11-05", "description": "SALARY PAYMENT NOV 2024",           "amount": -15000,  "is_matched": True,  "tally_ref": "Salaries – Nov 2024"},
    {"date": "2024-11-07", "description": "ABC SUPPLIERS PAYMENT",             "amount": -8500,   "is_matched": True,  "tally_ref": "Purchase Payment – ABC Suppliers"},
    {"date": "2024-11-10", "description": "UTILITY BILL DEWA",                 "amount": -1200,   "is_matched": False, "tally_ref": None},
    {"date": "2024-11-12", "description": "ONLINE TRANSFER TO ACCT 1234567890","amount": -5000,   "is_matched": False, "tally_ref": None},
    {"date": "2024-11-15", "description": "RECEIPT FROM AL FARDAN EXCHANGE",   "amount": 18000,   "is_matched": True,  "tally_ref": "Sales Receipt – Al Fardan"},
    {"date": "2024-11-18", "description": "RENT PAYMENT NOV 2024",             "amount": -5000,   "is_matched": True,  "tally_ref": "Rent – Nov 2024"},
    {"date": "2024-11-22", "description": "VISA CARD PAYMENT REF 98765",       "amount": -3200,   "is_matched": False, "tally_ref": None},
    {"date": "2024-11-28", "description": "INTEREST EARNED",                   "amount": 450,     "is_matched": False, "tally_ref": None},
]


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ReconciliationCreate(BaseModel):
    client_id: str
    period_start: date
    period_end: date
    bank_account: str
    statement_balance: Optional[float] = 0
    notes: Optional[str] = None


class ReconciliationPatch(BaseModel):
    status: Optional[str] = None
    statement_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    notes: Optional[str] = None


class TransactionAdd(BaseModel):
    transaction_date: date
    description: str
    amount: float


class MatchPayload(BaseModel):
    transaction_id: str
    tally_ref: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_tenant_id(db):
    """Placeholder — replace with JWT dependency when auth is wired."""
    return "demo-tenant"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("")
async def create_reconciliation(
    payload: ReconciliationCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Client).where(Client.id == payload.client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Client not found")

    rec = BankReconciliation(
        id=str(uuid.uuid4()),
        tenant_id=client.tenant_id,
        client_id=payload.client_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        bank_account=payload.bank_account,
        statement_balance=Decimal(str(payload.statement_balance or 0)),
        status="draft",
        notes=payload.notes,
    )
    db.add(rec)
    await db.flush()

    # Seed demo transactions
    for i, t in enumerate(DEMO_BANK_TRANSACTIONS):
        txn = BankTransaction(
            id=str(uuid.uuid4()),
            reconciliation_id=rec.id,
            tenant_id=client.tenant_id,
            transaction_date=date.fromisoformat(t["date"]),
            description=t["description"],
            amount=Decimal(str(t["amount"])),
            is_matched=t["is_matched"],
            tally_ref=t["tally_ref"],
        )
        db.add(txn)

    await db.commit()
    await db.refresh(rec)
    return {"id": rec.id, "status": rec.status, "client_id": rec.client_id}


@router.post("/upload")
async def upload_bank_statement(
    client_id: str = Query(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a bank statement — creates a reconciliation with demo transactions."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Client not found")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".pdf", ".csv", ".xlsx", ".xls"}:
        raise HTTPException(400, "Only PDF, CSV, XLSX files are accepted")

    rec = BankReconciliation(
        id=str(uuid.uuid4()),
        tenant_id=client.tenant_id,
        client_id=client_id,
        period_start=date(2024, 11, 1),
        period_end=date(2024, 11, 30),
        bank_account=file.filename or "Uploaded Statement",
        statement_balance=Decimal("125550"),
        status="in_progress",
    )
    db.add(rec)
    await db.flush()

    for t in DEMO_BANK_TRANSACTIONS:
        txn = BankTransaction(
            id=str(uuid.uuid4()),
            reconciliation_id=rec.id,
            tenant_id=client.tenant_id,
            transaction_date=date.fromisoformat(t["date"]),
            description=t["description"],
            amount=Decimal(str(t["amount"])),
            is_matched=t["is_matched"],
            tally_ref=t["tally_ref"],
        )
        db.add(txn)

    await db.commit()
    await db.refresh(rec)

    matched = sum(1 for t in DEMO_BANK_TRANSACTIONS if t["is_matched"])
    return {
        "id": rec.id,
        "client_id": client_id,
        "filename": file.filename,
        "status": rec.status,
        "summary": {
            "total": len(DEMO_BANK_TRANSACTIONS),
            "matched": matched,
            "unmatched": len(DEMO_BANK_TRANSACTIONS) - matched,
        },
    }


@router.get("/client/{client_id}")
async def list_reconciliations(client_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BankReconciliation).where(BankReconciliation.client_id == client_id)
    )
    recs = result.scalars().all()
    return [{"id": r.id, "period_start": r.period_start, "period_end": r.period_end,
             "bank_account": r.bank_account, "status": r.status} for r in recs]


@router.get("/{rec_id}")
async def get_reconciliation(rec_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BankReconciliation).where(BankReconciliation.id == rec_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "Reconciliation not found")

    txn_result = await db.execute(
        select(BankTransaction).where(BankTransaction.reconciliation_id == rec_id)
    )
    transactions = txn_result.scalars().all()
    matched = sum(1 for t in transactions if t.is_matched)

    return {
        "id": rec.id,
        "client_id": rec.client_id,
        "period_start": rec.period_start,
        "period_end": rec.period_end,
        "bank_account": rec.bank_account,
        "statement_balance": float(rec.statement_balance),
        "closing_balance": float(rec.closing_balance),
        "status": rec.status,
        "summary": {
            "total": len(transactions),
            "matched": matched,
            "unmatched": len(transactions) - matched,
        },
        "transactions": [
            {
                "id": t.id,
                "date": t.transaction_date.isoformat(),
                "description": t.description,
                "amount": float(t.amount),
                "is_matched": t.is_matched,
                "tally_ref": t.tally_ref,
            }
            for t in transactions
        ],
    }


@router.patch("/{rec_id}")
async def patch_reconciliation(
    rec_id: str,
    payload: ReconciliationPatch,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(BankReconciliation).where(BankReconciliation.id == rec_id))
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "Reconciliation not found")
    if payload.status:
        rec.status = payload.status
    if payload.statement_balance is not None:
        rec.statement_balance = Decimal(str(payload.statement_balance))
    if payload.closing_balance is not None:
        rec.closing_balance = Decimal(str(payload.closing_balance))
    if payload.notes is not None:
        rec.notes = payload.notes
    await db.commit()
    return {"success": True}


@router.delete("/{rec_id}")
async def delete_reconciliation(rec_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BankReconciliation).where(BankReconciliation.id == rec_id))
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "Reconciliation not found")
    await db.delete(rec)
    await db.commit()
    return {"success": True}


@router.post("/{rec_id}/match")
async def manual_match(rec_id: str, payload: MatchPayload, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BankTransaction).where(
            BankTransaction.reconciliation_id == rec_id,
            BankTransaction.id == payload.transaction_id,
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    txn.is_matched = True
    txn.tally_ref = payload.tally_ref
    await db.commit()
    return {"success": True, "transaction_id": txn.id, "tally_ref": txn.tally_ref}


@router.post("/{rec_id}/unmatch")
async def manual_unmatch(
    rec_id: str,
    transaction_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BankTransaction).where(
            BankTransaction.reconciliation_id == rec_id,
            BankTransaction.id == transaction_id,
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    txn.is_matched = False
    txn.tally_ref = None
    await db.commit()
    return {"success": True, "transaction_id": txn.id}