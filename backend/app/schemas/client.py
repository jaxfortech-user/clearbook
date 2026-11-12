from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ClientCreate(BaseModel):
    name: str
    trade_name: Optional[str] = None
    trn: Optional[str] = None
    entity_type: Optional[str] = None
    industry: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    # legacy compat — frontend sends "type" for entity_type
    type: Optional[str] = None

    def model_post_init(self, __context):
        if self.type and not self.entity_type:
            self.entity_type = self.type


class ClientUpdate(ClientCreate):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class ClientResponse(BaseModel):
    id: str
    name: str
    trade_name: Optional[str] = None
    trn: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    entity_type: Optional[str] = None
    industry: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    tally_host: Optional[str] = None
    tally_port: Optional[int] = None
    tally_company: Optional[str] = None
    tally_edu_mode: Optional[bool] = None
    tally_last_sync: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Computed fields the frontend expects
    @property
    def type(self) -> str:
        return self.entity_type or "—"

    @property
    def status(self) -> str:
        return "active" if self.is_active else "inactive"

    @property
    def tally_connected(self) -> bool:
        return bool(self.tally_company)

    model_config = {"from_attributes": True}

    def model_dump(self, **kwargs):
        d = super().model_dump(**kwargs)
        d["type"] = self.entity_type or "—"
        d["status"] = "active" if self.is_active else "inactive"
        d["tally_connected"] = bool(self.tally_company)
        d["docs"] = 0
        d["lastActivity"] = self.updated_at.strftime("%d %b %Y") if self.updated_at else "—"
        return d
