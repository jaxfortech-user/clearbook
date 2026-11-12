import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog


async def log(
    db: AsyncSession,
    entity_type: str,
    entity_id: str,
    action: str,
    client_id: str | None = None,
    actor: str | None = None,
    details: dict | None = None,
    tenant_id: str | None = None,
):
    entry = AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor or "system",
        client_id=client_id,
        details=details or {},
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    # Caller is responsible for commit — we don't commit here so we don't
    # break the caller's transaction if they want to roll back.
