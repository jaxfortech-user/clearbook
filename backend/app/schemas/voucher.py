from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import date, datetime
from uuid import UUID


class LedgerEntry(BaseModel):
    ledger_name: str
    ledger_type: str
    amount: float


class VoucherCreate(BaseModel):
    client_id: UUID
    document_id: Optional[UUID] = None
    voucher_type: str
    voucher_number: Optional[str] = None
    voucher_date: date
    party_name: str
    narration: Optional[str] = None
    amount: float
    tax_amount: Optional[float] = 0.0
    ledger_entries: Optional[List[LedgerEntry]] = []


class VoucherUpdate(BaseModel):
    voucher_type: Optional[str] = None
    voucher_number: Optional[str] = None
    voucher_date: Optional[date] = None
    party_name: Optional[str] = None
    narration: Optional[str] = None
    amount: Optional[float] = None
    tax_amount: Optional[float] = None
    ledger_entries: Optional[List[Any]] = None
    status: Optional[str] = None


class VoucherResponse(BaseModel):
    id: UUID
    client_id: UUID
    document_id: Optional[UUID]
    voucher_type: str
    voucher_number: Optional[str]
    voucher_date: date
    party_name: str
    narration: Optional[str]
    amount: float
    tax_amount: Optional[float]
    ledger_entries: Optional[List[Any]]
    status: str
    tally_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
