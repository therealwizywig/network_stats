#!/usr/bin/env python3
import os
import sys
import csv
import json
import subprocess
import re
import time
from datetime import datetime, timezone
import requests

TARGETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "targets.json")
CSV_FILE = os.path.expanduser("~/network_stats/dns_benchmark_results.csv")
TIMESTAMP_FILE = "/tmp/last_dns_benchmark"

INGEST_URL = "https://telemetry-ingest-32461014139.us-central1.run.app/telemetry"
INGEST_HEADERS = {
    "Content-Type": "application/json",
    "X-Ingest-Key": "UDE_rex!qhp*eby6kry"
}

def load_config():
    try:
        with open(TARGETS_FILE, 'r') as f:
            data = json.load(f)
        cfg = data.get("dns_benchmark", {})
        return (
            data.get("device_id", "test-device-default"),
            cfg.get("enabled", False),
            cfg.get("interval_minutes", 60),
            cfg.get("domains", []),
        )
    except Exception as e:
        print(f"Warning: could not load {TARGETS_FILE}: {e}", file=sys.stderr)
        return "test-device-default", False, 60, []

def is_due(interval_minutes):
    if interval_minutes <= 0:
        return True
    try:
        with open(TIMESTAMP_FILE) as f:
            last_run = float(f.read().strip())
        return (time.time() - last_run) >= interval_minutes * 60
    except Exception:
        return True

def mark_ran():
    try:
        with open(TIMESTAMP_FILE, 'w') as f:
            f.write(str(time.time()))
    except Exception:
        pass

def query_dns(domain):
    try:
        res = subprocess.run(
            ["dig", domain],
            capture_output=True, text=True, timeout=10
        )
        match = re.search(r"Query time: (\d+) msec", res.stdout)
        return int(match.group(1)) if match else ""
    except Exception:
        return ""

def get_utc_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def write_csv(payload):
    file_exists = os.path.isfile(CSV_FILE)
    try:
        if file_exists:
            with open(CSV_FILE, newline='') as f:
                existing_fields = list(csv.DictReader(f).fieldnames or [])
            all_fields = existing_fields + [k for k in payload.keys() if k not in existing_fields]
        else:
            all_fields = list(payload.keys())
        with open(CSV_FILE, mode='a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction='ignore')
            if not file_exists:
                writer.writeheader()
            writer.writerow({k: payload.get(k, "") for k in all_fields})
    except Exception as e:
        print(f"Failed writing to CSV: {e}", file=sys.stderr)

def main():
    device_id, enabled, interval_minutes, domains = load_config()

    if not enabled:
        sys.exit(0)

    if not is_due(interval_minutes):
        sys.exit(0)

    if not domains:
        print("No domains configured for dns_benchmark.", file=sys.stderr)
        sys.exit(1)

    payload = {
        "device_id": device_id,
        "dns_timestamp": get_utc_timestamp(),
    }

    times = []
    for domain in domains:
        ms = query_dns(domain)
        payload[f"dns_ms_{domain}"] = ms
        if isinstance(ms, int):
            times.append(ms)

    payload["dns_avg_ms"] = round(sum(times) / len(times), 2) if times else ""

    try:
        requests.post(INGEST_URL, json=payload, headers=INGEST_HEADERS, timeout=10)
    except Exception:
        pass

    write_csv(payload)

    mark_ran()

if __name__ == "__main__":
    main()
