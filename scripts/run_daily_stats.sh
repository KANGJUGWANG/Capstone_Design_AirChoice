#!/bin/bash
# run_daily_stats.sh
# AirChoice daily stats: PNG x2 via Discord webhook embed
# systemd timer: airchoice-daily-stats.timer (23:10 KST)

set -euo pipefail

LOG_DIR="/srv/Capstone/logs"
mkdir -p "$LOG_DIR" "/srv/Capstone/outputs/stats"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "daily stats start"

# 한글 폰트 설치 (기준 설치 시 스킵)
if ! fc-list | grep -qi NanumGothic; then
    log "NanumGothic 폰트 설치 중..."
    sudo apt-get install -y -q fonts-nanum 2>&1 | tail -3
    python3 -c "import matplotlib.font_manager as fm; fm._load_fontmanager(try_read_cache=False)" 2>/dev/null || true
fi

# Python 패키지 확인 및 설치
if ! python3 -c "import matplotlib, requests" 2>/dev/null; then
    log "Python 패키지 설치 중..."
    sudo apt-get install -y -q python3-matplotlib python3-requests python3-numpy 2>&1 | tail -3
fi

python3 /srv/Capstone/src/stats/daily_stats.py

log "daily stats done"
