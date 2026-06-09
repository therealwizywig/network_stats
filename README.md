# Network Stats — Raspberry Pi Network Monitor

Monitors internet health from a Raspberry Pi and reports metrics to a central telemetry endpoint. Tracks ping latency, packet loss, speed tests, URL reachability, power loss events, and connection details.

---

## Quick Start

Run these commands on a fresh Raspberry Pi:

```bash
# Install git and clone the repo
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/therealwizywig/network_stats ~/network_stats/repo

# Make scripts executable
chmod +x ~/network_stats/repo/setup_monitor.sh ~/network_stats/repo/monitor.py

# Run the setup script
sudo ~/network_stats/repo/setup_monitor.sh
```

When prompted, enter the **Device ID** assigned by Global (e.g. `current_year-001`). This ID is used to identify the device in all telemetry data.

---

## What the Setup Script Does

`setup_monitor.sh` provisions the Pi in one shot:

1. **Saves the Device ID** into `device_id` in `targets.json`
2. **Installs system dependencies** — git, Python, ethtool
3. **Applies a driver fix** for a known Raspberry Pi 4 Ethernet bug (`bcmgenet`) that causes the network interface to wedge under heavy load during speed tests. The fix reduces the transmit queue size and persists across reboots via a udev rule.
4. **Installs the official Ookla speedtest CLI** from the Ookla package repository (required for accurate server selection by ID)
5. **Installs and configures ZeroTier** for remote management access and joins the network
6. **Clones this repository** to `~/network_stats/repo`
7. **Installs and starts the `power_tracker` systemd service**

---

## What Runs on the Pi

### `monitor.py` — Network Health Check

Run on a schedule (e.g. via cron every 5 minutes). Each run collects:

| Field | Description |
|---|---|
| `device_id` | Unique identifier for this Pi |
| `ping_latency_*` / `ping_loss_*` | Latency and packet loss to each host in `target_servers` |
| `probe_*` | HTTP reachability status for each URL in `probe_urls` — one of `reached`, `redirected`, `error`, `timeout`, `ssl_error`, `dns_failed`, `failed` |
| `download_mbps_*` / `upload_mbps_*` | Speed test results per configured server |
| `speedtest_latency_*` / `speedtest_jitter_*` | Baseline ping latency and jitter measured by the speed test |
| `speedtest_dl_latency_*` / `speedtest_dl_jitter_*` | Latency and jitter **during** the download test (detects bufferbloat) |
| `speedtest_ul_latency_*` / `speedtest_ul_jitter_*` | Latency and jitter **during** the upload test |
| `speedtest_server_*` | Name and location of the speed test server used |
| `external_ip` / `external_city` | Public IP and city from ipinfo.io |
| `connection_type` | `ethernet` or `wifi` |
| `connection_speed` | e.g. `Gigabit`, `100 Mbps`, `WiFi 6` |
| `wan_status` | `Online` or `Offline` |
| `pi_uptime` | Seconds since last boot |
| `run_data_mb` | Total MB of data used by this monitor run |

Results are sent to the telemetry ingest endpoint. If the upload fails, they are saved locally to `~/network_stats/logs/speedtest_results.csv` as a fallback buffer.

### `dns_benchmark.py` — DNS Performance Benchmark

Run on a schedule. Measures how long your configured DNS server takes to resolve each domain using `dig`. Controlled entirely by the `dns_benchmark` block in `targets.json` — including an interval so it doesn't run every cycle and use unnecessary data.

| Field | Description |
|---|---|
| `dns_ms_{domain}` | Query time in ms for each domain (e.g. `dns_ms_google.com`) |
| `dns_avg_ms` | Average query time across all domains |

Results are sent to the telemetry endpoint or saved to `~/network_stats/logs/dns_benchmark_results.csv` on failure.

### `power_tracker.service` — Power Loss Tracker

A systemd service that runs continuously in the background. It writes a heartbeat timestamp to disk every 60 seconds. On each boot, it compares the last heartbeat to the current boot time to calculate:

- **Uptime** of the previous session (how long it ran before power was lost)
- **Downtime** (how long the Pi was off)

Results are logged to `~/network_stats/logs/power_log.csv`.

The heartbeat is flushed to disk with `sync` immediately after each write so that even a sudden power loss captures an accurate last-seen time.

---

## Configuration — `targets.json`

All targets and options are controlled from `targets.json` in the repo root. Edit this file to change what is monitored without touching any code.

```json
{
    "device_id": "site-chicago-01",
    "target_servers": {
        "google": "google.com",
        "github": "github.com"
    },
    "probe_urls": {
        "netsuite": "https://system.netsuite.com/",
        "salesforce": "https://login.salesforce.com/"
    },
    "dns_benchmark": {
        "enabled": true,
        "interval_minutes": 60,
        "domains": ["google.com", "amazon.com", "github.com"]
    },
    "run_speedtest": true,
    "speedtest_servers": [
        { "label": "auto" },
        { "label": "1776", "id": 1776 }
    ]
}
```

| Key | Description |
|---|---|
| `device_id` | Unique identifier for this Pi — set automatically by the setup script. |
| `target_servers` | Hosts to ping each run. Add or remove entries freely. |
| `probe_urls` | URLs to check for HTTP reachability each run. |
| `dns_benchmark.enabled` | `false` = never run; `true` = run on the configured interval. |
| `dns_benchmark.interval_minutes` | Minimum minutes between DNS benchmark runs. `0` = run every cycle. |
| `dns_benchmark.domains` | Domains to test DNS resolution against. |
| `run_speedtest` | `true` to run speed tests every cycle, `false` to skip entirely. |
| `speedtest_servers` | List of speed test servers. Omit `id` for auto (nearest). Add `"id"` to test a specific Ookla server. |

---

## Cron Setup

To run `monitor.py` every 5 minutes, add this to root's crontab (`sudo crontab -e`):

```
*/5 * * * * /usr/bin/python3 /root/network_stats/repo/monitor.py
*/5 * * * * /usr/bin/python3 /root/network_stats/repo/dns_benchmark.py
```

Both can run on the same 5-minute cron cycle — `dns_benchmark.py` will exit immediately if it's not yet due based on `interval_minutes`.
