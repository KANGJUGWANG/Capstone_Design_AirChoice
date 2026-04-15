#!/usr/bin/env python3
"""
src/utils/webhook.py
역할: Discord 웹훅 알림 전송
이벤트:
  startup       초기 상태 스냅샷 (raw / DB / backup)
  collect_done  --elapsed <분>
  insert_done   --hour <0~23> --date <YYYY-MM-DD>
  pipeline_fail --stage <collector|loader> --error <message>
  backup_done   --size <크기> --file <파일명>
  disk_warn
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path("/srv/Capstone")
ENV_FILE = PROJECT_ROOT / ".env"
DISK_WARN_THRESHOLD = 80


def _load_env() -> dict:
    env = {}
    if not ENV_FILE.exists():
        return env
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


_ENV = _load_env()

WEBHOOK_URL     = _ENV.get("DISCORD_WEBHOOK_URL", "")
MYSQL_CONTAINER = "capstone-mysql"
MYSQL_DATABASE  = _ENV.get("MYSQL_DATABASE", "capstone_db")
MYSQL_PASSWORD  = _ENV.get("MYSQL_ROOT_PASSWORD", "")
RAW_DIR         = PROJECT_ROOT / "data" / "raw" / "google_flights"
BACKUP_DIR      = PROJECT_ROOT / "backups"


def _get_disk_info() -> dict:
    try:
        usage = shutil.disk_usage("/")
        total_gb = usage.total / 1024 ** 3
        used_gb  = usage.used  / 1024 ** 3
        free_gb  = usage.free  / 1024 ** 3
        percent  = used_gb / total_gb * 100
        display  = f"{used_gb:.1f} GB / {total_gb:.0f} GB · 잔여 {free_gb:.1f} GB ({percent:.1f}%)"
        return {"percent": percent, "display": display}
    except Exception:
        return {"percent": 0, "display": "조회 실패"}


def _query(sql: str) -> str:
    if not MYSQL_PASSWORD:
        return ""
    cmd = [
        "docker", "exec", MYSQL_CONTAINER,
        "mysql", "-h", "127.0.0.1",
        "-uroot", f"-p{MYSQL_PASSWORD}",
        "-N", "-s", MYSQL_DATABASE,
        "-e", sql,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.stdout.strip()
    except Exception:
        return ""


def _query_rows(sql: str) -> list[list[str]]:
    raw = _query(sql)
    if not raw:
        return []
    return [line.split("\t") for line in raw.splitlines()]


def _query_int(sql: str, default: int = 0) -> int:
    try:
        return int(_query(sql).strip())
    except Exception:
        return default


def _send(embed: dict) -> bool:
    if not WEBHOOK_URL:
        print("[webhook] DISCORD_WEBHOOK_URL 미설정 — skip", file=sys.stderr)
        return False
    try:
        payload = {"content": "", "embeds": [embed]}
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            WEBHOOK_URL, data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            method="POST",
        )
        with urlopen(req, timeout=10) as resp:
            return resp.status in (200, 204)
    except URLError as e:
        print(f"[webhook] 전송 실패: {e}", file=sys.stderr)
        return False


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _today() -> str:
    return date.today().isoformat()


def _hour_label(hour: int) -> str:
    return f"{hour:02d}:00"


# ---------------------------------------------------------------------------
# startup: raw / DB / backup 초기 상태 스냅샷
# ---------------------------------------------------------------------------
def startup() -> None:
    # raw JSON 파일 현황
    raw_dates = sorted(p.name for p in RAW_DIR.iterdir() if p.is_dir()) if RAW_DIR.exists() else []
    if raw_dates:
        raw_lines = "\n".join(
            f"`{d}`: {sum(1 for _ in (RAW_DIR / d).rglob('*.json'))}개"
            for d in raw_dates
        )
    else:
        raw_lines = "없음 (초기화 완료)"

    # DB 현황
    total_obs   = _query_int("SELECT COUNT(*) FROM search_observation")
    total_offer = _query_int("SELECT COUNT(*) FROM flight_offer_observation")
    obs_rows = _query_rows(
        "SELECT observed_at, COUNT(*) FROM search_observation "
        "GROUP BY observed_at ORDER BY observed_at DESC LIMIT 5"
    )
    db_detail = "\n".join(
        f"`{r[0]}`: {int(r[1])}건" for r in obs_rows if len(r) == 2
    ) or "없음 (초기화 완료)"

    # 백업 현황
    backup_files = sorted(BACKUP_DIR.glob("*.sql.gz")) if BACKUP_DIR.exists() else []
    if backup_files:
        backup_lines = "\n".join(f"`{f.name}`" for f in backup_files[-3:])
    else:
        backup_lines = "없음 (초기화 완료)"

    disk = _get_disk_info()

    _send({
        "title": f"수집 시작 — {_today()} {_hour_label(datetime.now().hour)}",
        "color": 0x9B59B6,
        "fields": [
            {"name": "raw JSON 현황", "value": raw_lines, "inline": False},
            {"name": "DB 누적", "value": f"search: {total_obs:,}건 / offer: {total_offer:,}건", "inline": False},
            {"name": "최근 회차 (최대 5)", "value": db_detail, "inline": False},
            {"name": "백업 파일 (최근 3)", "value": backup_lines, "inline": False},
            {"name": "디스크", "value": disk["display"], "inline": False},
        ],
        "footer": {"text": f"AirChoice · {_now_str()}"},
    })


# ---------------------------------------------------------------------------
# collect_done
# ---------------------------------------------------------------------------
def collect_done(elapsed_min: int) -> None:
    today = _today()
    collect_dir = RAW_DIR / today
    route_counts: dict[str, int] = {}
    total_files = 0

    if collect_dir.exists():
        for f in sorted(collect_dir.rglob("*_oneway_*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                parts = f.stem.split("_")
                if len(parts) >= 4:
                    route = f"{parts[2]}\u2192{parts[3]}"
                    route_counts[route] = route_counts.get(route, 0) + data.get("card_count", 0)
                total_files += 1
            except Exception:
                pass
        total_files += sum(1 for _ in collect_dir.rglob("*_roundtrip_*.json"))

    elapsed_h = elapsed_min // 60
    elapsed_m = elapsed_min % 60
    elapsed_str = f"{elapsed_h}h {elapsed_m}m" if elapsed_h else f"{elapsed_m}m"
    route_lines = "\n".join(
        f"`{route}`: {cnt:,}건" for route, cnt in sorted(route_counts.items())
    ) or "집계 없음"

    collect_hour = datetime.now().hour
    _send({
        "title": f"수집 완료 — {today} {_hour_label(collect_hour)}",
        "color": 0x57F287,
        "fields": [
            {"name": "소요 시간", "value": elapsed_str, "inline": True},
            {"name": "수집 파일", "value": f"{total_files}개", "inline": True},
            {"name": "노선별 카드 수 (편도)", "value": route_lines, "inline": False},
        ],
        "footer": {"text": f"AirChoice · {_now_str()}"},
    })


# ---------------------------------------------------------------------------
# insert_done
# ---------------------------------------------------------------------------
def insert_done(collect_hour: int, collect_date: str) -> None:
    obs_count = _query_int(f"""
        SELECT COUNT(*) FROM search_observation
        WHERE DATE(observed_at) = '{collect_date}' AND HOUR(observed_at) = {collect_hour}
    """)
    offer_count = _query_int(f"""
        SELECT COUNT(f.offer_observation_id)
        FROM flight_offer_observation f
        JOIN search_observation s ON f.observation_id = s.observation_id
        WHERE DATE(s.observed_at) = '{collect_date}' AND HOUR(s.observed_at) = {collect_hour}
    """)
    status_rows = _query_rows(f"""
        SELECT f.price_status, COUNT(*) as cnt
        FROM flight_offer_observation f
        JOIN search_observation s ON f.observation_id = s.observation_id
        WHERE DATE(s.observed_at) = '{collect_date}' AND HOUR(s.observed_at) = {collect_hour}
        GROUP BY f.price_status
    """)
    status_lines = "\n".join(
        f"`{r[0]}`: {int(r[1]):,}건 ({int(r[1]) / max(offer_count, 1) * 100:.1f}%)"
        for r in status_rows if len(r) == 2
    ) or "없음"

    price_row = _query_rows(f"""
        SELECT MIN(f.price_krw), MAX(f.price_krw), ROUND(AVG(f.price_krw))
        FROM flight_offer_observation f
        JOIN search_observation s ON f.observation_id = s.observation_id
        WHERE s.route_type = 'oneway' AND s.origin_iata = 'ICN'
        AND s.destination_iata = 'NRT'
        AND DATE(s.observed_at) = '{collect_date}' AND HOUR(s.observed_at) = {collect_hour}
        AND f.price_krw IS NOT NULL
    """)
    price_str = "없음"
    if price_row and len(price_row[0]) == 3:
        try:
            r = price_row[0]
            price_str = f"최저 {int(r[0]):,}원 / 최고 {int(r[1]):,}원 / 평균 {int(r[2]):,}원"
        except Exception:
            pass

    total_obs   = _query_int("SELECT COUNT(*) FROM search_observation")
    total_offer = _query_int("SELECT COUNT(*) FROM flight_offer_observation")
    yesterday_offer = _query_int(f"""
        SELECT COUNT(f.offer_observation_id)
        FROM flight_offer_observation f
        JOIN search_observation s ON f.observation_id = s.observation_id
        WHERE DATE(s.observed_at) = DATE_SUB('{collect_date}', INTERVAL 1 DAY)
        AND HOUR(s.observed_at) = {collect_hour}
    """)
    delta_str = ""
    if yesterday_offer > 0:
        delta = offer_count - yesterday_offer
        sign = "+" if delta >= 0 else ""
        delta_str = f"전회차 대비 {sign}{delta:,}건"

    disk = _get_disk_info()

    _send({
        "title": f"적재 완료 — {collect_date} {_hour_label(collect_hour)}",
        "color": 0x5865F2,
        "fields": [
            {"name": "이번 적재", "value": f"search: {obs_count:,}건 / offer: {offer_count:,}건", "inline": False},
            {"name": "가격 상태 분포", "value": status_lines, "inline": False},
            {"name": "ICN→NRT 가격 범위 (편도)", "value": price_str, "inline": False},
            {"name": "DB 누적", "value": f"search: {total_obs:,}건 / offer: {total_offer:,}건", "inline": False},
            {"name": "디스크", "value": disk["display"], "inline": False},
        ],
        "footer": {"text": f"AirChoice · {_now_str()}{' · ' + delta_str if delta_str else ''}"},
    })


# ---------------------------------------------------------------------------
# pipeline_fail
# ---------------------------------------------------------------------------
def pipeline_fail(stage: str, error: str) -> None:
    _send({
        "title": f"파이프라인 실패 — {stage}",
        "color": 0xED4245,
        "fields": [
            {"name": "실패 단계", "value": stage, "inline": True},
            {"name": "시각", "value": _now_str(), "inline": True},
            {"name": "에러", "value": f"```{error[:200]}```", "inline": False},
            {"name": "로그", "value": "`/srv/Capstone/logs/cron.log`", "inline": False},
        ],
        "footer": {"text": "AirChoice"},
    })


# ---------------------------------------------------------------------------
# backup_done
# ---------------------------------------------------------------------------
def backup_done(size: str, filename: str) -> None:
    total_obs   = _query_int("SELECT COUNT(*) FROM search_observation")
    total_offer = _query_int("SELECT COUNT(*) FROM flight_offer_observation")

    _send({
        "title": f"백업 완료 — {_today()} 23:00",
        "color": 0xFEE75C,
        "fields": [
            {"name": "파일", "value": f"`{filename}`", "inline": False},
            {"name": "크기", "value": size, "inline": True},
            {"name": "업로드", "value": "Google Drive", "inline": True},
            {"name": "DB 누적", "value": f"search: {total_obs:,}건 / offer: {total_offer:,}건", "inline": False},
        ],
        "footer": {"text": f"AirChoice · {_now_str()}"},
    })


# ---------------------------------------------------------------------------
# disk_warn
# ---------------------------------------------------------------------------
def disk_warn() -> None:
    disk = _get_disk_info()
    if disk["percent"] < DISK_WARN_THRESHOLD:
        return
    _send({
        "title": f"⚠️ 디스크 경고 — {disk['percent']:.1f}% 사용 중",
        "color": 0xED4245,
        "fields": [
            {"name": "사용량", "value": disk["display"], "inline": False},
            {"name": "조치 필요", "value": "`/srv/Capstone/data/raw/` JSON 정리 또는 로그 확인", "inline": False},
        ],
        "footer": {"text": f"AirChoice · {_now_str()}"},
    })


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="AirChoice Discord webhook")
    sub = parser.add_subparsers(dest="event")

    sub.add_parser("startup")

    p_collect = sub.add_parser("collect_done")
    p_collect.add_argument("--elapsed", type=int, default=0)

    p_insert = sub.add_parser("insert_done")
    p_insert.add_argument("--hour", type=int, default=datetime.now().hour)
    p_insert.add_argument("--date", type=str, default=date.today().isoformat())

    p_fail = sub.add_parser("pipeline_fail")
    p_fail.add_argument("--stage", default="unknown")
    p_fail.add_argument("--error", default="비정상 종료")

    p_backup = sub.add_parser("backup_done")
    p_backup.add_argument("--size", default="?")
    p_backup.add_argument("--file", default="?")

    sub.add_parser("disk_warn")

    args = parser.parse_args()

    if args.event == "startup":
        startup()
    elif args.event == "collect_done":
        collect_done(args.elapsed)
    elif args.event == "insert_done":
        insert_done(args.hour, args.date)
    elif args.event == "pipeline_fail":
        pipeline_fail(args.stage, args.error)
    elif args.event == "backup_done":
        backup_done(args.size, args.file)
    elif args.event == "disk_warn":
        disk_warn()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
