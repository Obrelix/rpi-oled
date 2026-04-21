"""Shared PIL drawing helpers. Pure functions — no device state."""
from __future__ import annotations

from PIL import ImageDraw, ImageFont


_SMALL: ImageFont.ImageFont | None = None
_BIG: ImageFont.ImageFont | None = None


def get_small_font() -> ImageFont.ImageFont:
    """6x8 default bitmap font — always works, no file required."""
    global _SMALL
    if _SMALL is None:
        _SMALL = ImageFont.load_default()
    return _SMALL


def get_big_font():
    """Large font for the clock page. Tries DejaVu first, falls back to default."""
    global _BIG
    if _BIG is None:
        for path in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ):
            try:
                _BIG = ImageFont.truetype(path, 20)
                break
            except OSError:
                continue
        if _BIG is None:
            _BIG = ImageFont.load_default()
    return _BIG


def draw_status_dot(draw: ImageDraw.ImageDraw, x: int, y: int, *, active: bool, radius: int = 3) -> None:
    """Filled circle if active, outlined circle if not."""
    box = (x - radius, y - radius, x + radius, y + radius)
    if active:
        draw.ellipse(box, fill=1)
    else:
        draw.ellipse(box, outline=1, fill=0)


def draw_progress_bar(
    draw: ImageDraw.ImageDraw,
    x: int, y: int, width: int, height: int,
    pct: float,
) -> None:
    """Rect outline + filled portion proportional to pct [0-100]."""
    pct = max(0.0, min(100.0, pct))
    draw.rectangle((x, y, x + width - 1, y + height - 1), outline=1, fill=0)
    fill_w = int((width - 2) * (pct / 100.0))
    if fill_w > 0:
        draw.rectangle((x + 1, y + 1, x + fill_w, y + height - 2), fill=1)


def text_right_aligned(
    draw: ImageDraw.ImageDraw,
    x_right: int, y: int, text: str, font,
) -> None:
    """Draw text so its right edge lands at x_right."""
    w = _text_width(draw, text, font)
    draw.text((x_right - w, y), text, font=font, fill=1)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    # Pillow 10+ uses textbbox; older uses textsize
    try:
        box = draw.textbbox((0, 0), text, font=font)
        return box[2] - box[0]
    except AttributeError:
        return draw.textsize(text, font=font)[0]
