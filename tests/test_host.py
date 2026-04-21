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
    with patch("socket.socket", return_value=fake_sock):
        ip = host.get_primary_ip()
    assert ip == "192.168.1.201"
    fake_sock.connect.assert_called_once()
    fake_sock.close.assert_called_once()


def test_get_primary_ip_returns_none_on_error():
    with patch("socket.socket", side_effect=OSError):
        assert host.get_primary_ip() is None


# ---------- get_link_speed_mbps ----------

def test_parse_link_speed_returns_int():
    assert host.parse_link_speed("300\n") == 300


def test_parse_link_speed_returns_none_on_garbage():
    assert host.parse_link_speed("Unknown!\n") is None
