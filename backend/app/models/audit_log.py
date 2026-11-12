import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)   # voucher, document, client
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)        # created, approved, rejected, posted_to_tally, verified, extraction_complete, …
    actor: Mapped[str] = mapped_column(String(255), nullable=True)          # user email or "system"
    client_id: Mapped[str] = mapped_column(String(36), nullable=True, index=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=True)              # arbitrary context
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
