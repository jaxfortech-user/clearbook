"""
Clearbook Tally Connector — Configuration loader.
Reads config.json from the same directory as the executable.
Creates a template config.json if one doesn't exist.
"""

import json
import sys
from pathlib import Path


REQUIRED_KEYS = ["clearbook_host", "client_id", "api_key"]

TEMPLATE = {
    "clearbook_host": "clearbook-app.duckdns.org",
    "client_id": "REPLACE_WITH_YOUR_CLIENT_ID",
    "api_key": "REPLACE_WITH_YOUR_API_KEY",
    "tally_host": "127.0.0.1",
    "tally_port": 9000,
}


def get_config_dir() -> Path:
    """
    Returns the directory where config.json lives.
    When packaged with PyInstaller (sys.frozen), use the executable's directory.
    When running as a plain .py script, use the script's directory.
    """
    if getattr(sys, "frozen", False):
        # PyInstaller EXE — config sits next to the .exe
        return Path(sys.executable).parent
    else:
        # Development — config sits next to config.py
        return Path(__file__).parent


def load_config() -> dict:
    config_path = get_config_dir() / "config.json"

    if not config_path.exists():
        # First run — write a template so the CA firm knows what to fill in
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(TEMPLATE, f, indent=2)
        print(f"[Clearbook] config.json created at: {config_path}")
        print("[Clearbook] Please fill in your client_id and api_key, then restart.")
        sys.exit(0)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Validate required keys
    missing = [k for k in REQUIRED_KEYS if not config.get(k)]
    if missing:
        print(f"[Clearbook] Missing required config keys: {missing}")
        print(f"[Clearbook] Edit {config_path} and restart.")
        sys.exit(1)

    # Check for unfilled template values
    unfilled = [k for k in REQUIRED_KEYS if config.get(k, "").startswith("REPLACE_")]
    if unfilled:
        print(f"[Clearbook] Please replace template values for: {unfilled}")
        print(f"[Clearbook] Edit {config_path} and restart.")
        sys.exit(1)

    return config