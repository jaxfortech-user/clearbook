import uuid
from datetime import date, datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class PeriodStatus(PyEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    FILED = "FILED"


class ChecklistPhase(PyEnum):
    OPEN_MONTH = "OPEN_MONTH"
    TRANSACTION_ENTRY = "TRANSACTION_ENTRY"
    RECONCILIATION = "RECONCILIATION"
    MONTH_END_ADJUSTMENTS = "MONTH_END_ADJUSTMENTS"
    CLOSE_AND_VERIFY = "CLOSE_AND_VERIFY"
    FILING = "FILING"


class ChecklistStatus(PyEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class VATReturnStatus(PyEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    SUBMITTED = "SUBMITTED"


class ClientPeriod(Base):
    __tablename__ = "client_periods"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    client_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period_start = mapped_column(Date, nullable=False)
    period_end = mapped_column(Date, nullable=False)
    label = mapped_column(String(100), nullable=True)
    is_vat_period = mapped_column(Boolean, default=False, nullable=False)
    vat_quarter_end = mapped_column(Date, nullable=True)
    status = mapped_column(
        Enum(PeriodStatus, name="periodstatus"),
        nullable=False,
        default=PeriodStatus.OPEN,
    )
    assigned_to = mapped_column(String(255), nullable=True)
    reviewed_by = mapped_column(String(255), nullable=True)
    opened_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at = mapped_column(DateTime(timezone=True), nullable=True)
    filed_at = mapped_column(DateTime(timezone=True), nullable=True)

    checklist_items = relationship(
        "PeriodChecklistItem",
        back_populates="period",
        cascade="all, delete-orphan",
        order_by="PeriodChecklistItem.step_number",
    )
    vat_return = relationship(
        "VATReturn",
        back_populates="period",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("client_id", "period_start", name="uq_client_period_start"),
    )


class PeriodChecklistItem(Base):
    __tablename__ = "period_checklist_items"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("client_periods.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    step_number = mapped_column(Integer, nullable=False)
    item_key = mapped_column(String(80), nullable=False)
    phase = mapped_column(
        Enum(ChecklistPhase, name="checklistphase"), nullable=False
    )
    title = mapped_column(String(255), nullable=False)
    description = mapped_column(Text, nullable=True)
    status = mapped_column(
        Enum(ChecklistStatus, name="checkliststatus"),
        nullable=False,
        default=ChecklistStatus.PENDING,
    )
    completed_by = mapped_column(String(255), nullable=True)
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)
    notes = mapped_column(Text, nullable=True)

    period = relationship("ClientPeriod", back_populates="checklist_items")

    __table_args__ = (
        UniqueConstraint("period_id", "item_key", name="uq_period_item_key"),
    )


class VATReturn(Base):
    __tablename__ = "vat_returns"

    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_id = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("client_periods.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    tenant_id = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    status = mapped_column(
        Enum(VATReturnStatus, name="vatreturnstatus"),
        nullable=False,
        default=VATReturnStatus.DRAFT,
    )

    # Box 1 — Standard rated supplies (Emirates)
    box1_amount = mapped_column(Numeric(15, 2), default=0)
    box1_vat = mapped_column(Numeric(15, 2), default=0)
    # Box 2 — Tax refunds for tourists
    box2_amount = mapped_column(Numeric(15, 2), default=0)
    box2_vat = mapped_column(Numeric(15, 2), default=0)
    # Box 3 — Supplies subject to domestic reverse charge
    box3_amount = mapped_column(Numeric(15, 2), default=0)
    box3_vat = mapped_column(Numeric(15, 2), default=0)
    # Box 4 — Zero rated supplies
    box4_amount = mapped_column(Numeric(15, 2), default=0)
    # Box 5 — Exempt supplies
    box5_amount = mapped_column(Numeric(15, 2), default=0)
    # Box 6 — Goods imported into UAE
    box6_amount = mapped_column(Numeric(15, 2), default=0)
    box6_vat = mapped_column(Numeric(15, 2), default=0)
    # Box 7 — Adjustments to goods imported
    box7_amount = mapped_column(Numeric(15, 2), default=0)
    box7_vat = mapped_column(Numeric(15, 2), default=0)
    # Box 9 — Standard rated expenses (input VAT)
    box9_amount = mapped_column(Numeric(15, 2), default=0)
    box9_vat = mapped_column(Numeric(15, 2), default=0)
    # Box 10 — Supplies subject to domestic reverse charge (purchases)
    box10_amount = mapped_column(Numeric(15, 2), default=0)
    box10_vat = mapped_column(Numeric(15, 2), default=0)
    # Box 11 — Other inputs deductible
    box11_amount = mapped_column(Numeric(15, 2), default=0)
    box11_vat = mapped_column(Numeric(15, 2), default=0)
    # Box 12 — Input tax adjustments
    box12_amount = mapped_column(Numeric(15, 2), default=0)
    box12_vat = mapped_column(Numeric(15, 2), default=0)

    # Computed fields (derived — not user-entered)
    box8_total_output_vat = mapped_column(Numeric(15, 2), default=0)   # sum boxes 1-3 VAT
    box13_total_input_vat = mapped_column(Numeric(15, 2), default=0)   # sum boxes 9-12 VAT
    box14_net_vat_due = mapped_column(Numeric(15, 2), default=0)        # box8 - box13

    # EmaraTax filing fields
    emaratax_ref = mapped_column(String(100), nullable=True)
    ack_file_path = mapped_column(String(500), nullable=True)
    submitted_at = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by = mapped_column(String(255), nullable=True)
    approved_at = mapped_column(DateTime(timezone=True), nullable=True)

    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    period = relationship("ClientPeriod", back_populates="vat_return")

    def recalculate(self):
        """Recompute derived boxes 8, 13, 14."""
        self.box8_total_output_vat = (
            (self.box1_vat or 0)
            + (self.box2_vat or 0)
            + (self.box3_vat or 0)
        )
        self.box13_total_input_vat = (
            (self.box9_vat or 0)
            + (self.box10_vat or 0)
            + (self.box11_vat or 0)
            + (self.box12_vat or 0)
        )
        self.box14_net_vat_due = self.box8_total_output_vat - self.box13_total_input_vat
