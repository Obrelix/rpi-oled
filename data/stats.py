"""Parsers for system statistics from /proc, /sys, and shell tools.

Pure functions — they take file contents as strings and return simple
dicts/primitives. A StatsReader class wraps them with caching.
"""
from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Optional

import config


# ---------- Pure parsers ----------

def parse_meminfo(content: str) -> dict:
    """Parse /proc/meminfo. Returns MB + percent for RAM and swap."""
    values: dict[str, int] = {}
    for line in content.splitlines():
        m = re.match(r"^([A-Za-z]+):\s+(\d+)\s*kB", line)
        if m:
            values[m.group(1)] = int(m.group(2))

    ram_total_kb = values.get("MemTotal", 0)
    ram_avail_kb = values.get("MemAvailable", values.get("MemFree", 0))
    ram_used_kb = max(0, ram_total_kb - ram_avail_kb)

    swap_total_kb = values.get("SwapTotal", 0)
    swap_free_kb = values.get("SwapFree", 0)
    swap_used_kb = max(0, swap_total_kb - swap_free_kb)

    return {
        "ram_total_mb": ram_total_kb // 1024,
        "ram_used_mb": ram_used_kb // 1024,
        "ram_percent": (ram_used_kb / ram_total_kb * 100) if ram_total_kb else 0.0,
        "swap_total_mb": swap_total_kb // 1024,
        "swap_used_mb": swap_used_kb // 1024,
        "swap_percent": (swap_used_kb / swap_total_kb * 100) if swap_total_kb else 0.0,
    }


def _cpu_totals(content: str) -> Optional[tuple[int, int]]:
    """Return (busy, total) from the aggregate 'cpu ' line of /proc/stat."""
    for line in content.splitlines():
        if line.startswith("cpu "):
            parts = line.split()
            # fields: user nice system idle iowait irq softirq steal guest guest_nice
            nums = [int(x) for x in parts[1:]]
            idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
            total = sum(nums)
            return (total - idle, total)
    return None


def parse_cpu_percent(before: str, after: str) -> float:
    """CPU % over the interval between two /proc/stat snapshots."""
    b = _cpu_totals(before)
    a = _cpu_totals(after)
    if not b or not a:
        return 0.0
    busy_delta = a[0] - b[0]
    total_delta = a[1] - b[1]
    if total_delta <= 0:
        return 0.0
    return 100.0 * busy_delta / total_delta


def parse_thermal(content: str) -> Optional[float]:
    """Convert millidegrees string (from /sys/class/thermal/.../temp) to °C."""
    content = content.strip()
    if not content:
        return None
    try:
        return int(content) / 1000.0
    except ValueError:
        return None


def parse_net_bytes(content: str, iface: str) -> Optional[dict]:
    """Extract rx_bytes/tx_bytes for a given interface from /proc/net/dev."""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith(f"{iface}:"):
            _, rest = line.split(":", 1)
            parts = rest.split()
            # rx_bytes is field 0, tx_bytes is field 8 (after the 8 rx fields)
            if len(parts) >= 9:
                return {"rx_bytes": int(parts[0]), "tx_bytes": int(parts[8])}
    return None


def parse_df(output: str) -> dict:
    """Parse the one-line body of `df -k /`. Returns used_mb, total_mb, percent."""
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[-1] == "/":
            total_kb = int(parts[1])
            used_kb = int(parts[2])
            percent = int(parts[4].rstrip("%"))
            return {
                "used_mb": used_kb // 1024,
                "total_mb": total_kb // 1024,
                "percent": percent,
            }
    return {"used_mb": 0, "total_mb": 0, "percent": 0}


# ---------- Reader with cache ----------

class StatsReader:
    """Reads /proc & related files, caches results for STATS_CACHE_TTL."""

    MEMINFO_PATH = Path("/proc/meminfo")
    STAT_PATH = Path("/proc/stat")
    THERMAL_PATH = Path("/sys/class/thermal/thermal_zone0/temp")
    NET_DEV_PATH = Path("/proc/net/dev")

    def __init__(self) -> None:
        self._cache: dict = {}
        self._cache_at: float = 0.0
        self._last_stat: Optional[str] = None

    def get(self, iface: str = "wlan0") -> dict:
        now = time.monotonic()
        if self._cache and (now - self._cache_at) < config.STATS_CACHE_TTL:
            return self._cache

        snapshot = self._read_all(iface)
        self._cache = snapshot
        self._cache_at = now
        return snapshot

    def _read_all(self, iface: str) -> dict:
        # --- memory ---
        mem_content = self._read_file(self.MEMINFO_PATH)
        mem = parse_meminfo(mem_content) if mem_content else {}

        # --- temperature ---
        thermal_content = self._read_file(self.THERMAL_PATH)
        temp = parse_thermal(thermal_content) if thermal_content else None

        # --- disk ---
        df_output = self._safe_run(["df", "-k", "/"], fallback="")
        disk = self._try_parse(parse_df, df_output, fallback={"used_mb": 0, "total_mb": 0, "percent": 0}) if df_output else {"used_mb": 0, "total_mb": 0, "percent": 0}

        # --- network ---
        net_content = self._read_file(self.NET_DEV_PATH)
        net = self._try_parse(parse_net_bytes, net_content, iface, fallback=None) if net_content else None

        # --- CPU (delta between consecutive snapshots) ---
        now_stat = self._read_file(self.STAT_PATH)
        if self._last_stat and now_stat:
            cpu_pct = self._try_parse(parse_cpu_percent, self._last_stat, now_stat, fallback=0.0)
        else:
            cpu_pct = 0.0
        if now_stat:
            self._last_stat = now_stat

        return {"mem": mem, "cpu_percent": cpu_pct, "temp_c": temp, "disk": disk, "net": net}

    @staticmethod
    def _read_file(path: Path, fallback: str = "") -> str:
        try:
            return path.read_text()
        except OSError:
            return fallback

    @staticmethod
    def _try_parse(fn, *args, fallback):
        """Call fn(*args), return fallback if it raises ValueError or IndexError.
        Used for parsers that cast /proc fields to int — malformed content
        would otherwise crash the entire stats loop."""
        try:
            return fn(*args)
        except (ValueError, IndexError):
            return fallback

    @staticmethod
    def _safe_run(cmd, fallback=""):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=2.0).stdout
        except (OSError, subprocess.TimeoutExpired):
            return fallback
