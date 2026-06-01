#!/usr/bin/env bash
set -e

echo "==========================================="
echo "   Raspberry Pi Network Suite Setup"
echo "==========================================="

# 1. Ask for Device ID
DEFAULT_ID="test-device-01"
read -rp "Enter unique Device ID [Press Enter for '$DEFAULT_ID']: " USER_ID
DEVICE_ID=${USER_ID:-$DEFAULT_ID}

# 2. Save Configuration File
CONFIG_FILE="$HOME/network_stats/device_env.conf"
mkdir -p "$(dirname "$CONFIG_FILE")"
echo "DEVICE_ID=\"$DEVICE_ID\"" > "$CONFIG_FILE"
echo "[✓] Configuration saved to $CONFIG_FILE"
echo "    (You can manually edit this file at any time to change the ID)"

echo "-------------------------------------------"
echo "Provisioning System Dependencies..."
echo "-------------------------------------------"

# 3. Core Updates and Repo Additions
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl gnupg git python3-pip python3-requests

# Install official Ookla speedtest CLI
curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash
sudo apt-get install -y speedtest

# 4. Install and configure ZeroTier-One securely
if ! command -v zerotier-cli &> /dev/null; then
    curl -s https://raw.githubusercontent.com/zerotier/ZeroTierOne/master/doc/contact%40zerotier.com.gpg | gpg --dearmor | sudo tee /usr/share/keyrings/zerotier-archive-keyring.gpg >/dev/null
    echo "deb [signed-by=/usr/share/keyrings/zerotier-archive-keyring.gpg] http://download.zerotier.com/debian/bookworm bookworm main" | sudo tee /etc/apt/sources.list.d/zerotier.list
    sudo apt update && sudo apt install -y zerotier-one
fi

sudo systemctl enable zerotier-one
sudo systemctl start zerotier-one

echo "[✓] Core systems ready. Joining ZeroTier network..."
sudo zerotier-cli join 633e31d8a24687c7

# 5. Clone Target Git Repo
REPO_DIR="$HOME/network_stats/repo"
if [ ! -d "$REPO_DIR" ]; then
    GIT_TERMINAL_PROMPT=0 git clone https://github.com/therealwizywig/network_stats.git "$REPO_DIR"
fi

# 6. Install systemd services
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sudo cp "$SCRIPT_DIR/services/power_tracker.service" /etc/systemd/system/power_tracker.service
sudo systemctl daemon-reload
sudo systemctl enable power_tracker.service
sudo systemctl start power_tracker.service
echo "[✓] power_tracker service installed and started"

echo "==========================================="
echo " SETUP COMPLETE"
echo " Run 'cat $CONFIG_FILE' to check identity metadata."
echo "==========================================="
