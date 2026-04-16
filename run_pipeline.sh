#!/bin/bash
# run_pipeline.sh
# collect -> INSERT pipeline
# systemd timer: airchoice-pipeline.timer (00:00 / 08:00 / 16:00 KST)

set -euo pipefail

LOG_DIR="/srv/Capstone/logs"
PYTHON="/usr/bin/python3"
WEBHOOK_PY="/srv/Capstone/src/utils/webhook.py"
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_DIR}/cron.log"
}

send() {
    # send <event> [args...]
    # python3 path 명시 - systemd minimal PATH 대응
    $PYTHON $WEBHOOK_PY "$@" 2>> "${LOG_DIR}/webhook_error.log" || \
        log "[WARN] webhook send failed: $*"
}

echo "========================================"
log "pipeline start"
echo "========================================"

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
    send collect_done --elapsed "$ELAPSED"
else
    COLLECT_EXIT=$?
    log "collect failed (exit=${COLLECT_EXIT})"
    send pipeline_fail --stage collector --error "gf_collect exited abnormally (exit=${COLLECT_EXIT})"
    exit 1
fi

# ------------------------------------------------------------------
# step 2: INSERT
# ------------------------------------------------------------------
log "INSERT start"

if docker exec capstone-loader python -m src.loaders.gf_insert --hour "$COLLECT_HOUR" --date "$COLLECT_DATE"; then
    log "INSERT done"
    send insert_done --hour "$COLLECT_HOUR" --date "$COLLECT_DATE"
    send disk_warn
else
    INSERT_EXIT=$?
    log "INSERT failed (exit=${INSERT_EXIT})"
    send pipeline_fail --stage loader --error "gf_insert exited abnormally (exit=${INSERT_EXIT})"
    exit 1
fi

echo "========================================"
log "pipeline done"
echo "========================================"
