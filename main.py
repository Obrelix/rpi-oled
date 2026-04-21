#!/usr/bin/env python3
"""rpi-oled daemon entry point."""
from __future__ import annotations

import datetime as dt
import logging
import signal
import sys
import time
from typing import Optional

import config
import state as state_mod
from actions import system as actions
from data.host import HostInfoReader
from data.services import ServicesReader
from data.stats import StatsReader
from display import menu as menu_view
from display.pages import ALL_PAGES


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("rpi-oled")


class App:
    def __init__(self) -> None:
        self.state = state_mod.AppState()
        self.stats = StatsReader()
        self.host = HostInfoReader()
        self.services = ServicesReader()
        self.device = self._init_device()
        self.encoder = self._init_encoder()
        self.toast: Optional[tuple[str, float]] = None  # (message, expires_at)
        self._running = True

    def _init_device(self):
        try:
            from display.device import OLEDDevice
            return OLEDDevice()
        except Exception as e:
            log.error("OLED init failed: %s", e)
            sys.exit(1)

    def _init_encoder(self):
        try:
            from input.encoder import Encoder
            return Encoder(callback=self._on_input)
        except Exception as e:
            log.warning("Encoder init failed (%s); running in display-only mode", e)
            from input.encoder import FakeEncoder
            return FakeEncoder(callback=self._on_input)

    def _on_input(self, event: str) -> None:
        handler = {
            "rotate_cw": self.state.on_rotate_cw,
            "rotate_ccw": self.state.on_rotate_ccw,
            "short_press": self.state.on_short_press,
            "long_press": self.state.on_long_press,
        }.get(event)
        if not handler:
            return
        result = handler()
        if result == "execute":
            self._execute_confirmed_action()

    def _execute_confirmed_action(self) -> None:
        idx = self.state.confirm_idx
        if idx == 0:
            ok, msg = actions.restart_active_led(self.services)
        elif idx == 1:
            ok, msg = actions.reboot()
        elif idx == 2:
            ok, msg = actions.shutdown()
        else:
            return
        duration = config.TOAST_DURATION_SEC if ok else config.ERROR_TOAST_DURATION_SEC
        self.toast = (msg, time.monotonic() + duration)
        log.info("Action %d: %s (ok=%s)", idx, msg, ok)

    def _gather_data(self) -> dict:
        return {
            "host": self.host.get(),
            "stats": self.stats.get(iface=self.host.get().get("iface") or "wlan0"),
            "services": self.services.get(),
            "now": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _render(self) -> None:
        # Toast expiry
        now_m = time.monotonic()
        if self.toast and now_m > self.toast[1]:
            self.toast = None
            self.state.needs_redraw = True

        # Apply dim/blank state
        ds = self.state.display_state
        if ds == "blank":
            self.device.blank()
            return
        self.device.unblank()
        self.device.set_contrast(config.DIM_CONTRAST if ds == "dim" else config.FULL_CONTRAST)

        data = self._gather_data()
        with self.device.canvas(pixel_shift=self.state.pixel_shift_offset) as draw:
            if self.toast:
                menu_view.render_toast(draw, self.toast[0])
            elif self.state.mode == state_mod.Mode.MENU:
                menu_view.render_menu(draw, config.MENU_ITEMS, self.state.menu_idx)
            elif self.state.mode == state_mod.Mode.CONFIRM:
                menu_view.render_confirm(draw, config.MENU_ITEMS[self.state.confirm_idx])
            else:
                ALL_PAGES[self.state.page_idx].render(draw, data)
        self.state.mark_drawn()

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self._handle_term)
        signal.signal(signal.SIGINT, self._handle_term)
        last = time.monotonic()
        log.info("rpi-oled started")
        try:
            while self._running:
                now = time.monotonic()
                self.state.tick(now - last)
                last = now
                try:
                    self._render()
                except Exception as e:
                    log.exception("render failed: %s", e)
                time.sleep(config.TICK_INTERVAL)
        finally:
            self._shutdown()

    def _handle_term(self, *_args) -> None:
        log.info("received termination signal")
        self._running = False

    def _shutdown(self) -> None:
        try:
            self.encoder.close()
        except Exception:
            pass
        try:
            self.device.blank()
        except Exception:
            pass
        log.info("rpi-oled stopped")


def main() -> int:
    App().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
