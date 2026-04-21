"""Renderers for the action menu, confirm dialog, and toast overlays."""
from __future__ import annotations

from PIL import ImageDraw

import config
from display import renderer


def render_menu(draw: ImageDraw.ImageDraw, items: list[str], selected_idx: int) -> None:
    f = renderer.get_small_font()
    x = config.PAGE_MARGIN
    y = config.PAGE_MARGIN
    draw.text((x, y), "MENU", font=f, fill=1)
    row_y = y + 12
    for i, item in enumerate(items):
        if i == selected_idx:
            draw.rectangle((x - 2, row_y - 1, 128 - config.PAGE_MARGIN, row_y + 9), fill=1)
            draw.text((x, row_y), item, font=f, fill=0)
        else:
            draw.text((x, row_y), item, font=f, fill=1)
        row_y += 11


def render_confirm(draw: ImageDraw.ImageDraw, action_name: str) -> None:
    f = renderer.get_small_font()
    x = config.PAGE_MARGIN
    y = config.PAGE_MARGIN
    draw.text((x, y), "!  CONFIRM", font=f, fill=1)
    draw.text((x, y + 14), action_name, font=f, fill=1)
    draw.text((x, y + 32), "press = execute", font=f, fill=1)
    draw.text((x, y + 44), "rotate = cancel", font=f, fill=1)


def render_toast(draw: ImageDraw.ImageDraw, message: str) -> None:
    f = renderer.get_small_font()
    # Centered-ish in the lower band
    draw.rectangle((4, 24, 124, 40), outline=1, fill=0)
    draw.text((8, 28), message[:20], font=f, fill=1)
