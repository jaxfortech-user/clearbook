"""
Tenant (CA firm) management — super_admin only.
Also provides the CA firm's own profile endpoint for ca_admin.
"""
import uuid
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_user, require_super_admin
from app.core.security import hash_password
from app.models.tenant import Tenant
from app.models.user import User
from app.models.client import Client

router = APIRouter()


class TenantCreate(BaseModel):
    name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    plan: str = "trial"
    notes: Optional[str] = None
    # First CA admin user
    admin_email: str
    admin_password: str
    admin_full_name: Optional[str] = None


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    plan: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:80]


async def _unique_slug(db: AsyncSession, base: str) -> str:
    slug = base
    i = 1
    while True:
        r = await db.execute(select(Tenant).where(Tenant.slug == slug))
        if not r.scalar_one_or_none():
            return slug
        slug = f"{base}-{i}"
        i += 1


@router.get("/")
async def list_tenants(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    result = await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    tenants = result.scalars().all()
    out = []
    for t in tenants:
        users_r = await db.execute(select(func.count()).where(User.tenant_id == t.id))
        clients_r = await db.execute(select(func.count()).where(Client.tenant_id == t.id))
        out.append({
            "id": t.id, "name": t.name, "slug": t.slug,
            "contact_email": t.contact_email, "contact_phone": t.contact_phone,
            "plan": t.plan, "is_active": t.is_active, "notes": t.notes,
            "created_at": t.created_at.isoformat(),
            "user_count": users_r.scalar(),
            "client_count": clients_r.scalar(),
        })
    return out


@router.post("/", status_code=201)
async def create_tenant(
    payload: TenantCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    # Check email not taken
    existing = await db.execute(select(User).where(User.email == payload.admin_email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Admin email already registered")

    slug = await _unique_slug(db, _slugify(payload.name))
    tenant = Tenant(
        id=str(uuid.uuid4()),
        name=payload.name,
        slug=slug,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        plan=payload.plan,
        notes=payload.notes,
    )
    db.add(tenant)
    await db.flush()

    admin = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        email=payload.admin_email,
        hashed_password=hash_password(payload.admin_password),
        full_name=payload.admin_full_name or payload.name,
        role="ca_admin",
    )
    db.add(admin)
    await db.commit()

    return {
        "id": tenant.id, "name": tenant.name, "slug": tenant.slug,
        "plan": tenant.plan,
        "admin_email": admin.email,
        "message": f"Tenant '{tenant.name}' created with admin {admin.email}",
    }


@router.get("/me")
async def my_tenant(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "super_admin":
        return {"role": "super_admin", "tenant": None}
    if not user.tenant_id:
        raise HTTPException(404, "No tenant assigned")
    r = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    t = r.scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Tenant not found")
    return {
        "id": t.id, "name": t.name, "slug": t.slug,
        "plan": t.plan, "is_active": t.is_active,
    }


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    r = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    t = r.scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Tenant not found")
    users_r = await db.execute(select(User).where(User.tenant_id == t.id))
    users = users_r.scalars().all()
    return {
        "id": t.id, "name": t.name, "slug": t.slug,
        "contact_email": t.contact_email, "contact_phone": t.contact_phone,
        "plan": t.plan, "is_active": t.is_active, "notes": t.notes,
        "created_at": t.created_at.isoformat(),
        "users": [{"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role, "is_active": u.is_active} for u in users],
    }


@router.patch("/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    payload: TenantUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    r = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    t = r.scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Tenant not found")
    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(t, field, val)
    await db.commit()
    return {"id": t.id, "name": t.name, "plan": t.plan, "is_active": t.is_active}


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    r = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    t = r.scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Tenant not found")
    await db.delete(t)
    await db.commit()
