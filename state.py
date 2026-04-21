"""Pure state machine for rpi-oled. No I/O — fully testable."""
from __future__ import annotations

from enum import Enum
from threading import Lock
from typing import Optional

import config


PAGE_COUNT = 6  # Home, CPU, Memory, Network, Services, Clock


class Mode(Enum):
    PAGE = "page"
    MENU = "menu"
    CONFIRM = "confirm"


class AppState:
    def __init__(self) -> None:
        self._lock = Lock()
        self.mode: Mode = Mode.PAGE
        self.page_idx: int = 0
        self.menu_idx: int = 0
        self.confirm_idx: int = 0  # which menu item is being confirmed
        self.idle_elapsed: float = 0.0
        self.needs_redraw: bool = True
        self._pixel_shift_elapsed: float = 0.0
        self._pixel_shift_idx: int = 0

    # ---------- Properties ----------

    @property
    def display_state(self) -> str:
        if self.idle_elapsed >= config.BLANK_THRESHOLD_SEC:
            return "blank"
        if self.idle_elapsed >= config.DIM_THRESHOLD_SEC:
            return "dim"
        return "full"

    @property
    def pixel_shift_offset(self) -> tuple[int, int]:
        return config.PIXEL_SHIFT_SEQUENCE[self._pixel_shift_idx]

    # ---------- Lifecycle ----------

    def mark_drawn(self) -> None:
        with self._lock:
            self.needs_redraw = False

    def tick(self, dt: float) -> None:
        """Advance timers by dt seconds. Called from the main loop."""
        with self._lock:
            self.idle_elapsed += dt
            self._pixel_shift_elapsed += dt
            if self._pixel_shift_elapsed >= config.PIXEL_SHIFT_INTERVAL_SEC:
                self._pixel_shift_elapsed = 0.0
                self._pixel_shift_idx = (self._pixel_shift_idx + 1) % len(config.PIXEL_SHIFT_SEQUENCE)
                self.needs_redraw = True

    # ---------- Input handlers ----------

    def on_rotate_cw(self) -> Optional[str]:
        return self._handle_rotate(+1)

    def on_rotate_ccw(self) -> Optional[str]:
        return self._handle_rotate(-1)

    def on_short_press(self) -> Optional[str]:
        with self._lock:
            if self._was_blanked_consume_wake():
                return None
            if self.mode == Mode.PAGE:
                self.page_idx = 0  # jump home
                self.needs_redraw = True
                return None
            if self.mode == Mode.MENU:
                if self.menu_idx == config.MENU_CANCEL_INDEX:
                    self.mode = Mode.PAGE
                else:
                    self.confirm_idx = self.menu_idx
                    self.mode = Mode.CONFIRM
                self.needs_redraw = True
                return None
            if self.mode == Mode.CONFIRM:
                self.mode = Mode.PAGE
                self.menu_idx = 0
                self.needs_redraw = True
                return "execute"
        return None

    def on_long_press(self) -> Optional[str]:
        with self._lock:
            if self._was_blanked_consume_wake():
                return None
            if self.mode == Mode.PAGE:
                self.mode = Mode.MENU
                self.menu_idx = 0
            elif self.mode == Mode.MENU:
                self.mode = Mode.PAGE
            elif self.mode == Mode.CONFIRM:
                self.mode = Mode.MENU
            self.needs_redraw = True
        return None

    # ---------- Internal helpers ----------

    def _handle_rotate(self, delta: int) -> Optional[str]:
        with self._lock:
            if self._was_blanked_consume_wake():
                return None
            if self.mode == Mode.PAGE:
                self.page_idx = (self.page_idx + delta) % PAGE_COUNT
            elif self.mode == Mode.MENU:
                self.menu_idx = (self.menu_idx + delta) % len(config.MENU_ITEMS)
            elif self.mode == Mode.CONFIRM:
                self.mode = Mode.MENU  # any rotation aborts
            self.needs_redraw = True
        return None

    def _was_blanked_consume_wake(self) -> bool:
        """If we were blanked, reset idle timer and swallow this event.
        Otherwise, reset idle and return False so the caller processes it."""
        was_blanked = self.idle_elapsed >= config.BLANK_THRESHOLD_SEC
        self.idle_elapsed = 0.0
        self.needs_redraw = True
        return was_blanked
