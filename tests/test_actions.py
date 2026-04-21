import subprocess
from unittest.mock import MagicMock, patch

import pytest

from actions import system


# ---------- restart_active_led ----------

def test_restart_active_led_restarts_the_active_unit():
    reader = MagicMock()
    reader.active_led_service.return_value = {"key": "voidex", "unit": "voidex.service", "name": "Voidex"}
    runner = MagicMock(return_value=subprocess.CompletedProcess([], 0))
    ok, msg = system.restart_active_led(reader, runner=runner)
    assert ok is True
    assert "Voidex" in msg
    runner.assert_called_once()
    called_cmd = runner.call_args[0][0]
    assert called_cmd == ["systemctl", "restart", "voidex.service"]


def test_restart_active_led_reports_when_none_active():
    reader = MagicMock()
    reader.active_led_service.return_value = None
    runner = MagicMock()
    ok, msg = system.restart_active_led(reader, runner=runner)
    assert ok is False
    assert "No active" in msg
    runner.assert_not_called()


def test_restart_active_led_reports_failure_on_nonzero_exit():
    reader = MagicMock()
    reader.active_led_service.return_value = {"key": "voidex", "unit": "voidex.service", "name": "Voidex"}
    runner = MagicMock(return_value=subprocess.CompletedProcess([], 1, stderr="permission denied"))
    ok, msg = system.restart_active_led(reader, runner=runner)
    assert ok is False
    assert "failed" in msg.lower()


def test_restart_active_led_reports_failure_on_exception():
    reader = MagicMock()
    reader.active_led_service.return_value = {"key": "voidex", "unit": "voidex.service", "name": "Voidex"}
    runner = MagicMock(side_effect=OSError("boom"))
    ok, msg = system.restart_active_led(reader, runner=runner)
    assert ok is False
    assert "failed" in msg.lower()


# ---------- reboot ----------

def test_reboot_calls_reboot_binary():
    runner = MagicMock(return_value=subprocess.CompletedProcess([], 0))
    ok, _ = system.reboot(runner=runner)
    assert ok is True
    runner.assert_called_once()
    assert runner.call_args[0][0] == ["/sbin/reboot"]


def test_reboot_reports_failure_on_exception():
    runner = MagicMock(side_effect=OSError("denied"))
    ok, msg = system.reboot(runner=runner)
    assert ok is False
    assert "failed" in msg.lower()


# ---------- shutdown ----------

def test_shutdown_calls_shutdown_binary_with_halt_now():
    runner = MagicMock(return_value=subprocess.CompletedProcess([], 0))
    ok, _ = system.shutdown(runner=runner)
    assert ok is True
    runner.assert_called_once()
    assert runner.call_args[0][0] == ["/sbin/shutdown", "-h", "now"]


def test_shutdown_reports_failure_on_exception():
    runner = MagicMock(side_effect=OSError("denied"))
    ok, msg = system.shutdown(runner=runner)
    assert ok is False
    assert "failed" in msg.lower()
