from PIL import Image, ImageDraw

from display import pages


def _canvas():
    img = Image.new("1", (128, 64), 0)
    return img, ImageDraw.Draw(img)


def _pixels_lit(img: Image.Image) -> int:
    return sum(1 for p in img.getdata() if p)


SAMPLE_DATA = {
    "host": {
        "hostname": "rpi-hub",
        "iface": "wlan0",
        "ip": "192.168.1.201",
        "ssid": "SkyNet-5G",
        "link_mbps": 300,
        "uptime_sec": 3 * 86400 + 2 * 3600,
    },
    "stats": {
        "mem": {"ram_used_mb": 1480, "ram_total_mb": 3840, "ram_percent": 38.5,
                "swap_used_mb": 0, "swap_total_mb": 100, "swap_percent": 0.0},
        "cpu_percent": 14.2,
        "temp_c": 52.3,
        "disk": {"used_mb": 12400, "total_mb": 29800, "percent": 42},
        "net": {"rx_bytes": 142857142, "tx_bytes": 38111111},
    },
    "services": [
        {"key": "rpi-radio", "name": "RPi Radio", "status": "inactive", "group": "led-panel"},
        {"key": "voidex", "name": "Voidex", "status": "active", "group": "led-panel"},
        {"key": "maze-battlegrounds", "name": "Maze", "status": "inactive", "group": "led-panel"},
        {"key": "rpi-hub", "name": "RPi Hub", "status": "active", "group": None},
        {"key": "rpi-oled", "name": "RPi OLED", "status": "active", "group": None},
    ],
    "now": "2026-04-20 14:37:42",
}


def test_home_page_renders_ip_and_hostname():
    img, draw = _canvas()
    pages.HomePage().render(draw, SAMPLE_DATA)
    assert _pixels_lit(img) > 50


def test_cpu_page_renders_non_blank():
    img, draw = _canvas()
    pages.CPUPage().render(draw, SAMPLE_DATA)
    assert _pixels_lit(img) > 50


def test_memory_page_renders_non_blank():
    img, draw = _canvas()
    pages.MemoryPage().render(draw, SAMPLE_DATA)
    assert _pixels_lit(img) > 50


def test_network_page_renders_non_blank():
    img, draw = _canvas()
    pages.NetworkPage().render(draw, SAMPLE_DATA)
    assert _pixels_lit(img) > 50


def test_services_page_renders_one_row_per_service():
    img, draw = _canvas()
    pages.ServicesPage().render(draw, SAMPLE_DATA)
    assert _pixels_lit(img) > 50


def test_clock_page_renders_non_blank():
    img, draw = _canvas()
    pages.ClockPage().render(draw, SAMPLE_DATA)
    assert _pixels_lit(img) > 50


def test_all_pages_have_title():
    for cls in (pages.HomePage, pages.CPUPage, pages.MemoryPage,
                pages.NetworkPage, pages.ServicesPage, pages.ClockPage):
        assert isinstance(cls().title, str) and cls().title


def test_pages_list_has_six_entries_in_order():
    assert len(pages.ALL_PAGES) == 6
    assert pages.ALL_PAGES[0].__class__.__name__ == "HomePage"
    assert pages.ALL_PAGES[5].__class__.__name__ == "ClockPage"


def test_page_handles_missing_optional_data():
    """Pages must not crash if some data is None (e.g. SSID on eth0)."""
    minimal = {
        "host": {"hostname": "x", "iface": None, "ip": None, "ssid": None,
                 "link_mbps": None, "uptime_sec": 0},
        "stats": {"mem": {"ram_used_mb": 0, "ram_total_mb": 0, "ram_percent": 0.0,
                          "swap_used_mb": 0, "swap_total_mb": 0, "swap_percent": 0.0},
                  "cpu_percent": 0.0, "temp_c": None,
                  "disk": {"used_mb": 0, "total_mb": 0, "percent": 0},
                  "net": None},
        "services": [],
        "now": "1970-01-01 00:00:00",
    }
    for cls in (pages.HomePage, pages.CPUPage, pages.MemoryPage,
                pages.NetworkPage, pages.ServicesPage, pages.ClockPage):
        img, draw = _canvas()
        cls().render(draw, minimal)  # must not raise
