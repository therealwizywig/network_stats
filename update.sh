#!/usr/bin/env bash
# Safely pull the latest code from git, preserving all device-specific settings.
#
# Usage:
#   ./update.sh          — run immediately
#   ./update.sh --auto   — only run if auto_update_interval_days has passed (used by cron)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGETS="$SCRIPT_DIR/targets.json"
LOG_DIR="$SCRIPT_DIR/logs"
TARGETS_BACKUP="/tmp/network_stats_targets_backup.json"
LAST_UPDATE_FILE="$LOG_DIR/last_auto_update.txt"

mkdir -p "$LOG_DIR"

# --- Auto-update interval check ---
if [ "$1" = "--auto" ]; then
    INTERVAL_DAYS=$(python3 -c "
import json
with open('$TARGETS') as f:
    d = json.load(f)
print(d.get('auto_update_interval_days', 7))
")
    INTERVAL_SECS=$(( INTERVAL_DAYS * 86400 ))

    if [ -f "$LAST_UPDATE_FILE" ]; then
        LAST=$(cat "$LAST_UPDATE_FILE")
        NOW=$(date +%s)
        ELAPSED=$(( NOW - LAST ))
        if [ "$ELAPSED" -lt "$INTERVAL_SECS" ]; then
            DAYS_LEFT=$(( (INTERVAL_SECS - ELAPSED) / 86400 ))
            echo "[auto-update] Not due yet — $DAYS_LEFT day(s) until next update."
            exit 0
        fi
    fi
    echo "[auto-update] Due. Running update..."
fi

# --- Save current targets.json before git touches it ---
cp "$TARGETS" "$TARGETS_BACKUP"
echo "[→] Saved current settings."

echo "[→] Pulling latest code..."
git -C "$SCRIPT_DIR" stash 2>/dev/null || true
git -C "$SCRIPT_DIR" pull

# --- Merge: restore device-specific settings into the newly pulled targets.json ---
python3 - "$TARGETS_BACKUP" "$TARGETS" << 'EOF'
import json, sys

backup_path, new_path = sys.argv[1], sys.argv[2]

with open(backup_path) as f:
    old = json.load(f)

with open(new_path) as f:
    new = json.load(f)

# Top-level fields that are per-device and should never be overwritten by a pull
PRESERVE = [
    'device_id',
    'monitor_interval_minutes',
    'power_tracker_upload_interval_minutes',
    'run_speedtest',
    'auto_update_interval_days',
]
for key in PRESERVE:
    if key in old:
        new[key] = old[key]

# Nested dns_benchmark fields that are per-device
if 'dns_benchmark' in old and 'dns_benchmark' in new:
    for key in ['enabled', 'interval_minutes']:
        if key in old['dns_benchmark']:
            new['dns_benchmark'][key] = old['dns_benchmark'][key]

with open(new_path, 'w') as f:
    json.dump(new, f, indent=4)

print(f"  device_id                          : {new.get('device_id')}")
print(f"  monitor_interval_minutes           : {new.get('monitor_interval_minutes')}")
print(f"  power_tracker_upload_interval_mins : {new.get('power_tracker_upload_interval_minutes')}")
print(f"  run_speedtest                      : {new.get('run_speedtest')}")
print(f"  dns_benchmark.enabled              : {new.get('dns_benchmark', {}).get('enabled')}")
print(f"  dns_benchmark.interval_minutes     : {new.get('dns_benchmark', {}).get('interval_minutes')}")
print(f"  auto_update_interval_days          : {new.get('auto_update_interval_days', 7)}")
EOF

rm -f "$TARGETS_BACKUP"

# --- Refresh cron jobs in case intervals changed ---
bash "$SCRIPT_DIR/manage_crons.sh" update

# --- Mark update timestamp ---
date +%s > "$LAST_UPDATE_FILE"

echo "[✓] Update complete."
