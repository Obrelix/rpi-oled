"""Service registry reader + systemctl wrapper.

Reads rpi-hub's services.json (if present), appends synthetic entries
for rpi-hub and rpi-oled themselves, and provides a cached reader that
checks each unit's systemctl state.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Optional

import config


# ---------- Pure ----------

def load_services(path: Path = config.RPI_HUB_SERVICES_JSON) -> list[dict]:
    """Load services from rpi-hub's services.json. Returns a list of dicts
    with keys: key, name, unit, group (may be None). Always appends
    synthetic entries for rpi-hub and rpi-oled."""
    entries: list[dict] = []
    try:
        raw = json.loads(Path(path).read_text())
        if isinstance(raw, dict):
            for key, val in raw.items():
                if isinstance(val, dict) and "unit" in val:
                    entries.append({
                        "key": key,
                        "name": val.get("name", key),
                        "unit": val["unit"],
                        "group": val.get("group"),
                    })
    except (OSError, json.JSONDecodeError):
        pass  # fall through to synthetic only

    for syn in config.SYNTHETIC_SERVICES:
        entries.append({
            "key": syn["key"],
            "name": syn["name"],
            "unit": syn["unit"],
            "group": None,
        })
    return entries


def filter_by_group(services_list: list[dict], group: str) -> list[dict]:
    return [s for s in services_list if s.get("group") == group]


# ---------- Live ----------

def is_active(unit: str, timeout: float = config.SYSTEMCTL_TIMEOUT) -> str:
    """Return 'active', 'inactive', or '?' for the given systemd unit."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True, text=True, timeout=timeout,
        )
        out = result.stdout.strip()
        if out == "active":
            return "active"
        if out in {"inactive", "failed", "deactivating", "activating"}:
            return "inactive"
        return "?"
    except (OSError, subprocess.TimeoutExpired):
        return "?"


# ---------- Cached reader ----------

class ServicesReader:
    def __init__(self) -> None:
        self._cache: list[dict] = []
        self._cache_at: float = 0.0
        self._registry_at: float = 0.0
        self._registry: list[dict] = []

    def _load_registry(self) -> list[dict]:
        # Registry rarely changes — reload every 30 s at most
        now = time.monotonic()
        if not self._registry or (now - self._registry_at) > 30.0:
            self._registry = load_services()
            self._registry_at = now
        return self._registry

    def get(self) -> list[dict]:
        now = time.monotonic()
        if self._cache and (now - self._cache_at) < config.SERVICES_CACHE_TTL:
            return self._cache

        reg = self._load_registry()
        snapshot = [dict(s, status=is_active(s["unit"])) for s in reg]
        self._cache = snapshot
        self._cache_at = now
        return snapshot

    def active_led_service(self) -> Optional[dict]:
        """Return the first led-panel service with status=='active', else None."""
        for s in self.get():
            if s.get("group") == config.LED_PANEL_GROUP and s.get("status") == "active":
                return s
        return None
