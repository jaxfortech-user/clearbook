import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, DateTime, Date, Numeric, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class BankReconciliation(Base):
    __tablename__ = "bank_reconciliations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    bank_account: Mapped[str] = mapped_column(String(255), nullable=False)
    statement_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    closing_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft / in_progress / completed
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions: Mapped[list["BankTransaction"]] = relationship(
        "BankTransaction", back_populates="reconciliation", cascade="all, delete-orphan"
    )


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    reconciliation_id: Mapped[str] = mapped_column(String(36), ForeignKey("bank_reconciliations.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    is_matched: Mapped[bool] = mapped_column(Boolean, default=False)
    tally_ref: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reconciliation: Mapped["BankReconciliation"] = relationship(
        "BankReconciliation", back_populates="transactions"
    )