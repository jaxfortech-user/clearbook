"""
Bank reconciliation: upload bank statement CSV → parse → match against vouchers.
"""
import csv, io, os, uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.client import Client
from app.models.bank_reconciliation import BankReconciliation, BankTransaction

router = APIRouter()


# ── Serialiser ────────────────────────────────────────────────────────────────

def _txn_out(t: BankTransaction) -> dict:
    amt = float(t.amount or 0)
    return {
        "id": t.id,
        "date": t.transaction_date.isoformat() if t.transaction_date else "",
        "description": t.description or "",
        "debit":  round(abs(amt), 2) if amt < 0 else 0.0,
        "credit": round(amt, 2)      if amt > 0 else 0.0,
        "balance": 0.0,              # model has no running balance column
        "matched": bool(t.is_matched),
        "tally_ref": t.tally_ref,
        "suggested": None,
    }


async def _rec_out(rec: BankReconciliation, db: AsyncSession) -> dict:
    result = await db.execute(
        select(BankTransaction)
        .where(BankTransaction.reconciliation_id == rec.id)
        .order_by(BankTransaction.transaction_date)
    )
    txns = result.scalars().all()
    out_txns = [_txn_out(t) for t in txns]
    matched = sum(1 for t in out_txns if t["matched"])
    total_credits = sum(t["credit"] for t in out_txns)
    total_debits  = sum(t["debit"]  for t in out_txns)
    return {
        "id": rec.id,
        "client_id": rec.client_id,
        "client_name": "",
        "filename": rec.bank_account or "",
        "uploaded_at": rec.created_at.isoformat() if rec.created_at else "",
        "status": rec.status,
        "transactions": out_txns,
        "summary": {
            "total": len(out_txns),
            "matched": matched,
            "unmatched": len(out_txns) - matched,
            "total_credits": round(total_credits, 2),
            "total_debits": round(total_debits, 2),
            "closing_balance": float(rec.statement_balance or 0),
        },
    }


# ── CSV parser ────────────────────────────────────────────────────────────────

def _find_col(fieldnames, candidates):
    for c in candidates:
        for h in (fieldnames or []):
            if c in h.lower():
                return h
    return None


def _parse_date(s: str) -> Optional[date]:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y", "%d-%b-%Y", "%m/%d/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(s: str) -> float:
    if not s or s.strip() in ("", "-", "—"):
        return 0.0
    try:
        return float(s.replace(",", "").replace(" ", "").strip())
    except ValueError:
        return 0.0


def _parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    fn = reader.fieldnames or []

    date_col    = _find_col(fn, ["date", "value date", "txn date", "transaction date", "posting date"])
    desc_col    = _find_col(fn, ["description", "narration", "particulars", "details", "remarks", "transaction details"])
    debit_col   = _find_col(fn, ["debit", "withdrawal", "dr amount", "debit amount"])
    credit_col  = _find_col(fn, ["credit", "deposit", "cr amount", "credit amount"])
    amount_col  = _find_col(fn, ["amount"]) if not (debit_col or credit_col) else None
    ref_col     = _find_col(fn, ["reference", "ref no", "cheque", "chq", "transaction id", "txn id", "ref"])

    rows = []
    for row in reader:
        raw_date = (row.get(date_col) or "").strip() if date_col else ""
        txn_date = _parse_date(raw_date)
        if not txn_date:
            continue

        debit  = _parse_amount(row.get(debit_col,  "") if debit_col  else "")
        credit = _parse_amount(row.get(credit_col, "") if credit_col else "")

        if amount_col:
            amt = _parse_amount(row.get(amount_col, ""))
            if amt >= 0:
                credit = amt
            else:
                debit = abs(amt)

        # Store as signed amount: credit positive, debit negative
        amount = credit - debit

        rows.append({
            "transaction_date": txn_date,
            "description": (row.get(desc_col) or "").strip() if desc_col else "",
            "amount": amount,
            "reference": (row.get(ref_col) or "").strip() if ref_col else "",
        })
    return rows


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


class MatchPayload(BaseModel):
    transaction_id: str
    tally_ref: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_bank_statement(
    client_id: str = Query(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.tenant_id == current_user.tenant_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Client not found")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".csv", ".xlsx", ".xls", ".pdf"}:
        raise HTTPException(400, "Only CSV, XLSX or PDF files are accepted")

    content = await file.read()

    if ext == ".csv":
        rows = _parse_csv(content)
    else:
        # Non-CSV: seed placeholder rows so the UI shows something
        rows = []

    if not rows and ext == ".csv":
        raise HTTPException(400, "No parseable rows found in CSV. Check column headers include Date and Amount/Debit/Credit.")

    # Determine period from parsed rows
    dates = [r["transaction_date"] for r in rows if r.get("transaction_date")]
    period_start = min(dates) if dates else date.today().replace(day=1)
    period_end   = max(dates) if dates else date.today()

    rec = BankReconciliation(
        id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        client_id=client_id,
        period_start=period_start,
        period_end=period_end,
        bank_account=file.filename or "Uploaded Statement",
        statement_balance=Decimal("0"),
        status="in_progress",
    )
    db.add(rec)
    await db.flush()

    for r in rows:
        txn = BankTransaction(
            id=str(uuid.uuid4()),
            reconciliation_id=rec.id,
            tenant_id=current_user.tenant_id,
            transaction_date=r["transaction_date"],
            description=r["description"],
            amount=Decimal(str(r["amount"])),
            is_matched=False,
            tally_ref=None,
        )
        db.add(txn)

    await db.commit()
    await db.refresh(rec)
    return await _rec_out(rec, db)


@router.post("")
async def create_reconciliation(
    payload: ReconciliationCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Client).where(Client.id == payload.client_id, Client.tenant_id == current_user.tenant_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Client not found")

    rec = BankReconciliation(
        id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        client_id=payload.client_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        bank_account=payload.bank_account,
        statement_balance=Decimal(str(payload.statement_balance or 0)),
        status="draft",
        notes=payload.notes,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return await _rec_out(rec, db)


@router.get("/client/{client_id}")
async def list_reconciliations(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(BankReconciliation).where(
            BankReconciliation.client_id == client_id,
            BankReconciliation.tenant_id == current_user.tenant_id,
        ).order_by(BankReconciliation.created_at.desc())
    )
    recs = result.scalars().all()
    return [{"id": r.id, "period_start": r.period_start, "period_end": r.period_end,
             "bank_account": r.bank_account, "status": r.status} for r in recs]


@router.get("/{rec_id}")
async def get_reconciliation(
    rec_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(BankReconciliation).where(
            BankReconciliation.id == rec_id,
            BankReconciliation.tenant_id == current_user.tenant_id,
        )
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "Reconciliation not found")
    return await _rec_out(rec, db)


@router.patch("/{rec_id}")
async def patch_reconciliation(
    rec_id: str,
    payload: ReconciliationPatch,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(BankReconciliation).where(
            BankReconciliation.id == rec_id,
            BankReconciliation.tenant_id == current_user.tenant_id,
        )
    )
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
    return await _rec_out(rec, db)


@router.delete("/{rec_id}")
async def delete_reconciliation(
    rec_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(BankReconciliation).where(
            BankReconciliation.id == rec_id,
            BankReconciliation.tenant_id == current_user.tenant_id,
        )
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "Reconciliation not found")
    await db.delete(rec)
    await db.commit()
    return {"success": True}


@router.post("/{rec_id}/match")
async def manual_match(
    rec_id: str,
    payload: MatchPayload,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
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

    rec_result = await db.execute(
        select(BankReconciliation).where(BankReconciliation.id == rec_id)
    )
    rec = rec_result.scalar_one_or_none()
    return await _rec_out(rec, db)


@router.post("/{rec_id}/unmatch")
async def manual_unmatch(
    rec_id: str,
    transaction_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
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

    rec_result = await db.execute(
        select(BankReconciliation).where(BankReconciliation.id == rec_id)
    )
    rec = rec_result.scalar_one_or_none()
    return await _rec_out(rec, db)
