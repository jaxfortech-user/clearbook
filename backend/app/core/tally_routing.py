"""
Tally routing abstraction.

Decides whether to send XML through the WebSocket tunnel (production)
or via direct HTTP (development / direct_mode clients).

All Tally API endpoints call route_tally_xml() — they never talk to
Tally directly.
"""
import logging

import httpx

from app.core.config import settings
from app.core.tally_tunnel import tunnel_manager
from app.models.client import Client

logger = logging.getLogger(__name__)


async def _direct_http(host: str, port: int, xml_payload: str) -> str:
    """
    Send XML directly to Tally over HTTP.
    Used in development when the backend and Tally are on the same LAN.
    """
    url = f"http://{host}:{port}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            content=xml_payload.encode("utf-8"),
            headers={"Content-Type": "text/xml;charset=utf-8"},
        )
        response.raise_for_status()
        return response.text


async def route_tally_xml(client: Client, xml_payload: str) -> str:
    """
    Route a Tally XML request for the given client.

    Priority:
      1. WebSocket tunnel — if the connector is connected (production)
      2. Direct HTTP      — if ENV=development or client.tally_direct_mode
      3. Raise ConnectionError — connector not installed / disconnected
    """
    tenant_id = str(client.tenant_id)
    client_id = str(client.id)

    if tunnel_manager.is_connected(tenant_id, client_id):
        logger.info("[TallyRoute] Via tunnel: client=%s", client_id)
        return await tunnel_manager.send_and_wait(tenant_id, client_id, xml_payload)

    if settings.ENV == "development" or getattr(client, "tally_direct_mode", False):
        logger.info(
            "[TallyRoute] Via direct HTTP: %s:%s", client.tally_host, client.tally_port
        )
        return await _direct_http(client.tally_host, client.tally_port, xml_payload)

    raise ConnectionError(
        f"Tally Connector is not connected for client '{client.name}'. "
        "Install and run ClearbookConnector.exe on the client's Windows machine."
    )