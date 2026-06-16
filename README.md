# Network Stats — Raspberry Pi Network Monitor

Monitors internet health from a Raspberry Pi and reports metrics to a central telemetry endpoint. Tracks ping latency, packet loss, speed tests, URL reachability, power loss events, and connection details.

---

## Quick Start

Run these commands on a fresh Raspberry Pi:

```bash
# Install git and clone the repo
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/therealwizywig/network_stats ~/network_stats

# Make scripts executable
chmod +x ~/network_stats/setup_monitor.sh ~/network_stats/monitor.py

# Run the setup script
sudo ~/network_stats/setup_monitor.sh
```

When prompted, enter the **Device ID** assigned by Global (e.g. `site-chicago-01`). This ID is used to identify the device in all telemetry data.

---

## What the Setup Script Does

`setup_monitor.sh` provisions the Pi in one shot:

1. **Saves the Device ID** into `device_id` in `targets.json`
2. **Installs system dependencies** — git, Python, ethtool, dnsutils
3. **Applies a driver fix** for a known Raspberry Pi 4 Ethernet bug (`bcmgenet`) that causes the network interface to wedge under heavy load during speed tests
4. **Installs the official Ookla speedtest CLI** from the Ookla package repository
5. **Installs and configures ZeroTier** for remote management access and joins the network
6. **Clones or updates this repository** to `~/network_stats`
7. **Installs cron jobs** for monitor, dns_benchmark, and power_tracker via `manage_crons.sh`

---

## What Runs on the Pi

### `monitor.py` — Network Health Check

Runs on a cron schedule (controlled by `monitor_interval_minutes` in `targets.json`). Each run collects:

| Field | Description |
|---|---|
| `device_id` | Unique identifier for this Pi |
| `ping_latency_*` / `ping_loss_*` | Latency and packet loss to each host in `target_servers` |
| `probe_*` | HTTP reachability of each URL — one of `reached`, `redirected`, `error`, `timeout`, `ssl_error`, `dns_failed`, `failed` |
| `download_mbps_*` / `upload_mbps_*` | Speed test results per configured server |
| `speedtest_latency_*` / `speedtest_jitter_*` | Baseline ping latency and jitter |
| `speedtest_dl_latency_*` / `speedtest_dl_jitter_*` | Latency/jitter **during** download (detects bufferbloat) |
| `speedtest_ul_latency_*` / `speedtest_ul_jitter_*` | Latency/jitter **during** upload |
| `speedtest_server_*` | Name and location of the speed test server used |
| `external_ip` / `external_city` | Public IP and city from ipinfo.io |
| `connection_type` | `ethernet` or `wifi` |
| `connection_speed` | e.g. `Gigabit`, `100 Mbps`, `WiFi 6` |
| `wan_status` | `Online` or `Offline` |
| `pi_uptime` | Seconds since last boot |
| `run_data_mb` | Total MB of data used by this monitor run |

Results are sent to the telemetry ingest endpoint. If the upload fails, they are saved locally to `~/network_stats/logs/speedtest_results.csv`.

### `dns_benchmark.py` — DNS Performance Benchmark

Invoked by cron on the same schedule as `monitor.py`, but only actually runs based on its own `interval_minutes` setting. Tests each configured DNS server against each domain using `dig`.

| Field | Description |
|---|---|
| `dns_ms_{server}_{domain}` | Query time in ms per server/domain combo |
| `dns_avg_ms_{server}` | Average query time per DNS server |
| `run_data_mb` | Total MB used by this benchmark run |

Results are sent to the telemetry endpoint and always written to `~/network_stats/logs/dns_benchmark_results.csv`.

### `power_tracker.sh` — Power Loss Tracker

Runs as two cron jobs:
- **`@reboot`** — on every boot, calculates uptime and downtime from the previous session and logs a row to CSV
- **Every minute** — writes the current timestamp as a heartbeat, flushed immediately to disk with `sync`

Results are logged to `~/network_stats/logs/power_log.csv`.

---

## Configuration — `targets.json`

All targets, options, and cron intervals are controlled from `targets.json`. Run `manage_crons.sh update` after changing intervals.

```json
{
    "device_id": "site-chicago-01",
    "monitor_interval_minutes": 5,
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
        "domains": ["google.com", "amazon.com", "github.com"],
        "servers": [
            { "label": "default" },
            { "label": "cloudflare", "ip": "1.1.1.1" },
            { "label": "google_dns", "ip": "8.8.8.8" }
        ]
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
| `monitor_interval_minutes` | How often cron runs `monitor.py` and invokes `dns_benchmark.py`. |
| `target_servers` | Hosts to ping each run. |
| `probe_urls` | URLs to check for HTTP reachability each run. |
| `dns_benchmark.enabled` | `false` = never run; `true` = run on the configured interval. |
| `dns_benchmark.interval_minutes` | Minimum minutes between actual DNS benchmark runs. |
| `dns_benchmark.domains` | Domains to test DNS resolution against. |
| `dns_benchmark.servers` | DNS servers to test. Omit `ip` for system default. |
| `run_speedtest` | `true` to run speed tests, `false` to skip. |
| `speedtest_servers` | Speed test servers. Omit `id` for auto (nearest). |

---

## Managing Cron Jobs

After editing intervals in `targets.json`, apply the changes:

```bash
sudo ~/network_stats/manage_crons.sh update
```

To remove all network_stats cron jobs:

```bash
sudo ~/network_stats/manage_crons.sh remove
```
