# rpi-oled — Design Spec

**Date:** 2026-04-20
**Status:** Approved, ready for implementation planning
**Repo:** https://github.com/Obrelix/rpi-oled (new)
**Deploy target:** `/home/obrelix/rpi-oled` on the Pi at `192.168.1.201`

---

## 1. Purpose

A small always-on status display for the Raspberry Pi that currently runs rpi-hub. A 1.3" monochrome OLED shows glanceable system information (IP, CPU, temp, active LED-panel service, etc.); a rotary encoder lets the user cycle pages and trigger a small set of system actions (restart active LED service, reboot, shutdown) without leaving the room.

The daemon is **independent** of `rpi-hub.service` — it reads system state directly from `/proc`, `/sys`, and `systemctl`, and uses `rpi-hub`'s `services.json` only as a read-only service registry. It keeps working if the hub crashes. The hub manages it like any other service entry (start/stop/restart/deploy from the dashboard).

---

## 2. Hardware

### 2.1 Components

| Component | Part | Interface |
|---|---|---|
| Display | 1.3" monochrome OLED, 128×64, SH1106 driver (with SSD1306 auto-fallback for clone modules) | I2C |
| Input | HD-040 / KY-040 rotary encoder with integrated push-button | 3× GPIO (CLK, DT, SW) |
| Host | Raspberry Pi 4 (4 GB) with Adafruit 3211 RGB Matrix Bonnet in "quality" configuration (GPIO 4↔18 bridged) driving a 128×64 P2.5 HUB75 panel | — |

### 2.2 Pin plan

The 3211 Bonnet in quality mode consumes GPIOs **4, 5, 6, 12, 13, 16, 17, 18, 20, 21, 22, 23, 24, 26, 27**. The pins used below are all confirmed free and exposed on the Bonnet's labeled breakout.

| Device | Device pin | Bonnet label | Pi BCM | Pi physical pin |
|---|---|---|---|---|
| OLED | VDD | `3.3V` | — | 1 |
| OLED | GND | `GND` | — | 6 |
| OLED | SDA | `SDA` | GPIO 2 | 3 |
| OLED | SCK | `SCL` | GPIO 3 | 5 |
| Encoder | `+` | `3.3V` | — | 17 |
| Encoder | GND | `GND` | — | 9 |
| Encoder | CLK | `25` | GPIO 25 | 22 |
| Encoder | DT | `19` | GPIO 19 | 35 |
| Encoder | SW | `CE1` | GPIO 7 | 26 |

**Power rule:** the encoder `+` pin **must** be 3.3 V. The KY-040 / HD-040 pulls CLK/DT/SW up to VCC; 5 V would over-voltage the Pi's 3.3 V GPIO inputs.

### 2.3 Interference analysis

- **No EMI risk.** Mechanical encoder transitions are <100 Hz; negligible compared to the matrix's tens-of-MHz GPIO clock.
- **No CPU contention.** rpi-rgb-led-matrix is pinned to CPU 3 via `isolcpus=3`; encoder interrupts and the OLED I2C loop run on cores 0–2.
- **No register contention.** The matrix library touches only GPIO bits 4–27 that it owns; I2C0 (GPIO 2/3) and the encoder pins (7/19/25) are independent bits in the same register bank and are accessed atomically by standard kernel drivers / gpiozero.
- **Residual risk:** switch bounce on encoder contacts generates spurious edges per detent. This is a local debouncing concern handled by `gpiozero.RotaryEncoder`; not a system-level issue.

---

## 3. Architecture

### 3.1 Runtime

- **Language:** Python 3 (Pi OS Bookworm ships 3.11).
- **Process model:** single systemd-managed daemon, `rpi-oled.service`, running as root (matches rpi-hub; simplifies `systemctl restart`, `reboot`, `shutdown` permissions).
- **Isolation:** code runs in a venv at `/home/obrelix/rpi-oled/venv` to satisfy PEP 668 on Bookworm.
- **Dependencies:** `luma.oled`, `gpiozero`, `pillow`, `pytest`. `gpiozero` uses the `lgpio` backend by default on Bookworm.

### 3.2 File layout

```
rpi-oled/
├── main.py                   # Entry point, event loop, wiring
├── config.py                 # Pins, timeouts, I2C bus/address, paths
├── state.py                  # App state machine: page idx, mode, dim/sleep, menu
├── display/
│   ├── __init__.py
│   ├── device.py             # Luma init, SH1106→SSD1306 auto-fallback, pixel-shift origin
│   ├── renderer.py           # Shared text/icon helpers
│   ├── pages.py              # 6 Page classes: Home, CPU, Memory, Network, Services, Clock
│   └── menu.py               # Action menu + confirm dialog
├── input/
│   ├── __init__.py
│   └── encoder.py            # gpiozero wrapper → high-level events
├── data/
│   ├── __init__.py
│   ├── host.py               # hostname, uptime, IP, SSID, link speed
│   ├── stats.py              # /proc/stat, /proc/meminfo, thermal, net bytes, disk
│   └── services.py           # reads rpi-hub/services.json, queries systemctl is-active
├── actions/
│   ├── __init__.py
│   └── system.py             # restart_active_led / reboot / shutdown
├── tests/
│   ├── test_stats.py
│   ├── test_host.py
│   ├── test_services.py
│   ├── test_state.py
│   ├── test_pages.py
│   └── test_actions.py
├── requirements.txt
├── rpi-oled.service          # systemd unit
├── install.sh                # apt deps + venv + pip install + systemd enable
├── README.md
└── docs/superpowers/specs/
    └── 2026-04-20-rpi-oled-design.md   # this file
```

### 3.3 Module boundaries

Every module has one purpose and is testable in isolation.

| Module | Purpose | Depends on |
|---|---|---|
| `config` | Pin numbers, timeouts, paths, cache TTLs | — |
| `state` | Pure app state machine. No I/O. | `config` |
| `data/host`, `data/stats`, `data/services` | Read-only system facts. Pure parsers + thin subprocess wrappers. | stdlib only |
| `display/device` | Init OLED over I2C; expose `canvas()` context manager; pixel-shift; dim/blank | `luma.oled`, PIL |
| `display/renderer` | Font loading, text layout helpers, status-dot glyph | PIL |
| `display/pages` | One class per page, each with `.title` and `.render(draw, data)` | `display/renderer` |
| `display/menu` | Action menu rendering + confirm dialog | `display/renderer` |
| `input/encoder` | `gpiozero` wrapper that emits `rotate_cw`, `rotate_ccw`, `short_press`, `long_press` | `gpiozero` |
| `actions/system` | Named action functions with subprocess calls and error handling | `data/services` |
| `main` | Wires everything; 2 Hz tick; dispatches input events to `state`; asks pages/menu to render | all above |

---

## 4. Data Flow

### 4.1 Runtime loop

Two threads:

1. **Main thread** — 2 Hz tick (500 ms). Refreshes cached stats if stale, asks the active page (or menu) to render, pushes to OLED.
2. **gpiozero callback thread** — raises on every encoder event, updates `state`, sets a `needs_redraw` flag.

Both mutate `state` under a `threading.Lock`. Only `main` calls the OLED driver.

### 4.2 Cache TTLs

| Source | TTL | Rationale |
|---|---|---|
| `data.stats` (CPU, memory, temp, disk, net) | 1 s | CPU% is a delta over 1 s anyway |
| `data.host` (hostname, IP, SSID, link) | 10 s | Rarely changes |
| `data.services` (systemctl is-active) | 2 s | Subprocess cost; enough for live-feel |
| Clock page | forced tick every 1 s | Seconds must tick |

### 4.3 ASCII diagram

```
+-------------+                           +----------------+
| HD-040      |---GPIO IRQ--------------->| input/encoder  |
| encoder     |                           |  → events      |
+-------------+                           +-------+--------+
                                                  │
                                                  ▼
+-------------+ read   +--------------+    +-------------+
| /proc, /sys |<-------| data.stats   |<--►|   state     |
+-------------+        | data.host    |    |  (locked)   |
+-------------+        | data.services|    +------+------+
| services.json|<------+--------------+           │
| (rpi-hub)   |                                   ▼
+-------------+                            +-------------+
+-------------+        +--------------+    | active      |
| systemctl   |<-------| subprocess   |<-->| page/menu   |
+-------------+        +--------------+    +------+------+
                                                  │ render(draw, data)
                                                  ▼
                                           +-------------+
                                           | display     |
                                           |  device     |
                                           |  + shift    |
                                           |  + dim/off  |
                                           +------+------+
                                                  │ I2C
                                                  ▼
                                           [ 1.3" OLED ]
```

---

## 5. State Machine

### 5.1 Modes

```
    ┌──────────────── short press ─────────────────┐
    │                                              ▼
  PAGE ── long press ──▶ MENU ── short press ──▶ CONFIRM ── short press ──▶ execute, back to PAGE
    │                     │                        │
    │                     └── rotate ──▶ cycle menu items
    │                                              │
    │                                              └── rotate ──▶ back to MENU
    │
    └── rotate ──▶ prev/next page (wraps)
```

- **PAGE** is the default mode on startup and after any action.
- In **PAGE**: rotate = prev/next page with wrap; short-press = jump to Home (page 0); long-press = enter MENU.
- In **MENU**: rotate = prev/next menu item; short-press on an action item (idx 0–2) = enter CONFIRM; short-press on **Cancel** (idx 3) = back to PAGE directly, no CONFIRM; long-press = back to PAGE.
- In **CONFIRM**: short-press = execute the action; rotate (either direction) = back to MENU.

### 5.2 Menu items (fixed order)

| Idx | Item | Action |
|---|---|---|
| 0 | Restart active LED | `actions.system.restart_active_led()` |
| 1 | Reboot Pi | `actions.system.reboot()` |
| 2 | Shutdown Pi | `actions.system.shutdown()` |
| 3 | Cancel | Return to PAGE |

### 5.3 Dim / blank

| Idle duration | Behavior |
|---|---|
| 0–2 min | Full contrast |
| 2–10 min | Dimmed (contrast ≈ 32/255) |
| ≥ 10 min | Blanked (`device.hide()`) |

Any encoder event resets the idle timer and restores full contrast. A rotation while blanked counts as the wake event but does not advance the page on that first motion (prevents unintended nav on wake). A press while blanked wakes without triggering the press action.

### 5.4 Pixel shift

Origin `(x, y)` offset cycles through `{(0,0), (1,0), (1,1), (0,1)}`, advancing every 60 s. Applied to the draw origin inside `display/device.canvas()` so pages don't know about it. Page layouts reserve a 2 px margin on all sides.

---

## 6. Pages

All 6 pages render into a 128×64 canvas. Layout uses a 6 px margin left/top for pixel shift headroom (2 px shift + 4 px safety).

### 6.1 Home (idx 0)

```
┌──────────────────────────────────┐
│ ● voidex           uptime: 3d 2h │   ← active service + dot, uptime
│                                  │
│   hostname: rpi-hub              │
│   ip: 192.168.1.201              │
│                                  │
│ cpu 14%    mem 38%    temp 52°C  │   ← compact stats footer
└──────────────────────────────────┘
```
Filled dot `●` = at least one LED-panel service is running; empty `○` = none.

### 6.2 CPU (idx 1)

```
┌──────────────────────────────────┐
│ CPU                              │
│                                  │
│ usage:  14%                      │
│ temp:   52.3 °C                  │
│ load:   0.21 / 0.15 / 0.10       │
│                                  │
│ freq:   1500 MHz                 │
└──────────────────────────────────┘
```

### 6.3 Memory (idx 2)

```
┌──────────────────────────────────┐
│ MEMORY                           │
│                                  │
│ ram:   1480 / 3840 MB  (38%)     │
│ swap:     0 /  100 MB   (0%)     │
│ disk:  12.4 / 29.3 GB  (42%)     │
└──────────────────────────────────┘
```

### 6.4 Network (idx 3)

```
┌──────────────────────────────────┐
│ NETWORK                          │
│                                  │
│ iface: wlan0                     │
│ ip:    192.168.1.201             │
│ ssid:  SkyNet-5G                 │
│ link:  300 Mbps                  │
│ rx/tx: 142M / 38M                │
└──────────────────────────────────┘
```

### 6.5 Services (idx 4)

```
┌──────────────────────────────────┐
│ SERVICES                         │
│ ● voidex                         │
│ ○ rpi-radio                      │
│ ○ maze-battlegrounds             │
│ ○ rpi-signboard                  │
│ ● rpi-hub                        │
│ ● rpi-oled                       │
└──────────────────────────────────┘
```
One row per service in `services.json`, plus `rpi-hub.service` and `rpi-oled.service` added synthetically by `data/services.py` (neither is in the hub's registry since the hub doesn't manage itself). `●` = active, `○` = inactive, `?` = unknown (systemctl call failed). If the list exceeds 6 rows, the page scrolls automatically on a 4 s cycle.

### 6.6 Clock (idx 5)

```
┌──────────────────────────────────┐
│                                  │
│        14:37:42                  │   ← large font
│                                  │
│     Mon 20 Apr 2026              │
│                                  │
└──────────────────────────────────┘
```

---

## 7. Actions

### 7.1 `restart_active_led()`

1. Load `/home/obrelix/rpi-hub/services.json`.
2. Collect entries where `group == "led-panel"`.
3. For each, run `systemctl is-active <unit>` with 2 s timeout.
4. Pick the first returning `active`.
5. Run `systemctl restart <unit>`.
6. On success: toast "Restarted <name>" for 2 s, back to PAGE.
7. If none active: toast "No active LED service" for 2 s.
8. If subprocess fails: toast "Restart failed" for 3 s.

### 7.2 `reboot()`

`subprocess.Popen(["/sbin/reboot"])`. No output expected — the daemon dies with the system.

### 7.3 `shutdown()`

`subprocess.Popen(["/sbin/shutdown", "-h", "now"])`. Same.

All three actions are invoked only from the CONFIRM mode, ensuring at least two deliberate encoder events (long press → short press to select → short press to confirm) before anything fires.

---

## 8. Error Handling

| Failure | Behavior |
|---|---|
| I2C device not found at `0x3C`/`0x3D` on startup | Log error, `sys.exit(1)`. systemd restarts after 5 s. `StartLimitBurst=10` / `StartLimitIntervalSec=300` — after 10 failures in 5 min, systemd stops retrying. |
| SH1106 initializes but renders garbled | On first frame corruption heuristic (not easily detected) — mitigated by trying SSD1306 as a fallback if the initial I2C probe suggests it (address `0x3C` with no SH1106-specific init response). In practice: try SH1106 first; if any driver exception occurs in the first 3 s, retry as SSD1306. |
| `gpiozero` import fails or GPIO unavailable | Log warning, enter "display-only" mode — auto-cycle pages every 5 s so the screen is still useful. |
| `/proc` / `/sys` read fails | Return `None` from parser; pages render `--` or `N/A` for that field. No crash. |
| `systemctl` subprocess timeout (>2 s) | Mark status `?` for that unit; cache the result until next TTL. |
| `services.json` missing or invalid JSON | Log warning once per startup; Services page shows "hub registry unavailable". Other pages unaffected. |
| Action subprocess fails (permission denied, unit masked, etc.) | Catch, toast "Action failed" for 3 s, return to PAGE. |
| Exception inside `page.render()` | Catch in main loop, log, display "Render error: <page>" for 3 s, advance state to Home, continue. |
| Unhandled exception in event loop | Log with traceback, `sys.exit(2)`. systemd restarts per above policy. |

---

## 9. Testing

Mirrors rpi-hub's approach. Every test runs on Windows and Pi without hardware.

| Suite | File | What it covers | Mocks |
|---|---|---|---|
| Parsers | `tests/test_stats.py` | `parse_meminfo`, `parse_cpu_percent`, `parse_thermal`, `parse_df`, `parse_net_bytes` — pure functions | None |
| Host info | `tests/test_host.py` | Hostname, uptime, primary IP selection, SSID extraction | `subprocess.run` |
| Services | `tests/test_services.py` | Reads fixture `services.json`, filters by group, maps systemctl output to state | `subprocess.run`, fixture JSON |
| State machine | `tests/test_state.py` | Dispatch synthetic encoder events: rotate, short-press, long-press in every mode; assert resulting page idx, mode, menu idx, idle timer | None (pure) |
| Page render | `tests/test_pages.py` | For each page: instantiate, call `.render(draw, fake_data)` on a `PIL.Image(mode="1", size=(128,64))`, assert non-blank + checksum matches baseline | PIL canvas |
| Actions | `tests/test_actions.py` | `restart_active_led` picks active unit correctly; reboot/shutdown call right binary | `subprocess.run`, fixture JSON |

**Coverage targets:** parsers + state machine: 100%. Actions / services / host: ≥80%. Pages: smoke (non-blank render).

Run: `pytest -v` from repo root.

---

## 10. Deployment

### 10.1 `install.sh`

```bash
#!/bin/bash
set -e
sudo apt update
sudo apt install -y python3-pip python3-venv i2c-tools libjpeg-dev libopenjp2-7
sudo raspi-config nonint do_i2c 0

python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

sudo cp rpi-oled.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rpi-oled.service
sudo systemctl start rpi-oled.service

echo "rpi-oled installed. Status:"
sudo systemctl status rpi-oled.service --no-pager
```

### 10.2 `rpi-oled.service`

```ini
[Unit]
Description=RPi OLED - status display daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=/home/obrelix/rpi-oled/venv/bin/python /home/obrelix/rpi-oled/main.py
WorkingDirectory=/home/obrelix/rpi-oled
Restart=on-failure
RestartSec=5
StartLimitBurst=10
StartLimitIntervalSec=300

[Install]
WantedBy=multi-user.target
```

### 10.3 `requirements.txt`

```
luma.oled>=3.12
gpiozero>=2.0
pillow>=10.0
pytest>=8.0
```

### 10.4 First-time install on the Pi

```bash
ssh obrelix@192.168.1.201
git clone https://github.com/Obrelix/rpi-oled.git
cd rpi-oled
sudo bash install.sh
```

### 10.5 Updates via rpi-hub

The hub's Deploy page already supports `git pull` on any registered service's `deployPath`. After adding the `services.json` entry (section 11), deploy + restart is a two-click operation from the dashboard.

---

## 11. Integration with rpi-hub

Add this entry to `rpi-hub/services.json`:

```json
"rpi-oled": {
  "name": "RPi OLED",
  "unit": "rpi-oled.service",
  "deployPath": "/home/obrelix/rpi-oled",
  "repo": "https://github.com/Obrelix/rpi-oled.git",
  "configFile": "/home/obrelix/rpi-oled/config.py",
  "group": null,
  "description": "1.3\" OLED status display + rotary encoder"
}
```

Key point: `group: null`. The OLED uses I2C and 3 unrelated GPIOs — no conflict with the `led-panel` group (voidex, maze-battlegrounds, rpi-radio, rpi-signboard), so it runs concurrently with any of them.

No other rpi-hub code changes required. The entry makes rpi-oled startable/stoppable/restartable from the hub dashboard and deployable via the Deploy page.

---

## 12. Open Questions / Future Work

Not in scope for v1 but worth noting:

- **Per-page detail drill-in via double-click.** Currently unused; could show per-core CPU on CPU page, per-mount disk on Memory page, etc.
- **Custom pages via config.** Allow user to add simple info pages declaratively (title + list of `/proc` or shell-command data sources) without code changes.
- **Alerts.** Flash screen or invert colors on over-temp / low-disk / service-crash.
- **Web-side OLED preview** inside rpi-hub dashboard — render the current OLED frame as an image for remote monitoring.
- **Hardware button debouncing** via explicit RC filter if the stock KY-040/HD-040 proves too noisy in practice.
