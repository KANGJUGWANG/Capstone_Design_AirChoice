#!/bin/bash
# run_pipeline.sh
# 수집 → INSERT 순차 실행 파이프라인
# systemd timer 기준: airchoice-pipeline.timer (00:00 / 08:00 / 16:00 KST)

set -euo pipefail

LOG_DIR="/srv/Capstone/logs"
WEBHOOK="python3 /srv/Capstone/src/utils/webhook.py"
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

echo "========================================"
log "파이프라인 시작"
echo "========================================"

# 수집 시작 시각 캡체 (적재 웹훅 쿼리 기준)
# date +%-H : 알파없이 시간 (0~23). sed 사용 안 함 — 00 → '' 버그 방지
COLLECT_HOUR=$(date +%-H)
COLLECT_DATE=$(date '+%Y-%m-%d')

# ------------------------------------------------------------------
# 1단계: 수집
# ------------------------------------------------------------------
log "수집 시작"
COLLECT_START=$(date +%s)

if docker exec capstone-crawler python -m src.crawler.gf_collect; then
    COLLECT_END=$(date +%s)
    ELAPSED=$(( (COLLECT_END - COLLECT_START) / 60 ))
    log "수집 완료 (${ELAPSED}분)"
    $WEBHOOK collect_done --elapsed "$ELAPSED" || true
else
    log "수집 실패"
    $WEBHOOK pipeline_fail --stage "collector" --error "gf_collect 비정상 종료" || true
    exit 1
fi

# ------------------------------------------------------------------
# 2단계: INSERT
# ------------------------------------------------------------------
log "INSERT 시작"

if docker exec capstone-loader python -m src.loaders.gf_insert; then
    log "INSERT 완료"
    $WEBHOOK insert_done --hour "$COLLECT_HOUR" --date "$COLLECT_DATE" || true
    $WEBHOOK disk_warn || true
else
    log "INSERT 실패"
    $WEBHOOK pipeline_fail --stage "loader" --error "gf_insert 비정상 종료" || true
    exit 1
fi

echo "========================================"
log "파이프라인 완료"
echo "========================================"
