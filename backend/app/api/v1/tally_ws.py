"""
WebSocket endpoint for the Tally Connector Agent.

The Windows agent opens ONE persistent WSS connection per CA firm (tenant).
Nginx proxies it with 3600s timeouts (see nginx.conf).

Endpoint: GET /api/v1/tally/ws?token=<api_key>
"""
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.database import get_db
from app.core.tally_tunnel import tunnel_manager
from app.models.client import Client
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Auth ──────────────────────────────────────────────────────────────────────

async def _verify_connector_token(token: str, db: AsyncSession) -> Optional[str]:
    """Validate the connector API key and return tenant_id, or None if invalid."""
    result = await db.execute(
        select(Tenant).where(Tenant.connector_api_key == token)
    )
    tenant = result.scalar_one_or_none()
    return str(tenant.id) if tenant else None


async def _set_all_clients_status(tenant_id: str, status: str, db: AsyncSession) -> None:
    """Update tally_connector_status for every client under this tenant."""
    await db.execute(
        update(Client)
        .where(Client.tenant_id == tenant_id)
        .values(tally_connector_status=status)
    )
    await db.commit()


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws")
async def tally_connector_ws(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = await _verify_connector_token(token, db)
    if not tenant_id:
        await websocket.close(code=4001)
        logger.warning("[WS] Auth failed — invalid token")
        return

    await websocket.accept()
    tunnel_manager.register(tenant_id, websocket)
    await _set_all_clients_status(tenant_id, "connected", db)
    logger.info("[WS] Connector connected: tenant=%s", tenant_id)

    try:
        while True:
            data = await websocket.receive_json()

            # Heartbeat from connector
            if "tally_alive" in data:
                status = "connected" if data["tally_alive"] else "tally_offline"
                await _set_all_clients_status(tenant_id, status, db)
                continue

            # Tally response — resolve pending future
            request_id = data.get("request_id")
            response_xml = data.get("response_xml", "")
            error = data.get("error")

            if error:
                logger.warning("[WS] Tally error for request %s: %s", request_id, error)
                response_xml = f"<ERROR>{error}</ERROR>"

            if request_id:
                tunnel_manager.resolve(tenant_id, request_id, response_xml)

    except WebSocketDisconnect:
        logger.info("[WS] Connector disconnected: tenant=%s", tenant_id)
    finally:
        tunnel_manager.deregister(tenant_id)
        await _set_all_clients_status(tenant_id, "disconnected", db)


# ── Status endpoint (for frontend indicator) ──────────────────────────────────

@router.get("/ws/connector-status/{client_id}")
async def connector_status(client_id: str, db: AsyncSession = Depends(get_db)):
    """Returns live connector status for the frontend status dot."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        return {"status": "not_found", "tally_alive": False}
    is_live = tunnel_manager.is_connected(str(client.tenant_id), client_id)
    return {
        "status": client.tally_connector_status,
        "tally_alive": is_live,
    }