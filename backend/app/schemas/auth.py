from pydantic import BaseModel, EmailStr
from typing import Optional


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: Optional[str]
    role: str
    tenant_id: Optional[str] = None


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    role: str = "ca_staff"
    tenant_id: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
