"""Runtime configuration for rpi-oled. All tunables live here."""
from pathlib import Path

# ---------- Hardware ----------

# I2C OLED
I2C_BUS = 1
I2C_ADDRESS = 0x3C  # fallback 0x3D if primary not found
OLED_WIDTH = 128
OLED_HEIGHT = 64

# Rotary encoder (BCM GPIO numbers)
ENCODER_CLK_PIN = 25
ENCODER_DT_PIN = 19
ENCODER_SW_PIN = 7

# ---------- Paths ----------

# rpi-hub's service registry (read-only)
RPI_HUB_SERVICES_JSON = Path("/home/obrelix/rpi-hub/services.json")

# Synthetic services always shown on the Services page (not in rpi-hub's registry)
SYNTHETIC_SERVICES = [
    {"key": "rpi-hub", "name": "RPi Hub", "unit": "rpi-hub.service"},
    {"key": "rpi-oled", "name": "RPi OLED", "unit": "rpi-oled.service"},
]

# ---------- Timing ----------

TICK_HZ = 2                       # main loop refresh rate
TICK_INTERVAL = 1.0 / TICK_HZ     # seconds

STATS_CACHE_TTL = 1.0             # /proc cache age (s)
HOST_CACHE_TTL = 10.0             # hostname/ip/ssid cache age (s)
SERVICES_CACHE_TTL = 2.0          # systemctl cache age (s)
SYSTEMCTL_TIMEOUT = 2.0           # per-call timeout (s)

# ---------- UX ----------

DIM_THRESHOLD_SEC = 120           # 2 min idle → dim
BLANK_THRESHOLD_SEC = 600         # 10 min idle → blank

DIM_CONTRAST = 32                 # 0-255 (full=255)
FULL_CONTRAST = 255

PIXEL_SHIFT_INTERVAL_SEC = 60     # cycle origin offset every minute
PIXEL_SHIFT_SEQUENCE = [(0, 0), (1, 0), (1, 1), (0, 1)]

SHORT_PRESS_MAX_SEC = 0.4         # <400ms = short
LONG_PRESS_MIN_SEC = 0.8          # >800ms = long

TOAST_DURATION_SEC = 2.0
ERROR_TOAST_DURATION_SEC = 3.0

# ---------- Pages ----------

PAGE_MARGIN = 6                   # px — reserves headroom for pixel shift

MENU_ITEMS = ["Restart active LED", "Reboot Pi", "Shutdown Pi", "Cancel"]
MENU_CANCEL_INDEX = 3             # short-press on Cancel returns to PAGE
LED_PANEL_GROUP = "led-panel"     # group name for mutual-exclusion services
