"""
Shared FastAPI dependencies for auth + tenant scoping.

Roles:
  super_admin  — platform owner, no tenant, can see/manage everything
  ca_admin     — CA firm admin, scoped to their tenant
  ca_staff     — CA firm staff, scoped to their tenant (read/create, no delete)
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


async def require_ca_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("super_admin", "ca_admin"):
        raise HTTPException(status_code=403, detail="CA admin access required")
    return user


async def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


def tenant_filter(user: User) -> str | None:
    """Returns tenant_id to filter by, or None if super_admin (sees all)."""
    return None if user.role == "super_admin" else user.tenant_id
