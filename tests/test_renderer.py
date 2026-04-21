from PIL import Image, ImageDraw

from display import renderer


def _make_canvas():
    img = Image.new("1", (128, 64), 0)
    return img, ImageDraw.Draw(img)


def test_get_small_font_returns_usable_font():
    font = renderer.get_small_font()
    assert font is not None
    # Pillow fonts expose .getbbox or .getlength
    assert hasattr(font, "getbbox") or hasattr(font, "getsize")


def test_get_big_font_returns_usable_font():
    font = renderer.get_big_font()
    assert font is not None


def test_draw_status_dot_filled_sets_pixels():
    img, draw = _make_canvas()
    renderer.draw_status_dot(draw, 10, 10, active=True)
    # active dot must draw at least one lit pixel near (10, 10)
    pixels_lit = sum(1 for x in range(8, 15) for y in range(8, 15) if img.getpixel((x, y)))
    assert pixels_lit > 0


def test_draw_status_dot_inactive_is_circle_outline():
    img, draw = _make_canvas()
    renderer.draw_status_dot(draw, 10, 10, active=False)
    # outline should have lit pixels
    pixels_lit = sum(1 for x in range(6, 16) for y in range(6, 16) if img.getpixel((x, y)))
    assert pixels_lit > 0


def test_draw_progress_bar_fills_proportion():
    img, draw = _make_canvas()
    renderer.draw_progress_bar(draw, x=0, y=0, width=100, height=6, pct=50.0)
    # row 2 should be lit across about half the width
    lit_in_left_half = sum(1 for x in range(0, 50) if img.getpixel((x, 2)))
    lit_in_right_half = sum(1 for x in range(60, 100) if img.getpixel((x, 2)))
    assert lit_in_left_half > lit_in_right_half


def test_text_right_aligned_places_text_flush_right():
    img, draw = _make_canvas()
    font = renderer.get_small_font()
    renderer.text_right_aligned(draw, x_right=120, y=10, text="hello", font=font)
    # rightmost lit pixel should be near x_right
    rightmost = 0
    for x in range(128):
        for y in range(0, 30):
            if img.getpixel((x, y)):
                rightmost = max(rightmost, x)
    assert rightmost <= 120 and rightmost >= 100
