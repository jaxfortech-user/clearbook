import uuid
from datetime import datetime, date
from sqlalchemy import String, DateTime, Date, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ChecklistState(Base):
    __tablename__ = "checklist_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    checklist_type: Mapped[str] = mapped_column(String(50), nullable=False)  # vat_return / audit / payroll / custom
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[list["ChecklistItem"]] = relationship(
        "ChecklistItem", back_populates="checklist",
        cascade="all, delete-orphan",
        order_by="ChecklistItem.position",
    )

    def recalculate_progress(self):
        self.total_items = len(self.items)
        self.completed_items = sum(1 for i in self.items if i.is_completed)


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    checklist_id: Mapped[str] = mapped_column(String(36), ForeignKey("checklist_states.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_by: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    checklist: Mapped["ChecklistState"] = relationship(
        "ChecklistState", back_populates="items"
    )