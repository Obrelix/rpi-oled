#!/bin/bash
set -euo pipefail

echo "=== rpi-oled install ==="

# System packages
sudo apt update
sudo apt install -y python3-pip python3-venv i2c-tools libjpeg-dev libopenjp2-7 fonts-dejavu-core python3-lgpio

# Enable I2C (non-interactive)
sudo raspi-config nonint do_i2c 0

# Python venv + deps
# --system-site-packages lets the venv see python3-lgpio from apt, which
# gpiozero needs for its GPIO backend on Bookworm (no pip equivalent).
python3 -m venv --system-site-packages venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Install systemd unit
sudo cp rpi-oled.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rpi-oled.service
sudo systemctl restart rpi-oled.service

echo
echo "=== status ==="
sudo systemctl status rpi-oled.service --no-pager || true
echo
echo "rpi-oled installed. Follow logs with:  sudo journalctl -u rpi-oled -f"
