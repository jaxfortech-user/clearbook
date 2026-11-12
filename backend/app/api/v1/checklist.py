"""
Month-end closing checklist: per-client, per-period checklists.
DB-backed — replaces in-memory _checklists store.
"""
import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.models.client import Client
from app.models.checklist import ChecklistState, ChecklistItem

router = APIRouter()


# ── Default items (your existing 15 items kept intact) ───────────────────────

DEFAULT_ITEMS = [
    {"category": "Bank",               "task": "Upload & reconcile bank statement",   "description": "Match all bank transactions to Tally ledger entries",              "priority": "high"},
    {"category": "Bank",               "task": "Reconcile petty cash",                "description": "Physical count vs Tally petty cash balance",                       "priority": "medium"},
    {"category": "Payroll",            "task": "Post payroll journal entries",         "description": "Salary, WPS transfer, gratuity accrual",                           "priority": "high"},
    {"category": "Payroll",            "task": "Verify WPS compliance",               "description": "Confirm all salaries paid through approved WPS channel",            "priority": "high"},
    {"category": "VAT",                "task": "Reconcile VAT ledgers",               "description": "Input VAT, Output VAT, VAT payable accounts",                       "priority": "high"},
    {"category": "VAT",                "task": "Review intercompany transactions",     "description": "Identify any transactions requiring VAT adjustment",                "priority": "medium"},
    {"category": "Accounts Payable",   "task": "Match supplier invoices",             "description": "All invoices uploaded and vouchers created",                        "priority": "high"},
    {"category": "Accounts Payable",   "task": "Review aged payables",               "description": "Flag overdue payables beyond 60 days",                              "priority": "medium"},
    {"category": "Accounts Receivable","task": "Review aged receivables",             "description": "Follow up on invoices overdue beyond 30 days",                     "priority": "medium"},
    {"category": "Accounts Receivable","task": "Post customer receipts",              "description": "All customer payments posted in Tally",                             "priority": "high"},
    {"category": "Closing",            "task": "Review trial balance",                "description": "Check for unusual balances or rounding differences",                "priority": "high"},
    {"category": "Closing",            "task": "Post depreciation entries",           "description": "Fixed assets depreciation for the period",                          "priority": "medium"},
    {"category": "Closing",            "task": "Review intercompany balances",        "description": "Confirm all intercompany balances net to zero",                     "priority": "low"},
    {"category": "Compliance",         "task": "Corporate tax provision",             "description": "Calculate and post corporate tax provision (9% on taxable income)", "priority": "high"},
    {"category": "Compliance",         "task": "Confirm TRN registrations",           "description": "Verify all client TRNs are current with FTA",                      "priority": "low"},
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_period() -> str:
    today = date.today()
    return f"{today.year}-{today.month:02d}"


def _period_dates(period: str):
    """Convert 'YYYY-MM' to (period_start, period_end) dates."""
    year, month = int(period[:4]), int(period[5:7])
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    from datetime import timedelta
    end = end - timedelta(days=1)
    return start, end


def _serialize_checklist(checklist: ChecklistState, items: list[ChecklistItem]) -> dict:
    complete = sum(1 for i in items if i.is_completed)
    return {
        "id": checklist.id,
        "client_id": checklist.client_id,
        "checklist_type": checklist.checklist_type,
        "period_start": checklist.period_start.isoformat(),
        "period_end": checklist.period_end.isoformat(),
        "summary": {
            "total": len(items),
            "complete": complete,
            "pending": len(items) - complete,
        },
        "items": [
            {
                "id": item.id,
                "label": item.label,
                "position": item.position,
                "status": "complete" if item.is_completed else "pending",
                "completed_by": item.completed_by,
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            }
            for item in sorted(items, key=lambda x: x.position)
        ],
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{client_id}")
async def get_checklist(
    client_id: str,
    period: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if not period:
        period = _default_period()

    period_start, period_end = _period_dates(period)

    # Find existing checklist
    result = await db.execute(
        select(ChecklistState).where(
            ChecklistState.client_id == client_id,
            ChecklistState.period_start == period_start,
        )
    )
    checklist = result.scalar_one_or_none()

    if not checklist:
        # Auto-create with default items
        client_result = await db.execute(select(Client).where(Client.id == client_id))
        client = client_result.scalar_one_or_none()
        if not client:
            raise HTTPException(404, "Client not found")

        checklist = ChecklistState(
            id=str(uuid.uuid4()),
            tenant_id=client.tenant_id,
            client_id=client_id,
            checklist_type="month_end",
            period_start=period_start,
            period_end=period_end,
            total_items=len(DEFAULT_ITEMS),
            completed_items=0,
        )
        db.add(checklist)
        await db.flush()

        for i, item in enumerate(DEFAULT_ITEMS):
            db.add(ChecklistItem(
                id=str(uuid.uuid4()),
                checklist_id=checklist.id,
                tenant_id=client.tenant_id,
                label=f"[{item['category']}] {item['task']}",
                position=i,
                is_completed=False,
            ))

        await db.commit()
        await db.refresh(checklist)

    # Load items
    items_result = await db.execute(
        select(ChecklistItem).where(ChecklistItem.checklist_id == checklist.id)
    )
    items = items_result.scalars().all()

    return _serialize_checklist(checklist, items)


class UpdateItemPayload(BaseModel):
    status: str  # pending | complete | na
    notes: Optional[str] = None
    completed_by: Optional[str] = None


@router.put("/{client_id}/{item_id}")
async def update_checklist_item(
    client_id: str,
    item_id: str,
    payload: UpdateItemPayload,
    period: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if payload.status not in ("pending", "complete", "na"):
        raise HTTPException(400, "status must be pending, complete, or na")

    result = await db.execute(select(ChecklistItem).where(ChecklistItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Item not found")

    if payload.status == "complete":
        item.is_completed = True
        item.completed_at = datetime.utcnow()
        item.completed_by = payload.completed_by or "admin"
    else:
        item.is_completed = False
        item.completed_at = None
        item.completed_by = None

    await db.commit()

    # Return updated checklist
    checklist_result = await db.execute(
        select(ChecklistState).where(ChecklistState.id == item.checklist_id)
    )
    checklist = checklist_result.scalar_one_or_none()
    items_result = await db.execute(
        select(ChecklistItem).where(ChecklistItem.checklist_id == item.checklist_id)
    )
    items = items_result.scalars().all()
    checklist.recalculate_progress()
    await db.commit()

    return _serialize_checklist(checklist, items)


@router.post("/{client_id}/reset")
async def reset_checklist(
    client_id: str,
    period: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if not period:
        period = _default_period()
    period_start, _ = _period_dates(period)

    result = await db.execute(
        select(ChecklistState).where(
            ChecklistState.client_id == client_id,
            ChecklistState.period_start == period_start,
        )
    )
    checklist = result.scalar_one_or_none()
    if checklist:
        await db.delete(checklist)
        await db.commit()

    return {"message": "Checklist reset", "period": period}