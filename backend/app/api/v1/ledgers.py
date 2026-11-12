from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_current_user, tenant_filter
from app.models.ledger import Ledger

router = APIRouter()


class LedgerCreate(BaseModel):
    name: str
    tally_name: str
    group: Optional[str] = None
    description: Optional[str] = None


class LedgerUpdate(BaseModel):
    name: Optional[str] = None
    tally_name: Optional[str] = None
    group: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


def _to_dict(l: Ledger):
    return {
        "id": l.id,
        "name": l.name,
        "tally_name": l.tally_name,
        "group": l.group,
        "description": l.description,
        "is_active": l.is_active,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    }


@router.get("/")
async def list_ledgers(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    tid = tenant_filter(user)
    q = select(Ledger).where(Ledger.is_active == True)
    if tid:
        q = q.where(Ledger.tenant_id == tid)
    result = await db.execute(q.order_by(Ledger.name))
    return [_to_dict(l) for l in result.scalars().all()]


@router.post("/", status_code=201)
async def create_ledger(
    req: LedgerCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    tid = tenant_filter(user) or "system"
    ledger = Ledger(
        id=str(uuid.uuid4()),
        tenant_id=tid,
        name=req.name,
        tally_name=req.tally_name,
        group=req.group,
        description=req.description,
    )
    db.add(ledger)
    await db.commit()
    await db.refresh(ledger)
    return _to_dict(ledger)


@router.patch("/{ledger_id}")
async def update_ledger(
    ledger_id: str,
    req: LedgerUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(Ledger).filter(Ledger.id == ledger_id))
    ledger = result.scalar_one_or_none()
    if not ledger:
        raise HTTPException(404, "Ledger not found")
    tid = tenant_filter(user)
    if tid and ledger.tenant_id != tid:
        raise HTTPException(403, "Access denied")
    for field, val in req.model_dump(exclude_none=True).items():
        setattr(ledger, field, val)
    ledger.updated_at = datetime.utcnow()
    await db.commit()
    return _to_dict(ledger)


@router.delete("/{ledger_id}", status_code=204)
async def delete_ledger(
    ledger_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(select(Ledger).filter(Ledger.id == ledger_id))
    ledger = result.scalar_one_or_none()
    if not ledger:
        raise HTTPException(404, "Ledger not found")
    tid = tenant_filter(user)
    if tid and ledger.tenant_id != tid:
        raise HTTPException(403, "Access denied")
    ledger.is_active = False
    ledger.updated_at = datetime.utcnow()
    await db.commit()
