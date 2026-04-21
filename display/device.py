"""Luma OLED wrapper with SH1106 → SSD1306 fallback, dim/blank, pixel shift."""
from __future__ import annotations

import logging
from contextlib import contextmanager

from PIL import Image, ImageDraw

import config

log = logging.getLogger(__name__)


class OLEDDevice:
    """Thin wrapper around luma.oled that tries SH1106 first, falls back to SSD1306."""

    def __init__(self, bus: int = config.I2C_BUS, address: int = config.I2C_ADDRESS) -> None:
        # Imports are lazy so unit tests on non-Pi machines don't require these packages.
        from luma.core.interface.serial import i2c
        from luma.oled.device import sh1106, ssd1306

        serial = i2c(port=bus, address=address)
        try:
            self._device = sh1106(serial, width=config.OLED_WIDTH, height=config.OLED_HEIGHT)
            self._driver_name = "SH1106"
        except Exception as e:
            log.warning("SH1106 init failed (%s); trying SSD1306", e)
            self._device = ssd1306(serial, width=config.OLED_WIDTH, height=config.OLED_HEIGHT)
            self._driver_name = "SSD1306"
        log.info("OLED initialized as %s @ 0x%02X", self._driver_name, address)

        self._blanked: bool = False

    @property
    def driver_name(self) -> str:
        return self._driver_name

    @contextmanager
    def canvas(self, pixel_shift: tuple[int, int] = (0, 0)):
        """Yield a PIL ImageDraw that writes into a buffer, then flush to device.
        Pixel-shift translates the origin so static content doesn't burn in."""
        img = Image.new("1", (config.OLED_WIDTH, config.OLED_HEIGHT), 0)
        draw = ImageDraw.Draw(img)
        try:
            yield draw
        finally:
            if self._blanked:
                return
            if pixel_shift != (0, 0):
                img = _shift_image(img, *pixel_shift)
            self._device.display(img)

    def set_contrast(self, level: int) -> None:
        """level: 0-255."""
        level = max(0, min(255, level))
        try:
            self._device.contrast(level)
        except Exception as e:
            log.warning("set_contrast failed: %s", e)

    def blank(self) -> None:
        if self._blanked:
            return
        try:
            self._device.hide()
        except Exception:
            pass
        self._blanked = True

    def unblank(self) -> None:
        if not self._blanked:
            return
        try:
            self._device.show()
        except Exception:
            pass
        self._blanked = False


def _shift_image(img: Image.Image, dx: int, dy: int) -> Image.Image:
    """Return a new image with contents translated by (dx, dy)."""
    shifted = Image.new("1", img.size, 0)
    shifted.paste(img, (dx, dy))
    return shifted
