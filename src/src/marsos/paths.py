"""Filesystem locations. Everything is overridable by environment variables so tests never touch the real system."""
from __future__ import annotations
import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
DATA_DIR = PKG_DIR / "data"
QSS_FILE = PKG_DIR / "ui" / "marsos.qss"


def config_dir() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "marsos"


def state_dir() -> Path:
    return Path(os.environ.get("MARSOS_STATE_DIR", "/var/lib/marsos"))


def pending_file() -> Path:
    return state_dir() / "pending-apps.json"


def pending_status_file() -> Path:
    return state_dir() / "pending-status.json"


def is_live() -> bool:
    return os.environ.get("MARSOS_LIVE") == "1" or Path("/run/archiso").exists()


def helper_path() -> str:
    return os.environ.get("MARSOS_HELPER", "/usr/bin/marsos-helper")
