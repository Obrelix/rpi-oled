"""Six page classes. Each .render(draw, data) call paints one 128x64 canvas.

The data dict shape:
  host:     {hostname, iface, ip, ssid, link_mbps, uptime_sec}
  stats:    {mem, cpu_percent, temp_c, disk, net}
  services: list of {key, name, status, group}
  now:      preformatted timestamp string "YYYY-MM-DD HH:MM:SS"
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from PIL import ImageDraw

import config
from data import host as host_mod
from display import renderer


class Page(ABC):
    title: str = ""

    @abstractmethod
    def render(self, draw: ImageDraw.ImageDraw, data: dict) -> None: ...


def _or_dash(x, fmt: str = "{}") -> str:
    if x is None:
        return "--"
    return fmt.format(x)


# ---------- Page 0: Home ----------

class HomePage(Page):
    title = "HOME"

    def render(self, draw: ImageDraw.ImageDraw, data: dict) -> None:
        f = renderer.get_small_font()
        host_data = data["host"]
        stats = data["stats"]
        services = data["services"]

        # Determine which led-panel service (if any) is active
        active_led = next(
            (s for s in services if s.get("group") == config.LED_PANEL_GROUP and s.get("status") == "active"),
            None,
        )
        active = active_led is not None
        active_name = active_led["name"] if active_led else "no LED svc"

        x0 = config.PAGE_MARGIN
        y = config.PAGE_MARGIN
        # Top row: active service indicator + uptime
        renderer.draw_status_dot(draw, x0 + 3, y + 3, active=active)
        draw.text((x0 + 10, y), active_name, font=f, fill=1)
        renderer.text_right_aligned(
            draw, x_right=128 - config.PAGE_MARGIN, y=y,
            text=host_mod.format_uptime(host_data.get("uptime_sec") or 0),
            font=f,
        )

        # Host / IP
        draw.text((x0, y + 14), f"host: {host_data.get('hostname') or '--'}", font=f, fill=1)
        draw.text((x0, y + 24), f"ip:   {host_data.get('ip') or '--'}", font=f, fill=1)

        # Footer stats — Pillow default font is ~10 px tall, plus 1 px
        # pixel-shift safety, so draw at y=52 to keep the baseline visible.
        cpu = stats.get("cpu_percent", 0.0)
        mem_pct = stats["mem"].get("ram_percent", 0.0)
        temp = stats.get("temp_c")
        footer = f"cpu {int(cpu)}%  mem {int(mem_pct)}%  " + _or_dash(temp, "{:.0f}\u00b0C")
        draw.text((x0, 52), footer, font=f, fill=1)


# ---------- Page 1: CPU ----------

class CPUPage(Page):
    title = "CPU"

    def render(self, draw: ImageDraw.ImageDraw, data: dict) -> None:
        f = renderer.get_small_font()
        x = config.PAGE_MARGIN
        y = config.PAGE_MARGIN
        stats = data["stats"]
        draw.text((x, y), "CPU", font=f, fill=1)
        draw.text((x, y + 14), f"usage: {stats.get('cpu_percent', 0.0):.0f}%", font=f, fill=1)
        temp = stats.get("temp_c")
        draw.text((x, y + 24), f"temp:  {_or_dash(temp, '{:.1f} C')}", font=f, fill=1)
        renderer.draw_progress_bar(draw, x, y + 36, width=116, height=8, pct=stats.get("cpu_percent", 0.0))


# ---------- Page 2: Memory ----------

class MemoryPage(Page):
    title = "MEMORY"

    def render(self, draw: ImageDraw.ImageDraw, data: dict) -> None:
        f = renderer.get_small_font()
        x = config.PAGE_MARGIN
        y = config.PAGE_MARGIN
        mem = data["stats"]["mem"]
        disk = data["stats"]["disk"]
        draw.text((x, y), "MEMORY", font=f, fill=1)
        draw.text((x, y + 14),
                  f"ram:  {mem['ram_used_mb']}/{mem['ram_total_mb']} MB ({int(mem['ram_percent'])}%)",
                  font=f, fill=1)
        draw.text((x, y + 24),
                  f"swap: {mem['swap_used_mb']}/{mem['swap_total_mb']} MB ({int(mem['swap_percent'])}%)",
                  font=f, fill=1)
        disk_used_gb = disk["used_mb"] / 1024.0
        disk_total_gb = disk["total_mb"] / 1024.0
        draw.text((x, y + 34),
                  f"disk: {disk_used_gb:.1f}/{disk_total_gb:.1f} GB ({disk['percent']}%)",
                  font=f, fill=1)


# ---------- Page 3: Network ----------

class NetworkPage(Page):
    title = "NETWORK"

    def render(self, draw: ImageDraw.ImageDraw, data: dict) -> None:
        # Five data lines do not fit at 10 px/line on a 64 px tall canvas,
        # so we drop the `link` row (often "Unknown!" on wifi anyway) and
        # keep iface / ip / ssid / rx-tx on 11 px rows.
        f = renderer.get_small_font()
        x = config.PAGE_MARGIN
        y = config.PAGE_MARGIN
        h = data["host"]
        net = data["stats"].get("net")
        draw.text((x, y), "NETWORK", font=f, fill=1)
        draw.text((x, y + 12), f"iface: {h.get('iface') or '--'}", font=f, fill=1)
        draw.text((x, y + 23), f"ip:    {h.get('ip') or '--'}", font=f, fill=1)
        draw.text((x, y + 34), f"ssid:  {h.get('ssid') or '--'}", font=f, fill=1)
        if net:
            rx_mb = net["rx_bytes"] // 1_000_000
            tx_mb = net["tx_bytes"] // 1_000_000
            draw.text((x, y + 45), f"rx/tx: {rx_mb}M / {tx_mb}M", font=f, fill=1)


# ---------- Page 4: Services ----------

class ServicesPage(Page):
    title = "SERVICES"

    def render(self, draw, data):
        # Pillow default font is ~10 px tall, so 11 px pitch prevents overlap
        # and lets us fit 5 services vertically with no title bar. If the
        # list has more entries than fit, the tail is shown instead of the
        # head so the daemon's own row (rpi-oled) stays visible at the bottom.
        f = renderer.get_small_font()
        x = config.PAGE_MARGIN
        services = data["services"]
        row_pitch = 11
        row_y = config.PAGE_MARGIN
        max_rows = 5
        # Keep the tail: user cares most about rpi-oled / rpi-hub which
        # appear after user-registered services.
        visible = services[-max_rows:] if len(services) > max_rows else services
        for s in visible:
            status = s.get("status", "?")
            if status == "active":
                renderer.draw_status_dot(draw, x + 3, row_y + 5, active=True, radius=3)
            elif status == "inactive":
                renderer.draw_status_dot(draw, x + 3, row_y + 5, active=False, radius=3)
            else:
                draw.text((x, row_y), "?", font=f, fill=1)
            name = s["name"][:18]
            draw.text((x + 10, row_y), name, font=f, fill=1)
            row_y += row_pitch


# ---------- Page 5: Clock ----------

class ClockPage(Page):
    title = "CLOCK"

    def render(self, draw: ImageDraw.ImageDraw, data: dict) -> None:
        now = data.get("now", "")
        # Expected "YYYY-MM-DD HH:MM:SS"
        date_part, _, time_part = now.partition(" ")
        big = renderer.get_big_font()
        small = renderer.get_small_font()

        # Centered big time
        draw.text((8, 8), time_part, font=big, fill=1)
        # Centered small date
        draw.text((16, 44), date_part, font=small, fill=1)


# ---------- Registry ----------

ALL_PAGES: list[Page] = [
    HomePage(),
    CPUPage(),
    MemoryPage(),
    NetworkPage(),
    ServicesPage(),
    ClockPage(),
]
