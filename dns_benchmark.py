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

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGETS_FILE = os.path.join(_SCRIPT_DIR, "targets.json")
CSV_FILE = os.path.join(_SCRIPT_DIR, "logs", "dns_benchmark_results.csv")
os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
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
            cfg.get("servers", [{"label": "default"}]),
        )
    except Exception as e:
        print(f"Warning: could not load {TARGETS_FILE}: {e}", file=sys.stderr)
        return "test-device-default", False, 60, [], [{"label": "default"}]

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

def get_net_bytes():
    try:
        res = subprocess.run(["ip", "route", "get", "8.8.8.8"], capture_output=True, text=True)
        match = re.search(r"dev\s+(\S+)", res.stdout)
        if not match:
            return 0, 0
        iface = match.group(1)
        with open("/proc/net/dev") as f:
            for line in f:
                if line.strip().startswith(iface + ":"):
                    parts = line.split()
                    return int(parts[1]), int(parts[9])
        return 0, 0
    except Exception:
        return 0, 0

def query_dns(domain, server_ip=None):
    cmd = ["dig"]
    if server_ip:
        cmd.append(f"@{server_ip}")
    cmd.append(domain)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
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
    device_id, enabled, interval_minutes, domains, servers = load_config()

    if not enabled:
        sys.exit(0)

    if not is_due(interval_minutes):
        sys.exit(0)

    if not domains:
        print("No domains configured for dns_benchmark.", file=sys.stderr)
        sys.exit(1)

    rx_start, tx_start = get_net_bytes()

    payload = {
        "device_id": device_id,
        "dns_timestamp": get_utc_timestamp(),
    }

    for server in servers:
        label = server["label"]
        ip = server.get("ip")
        times = []
        for domain in domains:
            ms = query_dns(domain, ip)
            payload[f"dns_ms_{label}_{domain}"] = ms
            if isinstance(ms, int):
                times.append(ms)
        payload[f"dns_avg_ms_{label}"] = round(sum(times) / len(times), 2) if times else ""

    rx_end, tx_end = get_net_bytes()
    payload["run_data_mb"] = round((rx_end - rx_start + tx_end - tx_start) / (1024 * 1024), 2)

    try:
        requests.post(INGEST_URL, json=payload, headers=INGEST_HEADERS, timeout=10)
    except Exception:
        pass

    write_csv(payload)

    mark_ran()

if __name__ == "__main__":
    main()
