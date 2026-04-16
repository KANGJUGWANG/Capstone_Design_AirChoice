#!/bin/bash
# run_daily_stats.sh
# AirChoice daily stats: PNG + HTML via Discord webhook
# systemd timer: airchoice-daily-stats.timer (23:10 KST)

set -euo pipefail

LOG_DIR="/srv/Capstone/logs"
mkdir -p "$LOG_DIR" "/srv/Capstone/outputs/stats"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "daily stats start"

# install deps via apt (most reliable on Ubuntu, no pip flag issues)
if ! python3 -c "import matplotlib" 2>/dev/null; then
    log "installing python3 stats dependencies via apt..."
    sudo apt-get install -y -q python3-matplotlib python3-pandas python3-numpy python3-requests 2>&1 | tail -5
fi

python3 /srv/Capstone/src/stats/daily_stats.py

log "daily stats done"
