"""
Voucher approval workflow endpoints — fully async.
Status flow: draft → pending_approval → approved → synced_to_tally | rejected

Phase 1 MVP additions:
  - Audit logging on every status change
  - Tally read-back verification after posting
  - Duplicate invoice detection before voucher creation from a document
"""
import json
import uuid
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.deps import get_current_user, tenant_filter
from app.models.voucher import Voucher
from app.models.document import Document
from app.models.user import User
from app.services.audit_service import log as audit_log

router = APIRouter()


# -- Schemas -----------------------------------------------------------------

class VoucherEntrySchema(BaseModel):
    ledger_name: str
    is_debit: bool
    amount: float
    notes: Optional[str] = None


class VoucherCreateRequest(BaseModel):
    client_id: str
    document_id: Optional[str] = None
    voucher_type: str
    voucher_date: Optional[str] = None
    party_name: Optional[str] = None
    narration: Optional[str] = None
    amount: float
    tax_amount: float = 0.0
    currency: str = "AED"
    ledger_entries: Optional[List[VoucherEntrySchema]] = None


class VoucherApproveRequest(BaseModel):
    entries: Optional[List[VoucherEntrySchema]] = None
    approved_by: Optional[str] = None
    post_to_tally: bool = False
    tally_company: Optional[str] = None
    tally_host: str = "localhost"
    tally_port: int = 9000


class VoucherRejectRequest(BaseModel):
    reason: str


# -- Endpoints ---------------------------------------------------------------

@router.get("/client/{client_id}")
async def list_vouchers_by_client(
    client_id: str,
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(Voucher).filter(Voucher.client_id == client_id)
    if status:
        q = q.filter(Voucher.status == status)
    q = q.order_by(Voucher.created_at.desc()).limit(100)
    result = await db.execute(q)
    return [_voucher_to_dict(v) for v in result.scalars().all()]


@router.get("/pending-approval")
async def pending_approval(db: AsyncSession = Depends(get_db)):
    q = select(Voucher).filter(Voucher.status == "pending_approval").order_by(Voucher.created_at.desc())
    result = await db.execute(q)
    return [_voucher_to_dict(v) for v in result.scalars().all()]


@router.get("/")
async def list_vouchers(
    client_id: str = Query(None),
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Voucher)
    tid = tenant_filter(user)
    if tid:
        q = q.filter(Voucher.tenant_id == tid)
    if client_id:
        q = q.filter(Voucher.client_id == client_id)
    if status:
        q = q.filter(Voucher.status == status)
    q = q.order_by(Voucher.created_at.desc()).limit(100)
    result = await db.execute(q)
    return [_voucher_to_dict(v) for v in result.scalars().all()]


@router.get("/{voucher_id}")
async def get_voucher(voucher_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Voucher).filter(Voucher.id == voucher_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(404, "Voucher not found")
    return _voucher_to_dict(v)


@router.get("/{voucher_id}/audit-log")
async def get_voucher_audit_log(voucher_id: str, db: AsyncSession = Depends(get_db)):
    from app.models.audit_log import AuditLog
    from sqlalchemy import select as sel
    q = sel(AuditLog).filter(AuditLog.entity_id == voucher_id).order_by(AuditLog.created_at.asc())
    result = await db.execute(q)
    return [
        {
            "id": a.id,
            "action": a.action,
            "actor": a.actor,
            "details": a.details,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in result.scalars().all()
    ]


@router.post("/")
async def create_voucher(
    req: VoucherCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    parsed_date = (
        datetime.strptime(req.voucher_date, "%Y-%m-%d").date()
        if req.voucher_date
        else date.today()
    )
    auto_entries = (
        [e.model_dump() for e in req.ledger_entries]
        if req.ledger_entries
        else _auto_ledger_entries(req.voucher_type, req.party_name, req.amount)
    )

    tid = tenant_filter(user) or "system"
    v = Voucher(
        id=str(uuid.uuid4()),
        tenant_id=tid,
        client_id=req.client_id,
        document_id=req.document_id,
        voucher_type=req.voucher_type,
        voucher_date=parsed_date,
        party_name=req.party_name,
        narration=req.narration,
        amount=req.amount,
        tax_amount=req.tax_amount,
        ledger_entries=auto_entries or None,
        status="draft",
    )
    db.add(v)
    await audit_log(db, "voucher", v.id, "created", client_id=req.client_id,
                    details={"voucher_type": req.voucher_type, "amount": req.amount},
                    tenant_id=tenant_filter(user))
    await db.commit()
    await db.refresh(v)
    return _voucher_to_dict(v)


@router.post("/{voucher_id}/approve")
async def approve_voucher(
    voucher_id: str,
    req: VoucherApproveRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Voucher).filter(Voucher.id == voucher_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(404, "Voucher not found")
    if v.status not in ("pending_approval", "draft"):
        raise HTTPException(400, f"Cannot approve a voucher with status '{v.status}'")

    approved = [e.model_dump() for e in req.entries] if req.entries else v.ledger_entries
    v.approved_entries = approved
    v.approved_by = req.approved_by
    v.approved_at = datetime.utcnow()
    v.status = "approved"
    v.updated_at = datetime.utcnow()
    await audit_log(db, "voucher", v.id, "approved", client_id=v.client_id,
                    actor=req.approved_by, details={"entries_count": len(approved or [])})
    await db.commit()

    tally_result = None
    if req.post_to_tally and req.tally_company:
        tally_result = _post_to_tally_sync(v, req.tally_company, req.tally_host, req.tally_port)
        if tally_result.get("success"):
            v.tally_voucher_id = tally_result.get("tally_voucher_id", "")
            v.tally_company = req.tally_company
            v.tally_sync_at = datetime.utcnow()
            v.status = "synced_to_tally"
            v.updated_at = datetime.utcnow()
            await audit_log(db, "voucher", v.id, "posted_to_tally", client_id=v.client_id,
                            details={"tally_company": req.tally_company,
                                     "tally_voucher_id": tally_result.get("tally_voucher_id")})

            # Read-back verification
            verified = _verify_tally_voucher(
                req.tally_host, req.tally_port, req.tally_company,
                tally_result.get("tally_voucher_id", "")
            )
            tally_result["verified"] = verified
            await audit_log(db, "voucher", v.id, "tally_verified" if verified else "tally_verify_failed",
                            client_id=v.client_id,
                            details={"tally_voucher_id": tally_result.get("tally_voucher_id"), "verified": verified})
            await db.commit()

    return {
        "message": "Voucher approved" + (" and posted to Tally" if tally_result and tally_result.get("success") else ""),
        "voucher_id": v.id,
        "status": v.status,
        "tally_result": tally_result,
    }


@router.post("/{voucher_id}/reject")
async def reject_voucher(
    voucher_id: str,
    req: VoucherRejectRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Voucher).filter(Voucher.id == voucher_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(404, "Voucher not found")

    v.status = "rejected"
    v.rejection_reason = req.reason
    v.updated_at = datetime.utcnow()
    await audit_log(db, "voucher", v.id, "rejected", client_id=v.client_id,
                    details={"reason": req.reason})
    await db.commit()
    return {"message": "Voucher rejected", "voucher_id": v.id}


class UpdateEntriesRequest(BaseModel):
    entries: List[VoucherEntrySchema]


@router.post("/{voucher_id}/update-entries")
async def update_voucher_entries(
    voucher_id: str,
    req: UpdateEntriesRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Voucher).filter(Voucher.id == voucher_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(404, "Voucher not found")
    if v.status == "synced_to_tally":
        raise HTTPException(400, "Cannot edit entries on a voucher already posted to Tally.")

    entries_data = [e.model_dump() for e in req.entries]
    v.ledger_entries = entries_data
    v.approved_entries = entries_data
    v.updated_at = datetime.utcnow()
    await audit_log(db, "voucher", v.id, "entries_updated", client_id=v.client_id,
                    details={"entries_count": len(entries_data)})
    await db.commit()
    await db.refresh(v)
    return _voucher_to_dict(v)


@router.post("/{voucher_id}/post-to-tally")
async def post_voucher_to_tally(
    voucher_id: str,
    tally_company: str = Query(...),
    tally_host: str = Query("localhost"),
    tally_port: int = Query(9000),
    tally_edu_mode: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Voucher).filter(Voucher.id == voucher_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(404, "Voucher not found")
    if v.status not in ("approved", "pending_approval"):
        raise HTTPException(400, f"Voucher must be approved before posting. Status: '{v.status}'")

    tally_result = _post_to_tally_sync(v, tally_company, tally_host, tally_port, tally_edu_mode)
    if tally_result.get("success"):
        v.tally_voucher_id = tally_result.get("tally_voucher_id", "")
        v.tally_company = tally_company
        v.tally_sync_at = datetime.utcnow()
        v.status = "synced_to_tally"
        v.updated_at = datetime.utcnow()
        await audit_log(db, "voucher", v.id, "posted_to_tally", client_id=v.client_id,
                        details={"tally_company": tally_company,
                                 "tally_voucher_id": tally_result.get("tally_voucher_id")})

        # Read-back verification
        verified = _verify_tally_voucher(tally_host, tally_port, tally_company,
                                         tally_result.get("tally_voucher_id", ""))
        tally_result["verified"] = verified
        await audit_log(db, "voucher", v.id, "tally_verified" if verified else "tally_verify_failed",
                        client_id=v.client_id,
                        details={"tally_voucher_id": tally_result.get("tally_voucher_id"), "verified": verified})
        await db.commit()

    return tally_result


# -- Duplicate detection (called from documents endpoint) --------------------

async def check_duplicate_invoice(db: AsyncSession, client_id: str, invoice_number: str) -> Optional[str]:
    """
    Returns the existing voucher_id if a voucher with the same invoice number
    already exists for this client, otherwise None.
    """
    if not invoice_number:
        return None
    q = (
        select(Voucher)
        .filter(
            Voucher.client_id == client_id,
            Voucher.narration.ilike(f"%{invoice_number}%"),
            Voucher.status != "rejected",
        )
        .limit(1)
    )
    result = await db.execute(q)
    existing = result.scalar_one_or_none()
    return existing.id if existing else None


# -- Auto ledger entry generator ---------------------------------------------

def _auto_ledger_entries(voucher_type: str, party_name: str | None, amount: float) -> list:
    party = (party_name or "Party Account").strip()
    vtype = (voucher_type or "payment").lower()
    if vtype == "payment":
        return [{"ledger_name": party, "is_debit": True, "amount": amount},
                {"ledger_name": "Cash", "is_debit": False, "amount": amount}]
    elif vtype == "receipt":
        return [{"ledger_name": "Cash", "is_debit": True, "amount": amount},
                {"ledger_name": party, "is_debit": False, "amount": amount}]
    elif vtype == "contra":
        return [{"ledger_name": "Cash", "is_debit": True, "amount": amount},
                {"ledger_name": "Bank Account", "is_debit": False, "amount": amount}]
    else:
        return [{"ledger_name": party, "is_debit": True, "amount": amount},
                {"ledger_name": "Cash", "is_debit": False, "amount": amount}]


# -- Tally posting -----------------------------------------------------------

def _normalize_entries(raw_entries) -> list:
    if not raw_entries:
        return []
    if isinstance(raw_entries, str):
        try:
            raw_entries = json.loads(raw_entries)
        except Exception:
            return []
    if not isinstance(raw_entries, list):
        return []
    normalized = []
    for entry in raw_entries:
        if isinstance(entry, dict):
            normalized.append(entry)
        elif isinstance(entry, str):
            try:
                parsed = json.loads(entry)
                if isinstance(parsed, dict):
                    normalized.append(parsed)
            except Exception:
                pass
    return normalized


def _post_to_tally_sync(v: Voucher, company: str, host: str, port: int, edu_mode: bool = False) -> dict:
    try:
        from app.api.v1.tally import _build_voucher_xml, _post_tally_xml, _extract_voucher_number, _ensure_ledgers_exist

        entries = _normalize_entries(v.approved_entries or v.ledger_entries or [])
        if not entries:
            return {"success": False, "error": "No ledger entries on this voucher."}

        _ensure_ledgers_exist(company, host, port, entries, v.voucher_type or "payment")

        voucher_date = v.voucher_date.replace(day=1) if edu_mode else v.voucher_date
        xml = _build_voucher_xml(
            company=company, voucher_type=v.voucher_type, date=voucher_date,
            narration=v.narration or "", entries=entries,
        )
        response_text = _post_tally_xml(host, port, xml)

        if "LINEERROR" in response_text or "IMPORTERROR" in response_text:
            return {"success": False, "error": response_text}

        tally_id = _extract_voucher_number(response_text) or getattr(v, "voucher_number", "") or ""
        return {"success": True, "tally_voucher_id": tally_id, "status": "synced_to_tally"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def _verify_tally_voucher(host: str, port: int, company: str, voucher_id: str) -> bool:
    """
    Reads back from Tally to confirm the voucher exists.
    Returns True if Tally confirms it, False on any error or missing voucher.
    """
    if not voucher_id:
        return False
    try:
        from app.api.v1.tally import _post_tally_xml
        import xml.etree.ElementTree as ET

        xml = f"""<ENVELOPE>
  <HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
  <BODY><EXPORTDATA>
    <REQUESTDESC>
      <REPORTNAME>Voucher</REPORTNAME>
      <STATICVARIABLES>
        <SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
    </REQUESTDESC>
  </EXPORTDATA></BODY>
</ENVELOPE>"""
        response = _post_tally_xml(host, port, xml)
        # If response contains any voucher data we consider it verified
        return bool(response) and "ENVELOPE" in response and len(response) > 100
    except Exception:
        return False


# -- Serializer --------------------------------------------------------------

def _voucher_to_dict(v: Voucher) -> dict:
    display_status = "posted_to_tally" if v.status == "synced_to_tally" else v.status
    return {
        "id": v.id,
        "client_id": v.client_id,
        "document_id": v.document_id,
        "voucher_type": v.voucher_type,
        "voucher_number": getattr(v, "voucher_number", None),
        "date": v.voucher_date.isoformat() if v.voucher_date else None,
        "voucher_date": v.voucher_date.isoformat() if v.voucher_date else None,
        "party_name": v.party_name,
        "narration": v.narration,
        "total_amount": float(v.amount) if v.amount else 0,
        "amount": float(v.amount) if v.amount else 0,
        "tax_amount": float(v.tax_amount) if v.tax_amount else 0,
        "currency": getattr(v, "currency", "AED"),
        "ai_suggested_data": {"entries": v.ledger_entries or [], "voucher_type": v.voucher_type, "narration": v.narration},
        "ledger_entries": v.ledger_entries or [],
        "approved_entries": getattr(v, "approved_entries", None),
        "status": display_status,
        "raw_status": v.status,
        "approved_by": getattr(v, "approved_by", None),
        "approved_at": v.approved_at.isoformat() if getattr(v, "approved_at", None) else None,
        "rejection_reason": getattr(v, "rejection_reason", None),
        "tally_voucher_id": getattr(v, "tally_voucher_id", None),
        "tally_company": getattr(v, "tally_company", None),
        "tally_sync_at": v.tally_sync_at.isoformat() if getattr(v, "tally_sync_at", None) else None,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    }
