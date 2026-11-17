from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.core.database import get_db
from app.models.client_period import (
    ChecklistPhase,
    ChecklistStatus,
    ClientPeriod,
    PeriodChecklistItem,
    PeriodStatus,
    VATReturn,
    VATReturnStatus,
)

router = APIRouter()

# ── 25-step checklist template ────────────────────────────────────────────────
PERIOD_CHECKLIST: list[dict] = [
    # Phase 1 — Open the month
    {
        "step": 1, "key": "open_period", "phase": ChecklistPhase.OPEN_MONTH,
        "title": "Open the accounting period",
        "description": "Create the period in the system and set status to OPEN.",
        "default_status": ChecklistStatus.COMPLETE,   # auto-completed on creation
    },
    {
        "step": 2, "key": "request_documents", "phase": ChecklistPhase.OPEN_MONTH,
        "title": "Request documents from client",
        "description": "Send document request checklist to client (invoices, bank statements, payroll).",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 3, "key": "track_arrivals", "phase": ChecklistPhase.OPEN_MONTH,
        "title": "Track document arrivals",
        "description": "Mark off each document as received; chase missing items.",
        "default_status": ChecklistStatus.PENDING,
    },
    # Phase 2 — Transaction entry
    {
        "step": 4, "key": "post_sales", "phase": ChecklistPhase.TRANSACTION_ENTRY,
        "title": "Post sales invoices",
        "description": "Enter all sales/revenue transactions for the period.",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 5, "key": "post_purchases", "phase": ChecklistPhase.TRANSACTION_ENTRY,
        "title": "Post purchase invoices",
        "description": "Enter all supplier/expense invoices for the period.",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 6, "key": "post_salary", "phase": ChecklistPhase.TRANSACTION_ENTRY,
        "title": "Post salary journal",
        "description": "Enter payroll journal (1 Dr Salary Expense + Cr Basic + Cr WPS).",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 7, "key": "post_petty_cash", "phase": ChecklistPhase.TRANSACTION_ENTRY,
        "title": "Post petty cash vouchers",
        "description": "Enter petty cash expenses with multi-line Dr split and Cr Cash.",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 8, "key": "post_bank_payments", "phase": ChecklistPhase.TRANSACTION_ENTRY,
        "title": "Post bank payments",
        "description": "Enter all payments made from bank account.",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 9, "key": "post_bank_receipts", "phase": ChecklistPhase.TRANSACTION_ENTRY,
        "title": "Post bank receipts",
        "description": "Enter all amounts received into bank account.",
        "default_status": ChecklistStatus.PENDING,
    },
    # Phase 3 — Reconciliation
    {
        "step": 10, "key": "download_bank_statement", "phase": ChecklistPhase.RECONCILIATION,
        "title": "Download bank statement",
        "description": "Obtain official bank statement for the period.",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 11, "key": "match_bank_lines", "phase": ChecklistPhase.RECONCILIATION,
        "title": "Match bank statement lines",
        "description": "Reconcile each bank line against posted transactions.",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 12, "key": "post_missing_entries", "phase": ChecklistPhase.RECONCILIATION,
        "title": "Post missing entries",
        "description": "Enter any transactions found on statement but not yet posted.",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 13, "key": "confirm_closing_balance", "phase": ChecklistPhase.RECONCILIATION,
        "title": "Confirm closing balance",
        "description": "Verify ledger closing balance matches bank statement.",
        "default_status": ChecklistStatus.PENDING,
    },
    # Phase 4 — Month-end adjustments
    {
        "step": 14, "key": "post_depreciation", "phase": ChecklistPhase.MONTH_END_ADJUSTMENTS,
        "title": "Post depreciation journal",
        "description": "Run and post monthly depreciation for all fixed assets.",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 15, "key": "post_accruals", "phase": ChecklistPhase.MONTH_END_ADJUSTMENTS,
        "title": "Post accruals",
        "description": "Raise accrual journals for expenses incurred but not yet invoiced.",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 16, "key": "post_prepayments", "phase": ChecklistPhase.MONTH_END_ADJUSTMENTS,
        "title": "Post prepayments",
        "description": "Amortise any prepaid expenses for the period.",
        "default_status": ChecklistStatus.NOT_APPLICABLE,  # optional
    },
    {
        "step": 17, "key": "correction_journals", "phase": ChecklistPhase.MONTH_END_ADJUSTMENTS,
        "title": "Correction journals",
        "description": "Post any reclassification or correction entries identified during review.",
        "default_status": ChecklistStatus.NOT_APPLICABLE,  # optional
    },
    # Phase 5 — Close and verify
    {
        "step": 18, "key": "trial_balance", "phase": ChecklistPhase.CLOSE_AND_VERIFY,
        "title": "Review trial balance",
        "description": "Print/export trial balance and verify all accounts look reasonable.",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 19, "key": "ar_ap_check", "phase": ChecklistPhase.CLOSE_AND_VERIFY,
        "title": "AR / AP ageing check",
        "description": "Review AR and AP ageing reports; flag overdue items to client.",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 20, "key": "vat_computation", "phase": ChecklistPhase.CLOSE_AND_VERIFY,
        "title": "VAT computation",
        "description": "Calculate output and input VAT; verify net VAT payable.",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 21, "key": "ca_signoff", "phase": ChecklistPhase.CLOSE_AND_VERIFY,
        "title": "CA sign-off",
        "description": "Chartered Accountant reviews and approves the period. Triggers CLOSED status.",
        "default_status": ChecklistStatus.PENDING,
    },
    # Phase 6 — Filing (VAT periods only)
    {
        "step": 22, "key": "generate_vat_workings", "phase": ChecklistPhase.FILING,
        "title": "Generate VAT return workings",
        "description": "Produce VAT 201 workings document with all 14 FTA boxes populated.",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 23, "key": "ca_vat_approval", "phase": ChecklistPhase.FILING,
        "title": "CA approval of VAT return",
        "description": "CA reviews and approves the VAT 201 figures before submission.",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 24, "key": "emaratax_submission", "phase": ChecklistPhase.FILING,
        "title": "EmaraTax submission",
        "description": "CA manually submits VAT 201 on EmaraTax portal.",
        "default_status": ChecklistStatus.PENDING,
    },
    {
        "step": 25, "key": "upload_ack", "phase": ChecklistPhase.FILING,
        "title": "Upload acknowledgement",
        "description": "Upload EmaraTax ACK receipt and store reference number. Triggers FILED status.",
        "default_status": ChecklistStatus.PENDING,
    },
]

NON_VAT_STEPS = {t["key"] for t in PERIOD_CHECKLIST if t["phase"] == ChecklistPhase.FILING}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class PeriodCreate(BaseModel):
    client_id: UUID
    period_start: str        # YYYY-MM-DD
    period_end: str
    label: Optional[str] = None
    is_vat_period: bool = False
    vat_quarter_end: Optional[str] = None
    assigned_to: Optional[str] = None


class ChecklistUpdate(BaseModel):
    status: ChecklistStatus
    notes: Optional[str] = None


class VATReturnUpdate(BaseModel):
    box1_amount: Optional[float] = None
    box1_vat: Optional[float] = None
    box2_amount: Optional[float] = None
    box2_vat: Optional[float] = None
    box3_amount: Optional[float] = None
    box3_vat: Optional[float] = None
    box4_amount: Optional[float] = None
    box5_amount: Optional[float] = None
    box6_amount: Optional[float] = None
    box6_vat: Optional[float] = None
    box7_amount: Optional[float] = None
    box7_vat: Optional[float] = None
    box9_amount: Optional[float] = None
    box9_vat: Optional[float] = None
    box10_amount: Optional[float] = None
    box10_vat: Optional[float] = None
    box11_amount: Optional[float] = None
    box11_vat: Optional[float] = None
    box12_amount: Optional[float] = None
    box12_vat: Optional[float] = None


class ACKUpload(BaseModel):
    emaratax_ref: str
    ack_file_path: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize_period(p: ClientPeriod) -> dict:
    return {
        "id": str(p.id),
        "client_id": str(p.client_id),
        "period_start": str(p.period_start),
        "period_end": str(p.period_end),
        "label": p.label,
        "is_vat_period": p.is_vat_period,
        "vat_quarter_end": str(p.vat_quarter_end) if p.vat_quarter_end else None,
        "status": p.status.value,
        "assigned_to": p.assigned_to,
        "reviewed_by": p.reviewed_by,
        "opened_at": p.opened_at.isoformat() if p.opened_at else None,
        "closed_at": p.closed_at.isoformat() if p.closed_at else None,
        "filed_at": p.filed_at.isoformat() if p.filed_at else None,
        "checklist": [_serialize_item(i) for i in p.checklist_items],
    }


def _serialize_item(i: PeriodChecklistItem) -> dict:
    return {
        "id": str(i.id),
        "step_number": i.step_number,
        "item_key": i.item_key,
        "phase": i.phase.value,
        "title": i.title,
        "description": i.description,
        "status": i.status.value,
        "completed_by": i.completed_by,
        "completed_at": i.completed_at.isoformat() if i.completed_at else None,
        "notes": i.notes,
    }


async def _get_period(
    period_id: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> ClientPeriod:
    result = await db.execute(
        select(ClientPeriod)
        .options(
            selectinload(ClientPeriod.checklist_items),
            selectinload(ClientPeriod.vat_return),
        )
        .where(ClientPeriod.id == period_id, ClientPeriod.tenant_id == tenant_id)
    )
    period = result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    return period


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_period(
    body: PeriodCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    """Create a new accounting period and auto-generate the checklist."""
    from datetime import date as date_type
    tenant_id = current_user.tenant_id

    period = ClientPeriod(
        tenant_id=tenant_id,
        client_id=body.client_id,
        period_start=date_type.fromisoformat(body.period_start),
        period_end=date_type.fromisoformat(body.period_end),
        label=body.label,
        is_vat_period=body.is_vat_period,
        vat_quarter_end=(
            date_type.fromisoformat(body.vat_quarter_end)
            if body.vat_quarter_end else None
        ),
        assigned_to=body.assigned_to,
    )
    db.add(period)
    await db.flush()  # get period.id

    # Generate checklist items
    for tmpl in PERIOD_CHECKLIST:
        if not body.is_vat_period and tmpl["key"] in NON_VAT_STEPS:
            continue
        item = PeriodChecklistItem(
            period_id=period.id,
            tenant_id=tenant_id,
            step_number=tmpl["step"],
            item_key=tmpl["key"],
            phase=tmpl["phase"],
            title=tmpl["title"],
            description=tmpl["description"],
            status=tmpl["default_status"],
        )
        # Auto-complete step 1 (open_period) with system user
        if tmpl["key"] == "open_period":
            item.completed_by = str(current_user.id)
            item.completed_at = datetime.now(timezone.utc)
        db.add(item)

    await db.commit()
    await db.refresh(period)

    # Reload with relationships
    period = await _get_period(period.id, tenant_id, db)
    return _serialize_period(period)


@router.get("/")
async def list_periods(
    client_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    """List periods for the tenant, optionally filtered by client."""
    q = select(ClientPeriod).where(
        ClientPeriod.tenant_id == current_user.tenant_id
    ).options(selectinload(ClientPeriod.checklist_items))

    if client_id:
        q = q.where(ClientPeriod.client_id == client_id)

    q = q.order_by(ClientPeriod.period_start.desc())
    result = await db.execute(q)
    periods = result.scalars().all()
    return [_serialize_period(p) for p in periods]


@router.get("/{period_id}")
async def get_period(
    period_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    period = await _get_period(period_id, current_user.tenant_id, db)
    return _serialize_period(period)


@router.patch("/{period_id}/checklist/{item_key}")
async def update_checklist_item(
    period_id: UUID,
    item_key: str,
    body: ChecklistUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    """Tick off (or revert) any checklist step by its key."""
    period = await _get_period(period_id, current_user.tenant_id, db)

    item = next((i for i in period.checklist_items if i.item_key == item_key), None)
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    item.status = body.status
    if body.notes is not None:
        item.notes = body.notes

    if body.status == ChecklistStatus.COMPLETE:
        item.completed_by = str(current_user.id)
        item.completed_at = datetime.now(timezone.utc)
    else:
        item.completed_by = None
        item.completed_at = None

    # Auto-advance: ca_signoff → CLOSED
    if item_key == "ca_signoff" and body.status == ChecklistStatus.COMPLETE:
        period.status = PeriodStatus.CLOSED
        period.closed_at = datetime.now(timezone.utc)
        period.reviewed_by = str(current_user.id)

    await db.commit()
    await db.refresh(item)
    return _serialize_item(item)


@router.get("/{period_id}/vat")
async def get_vat_return(
    period_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    """Get the VAT return for a period (creates a draft if none exists)."""
    period = await _get_period(period_id, current_user.tenant_id, db)

    if not period.is_vat_period:
        raise HTTPException(status_code=400, detail="Not a VAT period")

    if not period.vat_return:
        vat = VATReturn(
            period_id=period.id,
            tenant_id=current_user.tenant_id,
        )
        db.add(vat)
        await db.commit()
        await db.refresh(vat)
        return _serialize_vat(vat)

    return _serialize_vat(period.vat_return)


@router.patch("/{period_id}/vat")
async def update_vat_return(
    period_id: UUID,
    body: VATReturnUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    """Update VAT box values and recompute derived boxes 8, 13, 14."""
    period = await _get_period(period_id, current_user.tenant_id, db)

    if not period.is_vat_period:
        raise HTTPException(status_code=400, detail="Not a VAT period")

    vat = period.vat_return
    if not vat:
        vat = VATReturn(period_id=period.id, tenant_id=current_user.tenant_id)
        db.add(vat)
        await db.flush()

    for field, val in body.model_dump(exclude_none=True).items():
        setattr(vat, field, val)

    vat.recalculate()
    await db.commit()
    await db.refresh(vat)
    return _serialize_vat(vat)


@router.patch("/{period_id}/vat/approve")
async def approve_vat_return(
    period_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    """CA approves the VAT return (step 23)."""
    period = await _get_period(period_id, current_user.tenant_id, db)

    if not period.vat_return:
        raise HTTPException(status_code=404, detail="VAT return not found")

    vat = period.vat_return
    vat.status = VATReturnStatus.APPROVED
    vat.approved_by = str(current_user.id)
    vat.approved_at = datetime.now(timezone.utc)

    # Also tick checklist step 23
    item = next(
        (i for i in period.checklist_items if i.item_key == "ca_vat_approval"), None
    )
    if item:
        item.status = ChecklistStatus.COMPLETE
        item.completed_by = str(current_user.id)
        item.completed_at = datetime.now(timezone.utc)

    await db.commit()
    return _serialize_vat(vat)


@router.post("/{period_id}/ack")
async def upload_ack(
    period_id: UUID,
    body: ACKUpload,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    """Store EmaraTax ACK and advance period to FILED (step 25)."""
    period = await _get_period(period_id, current_user.tenant_id, db)

    if not period.vat_return:
        raise HTTPException(status_code=404, detail="VAT return not found")

    vat = period.vat_return
    vat.emaratax_ref = body.emaratax_ref
    vat.ack_file_path = body.ack_file_path
    vat.status = VATReturnStatus.SUBMITTED
    vat.submitted_at = datetime.now(timezone.utc)

    # Tick step 25
    item = next(
        (i for i in period.checklist_items if i.item_key == "upload_ack"), None
    )
    if item:
        item.status = ChecklistStatus.COMPLETE
        item.completed_by = str(current_user.id)
        item.completed_at = datetime.now(timezone.utc)

    # Auto-advance period to FILED
    period.status = PeriodStatus.FILED
    period.filed_at = datetime.now(timezone.utc)

    await db.commit()
    return {"status": "FILED", "emaratax_ref": body.emaratax_ref}


def _serialize_vat(v: VATReturn) -> dict:
    return {
        "id": str(v.id),
        "period_id": str(v.period_id),
        "status": v.status.value,
        "boxes": {
            "box1": {"amount": float(v.box1_amount or 0), "vat": float(v.box1_vat or 0)},
            "box2": {"amount": float(v.box2_amount or 0), "vat": float(v.box2_vat or 0)},
            "box3": {"amount": float(v.box3_amount or 0), "vat": float(v.box3_vat or 0)},
            "box4": {"amount": float(v.box4_amount or 0)},
            "box5": {"amount": float(v.box5_amount or 0)},
            "box6": {"amount": float(v.box6_amount or 0), "vat": float(v.box6_vat or 0)},
            "box7": {"amount": float(v.box7_amount or 0), "vat": float(v.box7_vat or 0)},
            "box8_total_output_vat": float(v.box8_total_output_vat or 0),
            "box9": {"amount": float(v.box9_amount or 0), "vat": float(v.box9_vat or 0)},
            "box10": {"amount": float(v.box10_amount or 0), "vat": float(v.box10_vat or 0)},
            "box11": {"amount": float(v.box11_amount or 0), "vat": float(v.box11_vat or 0)},
            "box12": {"amount": float(v.box12_amount or 0), "vat": float(v.box12_vat or 0)},
            "box13_total_input_vat": float(v.box13_total_input_vat or 0),
            "box14_net_vat_due": float(v.box14_net_vat_due or 0),
        },
        "emaratax_ref": v.emaratax_ref,
        "ack_file_path": v.ack_file_path,
        "submitted_at": v.submitted_at.isoformat() if v.submitted_at else None,
        "approved_by": v.approved_by,
        "approved_at": v.approved_at.isoformat() if v.approved_at else None,
    }
