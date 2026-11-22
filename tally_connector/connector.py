"""
Clearbook Tally Connector
Runs on the CA firm's Windows machine alongside TallyPrime.
Connects outbound to Clearbook cloud via WebSocket tunnel.
Features: system tray icon, single-instance, auto-start on login.
"""

import asyncio
import json
import logging
import os
import socket
import sys
import threading
import winreg
from pathlib import Path

import httpx
import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from config import get_config_dir, load_config, reset_config, save_config

# ── Logging ───────────────────────────────────────────────────────────────────
log_path = get_config_dir() / "connector.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(log_path), encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ── Single-instance lock ───────────────────────────────────────────────────────
_MUTEX_NAME = "Global\\ClearbookConnector_SingleInstance"


def _acquire_single_instance():
    """Return a mutex handle or exit if another instance is already running."""
    import ctypes
    mutex = ctypes.windll.kernel32.CreateMutexW(None, True, _MUTEX_NAME)
    err = ctypes.windll.kernel32.GetLastError()
    if err == 183:  # ERROR_ALREADY_EXISTS
        import ctypes.wintypes
        # Bring existing window to front via tray (best-effort)
        sys.exit(0)
    return mutex  # keep reference alive for process lifetime


# ── Auto-start registry ───────────────────────────────────────────────────────
_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_VALUE = "ClearbookConnector"


def _set_autostart(enabled: bool) -> None:
    exe_path = sys.executable if getattr(sys, "frozen", False) else str(Path(__file__).resolve())
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE)
        if enabled:
            winreg.SetValueEx(key, _REG_VALUE, 0, winreg.REG_SZ, f'"{exe_path}"')
        else:
            try:
                winreg.DeleteValue(key, _REG_VALUE)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        log.warning(f"Could not update autostart registry: {e}")


def _is_autostart_enabled() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, _REG_VALUE)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False


# ── Tally connectivity ────────────────────────────────────────────────────────
BACKOFF_INITIAL = 5
BACKOFF_MAX = 60

_tally_host = "127.0.0.1"
_tally_port = 9000
_connected = False   # WebSocket connected
_tally_alive = False


def tally_is_alive(host: str = "127.0.0.1", port: int = 9000, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError):
        return False


async def forward_to_tally(xml_payload: str, host: str, port: int) -> str:
    url = f"http://{host}:{port}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            content=xml_payload.encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=utf-8"},
        )
        response.raise_for_status()
        return response.text


# ── System tray ───────────────────────────────────────────────────────────────
def _build_tray_icon(stop_event: threading.Event):
    """Create and run the pystray system tray icon (runs in its own thread)."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        log.warning("pystray/Pillow not available — running without tray icon.")
        return

    def _make_icon(color: str) -> "Image.Image":
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([8, 8, 56, 56], fill=color)
        return img

    icon_obj = {"tray": None}

    def _status_text() -> str:
        if _connected and _tally_alive:
            return "Connected ✓"
        elif _connected and not _tally_alive:
            return "Cloud OK — TallyPrime offline"
        else:
            return "Disconnected"

    def _update_icon():
        if icon_obj["tray"] is None:
            return
        if _connected and _tally_alive:
            icon_obj["tray"].icon = _make_icon("#22c55e")   # green
        elif _connected:
            icon_obj["tray"].icon = _make_icon("#f59e0b")   # amber
        else:
            icon_obj["tray"].icon = _make_icon("#ef4444")   # red
        icon_obj["tray"].title = f"Clearbook Connector — {_status_text()}"

    def _on_settings(_icon, _item):
        """Re-show the setup wizard, then restart the connector."""
        reset_config()
        stop_event.set()
        if icon_obj["tray"]:
            icon_obj["tray"].stop()
        # Relaunch self so wizard appears fresh
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _on_toggle_autostart(_icon, _item):
        enabled = _is_autostart_enabled()
        _set_autostart(not enabled)

    def _on_exit(_icon, _item):
        stop_event.set()
        _icon.stop()

    def _autostart_checked(_icon, _item):
        return _is_autostart_enabled()

    menu = pystray.Menu(
        pystray.MenuItem("Clearbook Connector", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(lambda _: _status_text(), None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Change Credentials…", _on_settings),
        pystray.MenuItem("Start with Windows", _on_toggle_autostart,
                         checked=_autostart_checked),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", _on_exit),
    )

    tray = pystray.Icon(
        "ClearbookConnector",
        _make_icon("#ef4444"),
        "Clearbook Connector — starting…",
        menu,
    )
    icon_obj["tray"] = tray

    # Expose update function globally so the async loop can call it
    global _update_tray
    _update_tray = _update_icon

    tray.run()


_update_tray = lambda: None   # replaced once tray starts


# ── Connector loop ────────────────────────────────────────────────────────────
async def run_connector(stop_event: threading.Event | None = None):
    global _connected, _tally_alive, _tally_host, _tally_port

    config = load_config()

    # Migrate old configs from home dir / dist dir into AppData
    _migrate_old_configs(config)

    # Set autostart on first successful config load
    if not _is_autostart_enabled():
        _set_autostart(True)
        log.info("Auto-start on login enabled.")

    ws_url = (
        f"wss://{config['clearbook_host']}/api/v1/tally/ws/{config['client_id']}"
        f"?token={config['api_key']}"
    )
    _tally_host = config.get("tally_host", "127.0.0.1")
    _tally_port = int(config.get("tally_port", 9000))

    backoff = BACKOFF_INITIAL

    log.info("Clearbook Tally Connector starting…")
    log.info(f"Connecting to: wss://{config['clearbook_host']}/api/v1/tally/ws/{config['client_id']}")

    while True:
        if stop_event and stop_event.is_set():
            break
        try:
            async with websockets.connect(
                ws_url,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                _connected = True
                _update_tray()
                log.info("✓ Connected to Clearbook cloud")
                backoff = BACKOFF_INITIAL

                alive = tally_is_alive(_tally_host, _tally_port)
                _tally_alive = alive
                _update_tray()
                await ws.send(json.dumps({"tally_alive": alive}))
                log.info(f"TallyPrime status: {'online' if alive else 'offline'}")

                async for raw_message in ws:
                    if stop_event and stop_event.is_set():
                        break
                    try:
                        msg = json.loads(raw_message)
                    except json.JSONDecodeError:
                        log.warning(f"Received non-JSON message: {raw_message[:100]}")
                        continue

                    if msg.get("type") == "ping":
                        alive = tally_is_alive(_tally_host, _tally_port)
                        _tally_alive = alive
                        _update_tray()
                        await ws.send(json.dumps({"tally_alive": alive}))
                        continue

                    request_id = msg.get("request_id")
                    xml_payload = msg.get("xml")

                    if not request_id or not xml_payload:
                        log.warning("Received message missing request_id or xml")
                        continue

                    log.info(f"→ Tally request [{request_id[:8]}…]")

                    try:
                        response_xml = await forward_to_tally(xml_payload, _tally_host, _tally_port)
                        reply = {"request_id": request_id, "response_xml": response_xml, "error": None}
                        log.info(f"← Tally response [{request_id[:8]}…] OK")
                    except Exception as e:
                        log.error(f"Tally error [{request_id[:8]}…]: {e}")
                        reply = {"request_id": request_id, "response_xml": None, "error": str(e)}

                    await ws.send(json.dumps(reply))

        except ConnectionClosedError as e:
            _connected = False
            _tally_alive = False
            _update_tray()
            if hasattr(e, "code") and e.code == 4001:
                log.error("❌ Authentication failed — check your API Key in tray → Change Credentials.")
                _show_auth_error()
                sys.exit(1)
            log.warning(f"Connection closed unexpectedly: {e}. Reconnecting in {backoff}s…")

        except ConnectionClosedOK:
            _connected = False
            _tally_alive = False
            _update_tray()
            log.info(f"Connection closed cleanly. Reconnecting in {backoff}s…")

        except Exception as e:
            _connected = False
            _tally_alive = False
            _update_tray()
            log.error(f"Connection error: {e}. Reconnecting in {backoff}s…")

        if stop_event and stop_event.is_set():
            break
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, BACKOFF_MAX)


def _show_auth_error():
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror(
            "Clearbook Connector — Auth Failed",
            "Your API Key was rejected (HTTP 403).\n\n"
            "Right-click the tray icon → Change Credentials…\n"
            "and enter the correct Client ID and API Key."
        )
        root.destroy()
    except Exception:
        pass


def _migrate_old_configs(config: dict) -> None:
    """Copy credentials from old locations into AppData config (one-time)."""
    appdata_cfg = get_config_dir() / "config.json"
    old_locations = [
        Path.home() / "config.json",
        Path.home() / "Downloads" / "config.json",
    ]
    for old in old_locations:
        if old.exists() and old != appdata_cfg:
            try:
                old_cfg = json.loads(old.read_text(encoding="utf-8-sig"))
                if old_cfg.get("client_id") and not str(old_cfg["client_id"]).startswith("REPLACE_"):
                    # Already migrated to AppData — just remove the stale file
                    old.unlink(missing_ok=True)
                    log.info(f"Removed stale config from {old}")
            except Exception:
                pass


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    _mutex = _acquire_single_instance()   # exits if already running

    stop_event = threading.Event()

    # System tray runs in background thread
    tray_thread = threading.Thread(target=_build_tray_icon, args=(stop_event,), daemon=True)
    tray_thread.start()

    asyncio.run(run_connector(stop_event))


if __name__ == "__main__":
    main()
