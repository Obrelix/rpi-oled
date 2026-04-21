import socket
from unittest.mock import MagicMock, patch

import pytest

from data import host


# ---------- format_uptime ----------

def test_format_uptime_seconds():
    assert host.format_uptime(45) == "45s"


def test_format_uptime_minutes():
    assert host.format_uptime(90) == "1m"


def test_format_uptime_hours():
    assert host.format_uptime(3 * 3600 + 1500) == "3h 25m"


def test_format_uptime_days():
    assert host.format_uptime(2 * 86400 + 5 * 3600 + 30) == "2d 5h"


# ---------- parse_uptime_seconds ----------

def test_parse_uptime_seconds_takes_first_field():
    assert host.parse_uptime_seconds("12345.67 98765.43\n") == 12345


# ---------- get_primary_interface ----------

def test_get_primary_interface_prefers_wlan0_when_default():
    route_output = "default via 192.168.1.1 dev wlan0 proto dhcp src 192.168.1.201 metric 600\n"
    assert host.parse_default_iface(route_output) == "wlan0"


def test_get_primary_interface_eth0_fallback():
    route_output = "default via 10.0.0.1 dev eth0 proto dhcp src 10.0.0.42 metric 100\n"
    assert host.parse_default_iface(route_output) == "eth0"


def test_get_primary_interface_none_on_empty():
    assert host.parse_default_iface("") is None


# ---------- parse_ssid_from_iwgetid ----------

def test_parse_ssid_returns_trimmed_line():
    assert host.parse_ssid_output("MyNetwork-5G\n") == "MyNetwork-5G"


def test_parse_ssid_empty_returns_none():
    assert host.parse_ssid_output("") is None


def test_parse_ssid_only_whitespace_returns_none():
    assert host.parse_ssid_output("   \n") is None


# ---------- get_primary_ip ----------

def test_get_primary_ip_opens_udp_and_reads_local():
    fake_sock = MagicMock()
    fake_sock.getsockname.return_value = ("192.168.1.201", 12345)
    with patch("socket.socket", return_value=fake_sock) as mock_cls:
        ip = host.get_primary_ip()
    assert ip == "192.168.1.201"
    mock_cls.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM)
    fake_sock.connect.assert_called_once_with(("8.8.8.8", 80))
    fake_sock.close.assert_called_once()


def test_get_primary_ip_returns_none_on_error():
    with patch("socket.socket", side_effect=OSError):
        assert host.get_primary_ip() is None


# ---------- get_link_speed_mbps ----------

def test_parse_link_speed_returns_int():
    assert host.parse_link_speed("300\n") == 300


def test_parse_link_speed_returns_none_on_garbage():
    assert host.parse_link_speed("Unknown!\n") is None


# ---------- HostInfoReader integration ----------

import time


def test_host_info_reader_wlan_populates_all_fields():
    """End-to-end: get() returns all 6 keys, including SSID for a wlan iface."""
    reader = host.HostInfoReader()
    with patch("data.host.get_primary_interface", return_value="wlan0"), \
         patch("data.host.get_hostname", return_value="rpi4"), \
         patch("data.host.get_primary_ip", return_value="192.168.1.201"), \
         patch("data.host.get_ssid", return_value="HomeNet"), \
         patch("data.host.get_link_speed_mbps", return_value=54), \
         patch("data.host.get_uptime_seconds", return_value=3661):
        result = reader.get()
    assert result == {
        "hostname": "rpi4",
        "iface": "wlan0",
        "ip": "192.168.1.201",
        "ssid": "HomeNet",
        "link_mbps": 54,
        "uptime_sec": 3661,
    }


def test_host_info_reader_eth_does_not_fetch_ssid():
    """SSID must be None (and get_ssid never called) on ethernet ifaces."""
    reader = host.HostInfoReader()
    with patch("data.host.get_primary_interface", return_value="eth0"), \
         patch("data.host.get_hostname", return_value="rpi4"), \
         patch("data.host.get_primary_ip", return_value="10.0.0.5"), \
         patch("data.host.get_ssid") as mock_ssid, \
         patch("data.host.get_link_speed_mbps", return_value=1000), \
         patch("data.host.get_uptime_seconds", return_value=100):
        result = reader.get()
    assert result["ssid"] is None
    mock_ssid.assert_not_called()


def test_host_info_reader_uses_cache_within_ttl():
    reader = host.HostInfoReader()
    reader._cache = {"sentinel": 1}
    reader._cache_at = time.monotonic()
    assert reader.get() is reader._cache
