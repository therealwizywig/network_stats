#!/usr/bin/env python3
"""
Per-minute uptime tracker. Sends rows to the telemetry ingest endpoint,
falls back to CSV if the upload fails.

Usage:
  python3 power_tracker.py          — heartbeat (run every minute via cron)
  python3 power_tracker.py --boot   — boot event (run @reboot via cron)
"""

import csv
import json
import os
import sys
import requests
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGETS_FILE = os.path.join(SCRIPT_DIR, "targets.json")
LOG_DIR = os.path.expanduser("~/network_stats/logs")
CSV_FILE = os.path.join(LOG_DIR, "power_log.csv")
HEARTBEAT_FILE = os.path.join(LOG_DIR, "last_heartbeat.txt")
LAST_BOOT_FILE = os.path.join(LOG_DIR, "last_boot.txt")

INGEST_URL = "https://telemetry-ingest-32461014139.us-central1.run.app/telemetry"
INGEST_HEADERS = {
    "Content-Type": "application/json",
    "X-Ingest-Key": "UDE_rex!qhp*eby6kry"
}

BACKFILL_CAP_MINUTES = 10_080  # 7 days

os.makedirs(LOG_DIR, exist_ok=True)


def load_device_id():
    with open(TARGETS_FILE) as f:
        return json.load(f).get("device_id", "unknown")


def now_utc():
    return datetime.now(timezone.utc)


def ts_to_epoch(dt):
    return int(dt.timestamp())


def epoch_to_dt(epoch):
    return datetime.fromtimestamp(int(epoch), tz=timezone.utc)


def fmt_timestamp(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def read_int_file(path):
    try:
        with open(path) as f:
            return int(f.read().strip())
    except Exception:
        return None


def write_int_file(path, value):
    with open(path, "w") as f:
        f.write(str(value))
    os.sync()


def write_csv(rows):
    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["device_id", "timestamp", "status"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def upload_row(row):
    try:
        response = requests.post(INGEST_URL, json=row, headers=INGEST_HEADERS, timeout=10)
        return response.status_code in (200, 201, 202)
    except Exception:
        return False


def build_row(device_id, dt, status):
    return {
        "device_id": device_id,
        "timestamp": fmt_timestamp(dt),
        "status": status,
    }


def run_heartbeat():
    device_id = load_device_id()
    now = now_utc()
    write_int_file(HEARTBEAT_FILE, ts_to_epoch(now))
    row = build_row(device_id, now, "online")
    if not upload_row(row):
        write_csv([row])


def run_boot():
    device_id = load_device_id()
    now = now_utc()

    last_heartbeat_epoch = read_int_file(HEARTBEAT_FILE)
    last_boot_epoch = read_int_file(LAST_BOOT_FILE)

    rows = []

    if last_heartbeat_epoch and last_boot_epoch:
        last_heartbeat_dt = epoch_to_dt(last_heartbeat_epoch)
        offline_start = last_heartbeat_dt + timedelta(minutes=1)
        offline_minutes = int((now - offline_start).total_seconds() / 60)
        offline_minutes = min(offline_minutes, BACKFILL_CAP_MINUTES)

        for i in range(offline_minutes):
            rows.append(build_row(device_id, offline_start + timedelta(minutes=i), "offline"))

        if offline_minutes > 0:
            print(f"[power_tracker] Backfilling {offline_minutes} offline minute(s).")

    write_int_file(LAST_BOOT_FILE, ts_to_epoch(now))
    write_int_file(HEARTBEAT_FILE, ts_to_epoch(now))

    rows.append(build_row(device_id, now, "online"))

    failed = []
    for row in rows:
        if not upload_row(row):
            failed.append(row)

    if failed:
        write_csv(failed)


if __name__ == "__main__":
    if "--boot" in sys.argv:
        run_boot()
    else:
        run_heartbeat()
