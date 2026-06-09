#!/bin/bash

# Directory and file paths
TRACK_DIR="$HOME/network_stats/logs"
CSV_FILE="$TRACK_DIR/power_log.csv"
HEARTBEAT_FILE="$TRACK_DIR/last_heartbeat.txt"
LAST_BOOT_FILE="$TRACK_DIR/last_boot.txt"

# Create directory if it doesn't exist
mkdir -p "$TRACK_DIR"

# Initialize CSV with headers if it doesn't exist
if [ ! -f "$CSV_FILE" ]; then
    echo "Boot_Time,Power_Loss_Time,Uptime_Seconds,Downtime_Seconds" > "$CSV_FILE"
fi

# Get current boot time in seconds
# Because of your Pi 5 RTC battery, this will be perfectly accurate immediately!
CURRENT_BOOT=$(date +%s)

# If previous records exist, calculate uptime and downtime
if [ -f "$HEARTBEAT_FILE" ] && [ -f "$LAST_BOOT_FILE" ]; then
    LAST_HEARTBEAT=$(cat "$HEARTBEAT_FILE")
    LAST_BOOT=$(cat "$LAST_BOOT_FILE")

    # Calculate durations
    UPTIME=$((LAST_HEARTBEAT - LAST_BOOT))
    DOWNTIME=$((CURRENT_BOOT - LAST_HEARTBEAT))

    # Convert epoch timestamps to human-readable dates
    LAST_BOOT_HR=$(date -d @"$LAST_BOOT" +"%Y-%m-%d %H:%M:%S")
    LAST_HEARTBEAT_HR=$(date -d @"$LAST_HEARTBEAT" +"%Y-%m-%d %H:%M:%S")

    # Append data to CSV
    echo "$LAST_BOOT_HR,$LAST_HEARTBEAT_HR,$UPTIME,$DOWNTIME" >> "$CSV_FILE"
fi

# Record the current boot time for the next session
echo "$CURRENT_BOOT" > "$LAST_BOOT_FILE"

# Start the Heartbeat loop (updates every 60 seconds)
while true; do
    date +%s > "$HEARTBEAT_FILE"
    
    # Force Linux to physically write this to the SD card immediately
    # rather than holding it in the volatile RAM cache
    sync -f "$HEARTBEAT_FILE"
    
    sleep 60
done
