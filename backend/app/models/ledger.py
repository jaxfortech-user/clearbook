import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text
from app.core.database import Base


class Ledger(Base):
    __tablename__ = "ledgers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)           # platform display name
    tally_name = Column(String(255), nullable=False)     # exact name in Tally
    group = Column(String(100), nullable=True)           # Tally group e.g. "Sundry Debtors"
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
