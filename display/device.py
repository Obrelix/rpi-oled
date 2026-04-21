"""Luma OLED wrapper with SH1106 -> SSD1306 fallback, dim/blank, pixel shift.

Tolerates transient I2C hiccups common on jumper-wired displays: startup
init is retried on OSError, and per-frame write failures are absorbed
with a single rate-limited warning instead of a full stack trace each
time the bus burps.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager

from PIL import Image, ImageDraw

import config

log = logging.getLogger(__name__)

# How long to wait between init retries, and how many times to try before
# giving up and letting systemd restart the whole process.
INIT_RETRY_DELAY_SEC = 1.0
INIT_RETRY_ATTEMPTS = 5

# Suppress repeated I/O warnings at the rate of at most one per interval,
# so a flaky wire doesn't produce hundreds of log lines per minute.
IO_WARN_INTERVAL_SEC = 10.0


class OLEDDevice:
    """Thin wrapper around luma.oled that tries SH1106 first, falls back to SSD1306."""

    def __init__(self, bus: int = config.I2C_BUS, address: int = config.I2C_ADDRESS) -> None:
        # Imports are lazy so unit tests on non-Pi machines don't require these packages.
        from luma.core.interface.serial import i2c
        from luma.oled.device import sh1106, ssd1306

        self._device = None
        self._driver_name = ""
        last_err: Exception | None = None
        for attempt in range(1, INIT_RETRY_ATTEMPTS + 1):
            serial = i2c(port=bus, address=address)
            try:
                self._device = sh1106(serial, width=config.OLED_WIDTH, height=config.OLED_HEIGHT)
                self._driver_name = "SH1106"
                break
            except Exception as e:
                last_err = e
                log.debug("SH1106 init attempt %d failed (%s); trying SSD1306", attempt, e)
                try:
                    self._device = ssd1306(serial, width=config.OLED_WIDTH, height=config.OLED_HEIGHT)
                    self._driver_name = "SSD1306"
                    break
                except Exception as e2:
                    last_err = e2
                    if attempt < INIT_RETRY_ATTEMPTS:
                        log.warning(
                            "OLED init attempt %d/%d failed (%s); retrying in %.1fs",
                            attempt, INIT_RETRY_ATTEMPTS, e2, INIT_RETRY_DELAY_SEC,
                        )
                        time.sleep(INIT_RETRY_DELAY_SEC)

        if self._device is None:
            raise RuntimeError(f"OLED init failed after {INIT_RETRY_ATTEMPTS} attempts: {last_err}")

        log.info("OLED initialized as %s @ 0x%02X", self._driver_name, address)
        self._blanked: bool = False
        self._last_io_warn_at: float = 0.0
        self._io_errors_since_warn: int = 0

    @property
    def driver_name(self) -> str:
        return self._driver_name

    @contextmanager
    def canvas(self, pixel_shift: tuple[int, int] = (0, 0)):
        """Yield a PIL ImageDraw that writes into a buffer, then flush to device.
        Pixel-shift translates the origin so static content doesn't burn in.
        Absorbs transient I/O errors so a flaky bus doesn't crash rendering."""
        img = Image.new("1", (config.OLED_WIDTH, config.OLED_HEIGHT), 0)
        draw = ImageDraw.Draw(img)
        try:
            yield draw
        finally:
            if self._blanked:
                return
            if pixel_shift != (0, 0):
                img = _shift_image(img, *pixel_shift)
            try:
                self._device.display(img)
            except Exception as e:
                self._record_io_error("display", e)

    def set_contrast(self, level: int) -> None:
        """level: 0-255."""
        level = max(0, min(255, level))
        try:
            self._device.contrast(level)
        except Exception as e:
            self._record_io_error("contrast", e)

    def blank(self) -> None:
        if self._blanked:
            return
        try:
            self._device.hide()
        except Exception as e:
            self._record_io_error("hide", e)
        self._blanked = True

    def unblank(self) -> None:
        if not self._blanked:
            return
        try:
            self._device.show()
        except Exception as e:
            self._record_io_error("show", e)
        self._blanked = False

    def _record_io_error(self, op: str, e: Exception) -> None:
        """Warn at most once per IO_WARN_INTERVAL_SEC about transient I2C errors,
        including a suppressed-count so sustained problems are still visible."""
        now = time.monotonic()
        self._io_errors_since_warn += 1
        if (now - self._last_io_warn_at) >= IO_WARN_INTERVAL_SEC:
            log.warning(
                "I2C %s error (%d similar in last %.0fs): %s",
                op, self._io_errors_since_warn, IO_WARN_INTERVAL_SEC, e,
            )
            self._last_io_warn_at = now
            self._io_errors_since_warn = 0


def _shift_image(img: Image.Image, dx: int, dy: int) -> Image.Image:
    """Return a new image with contents translated by (dx, dy)."""
    shifted = Image.new("1", img.size, 0)
    shifted.paste(img, (dx, dy))
    return shifted
