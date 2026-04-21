import json
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import config
from data import services

FIXTURES = Path(__file__).parent / "fixtures"


# ---------- load_services ----------

def test_load_services_returns_entries_with_synthetic_appended():
    result = services.load_services(FIXTURES / "services.json")
    keys = [s["key"] for s in result]
    assert "rpi-radio" in keys
    assert "voidex" in keys
    assert "maze-battlegrounds" in keys
    # synthetic entries appended
    assert keys[-2:] == ["rpi-hub", "rpi-oled"]


def test_load_services_missing_file_returns_only_synthetic():
    result = services.load_services(Path("/does/not/exist.json"))
    keys = [s["key"] for s in result]
    assert keys == ["rpi-hub", "rpi-oled"]


def test_load_services_invalid_json_returns_only_synthetic(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    result = services.load_services(bad)
    assert [s["key"] for s in result] == ["rpi-hub", "rpi-oled"]


def test_load_services_exposes_group_and_unit():
    result = services.load_services(FIXTURES / "services.json")
    voidex = next(s for s in result if s["key"] == "voidex")
    assert voidex["unit"] == "voidex.service"
    assert voidex["group"] == "led-panel"
    assert voidex["name"] == "Voidex"


# ---------- is_active ----------

def _fake_run(stdout="", returncode=0, raise_exc=None):
    def _run(cmd, **kwargs):
        if raise_exc:
            raise raise_exc
        result = subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")
        return result
    return _run


def test_is_active_returns_active_on_matching_output():
    with patch("subprocess.run", _fake_run(stdout="active\n", returncode=0)):
        assert services.is_active("voidex.service") == "active"


def test_is_active_returns_inactive_on_inactive_output():
    with patch("subprocess.run", _fake_run(stdout="inactive\n", returncode=3)):
        assert services.is_active("voidex.service") == "inactive"


def test_is_active_returns_question_on_timeout():
    with patch("subprocess.run", _fake_run(raise_exc=subprocess.TimeoutExpired("systemctl", 2))):
        assert services.is_active("voidex.service") == "?"


def test_is_active_returns_question_on_oserror():
    with patch("subprocess.run", _fake_run(raise_exc=OSError("nope"))):
        assert services.is_active("voidex.service") == "?"


# ---------- filter_by_group ----------

def test_filter_by_group_returns_matching_entries():
    all_services = services.load_services(FIXTURES / "services.json")
    led = services.filter_by_group(all_services, "led-panel")
    keys = [s["key"] for s in led]
    assert keys == ["rpi-radio", "voidex", "maze-battlegrounds"]


def test_filter_by_group_excludes_synthetic_entries():
    all_services = services.load_services(FIXTURES / "services.json")
    led = services.filter_by_group(all_services, "led-panel")
    for s in led:
        assert s["key"] not in {"rpi-hub", "rpi-oled"}


# ---------- ServicesReader integration ----------

def test_services_reader_get_attaches_status_to_every_entry():
    """End-to-end: get() reads the registry, queries is_active for each,
    and returns a list with status attached."""
    reader = services.ServicesReader()
    # Point the registry loader at our fixture
    with patch("data.services.load_services", return_value=[
        {"key": "voidex", "name": "Voidex", "unit": "voidex.service", "group": "led-panel"},
        {"key": "rpi-radio", "name": "RPi Radio", "unit": "rpi-radio.service", "group": "led-panel"},
    ]), patch("data.services.is_active", side_effect=["active", "inactive"]):
        result = reader.get()
    assert [s["status"] for s in result] == ["active", "inactive"]
    assert result[0]["key"] == "voidex"


def test_services_reader_active_led_service_returns_the_running_one():
    reader = services.ServicesReader()
    reader._cache = [
        {"key": "voidex", "name": "Voidex", "unit": "voidex.service", "group": "led-panel", "status": "active"},
        {"key": "rpi-radio", "name": "RPi Radio", "unit": "rpi-radio.service", "group": "led-panel", "status": "inactive"},
        {"key": "rpi-hub", "name": "RPi Hub", "unit": "rpi-hub.service", "group": None, "status": "active"},
    ]
    reader._cache_at = time.monotonic()
    active = reader.active_led_service()
    assert active is not None
    assert active["key"] == "voidex"


def test_services_reader_active_led_service_none_when_all_inactive():
    reader = services.ServicesReader()
    reader._cache = [
        {"key": "voidex", "name": "Voidex", "unit": "voidex.service", "group": "led-panel", "status": "inactive"},
        {"key": "rpi-hub", "name": "RPi Hub", "unit": "rpi-hub.service", "group": None, "status": "active"},
    ]
    reader._cache_at = time.monotonic()
    assert reader.active_led_service() is None


def test_services_reader_uses_cache_within_ttl():
    reader = services.ServicesReader()
    sentinel = [{"sentinel": 1}]
    reader._cache = sentinel
    reader._cache_at = time.monotonic()
    # If get() bypassed cache, it would call load_services which would fail
    # (path doesn't exist) — but we expect it NOT to be called.
    with patch("data.services.load_services") as mock_load:
        result = reader.get()
    mock_load.assert_not_called()
    assert result is sentinel
