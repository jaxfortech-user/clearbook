import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, JSON, Text, DateTime, ForeignKey
from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False, index=True)
    client_id = Column(String(36), nullable=True, index=True)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(20))
    s3_key = Column(String(500))
    status = Column(String(50), default="uploaded", index=True)
    document_type = Column(String(100))
    confidence_score = Column(Float)
    is_handwritten = Column(Boolean, default=False)
    extracted_data = Column(JSON)
    notes = Column(Text)
    uploaded_by = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)