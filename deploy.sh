#!/usr/bin/env bash
# Push updates to all Pi devices over SSH.
# Add each device as: user@zerotier-ip
# Usage: ./deploy.sh

DEVICES=(
    # "speed@10.244.0.2"
    # "speed@10.244.0.3"
)

REMOTE_SCRIPT="/home/speed/network_stats/update.sh"

if [ ${#DEVICES[@]} -eq 0 ]; then
    echo "No devices configured. Add Pi ZeroTier IPs to the DEVICES list in deploy.sh."
    exit 1
fi

PASS=0
FAIL=0

for DEVICE in "${DEVICES[@]}"; do
    echo ""
    echo "━━━ $DEVICE ━━━"
    if ssh -o ConnectTimeout=10 -o BatchMode=yes "$DEVICE" "bash $REMOTE_SCRIPT"; then
        echo "✓ $DEVICE — done"
        ((PASS++))
    else
        echo "✗ $DEVICE — failed"
        ((FAIL++))
    fi
done

echo ""
echo "━━━ Results: $PASS succeeded, $FAIL failed ━━━"
