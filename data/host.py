"""Host identity and network facts."""
from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path
from typing import Optional

import config


# ---------- Pure parsers ----------

def format_uptime(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins_rem = minutes % 60
    if hours < 24:
        return f"{hours}h {mins_rem}m"
    days = hours // 24
    hours_rem = hours % 24
    return f"{days}d {hours_rem}h"


def parse_uptime_seconds(content: str) -> int:
    first = content.strip().split()[0] if content.strip() else "0"
    try:
        return int(float(first))
    except ValueError:
        return 0


def parse_default_iface(route_output: str) -> Optional[str]:
    """Given `ip route show default` output, extract the dev name."""
    for line in route_output.splitlines():
        parts = line.split()
        if parts and parts[0] == "default" and "dev" in parts:
            idx = parts.index("dev")
            if idx + 1 < len(parts):
                return parts[idx + 1]
    return None


def parse_ssid_output(output: str) -> Optional[str]:
    s = output.strip()
    return s if s else None


def parse_link_speed(content: str) -> Optional[int]:
    content = content.strip()
    try:
        return int(content)
    except ValueError:
        return None


# ---------- Live readers ----------

def get_hostname() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return "unknown"


def get_uptime_seconds() -> int:
    try:
        return parse_uptime_seconds(Path("/proc/uptime").read_text())
    except OSError:
        return 0


def get_primary_interface() -> Optional[str]:
    try:
        out = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True, text=True, timeout=2.0,
        ).stdout
        return parse_default_iface(out)
    except (OSError, subprocess.TimeoutExpired):
        return None


def get_primary_ip() -> Optional[str]:
    """Use a UDP socket trick to determine the local IP used for outbound traffic."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return None


def get_ssid(iface: str) -> Optional[str]:
    try:
        out = subprocess.run(
            ["iwgetid", iface, "-r"],
            capture_output=True, text=True, timeout=2.0,
        ).stdout
        return parse_ssid_output(out)
    except (OSError, subprocess.TimeoutExpired):
        return None


def get_link_speed_mbps(iface: str) -> Optional[int]:
    try:
        return parse_link_speed(Path(f"/sys/class/net/{iface}/speed").read_text())
    except OSError:
        return None


# ---------- Reader with cache ----------

class HostInfoReader:
    def __init__(self) -> None:
        self._cache: dict = {}
        self._cache_at: float = 0.0

    def get(self) -> dict:
        now = time.monotonic()
        if self._cache and (now - self._cache_at) < config.HOST_CACHE_TTL:
            return self._cache

        iface = get_primary_interface()
        self._cache = {
            "hostname": get_hostname(),
            "iface": iface,
            "ip": get_primary_ip(),
            "ssid": get_ssid(iface) if iface and iface.startswith("wlan") else None,
            "link_mbps": get_link_speed_mbps(iface) if iface else None,
            "uptime_sec": get_uptime_seconds(),
        }
        self._cache_at = now
        return self._cache
