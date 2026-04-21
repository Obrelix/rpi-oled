from pathlib import Path
from unittest.mock import patch

import pytest

from data import stats

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


# ---------- parse_meminfo ----------

def test_parse_meminfo_returns_totals_and_percent():
    result = stats.parse_meminfo(read_fixture("meminfo.txt"))
    assert result["ram_total_mb"] == 3840  # 3932160 kB / 1024
    # used = (MemTotal_kB - MemAvailable_kB) // 1024 = (3932160 - 2451200) // 1024 = 1446
    assert result["ram_used_mb"] == pytest.approx(1447, abs=1)
    assert result["ram_percent"] == pytest.approx(37.6, abs=0.5)
    assert result["swap_total_mb"] == 100
    assert result["swap_used_mb"] == 0
    assert result["swap_percent"] == 0.0


def test_parse_meminfo_handles_zero_swap():
    content = "MemTotal: 1000 kB\nMemAvailable: 500 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB\n"
    result = stats.parse_meminfo(content)
    assert result["swap_percent"] == 0.0  # must not divide by zero


# ---------- parse_cpu_percent ----------

def test_parse_cpu_percent_computes_delta():
    before = read_fixture("stat_before.txt")
    after = read_fixture("stat_after.txt")
    pct = stats.parse_cpu_percent(before, after)
    assert pct == pytest.approx(15.0, abs=0.5)


def test_parse_cpu_percent_zero_when_no_delta():
    sample = "cpu  100 0 50 850 0 0 0 0 0 0\n"
    assert stats.parse_cpu_percent(sample, sample) == 0.0


# ---------- parse_thermal ----------

def test_parse_thermal_converts_millidegrees():
    assert stats.parse_thermal("52300\n") == pytest.approx(52.3, abs=0.01)


def test_parse_thermal_returns_none_on_empty():
    assert stats.parse_thermal("") is None


# ---------- parse_net_bytes ----------

def test_parse_net_bytes_returns_rx_tx_for_iface():
    content = read_fixture("net_dev.txt")
    result = stats.parse_net_bytes(content, "wlan0")
    assert result == {"rx_bytes": 142857142, "tx_bytes": 38111111}


def test_parse_net_bytes_returns_none_for_missing_iface():
    content = read_fixture("net_dev.txt")
    assert stats.parse_net_bytes(content, "eth1") is None


# ---------- parse_df ----------

def test_parse_df_extracts_used_total_percent():
    # Format: Filesystem 1K-blocks Used Available Use% Mounted-on
    df_output = (
        "Filesystem     1K-blocks     Used Available Use% Mounted on\n"
        "/dev/root       30535888 12748320  16521136  44% /\n"
    )
    result = stats.parse_df(df_output)
    # 12748320 KB = ~12449 MB, 30535888 KB = ~29820 MB
    assert result["used_mb"] == pytest.approx(12449, abs=5)
    assert result["total_mb"] == pytest.approx(29820, abs=5)
    assert result["percent"] == 44


# ---------- StatsReader integration ----------

def test_stats_reader_populates_all_fields_when_files_readable(tmp_path):
    """End-to-end: StatsReader.get() should return all fields populated
    when /proc files are readable. Regression test for a bug where
    net_content and cpu stat_content were silently empty."""
    meminfo = FIXTURES / "meminfo.txt"
    stat_before = FIXTURES / "stat_before.txt"
    stat_after = FIXTURES / "stat_after.txt"
    net_dev = FIXTURES / "net_dev.txt"
    thermal = tmp_path / "thermal"
    thermal.write_text("48000\n")

    reader = stats.StatsReader()
    # Point every file path attribute at our fixtures
    reader.MEMINFO_PATH = meminfo
    reader.STAT_PATH = stat_before
    reader.THERMAL_PATH = thermal
    reader.NET_DEV_PATH = net_dev

    def _fake_df(cmd, **kwargs):
        class _R:
            stdout = "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/root 30535888 12748320 16521136 44% /\n"
        return _R()

    with patch("subprocess.run", _fake_df):
        first = reader.get(iface="wlan0")

    assert first["mem"]["ram_total_mb"] == 3840
    assert first["temp_c"] == pytest.approx(48.0, abs=0.1)
    assert first["net"] == {"rx_bytes": 142857142, "tx_bytes": 38111111}
    assert first["disk"]["percent"] == 44
    # First call has no delta yet, so cpu_percent is 0 — this is expected.
    assert first["cpu_percent"] == 0.0

    # Second call: bypass cache by resetting _cache_at, swap stat file to "after"
    reader._cache_at = 0.0
    reader.STAT_PATH = stat_after
    with patch("subprocess.run", _fake_df):
        second = reader.get(iface="wlan0")
    assert second["cpu_percent"] == pytest.approx(15.0, abs=0.5)


def test_stats_reader_uses_cache_within_ttl():
    reader = stats.StatsReader()
    # Populate once from real or empty data (just need _cache non-empty)
    reader._cache = {"sentinel": 1}
    reader._cache_at = __import__("time").monotonic()
    # Subsequent get() should return the same object
    assert reader.get() is reader._cache


# ---------- parse_meminfo edge cases ----------

def test_parse_meminfo_empty_input_returns_zeros():
    result = stats.parse_meminfo("")
    assert result["ram_total_mb"] == 0
    assert result["ram_used_mb"] == 0
    assert result["ram_percent"] == 0.0
    assert result["swap_percent"] == 0.0
