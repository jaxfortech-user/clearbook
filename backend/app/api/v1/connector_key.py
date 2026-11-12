"""
Connector key management endpoints.

POST /api/v1/connector/generate-key
  Generates a unique API key for the tenant's Tally Connector agent.
  The Windows agent uses this key to authenticate the WebSocket tunnel.

GET /api/v1/connector/status
  Returns live connector status for all clients belonging to the tenant.
"""
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.tally_tunnel import tunnel_manager
from app.models.client import Client
from app.models.tenant import Tenant
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate-key")
async def generate_connector_key(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate (or regenerate) the connector API key for this tenant.

    Format: "cb_" + 48 hex chars (192-bit entropy).
    Stored on the Tenant record.  Returns once — store it securely.
    """
    result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    api_key = "cb_" + secrets.token_hex(24)   # 48 hex chars
    tenant.connector_api_key = api_key
    await db.commit()

    logger.info("Generated new connector API key for tenant %s", tenant.id)

    return {
        "api_key": api_key,
        "config_template": {
            "clearbook_host": "wss://YOUR_SUBDOMAIN.duckdns.org",
            "client_id": "PASTE_CLIENT_UUID_HERE",
            "api_key": api_key,
            "tally_host": "localhost",
            "tally_port": 9000,
        },
    }


@router.get("/status")
async def connector_status_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns live connector status for every client in the tenant.
    Used by the dashboard to show which clients have active tunnels.
    """
    result = await db.execute(
        select(Client).where(Client.tenant_id == current_user.tenant_id)
    )
    clients = result.scalars().all()

    return [
        {
            "client_id": str(c.id),
            "client_name": c.name,
            "status": c.tally_connector_status,
            "tally_alive": tunnel_manager.is_connected(
                str(c.tenant_id), str(c.id)
            ),
        }
        for c in clients
    ]