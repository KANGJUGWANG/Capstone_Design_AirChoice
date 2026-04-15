#!/bin/bash
# run_pipeline.sh
# collect -> INSERT pipeline
# systemd timer: airchoice-pipeline.timer (00:00 / 08:00 / 16:00 KST)

set -euo pipefail

LOG_DIR="/srv/Capstone/logs"
WEBHOOK="python3 /srv/Capstone/src/utils/webhook.py"
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

echo "========================================"
log "pipeline start"
echo "========================================"

# capture collect start time (date +%-H: 0~23 integer, no leading zero)
COLLECT_HOUR=$(date +%-H)
COLLECT_DATE=$(date '+%Y-%m-%d')

# ------------------------------------------------------------------
# step 1: collect
# ------------------------------------------------------------------
log "collect start"
COLLECT_START=$(date +%s)

if docker exec capstone-crawler python -m src.crawler.gf_collect; then
    COLLECT_END=$(date +%s)
    ELAPSED=$(( (COLLECT_END - COLLECT_START) / 60 ))
    log "collect done (${ELAPSED}min)"
    $WEBHOOK collect_done --elapsed "$ELAPSED" || true
else
    log "collect failed"
    $WEBHOOK pipeline_fail --stage collector --error "gf_collect exited abnormally" || true
    exit 1
fi

# ------------------------------------------------------------------
# step 2: INSERT
# ------------------------------------------------------------------
log "INSERT start"

if docker exec capstone-loader python -m src.loaders.gf_insert --hour "$COLLECT_HOUR" --date "$COLLECT_DATE"; then
    log "INSERT done"
    $WEBHOOK insert_done --hour "$COLLECT_HOUR" --date "$COLLECT_DATE" || true
    $WEBHOOK disk_warn || true
else
    log "INSERT failed"
    $WEBHOOK pipeline_fail --stage loader --error "gf_insert exited abnormally" || true
    exit 1
fi

echo "========================================"
log "pipeline done"
echo "========================================"
