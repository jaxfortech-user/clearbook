"""
TallyTunnelManager — in-memory singleton managing active WebSocket
connections from Tally Connector agents.

Each connector opens one persistent WSS connection keyed by
tenant_id:client_id.  Requests are correlated with UUID4 request_ids
so concurrent calls for the same client never cross responses.
"""
import asyncio
import logging
from typing import Dict, Optional
from uuid import uuid4

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class TallyTunnelManager:

    def __init__(self):
        # Active WebSocket connections: tenant_id → WebSocket (one per tenant)
        self._connections: Dict[str, WebSocket] = {}
        # Pending response futures: "tenant_id:request_id" → Future
        self._pending: Dict[str, asyncio.Future] = {}

    # ── Connection lifecycle ──────────────────────────────────────────────────

    def register(self, tenant_id: str, websocket: WebSocket) -> None:
        self._connections[tenant_id] = websocket
        logger.info("[Tunnel] Registered connector: tenant=%s", tenant_id)

    def deregister(self, tenant_id: str) -> None:
        self._connections.pop(tenant_id, None)
        to_cancel = [k for k in self._pending if k.startswith(f"{tenant_id}:")]
        for fk in to_cancel:
            future = self._pending.pop(fk, None)
            if future and not future.done():
                future.cancel()
        logger.info("[Tunnel] Deregistered connector: tenant=%s", tenant_id)

    def is_connected(self, tenant_id: str, client_id: str = "") -> bool:
        return tenant_id in self._connections

    def connected_clients(self) -> list[str]:
        return list(self._connections.keys())

    def connection_count(self) -> int:
        return len(self._connections)

    def disconnect_all(self) -> None:
        """Called on app shutdown to close all active tunnels."""
        for key, ws in list(self._connections.items()):
            try:
                asyncio.get_event_loop().create_task(ws.close())
            except Exception:
                pass
        self._connections.clear()
        logger.info("[Tunnel] All connections closed on shutdown")

    # ── Request / response ────────────────────────────────────────────────────

    async def send_and_wait(
        self,
        tenant_id: str,
        xml_payload: str,
        timeout: float = 30.0,
        client_id: str = "",  # kept for backward compat — not used
    ) -> str:
        websocket = self._connections.get(tenant_id)
        if not websocket:
            raise ConnectionError(
                "No active Tally Connector for this tenant. "
                "Install and run ClearbookConnector.exe on the Tally machine."
            )

        request_id = str(uuid4())
        future_key = f"{tenant_id}:{request_id}"
        loop = asyncio.get_event_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._pending[future_key] = future

        try:
            await websocket.send_json(
                {"request_id": request_id, "xml": xml_payload}
            )
            response = await asyncio.wait_for(
                asyncio.shield(future), timeout=timeout
            )
            return response
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Tally did not respond within {timeout}s (request='{request_id}')"
            )
        finally:
            self._pending.pop(future_key, None)

    def resolve(self, tenant_id: str, request_id: str, response_xml: str, client_id: str = "") -> bool:
        """Called when the connector sends back a response."""
        future_key = f"{tenant_id}:{request_id}"
        future = self._pending.get(future_key)
        if future and not future.done():
            future.set_result(response_xml)
            return True
        logger.warning("[Tunnel] No pending future for request_id=%s", request_id)
        return False


# Global singleton — imported by tally_ws.py and tally_routing.py
tunnel_manager = TallyTunnelManager()