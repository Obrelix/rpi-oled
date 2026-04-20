from pathlib import Path

import pytest

from data import stats

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


# ---------- parse_meminfo ----------

def test_parse_meminfo_returns_totals_and_percent():
    result = stats.parse_meminfo(read_fixture("meminfo.txt"))
    assert result["ram_total_mb"] == 3840  # 3932160 kB / 1024
    # used = total - available = 3840 - 2393 = 1447
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
