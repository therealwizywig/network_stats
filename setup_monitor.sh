#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==========================================="
echo "   Raspberry Pi Network Suite Setup"
echo "==========================================="

# 1. Ask for Device ID
DEFAULT_ID="test-device-01"
read -rp "Enter unique Device ID [Press Enter for '$DEFAULT_ID']: " USER_ID
DEVICE_ID=${USER_ID:-$DEFAULT_ID}

echo "-------------------------------------------"
echo "Provisioning System Dependencies..."
echo "-------------------------------------------"

# 2. Core Updates and Dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl gnupg git python3-pip python3-requests ethtool dnsutils

# Fix bcmgenet driver wedge bug on Pi 4 under heavy network load
sudo ethtool -G eth0 tx 256 2>/dev/null || true
echo 'ACTION=="add", SUBSYSTEM=="net", KERNEL=="eth0", RUN+="/sbin/ethtool -G eth0 tx 256"' \
    | sudo tee /etc/udev/rules.d/99-bcmgenet-fix.rules > /dev/null

# Install official Ookla speedtest CLI
curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash
sudo apt-get install -y speedtest

# 3. Install and configure ZeroTier-One securely
if ! command -v zerotier-cli &> /dev/null; then
    curl -s https://raw.githubusercontent.com/zerotier/ZeroTierOne/master/doc/contact%40zerotier.com.gpg | gpg --dearmor | sudo tee /usr/share/keyrings/zerotier-archive-keyring.gpg >/dev/null
    echo "deb [signed-by=/usr/share/keyrings/zerotier-archive-keyring.gpg] http://download.zerotier.com/debian/bookworm bookworm main" | sudo tee /etc/apt/sources.list.d/zerotier.list
    sudo apt update && sudo apt install -y zerotier-one
fi

sudo systemctl enable zerotier-one
sudo systemctl start zerotier-one

echo "[✓] Core systems ready. Joining ZeroTier network..."
sudo zerotier-cli join 633e31d8a24687c7

# 4. Clone or update repo
NS_DIR="$HOME/network_stats"
if [ -d "$NS_DIR/.git" ]; then
    GIT_TERMINAL_PROMPT=0 git -C "$NS_DIR" pull
else
    GIT_TERMINAL_PROMPT=0 git clone https://github.com/therealwizywig/network_stats.git "$NS_DIR"
fi

# 5. Write Device ID into targets.json
python3 - "$SCRIPT_DIR/targets.json" "$DEVICE_ID" << 'EOF'
import json, sys
path, device_id = sys.argv[1], sys.argv[2]
with open(path, 'r') as f:
    data = json.load(f)
data['device_id'] = device_id
with open(path, 'w') as f:
    json.dump(data, f, indent=4)
EOF
echo "[✓] Device ID '$DEVICE_ID' saved to targets.json"

# 6. Install cron jobs
chmod +x "$SCRIPT_DIR/manage_crons.sh"
bash "$SCRIPT_DIR/manage_crons.sh" update
echo "[✓] Cron jobs installed"

echo "==========================================="
echo " SETUP COMPLETE"
echo " Device ID '$DEVICE_ID' is stored in $SCRIPT_DIR/targets.json"
echo "==========================================="
