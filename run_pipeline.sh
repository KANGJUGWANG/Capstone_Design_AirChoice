#!/bin/bash
# run_pipeline.sh
# 수집 → INSERT 순차 실행 파이프라인
# cron 등록 기준:
#   0  8 * * * /srv/Capstone/run_pipeline.sh >> /srv/Capstone/logs/cron.log 2>&1
#   0 16 * * * /srv/Capstone/run_pipeline.sh >> /srv/Capstone/logs/cron.log 2>&1
#   0  0 * * * /srv/Capstone/run_pipeline.sh >> /srv/Capstone/logs/cron.log 2>&1

set -euo pipefail

LOG_DIR="/srv/Capstone/logs"
mkdir -p "$LOG_DIR"

echo "========================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 파이프라인 시작"
echo "========================================"

# ------------------------------------------------------------------
# 1단계: 수집
# ------------------------------------------------------------------
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 수집 시작"

if docker exec capstone-crawler python -m src.crawler.gf_collect; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 수집 완료"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 수집 실패 — INSERT 중단"
    exit 1
fi

# ------------------------------------------------------------------
# 2단계: INSERT
# ------------------------------------------------------------------
echo "[$(date '+%Y-%m-%d %H:%M:%S')] INSERT 시작"

if docker exec capstone-loader python -m src.loaders.gf_insert; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] INSERT 완료"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] INSERT 실패"
    exit 1
fi

echo "========================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 파이프라인 완료"
echo "========================================"
