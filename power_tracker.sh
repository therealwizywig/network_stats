#!/bin/bash

TRACK_DIR="$HOME/network_stats/logs"
CSV_FILE="$TRACK_DIR/power_log.csv"
HEARTBEAT_FILE="$TRACK_DIR/last_heartbeat.txt"
LAST_BOOT_FILE="$TRACK_DIR/last_boot.txt"

mkdir -p "$TRACK_DIR"

if [ ! -f "$CSV_FILE" ]; then
    echo "Boot_Time,Power_Loss_Time,Uptime_Seconds,Downtime_Seconds" > "$CSV_FILE"
fi

if [ "$1" = "--boot" ]; then
    # Called at @reboot — calculate uptime/downtime from previous session
    CURRENT_BOOT=$(date +%s)
    if [ -f "$HEARTBEAT_FILE" ] && [ -f "$LAST_BOOT_FILE" ]; then
        LAST_HEARTBEAT=$(cat "$HEARTBEAT_FILE")
        LAST_BOOT=$(cat "$LAST_BOOT_FILE")
        UPTIME=$((LAST_HEARTBEAT - LAST_BOOT))
        DOWNTIME=$((CURRENT_BOOT - LAST_HEARTBEAT))
        LAST_BOOT_HR=$(date -d @"$LAST_BOOT" +"%Y-%m-%d %H:%M:%S")
        LAST_HEARTBEAT_HR=$(date -d @"$LAST_HEARTBEAT" +"%Y-%m-%d %H:%M:%S")
        echo "$LAST_BOOT_HR,$LAST_HEARTBEAT_HR,$UPTIME,$DOWNTIME" >> "$CSV_FILE"
    fi
    echo "$CURRENT_BOOT" > "$LAST_BOOT_FILE"
else
    # Called every minute by cron — write heartbeat to disk immediately
    date +%s > "$HEARTBEAT_FILE"
    sync -f "$HEARTBEAT_FILE"
fi
