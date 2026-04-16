#!/bin/bash
# run_daily_stats.sh
# AirChoice daily stats: PNG + HTML via Discord webhook
# systemd timer: airchoice-daily-stats.timer (23:10 KST)

set -euo pipefail

LOG_DIR="/srv/Capstone/logs"
mkdir -p "$LOG_DIR" "/srv/Capstone/outputs/stats"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "daily stats start"

# install deps (python3 -m pip, pip3 없는 환경 대응)
python3 -m pip install --break-system-packages --quiet \
    matplotlib pandas numpy requests 2>&1 | tail -3 || \
python3 -m ensurepip --upgrade 2>/dev/null && \
python3 -m pip install --break-system-packages --quiet \
    matplotlib pandas numpy requests 2>&1 | tail -3 || true

python3 /srv/Capstone/src/stats/daily_stats.py

log "daily stats done"
