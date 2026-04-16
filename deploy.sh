#!/bin/bash
set -e

REPO="KANGJUGWANG/Capstone_Design_AirChoice"
BRANCH="main"
RAW="https://raw.githubusercontent.com/${REPO}/${BRANCH}"

echo "=== AirChoice deploy start ==="

mkdir -p /srv/Capstone/src/config
mkdir -p /srv/Capstone/src/crawler
mkdir -p /srv/Capstone/src/loaders
mkdir -p /srv/Capstone/src/utils
mkdir -p /srv/Capstone/src/stats
mkdir -p /srv/Capstone/docker/crawler
mkdir -p /srv/Capstone/docker/loader
mkdir -p /srv/Capstone/requirements
mkdir -p /srv/Capstone/data/raw/google_flights
mkdir -p /srv/Capstone/outputs/stats
mkdir -p /srv/Capstone/logs
mkdir -p /srv/Capstone/scripts
mkdir -p /srv/Capstone/deploy/systemd
mkdir -p /srv/Capstone/backups

# src
curl -fsSL "${RAW}/src/__init__.py"                  -o /srv/Capstone/src/__init__.py
curl -fsSL "${RAW}/src/config/__init__.py"           -o /srv/Capstone/src/config/__init__.py
curl -fsSL "${RAW}/src/config/settings.py"           -o /srv/Capstone/src/config/settings.py
curl -fsSL "${RAW}/src/crawler/__init__.py"          -o /srv/Capstone/src/crawler/__init__.py
curl -fsSL "${RAW}/src/crawler/constants.py"         -o /srv/Capstone/src/crawler/constants.py
curl -fsSL "${RAW}/src/crawler/url_builder.py"       -o /srv/Capstone/src/crawler/url_builder.py
curl -fsSL "${RAW}/src/crawler/parser.py"            -o /srv/Capstone/src/crawler/parser.py
curl -fsSL "${RAW}/src/crawler/collector.py"         -o /srv/Capstone/src/crawler/collector.py
curl -fsSL "${RAW}/src/crawler/gf_collect.py"        -o /srv/Capstone/src/crawler/gf_collect.py
curl -fsSL "${RAW}/src/loaders/__init__.py"          -o /srv/Capstone/src/loaders/__init__.py
curl -fsSL "${RAW}/src/loaders/gf_insert.py"         -o /srv/Capstone/src/loaders/gf_insert.py
curl -fsSL "${RAW}/src/utils/__init__.py"            -o /srv/Capstone/src/utils/__init__.py
curl -fsSL "${RAW}/src/utils/webhook.py"             -o /srv/Capstone/src/utils/webhook.py
curl -fsSL "${RAW}/src/stats/__init__.py"            -o /srv/Capstone/src/stats/__init__.py
curl -fsSL "${RAW}/src/stats/daily_stats.py"         -o /srv/Capstone/src/stats/daily_stats.py

# requirements / docker
curl -fsSL "${RAW}/requirements/crawler.txt"         -o /srv/Capstone/requirements/crawler.txt
curl -fsSL "${RAW}/requirements/loaders.txt"         -o /srv/Capstone/requirements/loaders.txt
curl -fsSL "${RAW}/requirements/stats.txt"           -o /srv/Capstone/requirements/stats.txt
curl -fsSL "${RAW}/docker/crawler/Dockerfile"        -o /srv/Capstone/docker/crawler/Dockerfile
curl -fsSL "${RAW}/docker/loader/Dockerfile"         -o /srv/Capstone/docker/loader/Dockerfile
curl -fsSL "${RAW}/docker-compose.yml"               -o /srv/Capstone/docker-compose.yml

# scripts
curl -fsSL "${RAW}/run_pipeline.sh"                  -o /srv/Capstone/run_pipeline.sh
chmod +x /srv/Capstone/run_pipeline.sh
curl -fsSL "${RAW}/scripts/backup_db.sh"             -o /srv/Capstone/scripts/backup_db.sh
chmod +x /srv/Capstone/scripts/backup_db.sh
curl -fsSL "${RAW}/scripts/run_daily_stats.sh"       -o /srv/Capstone/scripts/run_daily_stats.sh
chmod +x /srv/Capstone/scripts/run_daily_stats.sh

# systemd units
curl -fsSL "${RAW}/deploy/systemd/airchoice-pipeline.service"     -o /srv/Capstone/deploy/systemd/airchoice-pipeline.service
curl -fsSL "${RAW}/deploy/systemd/airchoice-pipeline.timer"       -o /srv/Capstone/deploy/systemd/airchoice-pipeline.timer
curl -fsSL "${RAW}/deploy/systemd/airchoice-backup.service"       -o /srv/Capstone/deploy/systemd/airchoice-backup.service
curl -fsSL "${RAW}/deploy/systemd/airchoice-backup.timer"         -o /srv/Capstone/deploy/systemd/airchoice-backup.timer
curl -fsSL "${RAW}/deploy/systemd/airchoice-daily-stats.service" -o /srv/Capstone/deploy/systemd/airchoice-daily-stats.service
curl -fsSL "${RAW}/deploy/systemd/airchoice-daily-stats.timer"   -o /srv/Capstone/deploy/systemd/airchoice-daily-stats.timer

echo "=== AirChoice deploy complete ==="
