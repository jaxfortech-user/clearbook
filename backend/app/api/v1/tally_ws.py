"""
WebSocket endpoint for the Tally Connector Agent.

The Windows agent opens a persistent WSS connection here.
Nginx proxies it with 3600s timeouts (see nginx.conf).

Endpoint: GET /api/v1/tally/ws/{client_id}?token=<api_key>
"""
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.tally_tunnel import tunnel_manager
from app.models.client import Client
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Auth ──────────────────────────────────────────────────────────────────────

async def _verify_connector_token(
    token: str,
    client_id: str,
    db: AsyncSession,
) -> Optional[tuple[str, str]]:
    """
    Validate the connector API key and return (tenant_id, client_id)
    or None if invalid.
    """
    # Look up tenant by connector_api_key
    result = await db.execute(
        select(Tenant).where(Tenant.connector_api_key == token)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        return None

    # Verify the client belongs to this tenant
    result = await db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.tenant_id == tenant.id,
        )
    )
    client = result.scalar_one_or_none()
    if not client:
        return None

    return str(tenant.id), str(client.id)


async def _set_connector_status(
    client_id: str,
    status: str,
    db: AsyncSession,
) -> None:
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client:
        client.tally_connector_status = status
        await db.commit()


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/{client_id}")
async def tally_connector_ws(
    websocket: WebSocket,
    client_id: str,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    # Authenticate before accepting
    ids = await _verify_connector_token(token, client_id, db)
    if not ids:
        await websocket.close(code=4001)
        logger.warning("[WS] Auth failed for client_id=%s", client_id)
        return

    tenant_id, client_id = ids
    await websocket.accept()
    tunnel_manager.register(tenant_id, client_id, websocket)
    await _set_connector_status(client_id, "connected", db)
    logger.info("[WS] Connector connected: tenant=%s client=%s", tenant_id, client_id)

    try:
        while True:
            data = await websocket.receive_json()

            # Heartbeat from connector
            if "tally_alive" in data:
                status = "connected" if data["tally_alive"] else "tally_offline"
                await _set_connector_status(client_id, status, db)
                continue

            # Tally response — resolve pending future
            request_id = data.get("request_id")
            response_xml = data.get("response_xml", "")
            error = data.get("error")

            if error:
                logger.warning(
                    "[WS] Tally error for request %s: %s", request_id, error
                )
                # Resolve with error XML so the caller gets a meaningful response
                response_xml = f"<ERROR>{error}</ERROR>"

            if request_id:
                tunnel_manager.resolve(tenant_id, client_id, request_id, response_xml)

    except WebSocketDisconnect:
        logger.info("[WS] Connector disconnected: client=%s", client_id)
    finally:
        tunnel_manager.deregister(tenant_id, client_id)
        await _set_connector_status(client_id, "disconnected", db)


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