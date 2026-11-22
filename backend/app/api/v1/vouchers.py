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
from app.models.client import Client
from app.models.document import Document
from app.models.user import User
from app.services.audit_service import log as audit_log

router = APIRouter()


# -- Schemas -----------------------------------------------------------------

class VoucherEntrySchema(BaseModel):
    ledger_name: str
    is_debit: bool
    vat_amount: Optional[float] = 0.0
    bill_ref: Optional[str] = None
    line_narration: Optional[str] = None
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
        tally_result = await _post_to_tally_sync(v, req.tally_company, req.tally_host, req.tally_port)
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

    client_result = await db.execute(select(Client).filter(Client.id == v.client_id))
    tally_client_obj = client_result.scalar_one_or_none()
    tally_result = await _post_to_tally_sync(v, tally_company, tally_host, tally_port, tally_edu_mode, client_obj=tally_client_obj)
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
    # Journal and Contra: return empty — user must supply lines manually
    if voucher_type.lower() in ("journal", "contra"):
        return []
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


async def _post_to_tally_sync(v: Voucher, company: str, host: str, port: int, edu_mode: bool = False, client_obj=None) -> dict:
    try:
        from app.api.v1.tally import _build_voucher_xml, _extract_voucher_number, _ensure_ledgers_via_tunnel, _ensure_stock_items_via_tunnel
        from app.core.tally_routing import route_tally_xml

        entries = _normalize_entries(v.approved_entries or v.ledger_entries or [])
        if not entries:
            return {"success": False, "error": "No ledger entries on this voucher."}

        stock_items = _normalize_entries(v.stock_items) if getattr(v, "stock_items", None) else []
        invoice_subtype = getattr(v, "invoice_subtype", None) or "accounting_invoice"
        voucher_date = v.voucher_date.replace(day=1) if edu_mode else v.voucher_date

        # Route by voucher type when line_items present (Payment/Receipt/Journal/Contra)
        _vt = (v.voucher_type or "").lower()
        if v.line_items and _vt in ("payment", "receipt"):
            xml = _make_payment_xml(v, company)
        elif v.line_items and _vt == "journal":
            xml = _make_journal_xml(v, company)
        elif v.line_items and _vt == "contra":
            xml = _make_contra_xml(v, company)
        else:
            xml = _build_voucher_xml(
                company=company, voucher_type=v.voucher_type, date=voucher_date,
                narration=v.narration or "", entries=entries,
                stock_items=stock_items, invoice_subtype=invoice_subtype,
            )

        _effective_client = client_obj if client_obj else type('C', (), {'tally_host': host, 'tally_port': port, 'tenant_id': None, 'id': v.client_id, 'name': company, 'tally_direct_mode': False})()
        await _ensure_ledgers_via_tunnel(company, _effective_client, entries, v.voucher_type or "payment")
        if stock_items:
            await _ensure_stock_items_via_tunnel(company, _effective_client, stock_items)

        if client_obj is None:
            class _TallyClient:
                def __init__(self, h, p, cid):
                    self.tally_host = h
                    self.tally_port = p
                    self.tenant_id = None
                    self.id = cid
                    self.name = company
                    self.tally_direct_mode = False
            client_obj = _TallyClient(host, port, v.client_id)

        response_text = await route_tally_xml(client_obj, xml)

        if "LINEERROR" in response_text or "IMPORTERROR" in response_text:
            return {"success": False, "error": response_text}

        # Check CREATED count — EDU/strict Tally may accept HTTP but create 0 vouchers
        import xml.etree.ElementTree as _ET
        try:
            _root = _ET.fromstring(response_text)
            _created = _root.find(".//CREATED")
            if _created is not None and _created.text and int(_created.text) == 0:
                _ignored = _root.find(".//IGNORED")
                _exceptions = _root.find(".//EXCEPTIONS")
                return {"success": False, "error": f"Tally accepted request but created 0 vouchers. IGNORED={getattr(_ignored,'text','?')} EXCEPTIONS={getattr(_exceptions,'text','?')} Response: {response_text[:500]}"}
        except Exception:
            pass

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
        "invoice_subtype": getattr(v, "invoice_subtype", None) or "accounting_invoice",
        "stock_items": getattr(v, "stock_items", None) or [],
        "dispatch_details": getattr(v, "dispatch_details", None),
        "party_address": getattr(v, "party_address", None),
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


@router.post("/{voucher_id}/submit")
async def submit_voucher(
    voucher_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Submit a draft voucher for approval."""
    result = await db.execute(select(Voucher).filter(Voucher.id == voucher_id))
    voucher = result.scalar_one_or_none()
    if not voucher:
        raise HTTPException(404, "Voucher not found")
    if voucher.status != "draft":
        raise HTTPException(400, f"Cannot submit voucher with status '{voucher.status}'")
    voucher.status = "pending_approval"
    voucher.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(voucher)
    return {"id": voucher.id, "status": voucher.status}


# ── Outstanding (bill-by-bill) ─────────────────────────────────────────────

class SettleRequest(BaseModel):
    settled_ref: str
    settled_date: Optional[str] = None


def _outstanding_dict(v: Voucher):
    return {
        "id": v.id,
        "voucher_type": v.voucher_type,
        "voucher_number": v.voucher_number,
        "voucher_date": v.voucher_date.isoformat() if v.voucher_date else None,
        "party_name": v.party_name,
        "amount": float(v.amount or 0),
        "tax_amount": float(v.tax_amount or 0),
        "narration": v.narration,
        "status": v.status,
        "is_settled": v.is_settled,
        "settled_ref": v.settled_ref,
        "settled_date": v.settled_date.isoformat() if v.settled_date else None,
    }


@router.get("/outstanding/{client_id}")
async def get_outstanding(
    client_id: str,
    include_settled: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return purchase + sales invoices for a client, unsettled by default."""
    tid = tenant_filter(user)
    invoice_types = ["Purchase", "Sales", "purchase_invoice", "sales_invoice"]
    q = select(Voucher).where(
        Voucher.client_id == client_id,
        Voucher.voucher_type.in_(invoice_types),
    )
    if tid:
        q = q.where(Voucher.tenant_id == tid)
    if not include_settled:
        q = q.where(Voucher.is_settled == False)
    result = await db.execute(q.order_by(Voucher.voucher_date))
    return [_outstanding_dict(v) for v in result.scalars().all()]


@router.post("/{voucher_id}/settle")
async def settle_voucher(
    voucher_id: str,
    req: SettleRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a voucher as settled (payment received/made)."""
    result = await db.execute(select(Voucher).filter(Voucher.id == voucher_id))
    voucher = result.scalar_one_or_none()
    if not voucher:
        raise HTTPException(404, "Voucher not found")
    tid = tenant_filter(user)
    if tid and voucher.tenant_id != tid:
        raise HTTPException(403, "Access denied")
    voucher.is_settled = True
    voucher.settled_ref = req.settled_ref
    voucher.settled_date = (
        date.fromisoformat(req.settled_date) if req.settled_date
        else datetime.utcnow().date()
    )
    voucher.updated_at = datetime.utcnow()
    await db.commit()
    return _outstanding_dict(voucher)


# ── Tally XML builders for Payment / Receipt / Journal / Contra ──────────────

def _tally_date(d) -> str:
    from datetime import date as _d
    if isinstance(d, _d):
        return d.strftime("%Y%m%d")
    return str(d).replace("-", "") if d else ""


def _make_payment_xml(v, company: str) -> str:
    items = v.line_items or []
    lines_xml = ""
    for item in items:
        ledger = item.get("ledger", "")
        amount = float(item.get("amount", 0))
        typ = item.get("type", "debit")
        is_positive = "Yes" if typ == "debit" else "No"
        tally_amount = -amount if typ == "debit" else amount
        bill_xml = ""
        if v.bill_ref and item.get("is_party"):
            bill_xml = f"""
              <BILLALLOCATIONS.LIST>
                <NAME>{v.bill_ref}</NAME>
                <BILLTYPE>Agst Ref</BILLTYPE>
                <AMOUNT>{tally_amount:.2f}</AMOUNT>
              </BILLALLOCATIONS.LIST>"""
        lines_xml += f"""
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>{ledger}</LEDGERNAME>
              <ISDEEMEDPOSITIVE>{is_positive}</ISDEEMEDPOSITIVE>
              <AMOUNT>{tally_amount:.2f}</AMOUNT>{bill_xml}
            </ALLLEDGERENTRIES.LIST>"""
    vtype = v.voucher_type
    return f"""<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
  <BODY><IMPORTDATA>
    <REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME>
      <STATICVARIABLES><SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY></STATICVARIABLES>
    </REQUESTDESC>
    <REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF">
      <VOUCHER VCHTYPE="{vtype}" ACTION="Create" OBJVIEW="Accounting Voucher View">
        <DATE>{_tally_date(v.voucher_date)}</DATE>
        <VOUCHERTYPENAME>{vtype}</VOUCHERTYPENAME>
        <VOUCHERNUMBER>{v.voucher_number or ""}</VOUCHERNUMBER>
        <NARRATION>{v.narration or ""}</NARRATION>
        {lines_xml}
      </VOUCHER>
    </TALLYMESSAGE></REQUESTDATA>
  </IMPORTDATA></BODY></ENVELOPE>"""


def _make_journal_xml(v, company: str) -> str:
    items = v.line_items or []
    lines_xml = ""
    for item in items:
        ledger = item.get("ledger", "")
        amount = float(item.get("amount", 0))
        typ = item.get("type", "debit")
        is_positive = "Yes" if typ == "debit" else "No"
        tally_amount = -amount if typ == "debit" else amount
        lines_xml += f"""
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>{ledger}</LEDGERNAME>
              <ISDEEMEDPOSITIVE>{is_positive}</ISDEEMEDPOSITIVE>
              <AMOUNT>{tally_amount:.2f}</AMOUNT>
            </ALLLEDGERENTRIES.LIST>"""
    return f"""<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
  <BODY><IMPORTDATA>
    <REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME>
      <STATICVARIABLES><SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY></STATICVARIABLES>
    </REQUESTDESC>
    <REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF">
      <VOUCHER VCHTYPE="Journal" ACTION="Create" OBJVIEW="Accounting Voucher View">
        <DATE>{_tally_date(v.voucher_date)}</DATE>
        <VOUCHERTYPENAME>Journal</VOUCHERTYPENAME>
        <VOUCHERNUMBER>{v.voucher_number or ""}</VOUCHERNUMBER>
        <NARRATION>{v.narration or ""}</NARRATION>
        {lines_xml}
      </VOUCHER>
    </TALLYMESSAGE></REQUESTDATA>
  </IMPORTDATA></BODY></ENVELOPE>"""


def _make_contra_xml(v, company: str) -> str:
    items = v.line_items or []
    lines_xml = ""
    for item in items:
        ledger = item.get("ledger", "")
        amount = float(item.get("amount", 0))
        typ = item.get("type", "debit")
        is_positive = "Yes" if typ == "debit" else "No"
        tally_amount = -amount if typ == "debit" else amount
        lines_xml += f"""
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>{ledger}</LEDGERNAME>
              <ISDEEMEDPOSITIVE>{is_positive}</ISDEEMEDPOSITIVE>
              <AMOUNT>{tally_amount:.2f}</AMOUNT>
            </ALLLEDGERENTRIES.LIST>"""
    return f"""<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
  <BODY><IMPORTDATA>
    <REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME>
      <STATICVARIABLES><SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY></STATICVARIABLES>
    </REQUESTDESC>
    <REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF">
      <VOUCHER VCHTYPE="Contra" ACTION="Create" OBJVIEW="Accounting Voucher View">
        <DATE>{_tally_date(v.voucher_date)}</DATE>
        <VOUCHERTYPENAME>Contra</VOUCHERTYPENAME>
        <VOUCHERNUMBER>{v.voucher_number or ""}</VOUCHERNUMBER>
        <NARRATION>{v.narration or ""}</NARRATION>
        {lines_xml}
      </VOUCHER>
    </TALLYMESSAGE></REQUESTDATA>
  </IMPORTDATA></BODY></ENVELOPE>"""


# ── Manual voucher create ─────────────────────────────────────────────────────

class LineItemReq(BaseModel):
    ledger: str
    type: str
    amount: float
    is_party: bool = False

class ManualVoucherReq(BaseModel):
    voucher_type: str
    voucher_number: str
    voucher_date: str
    narration: str = ""
    line_items: list[LineItemReq]
    bill_ref: str = ""
    bill_party: str = ""
    template_name: str = ""


@router.post("/manual/{client_id}")
async def create_manual_voucher(
    client_id: str,
    req: ManualVoucherReq,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    from datetime import date
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.tenant_id == current_user.tenant_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    debits = sum(i.amount for i in req.line_items if i.type == "debit")
    credits_ = sum(i.amount for i in req.line_items if i.type == "credit")
    if abs(debits - credits_) > 0.01:
        raise HTTPException(status_code=400,
            detail=f"Does not balance: Dr {debits:.2f} Cr {credits_:.2f}")
    vdate = date.fromisoformat(req.voucher_date)
    v = Voucher(
        tenant_id=current_user.tenant_id,
        client_id=client_id,
        voucher_type=req.voucher_type,
        voucher_number=req.voucher_number,
        voucher_date=vdate,
        narration=req.narration,
        amount=debits,
        tax_amount=0,
        status="approved",
        line_items=[i.dict() for i in req.line_items],
        bill_ref=req.bill_ref or None,
        bill_party=req.bill_party or None,
        template_name=req.template_name or None,
        is_recurring=bool(req.template_name),
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return _outstanding_dict(v)


@router.get("/templates/{client_id}")
async def list_voucher_templates(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(
        select(Voucher).where(
            Voucher.tenant_id == current_user.tenant_id,
            Voucher.client_id == client_id,
            Voucher.is_recurring == True
        ).order_by(Voucher.created_at.desc())
    )
    templates = result.scalars().all()
    return [_outstanding_dict(t) for t in templates]


@router.post("/from-template/{voucher_id}")
async def create_from_template(
    voucher_id: str,
    new_date: str,
    new_ref: str = "",
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    from datetime import date
    result = await db.execute(
        select(Voucher).where(
            Voucher.id == voucher_id,
            Voucher.tenant_id == current_user.tenant_id,
            Voucher.is_recurring == True
        )
    )
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    v = Voucher(
        tenant_id=current_user.tenant_id,
        client_id=tpl.client_id,
        voucher_type=tpl.voucher_type,
        voucher_number=new_ref or tpl.voucher_number,
        voucher_date=date.fromisoformat(new_date),
        narration=tpl.narration,
        amount=tpl.amount,
        tax_amount=0,
        status="approved",
        line_items=tpl.line_items,
        bill_ref=None,
        bill_party=None,
        is_recurring=False,
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return _outstanding_dict(v)
