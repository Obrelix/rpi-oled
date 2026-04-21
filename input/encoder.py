"""Rotary encoder + push-button wrapper using gpiozero.

Emits four event strings via a single callback:
  - 'rotate_cw'
  - 'rotate_ccw'
  - 'short_press'
  - 'long_press'
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Optional

import config

log = logging.getLogger(__name__)

EventCallback = Callable[[str], None]


class Encoder:
    """gpiozero-backed rotary encoder + button with short/long press."""

    def __init__(
        self,
        callback: EventCallback,
        clk_pin: int = config.ENCODER_CLK_PIN,
        dt_pin: int = config.ENCODER_DT_PIN,
        sw_pin: int = config.ENCODER_SW_PIN,
    ) -> None:
        from gpiozero import Button, RotaryEncoder

        self._callback = callback
        self._press_start: Optional[float] = None

        self._rotary = RotaryEncoder(a=clk_pin, b=dt_pin, max_steps=0, bounce_time=0.001)
        self._rotary.when_rotated_clockwise = lambda: callback("rotate_cw")
        self._rotary.when_rotated_counter_clockwise = lambda: callback("rotate_ccw")

        self._button = Button(sw_pin, pull_up=True, bounce_time=0.05)
        self._button.when_pressed = self._on_press
        self._button.when_released = self._on_release

        log.info("Encoder initialized (CLK=%d DT=%d SW=%d)", clk_pin, dt_pin, sw_pin)

    def _on_press(self) -> None:
        self._press_start = time.monotonic()

    def _on_release(self) -> None:
        if self._press_start is None:
            return
        held = time.monotonic() - self._press_start
        self._press_start = None
        if held >= config.LONG_PRESS_MIN_SEC:
            self._callback("long_press")
        elif held <= config.SHORT_PRESS_MAX_SEC:
            self._callback("short_press")
        # else: held between 0.4s and 0.8s — ignore as ambiguous

    def close(self) -> None:
        try:
            self._rotary.close()
            self._button.close()
        except Exception:
            pass


class FakeEncoder:
    """Drop-in fallback when GPIO is unavailable (e.g. dev machine).
    Does nothing — caller should handle no-input mode separately."""

    def __init__(self, callback: EventCallback) -> None:
        self._callback = callback
        log.warning("FakeEncoder active — no hardware input")

    def close(self) -> None:
        pass
