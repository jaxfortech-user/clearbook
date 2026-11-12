"""
Clearbook Tally Connector Agent
Runs on the CA firm's Windows machine alongside TallyPrime.
Connects outbound to Clearbook cloud via WebSocket tunnel.
"""

import asyncio
import json
import logging
import socket
import sys
from datetime import datetime

import httpx
import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("connector.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# Reconnect backoff: starts at 5s, doubles each failure, caps at 60s
BACKOFF_INITIAL = 5
BACKOFF_MAX = 60


def tally_is_alive(host: str = "127.0.0.1", port: int = 9000, timeout: float = 2.0) -> bool:
    """Quick TCP probe to check if TallyPrime is listening on port 9000."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError):
        return False


async def forward_to_tally(xml_payload: str, tally_host: str, tally_port: int) -> str:
    """POST XML to TallyPrime HTTP server and return the response XML."""
    url = f"http://{tally_host}:{tally_port}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            content=xml_payload.encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=utf-8"},
        )
        response.raise_for_status()
        return response.text


async def run_connector():
    config = load_config()

    ws_url = (
        f"wss://{config['clearbook_host']}/api/v1/tally/ws/{config['client_id']}"
        f"?token={config['api_key']}"
    )

    tally_host = config.get("tally_host", "127.0.0.1")
    tally_port = int(config.get("tally_port", 9000))

    backoff = BACKOFF_INITIAL

    log.info("Clearbook Tally Connector starting...")
    log.info(f"Connecting to: wss://{config['clearbook_host']}/api/v1/tally/ws/{config['client_id']}")

    while True:
        try:
            async with websockets.connect(
                ws_url,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                log.info("✓ Connected to Clearbook cloud")
                backoff = BACKOFF_INITIAL  # reset on successful connect

                # Send initial heartbeat
                alive = tally_is_alive(tally_host, tally_port)
                await ws.send(json.dumps({"tally_alive": alive}))
                log.info(f"TallyPrime status: {'online' if alive else 'offline'}")

                async for raw_message in ws:
                    try:
                        msg = json.loads(raw_message)
                    except json.JSONDecodeError:
                        log.warning(f"Received non-JSON message: {raw_message[:100]}")
                        continue

                    # Heartbeat ping from server
                    if msg.get("type") == "ping":
                        alive = tally_is_alive(tally_host, tally_port)
                        await ws.send(json.dumps({"tally_alive": alive}))
                        continue

                    # Tally XML request
                    request_id = msg.get("request_id")
                    xml_payload = msg.get("xml")

                    if not request_id or not xml_payload:
                        log.warning("Received message missing request_id or xml")
                        continue

                    log.info(f"→ Tally request [{request_id[:8]}...]")

                    try:
                        response_xml = await forward_to_tally(xml_payload, tally_host, tally_port)
                        reply = {
                            "request_id": request_id,
                            "response_xml": response_xml,
                            "error": None,
                        }
                        log.info(f"← Tally response [{request_id[:8]}...] OK")
                    except Exception as e:
                        log.error(f"Tally error [{request_id[:8]}...]: {e}")
                        reply = {
                            "request_id": request_id,
                            "response_xml": None,
                            "error": str(e),
                        }

                    await ws.send(json.dumps(reply))

        except ConnectionClosedError as e:
            if hasattr(e, "code") and e.code == 4001:
                log.error("❌ Authentication failed — invalid API key. Stopping.")
                sys.exit(1)
            log.warning(f"Connection closed unexpectedly: {e}. Reconnecting in {backoff}s...")

        except ConnectionClosedOK:
            log.info(f"Connection closed cleanly. Reconnecting in {backoff}s...")

        except Exception as e:
            log.error(f"Connection error: {e}. Reconnecting in {backoff}s...")

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, BACKOFF_MAX)


if __name__ == "__main__":
    asyncio.run(run_connector())