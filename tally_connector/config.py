"""
Clearbook Tally Connector — Configuration loader.
Shows a GUI setup wizard on first run instead of asking the CA to edit JSON.
"""

import json
import sys
from pathlib import Path


REQUIRED_KEYS = ["clearbook_host", "client_id", "api_key"]

DEFAULTS = {
    "clearbook_host": "clearbook-app.duckdns.org",
    "tally_host": "127.0.0.1",
    "tally_port": 9000,
}


def get_config_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _show_setup_wizard(config_path: Path) -> dict:
    """GUI wizard — asks Client ID and API Key, saves config.json."""
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        print("[Clearbook] tkinter not available. Edit config.json manually.")
        sys.exit(1)

    root = tk.Tk()
    root.title("Clearbook Connector — First Time Setup")
    root.resizable(False, False)
    root.geometry("420x260")

    # Center on screen
    root.update_idletasks()
    x = (root.winfo_screenwidth() - 420) // 2
    y = (root.winfo_screenheight() - 260) // 2
    root.geometry(f"420x260+{x}+{y}")

    tk.Label(root, text="Clearbook Tally Connector", font=("Segoe UI", 13, "bold")).pack(pady=(18, 2))
    tk.Label(root, text="Enter the credentials from Clearbook → Settings → Tally Integration",
             font=("Segoe UI", 9), wraplength=380, fg="#555").pack(pady=(0, 14))

    # Client ID
    tk.Label(root, text="Client ID", font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=30)
    client_var = tk.StringVar()
    tk.Entry(root, textvariable=client_var, font=("Segoe UI", 10), width=44).pack(padx=30, pady=(2, 10))

    # API Key
    tk.Label(root, text="API Key", font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=30)
    api_var = tk.StringVar()
    tk.Entry(root, textvariable=api_var, font=("Segoe UI", 10), width=44, show="*").pack(padx=30, pady=(2, 16))

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

    tk.Button(root, text="Connect", command=on_save,
              bg="#2563eb", fg="white", font=("Segoe UI", 10, "bold"),
              relief="flat", padx=20, pady=6, cursor="hand2").pack()

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
