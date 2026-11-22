"""
Clearbook Tally Connector — Configuration loader.
Config is stored in %APPDATA%\ClearbookConnector\config.json so it persists
regardless of where the exe is launched from.
Shows a GUI setup wizard on first run / when credentials are missing.
"""

import json
import os
import sys
from pathlib import Path

REQUIRED_KEYS = ["clearbook_host", "client_id", "api_key"]

DEFAULTS = {
    "clearbook_host": "clearbook-app.duckdns.org",
    "tally_host": "127.0.0.1",
    "tally_port": 9000,
}


def get_config_dir() -> Path:
    """Always use %APPDATA%\ClearbookConnector — independent of launch location."""
    appdata = os.environ.get("APPDATA") or str(Path.home())
    d = Path(appdata) / "ClearbookConnector"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _show_setup_wizard(config_path: Path) -> dict:
    """GUI wizard — asks Client ID and API Key, saves config.json."""
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        print("[Clearbook] tkinter not available. Edit config.json manually.")
        sys.exit(1)

    root = tk.Tk()
    root.title("Clearbook Connector — Setup")
    root.resizable(False, False)
    root.geometry("460x300")
    root.attributes("-topmost", True)

    # Center on screen
    root.update_idletasks()
    x = (root.winfo_screenwidth() - 460) // 2
    y = (root.winfo_screenheight() - 300) // 2
    root.geometry(f"460x300+{x}+{y}")

    tk.Label(root, text="Clearbook Tally Connector",
             font=("Segoe UI", 14, "bold")).pack(pady=(22, 4))
    tk.Label(root,
             text="Enter the credentials from:\nClearbook platform → Client → Settings → Tally Integration",
             font=("Segoe UI", 9), fg="#555", justify="center").pack(pady=(0, 18))

    # Client ID
    tk.Label(root, text="Client ID", font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=36)
    client_var = tk.StringVar()
    tk.Entry(root, textvariable=client_var, font=("Segoe UI", 10), width=50).pack(padx=36, pady=(2, 12))

    # API Key
    tk.Label(root, text="API Key", font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=36)
    api_var = tk.StringVar()
    tk.Entry(root, textvariable=api_var, font=("Segoe UI", 10), width=50, show="•").pack(padx=36, pady=(2, 20))

    result = {}

    def on_save():
        cid = client_var.get().strip()
        key = api_var.get().strip()
        if not cid or not key:
            messagebox.showwarning("Missing fields", "Please enter both Client ID and API Key.")
            return
        result["client_id"] = cid
        result["api_key"] = key
        root.destroy()

    tk.Button(root, text="  Connect  ", command=on_save,
              bg="#2563eb", fg="white", font=("Segoe UI", 10, "bold"),
              relief="flat", padx=20, pady=8, cursor="hand2").pack()

    root.mainloop()

    if not result:
        sys.exit(0)   # user closed the window

    config = {**DEFAULTS, **result}
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    return config


def load_config() -> dict:
    config_path = get_config_dir() / "config.json"

    # First run — show wizard
    if not config_path.exists():
        return _show_setup_wizard(config_path)

    with open(config_path, "r", encoding="utf-8-sig") as f:
        config = json.load(f)

    # Unfilled template — show wizard again
    unfilled = [k for k in ["client_id", "api_key"]
                if not config.get(k) or str(config.get(k, "")).startswith("REPLACE_")]
    if unfilled:
        return _show_setup_wizard(config_path)

    return config


def save_config(config: dict) -> None:
    config_path = get_config_dir() / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def reset_config() -> None:
    """Delete saved config so wizard shows on next launch."""
    config_path = get_config_dir() / "config.json"
    if config_path.exists():
        config_path.unlink()
