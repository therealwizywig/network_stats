#!/usr/bin/env python3
"""
Per-minute uptime tracker. Queues rows locally and uploads in batches
on a configurable interval (power_tracker_upload_interval_minutes in targets.json).

Usage:
  python3 power_tracker.py          — heartbeat (run every minute via cron)
  python3 power_tracker.py --boot   — boot event (run @reboot via cron)
"""

import csv
import json
import os
import sys
import time
import requests
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGETS_FILE = os.path.join(SCRIPT_DIR, "targets.json")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
CSV_FILE = os.path.join(LOG_DIR, "power_log.csv")
QUEUE_FILE = os.path.join(LOG_DIR, "power_queue.jsonl")
HEARTBEAT_FILE = os.path.join(LOG_DIR, "last_heartbeat.txt")
LAST_BOOT_FILE = os.path.join(LOG_DIR, "last_boot.txt")
LAST_UPLOAD_FILE = os.path.join(LOG_DIR, "last_power_upload.txt")

INGEST_URL = "https://telemetry-ingest-32461014139.us-central1.run.app/power"
INGEST_HEADERS = {
    "Content-Type": "application/json",
    "X-Ingest-Key": "UDE_rex!qhp*eby6kry"
}

BACKFILL_CAP_MINUTES = 10_080  # 7 days

os.makedirs(LOG_DIR, exist_ok=True)


def load_config():
    with open(TARGETS_FILE) as f:
        d = json.load(f)
    return (
        d.get("device_id", "unknown"),
        d.get("power_tracker_upload_interval_minutes", 60),
    )


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


def build_row(device_id, dt, status):
    return {
        "device_id": device_id,
        "timestamp": fmt_timestamp(dt),
        "status": status,
    }


def queue_rows(rows):
    with open(QUEUE_FILE, "a") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def read_queue():
    if not os.path.exists(QUEUE_FILE):
        return []
    rows = []
    with open(QUEUE_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def clear_queue():
    open(QUEUE_FILE, "w").close()


def is_upload_due(interval_minutes):
    last = read_int_file(LAST_UPLOAD_FILE)
    if last is None:
        return True
    return (time.time() - last) >= interval_minutes * 60


def mark_uploaded():
    write_int_file(LAST_UPLOAD_FILE, int(time.time()))


def upload_queue():
    rows = read_queue()
    if not rows:
        return

    failed = []
    for row in rows:
        try:
            response = requests.post(INGEST_URL, json=row, headers=INGEST_HEADERS, timeout=10)
            if response.status_code not in (200, 201, 202):
                failed.append(row)
        except Exception:
            failed.append(row)

    if not failed:
        clear_queue()
        mark_uploaded()
        print(f"[power_tracker] Uploaded {len(rows)} queued row(s).")
    else:
        # Keep only failed rows in the queue
        with open(QUEUE_FILE, "w") as f:
            for row in failed:
                f.write(json.dumps(row) + "\n")
        # Write successes to CSV fallback for visibility
        succeeded = [r for r in rows if r not in failed]
        if succeeded:
            write_csv(succeeded)
        print(f"[power_tracker] {len(failed)}/{len(rows)} row(s) failed upload, kept in queue.")


def write_csv(rows):
    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["device_id", "timestamp", "status"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def run_heartbeat():
    device_id, upload_interval = load_config()
    now = now_utc()
    write_int_file(HEARTBEAT_FILE, ts_to_epoch(now))
    queue_rows([build_row(device_id, now, "online")])

    if is_upload_due(upload_interval):
        upload_queue()


def run_boot():
    device_id, upload_interval = load_config()
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
    queue_rows(rows)

    if is_upload_due(upload_interval):
        upload_queue()


if __name__ == "__main__":
    if "--boot" in sys.argv:
        run_boot()
    else:
        run_heartbeat()
