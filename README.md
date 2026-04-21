# rpi-oled

A 1.3" I2C OLED status display + rotary encoder companion for a Raspberry Pi running [rpi-hub](https://github.com/Obrelix/rpi-hub). Shows IP, CPU, temperature, service status, clock, and more. Rotary encoder cycles pages; long-press opens an action menu for restarting the active LED-panel service, rebooting, or shutting down.

Runs as a systemd daemon, registered in rpi-hub's `services.json` so it can be start/stopped/restarted/deployed from the hub's dashboard like any other managed service.

## Hardware

- Raspberry Pi 4 (or compatible) with the Adafruit 3211 RGB Matrix Bonnet in quality mode
- 1.3" I2C OLED (SH1106 preferred; SSD1306 auto-fallback)
- KY-040 / HD-040 rotary encoder

### Wiring

All pins below are exposed on the 3211 Bonnet's breakout header and do not conflict with the LED matrix driver.

| Device pin | Bonnet label | Pi BCM | Pi physical |
|---|---|---|---|
| OLED VDD | `3.3V` | — | 1 |
| OLED GND | `GND` | — | 6 |
| OLED SDA | `SDA` | GPIO 2 | 3 |
| OLED SCK | `SCL` | GPIO 3 | 5 |
| Encoder `+` | `3.3V` | — | 17 |
| Encoder GND | `GND` | — | 9 |
| Encoder CLK | `25` | GPIO 25 | 22 |
| Encoder DT | `19` | GPIO 19 | 35 |
| Encoder SW | `CE1` | GPIO 7 | 26 |

**Do not connect the encoder `+` pin to 5 V** — the Pi's GPIO inputs are 3.3 V-only.

## Install (on the Pi)

```bash
git clone https://github.com/Obrelix/rpi-oled.git
cd rpi-oled
sudo bash install.sh
```

Then add this entry to `/home/obrelix/rpi-hub/services.json` so the hub can manage it:

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

## Usage

- **Rotate encoder:** switch between 6 pages (Home → CPU → Memory → Network → Services → Clock, wraps)
- **Short-press encoder button:** jump to Home page
- **Long-press (>0.8 s):** open action menu
  - Rotate to select: Restart active LED / Reboot Pi / Shutdown Pi / Cancel
  - Short-press an action: open confirm dialog
  - Short-press in confirm: execute
  - Rotate in confirm: cancel back to menu

After 2 minutes of idle the display dims; after 10 minutes it blanks. Any encoder motion wakes it.

## Pages

```
HOME              CPU               MEMORY
* voidex  3d 2h   CPU               MEMORY
host: rpi-hub     usage:  14%       ram:  1480/3840 MB
ip: 192.168...    temp:   52.3 C    swap:    0/ 100 MB
cpu 14% ...       [====        ]    disk: 12.4/29.3 GB

NETWORK           SERVICES          CLOCK
NETWORK           SERVICES
iface: wlan0      * voidex              14:37:42
ip: 192.168...    o rpi-radio
ssid: SkyNet      o maze-...         Mon 20 Apr 2026
link: 300 Mbps    * rpi-hub
rx/tx: 142M/38M   * rpi-oled
```

## Development

Runs on Windows + Pi. All tests pass without hardware.

```bash
pip install -r requirements.txt
pytest -v
```

## Architecture

See `docs/superpowers/specs/2026-04-20-rpi-oled-design.md` for the full design spec and `docs/superpowers/plans/2026-04-20-rpi-oled.md` for the implementation plan.
