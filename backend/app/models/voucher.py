import uuid
from datetime import datetime, date
from sqlalchemy import String, DateTime, Date, Numeric, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Voucher(Base):
    __tablename__ = "vouchers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id"), nullable=False)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=True)
    voucher_type: Mapped[str] = mapped_column(String(50), nullable=False)
    voucher_number: Mapped[str] = mapped_column(String(100), nullable=True)
    voucher_date: Mapped[date] = mapped_column(Date, nullable=False)
    party_name: Mapped[str] = mapped_column(String(255), nullable=True)
    narration: Mapped[str] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    ledger_entries: Mapped[dict] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    tally_sync_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="AED", nullable=True)
    approved_entries: Mapped[dict] = mapped_column(JSON, nullable=True)
    approved_by: Mapped[str] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str] = mapped_column(Text, nullable=True)
    tally_voucher_id: Mapped[str] = mapped_column(String(100), nullable=True)
    tally_company: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)