#!/bin/bash
# run_daily_stats.sh
# AirChoice daily stats: PNG x2 via Discord webhook
# systemd timer: airchoice-daily-stats.timer (23:10 KST)

set -euo pipefail

PROJECT_ROOT="/srv/Capstone"
LOG_DIR="${PROJECT_ROOT}/logs"
PYTHON="/usr/bin/python3"
WEBHOOK_PY="${PROJECT_ROOT}/src/utils/webhook.py"
mkdir -p "$LOG_DIR" "${PROJECT_ROOT}/outputs/stats"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_DIR}/daily_stats_run.log"; }

send_fail() {
    $PYTHON $WEBHOOK_PY pipeline_fail --stage "stats_$1" --error "$2" \
        2>> "${LOG_DIR}/webhook_error.log" || true
}

log "daily stats start"

# NanumGothic 폰트 확인 및 설치
if ! fc-list 2>/dev/null | grep -qi NanumGothic; then
    log "NanumGothic 폰트 설치 중..."
    sudo apt-get install -y -q fonts-nanum 2>&1 | tail -3
    $PYTHON -c "import matplotlib.font_manager as fm; fm._load_fontmanager(try_read_cache=False)" 2>/dev/null || true
fi

# Python 패키지 확인 및 설치
if ! $PYTHON -c "import matplotlib, requests, numpy" 2>/dev/null; then
    log "Python 패키지 설치 중..."
    sudo apt-get install -y -q python3-matplotlib python3-requests python3-numpy 2>&1 | tail -3
fi

if ! $PYTHON "${PROJECT_ROOT}/src/stats/daily_stats.py"; then
    EXIT_CODE=$?
    log "daily stats 실패 (exit=${EXIT_CODE})"
    send_fail "generate" "daily_stats.py exited with code ${EXIT_CODE}"
    exit 1
fi

log "daily stats done"
