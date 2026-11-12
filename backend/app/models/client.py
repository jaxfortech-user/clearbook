import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("tenant_id", "trn", name="uq_clients_tenant_trn"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[str] = mapped_column(String(255), nullable=True)
    trn: Mapped[str] = mapped_column(String(50), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=True)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str] = mapped_column(String(50), nullable=True)
    tally_host: Mapped[str] = mapped_column(String(255), nullable=True)
    tally_port: Mapped[int] = mapped_column(nullable=True)
    tally_company: Mapped[str] = mapped_column(String(255), nullable=True)
    tally_edu_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    tally_last_sync: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    tally_connector_status: Mapped[str] = mapped_column(String(20), default="not_installed")  # NEW
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)