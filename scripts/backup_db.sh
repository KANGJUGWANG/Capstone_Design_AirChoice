#!/usr/bin/env bash
# =============================================================================
# AirChoice DB Backup Script
# 역할: capstone_db mysqldump → gzip → Google Drive 업로드 → 로컬 압축본 삭제
# 실행: systemd airchoice-backup.service 또는 수동 bash /srv/Capstone/scripts/backup_db.sh
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
PROJECT_ROOT="/srv/Capstone"
BACKUP_TMP_DIR="${PROJECT_ROOT}/backups"
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/backup.log"

MYSQL_CONTAINER="capstone-mysql"
MYSQL_DATABASE="capstone_db"
ENV_FILE="${PROJECT_ROOT}/.env"

RCLONE_REMOTE="gdrive"
RCLONE_DEST="${RCLONE_REMOTE}:AirChoice_Backup/db"

# ---------------------------------------------------------------------------
# 초기화
# ---------------------------------------------------------------------------
mkdir -p "${BACKUP_TMP_DIR}" "${LOG_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

# .env 로드
if [[ -f "${ENV_FILE}" ]]; then
    set -o allexport
    # shellcheck disable=SC1090
    source <(grep -v '^#' "${ENV_FILE}" | grep -v '^$')
    set +o allexport
else
    log "[ERROR] .env 파일 없음: ${ENV_FILE}"
    exit 1
fi

# .env에 MYSQL_USER가 있어도 백업은 항상 root로 실행
MYSQL_USER="root"
MYSQL_PASSWORD="${MYSQL_ROOT_PASSWORD:-}"

if [[ -z "${MYSQL_PASSWORD}" ]]; then
    log "[ERROR] MYSQL_ROOT_PASSWORD 미설정"
    exit 1
fi

# ---------------------------------------------------------------------------
# 백업 파일명
# ---------------------------------------------------------------------------
DATE_TAG=$(date '+%Y%m%d_%H%M%S')
DUMP_FILE="${BACKUP_TMP_DIR}/${MYSQL_DATABASE}_${DATE_TAG}.sql.gz"

log "========== 백업 시작 =========="
log "대상 DB   : ${MYSQL_DATABASE}"
log "컨테이너  : ${MYSQL_CONTAINER}"
log "임시 저장 : ${DUMP_FILE}"
log "업로드 대상: ${RCLONE_DEST}"

# ---------------------------------------------------------------------------
# 1. mysqldump → gzip
# ---------------------------------------------------------------------------
log "[1/3] mysqldump 실행..."
docker exec "${MYSQL_CONTAINER}" \
    mysqldump \
    --user="${MYSQL_USER}" \
    --password="${MYSQL_PASSWORD}" \
    --single-transaction \
    --routines \
    --triggers \
    "${MYSQL_DATABASE}" \
    | gzip > "${DUMP_FILE}"

DUMP_SIZE=$(du -sh "${DUMP_FILE}" | cut -f1)
log "[1/3] 완료 — 크기: ${DUMP_SIZE}"

# ---------------------------------------------------------------------------
# 2. rclone → Google Drive 업로드
# ---------------------------------------------------------------------------
log "[2/3] Google Drive 업로드 중..."
rclone copy "${DUMP_FILE}" "${RCLONE_DEST}" \
    --log-level INFO \
    --log-file "${LOG_FILE}"
log "[2/3] 완료 — 경로: ${RCLONE_DEST}/$(basename "${DUMP_FILE}")"

# ---------------------------------------------------------------------------
# 3. 로컬 압축본 삭제 (원본 DB는 그대로 유지)
# ---------------------------------------------------------------------------
log "[3/3] 로컬 압축본 삭제..."
rm -f "${DUMP_FILE}"
log "[3/3] 완료"

log "========== 백업 정상 완료 =========="
