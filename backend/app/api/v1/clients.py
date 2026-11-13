from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_current_user, tenant_filter
from app.models.client import Client
from app.models.user import User
from app.schemas.client import ClientCreate, ClientUpdate

router = APIRouter(prefix="/clients", tags=["Clients"])


def _client_to_dict(c: Client) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "trade_name": c.trade_name,
        "trn": c.trn or "",
        "email": c.email,
        "phone": c.phone,
        "address": c.address,
        "entity_type": c.entity_type,
        "type": c.entity_type or "—",
        "industry": c.industry,
        "contact_name": c.contact_name,
        "contact_email": c.contact_email,
        "contact_phone": c.contact_phone,
        "tally_host": c.tally_host,
        "tally_port": c.tally_port,
        "tally_company": c.tally_company,
        "tally_edu_mode": c.tally_edu_mode,
        "tally_last_sync": c.tally_last_sync.isoformat() if c.tally_last_sync else None,
        "tally_connected": bool(c.tally_company),
        "is_active": c.is_active,
        "status": "active" if c.is_active else "inactive",
        "docs": 0,
        "lastActivity": c.updated_at.strftime("%d %b %Y") if c.updated_at else "—",
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = payload.model_dump(exclude={"type"})
    if payload.type and not payload.entity_type:
        data["entity_type"] = payload.type
    data.pop("type", None)

    tid = tenant_filter(user) or "system"
    client = Client(id=str(uuid.uuid4()), tenant_id=tid, **{k: v for k, v in data.items() if v is not None})
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return _client_to_dict(client)


@router.get("/")
async def list_clients(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Client).where(Client.is_active == True)
    tid = tenant_filter(user)
    if tid:
        q = q.where(Client.tenant_id == tid)
    result = await db.execute(q.offset(skip).limit(limit))
    return [_client_to_dict(c) for c in result.scalars().all()]


@router.get("/{client_id}")
async def get_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    tid = tenant_filter(user)
    if tid and client.tenant_id != tid:
        raise HTTPException(status_code=403, detail="Access denied")
    return _client_to_dict(client)


@router.patch("/{client_id}")
@router.put("/{client_id}")
async def update_client(
    client_id: str,
    payload: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    tid = tenant_filter(user)
    if tid and client.tenant_id != tid:
        raise HTTPException(status_code=403, detail="Access denied")

    update_data = payload.model_dump(exclude_unset=True, exclude={"type"})
    if payload.type and not payload.entity_type:
        update_data["entity_type"] = payload.type
    update_data.pop("type", None)

    for key, value in update_data.items():
        setattr(client, key, value)
    client.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(client)
    return _client_to_dict(client)


@router.put("/{client_id}/tally-mapping")
async def update_tally_mapping(client_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    for field in ("tally_host", "tally_port", "tally_company", "tally_edu_mode"):
        if field in payload:
            setattr(client, field, payload[field])
    client.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(client)
    return _client_to_dict(client)


@router.post("/{client_id}/test-tally-connection")
async def test_tally_connection(client_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if not client.tally_company:
        raise HTTPException(status_code=400, detail="No Tally company mapped for this client")

    from app.api.v1.tally import route_tally_xml
    import xml.etree.ElementTree as ET
    xml = """<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>List of Companies</REPORTNAME>
</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"""
    try:
        response = await route_tally_xml(client, xml)
        root = ET.fromstring(response)
        companies = [c.text for c in root.iter("BASICCOMPANYNAME") if c.text]
        return {"connected": True, "company_list": companies}
    except Exception as e:
        return {"connected": False, "company_list": [], "error": str(e)}
