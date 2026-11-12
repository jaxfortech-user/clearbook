from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class DocumentResponse(BaseModel):
    id: str
    client_id: str
    file_name: str
    file_type: str
    s3_key: str
    status: str
    document_type: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None
    is_handwritten: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}