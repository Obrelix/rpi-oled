"""The three destructive system actions. All take an injectable runner
(defaulting to subprocess.run) for testability."""
from __future__ import annotations

import subprocess
from typing import Callable


Runner = Callable[..., subprocess.CompletedProcess]


def _run_checked(cmd: list[str], runner: Runner) -> tuple[bool, str]:
    """Run cmd; return (success, detail)."""
    try:
        result = runner(cmd, capture_output=True, text=True, timeout=10.0)
        if result.returncode == 0:
            return True, ""
        return False, (result.stderr or "").strip() or f"exit {result.returncode}"
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)


def restart_active_led(
    services_reader,
    runner: Runner = subprocess.run,
) -> tuple[bool, str]:
    active = services_reader.active_led_service()
    if not active:
        return False, "No active LED service"
    ok, err = _run_checked(["systemctl", "restart", active["unit"]], runner)
    if ok:
        return True, f"Restarted {active['name']}"
    return False, f"Restart failed: {err}" if err else "Restart failed"


def reboot(runner: Runner = subprocess.run) -> tuple[bool, str]:
    ok, err = _run_checked(["/sbin/reboot"], runner)
    return (True, "Rebooting\u2026") if ok else (False, f"Reboot failed: {err}" if err else "Reboot failed")


def shutdown(runner: Runner = subprocess.run) -> tuple[bool, str]:
    ok, err = _run_checked(["/sbin/shutdown", "-h", "now"], runner)
    return (True, "Shutting down\u2026") if ok else (False, f"Shutdown failed: {err}" if err else "Shutdown failed")
