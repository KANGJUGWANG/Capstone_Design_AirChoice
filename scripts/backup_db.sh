#!/usr/bin/env bash
# backup_db.sh
# capstone_db mysqldump -> gzip -> Google Drive -> local delete
# systemd: airchoice-backup.service (23:00 KST)

set -euo pipefail

PROJECT_ROOT="/srv/Capstone"
BACKUP_TMP_DIR="${PROJECT_ROOT}/backups"
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/backup.log"
MYSQL_CONTAINER="capstone-mysql"
MYSQL_DATABASE="capstone_db"
ENV_FILE="${PROJECT_ROOT}/.env"
RCLONE_REMOTE="gdrive"
RCLONE_DEST="${RCLONE_REMOTE}:AirChoice_Backup/db"
PYTHON="/usr/bin/python3"
WEBHOOK_PY="${PROJECT_ROOT}/src/utils/webhook.py"

# rclone rate limit 설정
# --tpslimit 1      : 초당 API 호출 1회로 제한 (rateLimitExceeded 방지)
# --retries 5       : 실패 시 최대 5회 재시도
# --retries-sleep 30s : 재시도 간격 30초
RCLONE_OPTS="--tpslimit 1 --retries 5 --retries-sleep 30s --log-level INFO --log-file ${LOG_FILE}"

mkdir -p "${BACKUP_TMP_DIR}" "${LOG_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

send() {
    $PYTHON $WEBHOOK_PY "$@" 2>> "${LOG_DIR}/webhook_error.log" || \
        log "[WARN] webhook send failed: $*"
}

send_fail() {
    local stage="$1" msg="$2"
    send pipeline_fail --stage "backup_${stage}" --error "${msg}"
}

# .env 로드
if [[ -f "${ENV_FILE}" ]]; then
    set -o allexport
    source <(grep -v '^#' "${ENV_FILE}" | grep -v '^$')
    set +o allexport
else
    log "[ERROR] .env 없음: ${ENV_FILE}"
    send_fail "init" ".env not found"
    exit 1
fi

MYSQL_USER="root"
MYSQL_PASSWORD="${MYSQL_ROOT_PASSWORD:-}"

if [[ -z "${MYSQL_PASSWORD}" ]]; then
    log "[ERROR] MYSQL_ROOT_PASSWORD 미설정"
    send_fail "init" "MYSQL_ROOT_PASSWORD not set"
    exit 1
fi

# 잔류 압축본 정리 (이전 실패로 남은 파일)
if ls "${BACKUP_TMP_DIR}"/*.sql.gz 2>/dev/null | grep -q .; then
    log "[CLEAN] 잔류 압축본 삭제..."
    rm -f "${BACKUP_TMP_DIR}"/*.sql.gz
    log "[CLEAN] 완료"
fi

DATE_TAG=$(date '+%Y%m%d_%H%M%S')
DUMP_FILE="${BACKUP_TMP_DIR}/${MYSQL_DATABASE}_${DATE_TAG}.sql.gz"
DUMP_FILENAME=$(basename "${DUMP_FILE}")

log "========== 백업 시작 =========="
log "대상 DB   : ${MYSQL_DATABASE}"
log "컨테이너  : ${MYSQL_CONTAINER}"
log "임시 저장 : ${DUMP_FILE}"
log "업로드 대상: ${RCLONE_DEST}"

# 1. mysqldump
log "[1/3] mysqldump 실행..."
if ! docker exec "${MYSQL_CONTAINER}" \
    mysqldump -h 127.0.0.1 \
    --user="${MYSQL_USER}" --password="${MYSQL_PASSWORD}" \
    --single-transaction --routines --triggers \
    "${MYSQL_DATABASE}" | gzip > "${DUMP_FILE}"; then
    log "[ERROR] mysqldump 실패"
    send_fail "mysqldump" "mysqldump failed"
    exit 1
fi
DUMP_SIZE=$(du -sh "${DUMP_FILE}" | cut -f1)
log "[1/3] 완료 — 크기: ${DUMP_SIZE}"

# 2. rclone upload (tpslimit + retry 적용)
log "[2/3] Google Drive 업로드 중... (rate limit 대응 모드)"
if ! rclone copy "${DUMP_FILE}" "${RCLONE_DEST}" ${RCLONE_OPTS}; then
    log "[ERROR] rclone 업로드 실패"
    send_fail "rclone" "rclone upload to ${RCLONE_DEST} failed"
    rm -f "${DUMP_FILE}"
    exit 1
fi
log "[2/3] 완료 — 경로: ${RCLONE_DEST}/${DUMP_FILENAME}"

# 3. 로컬 삭제
log "[3/3] 로컬 압축본 삭제..."
rm -f "${DUMP_FILE}"
log "[3/3] 완료"

# 4. 완료 웹훅
send backup_done --size "${DUMP_SIZE}" --file "${DUMP_FILENAME}"

log "========== 백업 정상 완료 =========="
