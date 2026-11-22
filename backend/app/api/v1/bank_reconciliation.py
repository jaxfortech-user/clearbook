"""
Bank reconciliation: upload bank statement → AI parse → auto-match vouchers → auto-create drafts.
"""
import csv, io, os, uuid, tempfile
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
from app.models.voucher import Voucher
from app.services.ai_extraction_service import extract_bank_statement

router = APIRouter()

_MATCH_TOLERANCE_DAYS = 7   # match window for date similarity
_MATCH_AMOUNT_DIFF    = 0.01  # tolerance for amount match


# ── Serialiser ────────────────────────────────────────────────────────────────

def _txn_out(t: BankTransaction) -> dict:
    debit  = float(getattr(t, "debit",  None) or 0)
    credit = float(getattr(t, "credit", None) or 0)
    # Fallback for rows inserted before the new columns existed
    if debit == 0 and credit == 0:
        amt = float(t.amount or 0)
        if amt >= 0:
            credit = amt
        else:
            debit = abs(amt)
    return {
        "id": t.id,
        "date": t.transaction_date.isoformat() if t.transaction_date else "",
        "description": t.description or "",
        "debit":   round(debit,  2),
        "credit":  round(credit, 2),
        "balance": float(getattr(t, "balance", None) or 0),
        "matched": bool(t.is_matched),
        "tally_ref": t.tally_ref,
        "suggested": getattr(t, "suggested_voucher_ref", None),
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

    # Resolve client name
    client_name = ""
    try:
        cr = await db.execute(select(Client).where(Client.id == rec.client_id))
        c = cr.scalar_one_or_none()
        if c:
            client_name = c.name
    except Exception:
        pass

    return {
        "id": rec.id,
        "client_id": rec.client_id,
        "client_name": client_name,
        "bank_name": getattr(rec, "bank_name", None) or "",
        "filename": getattr(rec, "filename", None) or rec.bank_account or "",
        "uploaded_at": rec.created_at.isoformat() if rec.created_at else "",
        "status": rec.status,
        "transactions": out_txns,
        "summary": {
            "total": len(out_txns),
            "matched": matched,
            "unmatched": len(out_txns) - matched,
            "total_credits": round(total_credits, 2),
            "total_debits": round(total_debits, 2),
            "opening_balance": float(getattr(rec, "opening_balance", None) or 0),
            "closing_balance": float(rec.statement_balance or 0),
        },
    }


# ── Auto-match helpers ─────────────────────────────────────────────────────────

async def _auto_match_and_suggest(
    txns: list[BankTransaction],
    client_id: str,
    tenant_id: str,
    db: AsyncSession,
):
    """
    For each transaction, look for an existing voucher with matching amount+date.
    Set suggested_voucher_id/ref.  For strong matches also set is_matched=True.
    """
    # Fetch all vouchers for this client
    result = await db.execute(
        select(Voucher).where(
            Voucher.client_id == client_id,
            Voucher.tenant_id == tenant_id,
        )
    )
    vouchers = result.scalars().all()

    for txn in txns:
        txn_amount = float(txn.debit or 0) if float(txn.debit or 0) > 0 else float(txn.credit or 0)
        for v in vouchers:
            v_amount = abs(float(v.amount or 0))
            if v_amount == 0:
                continue
            if abs(v_amount - txn_amount) > _MATCH_AMOUNT_DIFF * max(v_amount, txn_amount) + 1:
                continue
            # Amount roughly matches — check date window
            if v.voucher_date and txn.transaction_date:
                delta = abs((v.voucher_date - txn.transaction_date).days)
                if delta <= _MATCH_TOLERANCE_DAYS:
                    txn.suggested_voucher_id  = str(v.id)
                    txn.suggested_voucher_ref = str(v.voucher_number or v.id)
                    # Exact amount + close date → auto-match
                    if abs(v_amount - txn_amount) < _MATCH_AMOUNT_DIFF and delta <= 2:
                        txn.is_matched = True
                        txn.tally_ref  = str(v.voucher_number or v.id)
                    break


async def _auto_create_vouchers(
    txns: list[BankTransaction],
    client_id: str,
    tenant_id: str,
    db: AsyncSession,
):
    """
    For unmatched transactions that have no suggestion, auto-create draft
    Receipt (credit) or Payment (debit) vouchers so the accountant can review.
    """
    created = 0
    for txn in txns:
        if txn.is_matched or txn.suggested_voucher_id:
            continue  # already handled

        debit  = float(txn.debit  or 0)
        credit = float(txn.credit or 0)
        if debit == 0 and credit == 0:
            continue

        voucher_type = "Receipt" if credit > 0 else "Payment"
        amount       = credit if credit > 0 else debit

        # Build a minimal ledger entry suggestion
        bank_ledger = "Bank Account"
        counterpart = "Sundry Debtors" if credit > 0 else "Sundry Creditors"
        entries = [
            {"ledger": bank_ledger,  "amount": amount, "type": "Dr" if credit > 0 else "Cr"},
            {"ledger": counterpart,  "amount": amount, "type": "Cr" if credit > 0 else "Dr"},
        ]

        new_voucher = Voucher(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            client_id=client_id,
            voucher_type=voucher_type,
            voucher_date=txn.transaction_date,
            narration=txn.description or "",
            amount=Decimal(str(amount)),
            status="draft",
            currency="AED",
            ledger_entries=entries,
        )
        db.add(new_voucher)
        txn.suggested_voucher_id  = new_voucher.id
        txn.suggested_voucher_ref = f"{voucher_type}/{txn.transaction_date}"
        created += 1

    return created


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
        raise HTTPException(400, "Only CSV, XLSX, XLS or PDF files are accepted")

    content = await file.read()

    # Save to temp file for AI extraction
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        ai_result = extract_bank_statement(tmp_path)
    except Exception as e:
        ai_result = {"transactions": [], "error": str(e)}
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    raw_transactions = ai_result.get("transactions") or []
    bank_name        = ai_result.get("bank_name")
    opening_balance  = ai_result.get("opening_balance")
    closing_balance  = ai_result.get("closing_balance")

    if not raw_transactions:
        raise HTTPException(
            400,
            f"No transactions found in uploaded file. AI message: {ai_result.get('error', 'Unknown error')}"
        )

    # Determine period from parsed rows
    dates = []
    for r in raw_transactions:
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            dates.append(d)
        except Exception:
            pass

    period_start = min(dates) if dates else date.today().replace(day=1)
    period_end   = max(dates) if dates else date.today()

    rec = BankReconciliation(
        id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        client_id=client_id,
        period_start=period_start,
        period_end=period_end,
        bank_account=ai_result.get("account_number") or file.filename or "Uploaded Statement",
        bank_name=bank_name,
        filename=file.filename,
        opening_balance=Decimal(str(opening_balance)) if opening_balance is not None else None,
        statement_balance=Decimal(str(closing_balance)) if closing_balance is not None else Decimal("0"),
        status="in_progress",
    )
    db.add(rec)
    await db.flush()

    txn_objects = []
    for r in raw_transactions:
        try:
            txn_date = datetime.strptime(r["date"], "%Y-%m-%d").date()
        except Exception:
            continue

        debit  = Decimal(str(r.get("debit")  or 0))
        credit = Decimal(str(r.get("credit") or 0))
        amount = credit - debit
        balance_val = r.get("balance")

        txn = BankTransaction(
            id=str(uuid.uuid4()),
            reconciliation_id=rec.id,
            tenant_id=current_user.tenant_id,
            transaction_date=txn_date,
            description=str(r.get("description") or ""),
            amount=amount,
            debit=debit,
            credit=credit,
            balance=Decimal(str(balance_val)) if balance_val is not None else None,
            reference=str(r.get("reference") or "") or None,
            is_matched=False,
        )
        db.add(txn)
        txn_objects.append(txn)

    await db.flush()

    # Auto-match against existing vouchers
    await _auto_match_and_suggest(txn_objects, client_id, current_user.tenant_id, db)

    # Auto-create draft vouchers for truly unmatched transactions
    await _auto_create_vouchers(txn_objects, client_id, current_user.tenant_id, db)

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
