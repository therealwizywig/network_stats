#!/usr/bin/env bash
# Usage:
#   ./manage_crons.sh update   — install/refresh cron jobs from targets.json
#   ./manage_crons.sh remove   — remove all network_stats cron jobs

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTION="${1:-update}"

# Strip any existing network_stats cron entries
CLEAN_CRONTAB=$(crontab -l 2>/dev/null | grep -v "network_stats/monitor.py\|network_stats/dns_benchmark.py\|network_stats/power_tracker.sh" || true)

if [ "$ACTION" = "remove" ]; then
    echo "$CLEAN_CRONTAB" | crontab -
    echo "[✓] All network_stats cron jobs removed."
    exit 0
fi

# Read interval from targets.json
MONITOR_INTERVAL=$(python3 -c "
import json
with open('$SCRIPT_DIR/targets.json') as f:
    d = json.load(f)
print(d.get('monitor_interval_minutes', 5))
")

echo "$CLEAN_CRONTAB
@reboot /bin/bash $SCRIPT_DIR/power_tracker.sh --boot
* * * * * /bin/bash $SCRIPT_DIR/power_tracker.sh
*/$MONITOR_INTERVAL * * * * /usr/bin/python3 $SCRIPT_DIR/monitor.py
*/$MONITOR_INTERVAL * * * * /usr/bin/python3 $SCRIPT_DIR/dns_benchmark.py" | crontab -

echo "[✓] Cron jobs updated:"
echo "    power_tracker  — @reboot + every minute"
echo "    monitor.py     — every $MONITOR_INTERVAL minutes"
echo "    dns_benchmark  — every $MONITOR_INTERVAL minutes"
