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
import time
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
        display  = f"{used_gb:.1f} GB / {total_gb:.0f} GB · \uc794\uc5ec {free_gb:.1f} GB ({percent:.1f}%)"
        return {"percent": percent, "display": display}
    except Exception:
        return {"percent": 0, "display": "\uc870\ud68c \uc2e4\ud328"}


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


def _send(embed: dict, max_retries: int = 3) -> bool:
    """Discord embed 전송. 503/429 등 일시 장애 시 에크스포년셜셜 백오프로 재시도."""
    if not WEBHOOK_URL:
        print("[webhook] DISCORD_WEBHOOK_URL \ubbf8\uc124\uc815 \u2014 skip", file=sys.stderr)
        return False

    payload = {"content": "", "embeds": [embed]}
    data = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        try:
            req = Request(
                WEBHOOK_URL, data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0",
                },
                method="POST",
            )
            with urlopen(req, timeout=10) as resp:
                if resp.status in (200, 204):
                    return True
                print(f"[webhook] HTTP {resp.status} (\uc2dc\ub3c4 {attempt+1}/{max_retries})", file=sys.stderr)
        except URLError as e:
            print(f"[webhook] \uc804\uc1a1 \uc2e4\ud328 (\uc2dc\ub3c4 {attempt+1}/{max_retries}): {e}", file=sys.stderr)

        if attempt < max_retries - 1:
            wait = 5 * (attempt + 1)  # 5s, 10s backoff
            print(f"[webhook] {wait}\ucd08 \ud6c4 \uc7ac\uc2dc\ub3c4...", file=sys.stderr)
            time.sleep(wait)

    return False


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _today() -> str:
    return date.today().isoformat()


def _hour_label(hour: int) -> str:
    return f"{hour:02d}:00"


# ---------------------------------------------------------------------------
# startup
# ---------------------------------------------------------------------------
def startup() -> None:
    raw_dates = sorted(p.name for p in RAW_DIR.iterdir() if p.is_dir()) if RAW_DIR.exists() else []
    if raw_dates:
        raw_lines = "\n".join(
            f"`{d}`: {sum(1 for _ in (RAW_DIR / d).rglob('*.json'))}\uac1c"
            for d in raw_dates
        )
    else:
        raw_lines = "\uc5c6\uc74c (\ucd08\uae30\ud654 \uc644\ub8cc)"

    total_obs   = _query_int("SELECT COUNT(*) FROM search_observation")
    total_offer = _query_int("SELECT COUNT(*) FROM flight_offer_observation")
    obs_rows = _query_rows(
        "SELECT observed_at, COUNT(*) FROM search_observation "
        "GROUP BY observed_at ORDER BY observed_at DESC LIMIT 5"
    )
    db_detail = "\n".join(
        f"`{r[0]}`: {int(r[1])}\uac74" for r in obs_rows if len(r) == 2
    ) or "\uc5c6\uc74c (\ucd08\uae30\ud654 \uc644\ub8cc)"

    backup_files = sorted(BACKUP_DIR.glob("*.sql.gz")) if BACKUP_DIR.exists() else []
    backup_lines = "\n".join(f"`{f.name}`" for f in backup_files[-3:]) if backup_files else "\uc5c6\uc74c"

    disk = _get_disk_info()
    _send({
        "title": f"\uc218\uc9d1 \uc2dc\uc791 \u2014 {_today()} {_hour_label(datetime.now().hour)}",
        "color": 0x9B59B6,
        "fields": [
            {"name": "raw JSON \ud604\ud669", "value": raw_lines, "inline": False},
            {"name": "DB \ub204\uc801", "value": f"search: {total_obs:,}\uac74 / offer: {total_offer:,}\uac74", "inline": False},
            {"name": "\ucd5c\uadfc \ud68c\ucc28 (\ucd5c\ub300 5)", "value": db_detail, "inline": False},
            {"name": "\ubc31\uc5c5 \ud30c\uc77c (\ucd5c\uadfc 3)", "value": backup_lines, "inline": False},
            {"name": "\ub514\uc2a4\ud06c", "value": disk["display"], "inline": False},
        ],
        "footer": {"text": f"AirChoice \u00b7 {_now_str()}"},
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
        # 현재 회차 HH00 폴더만 집계 — 당일 전체 누적 표시 오류 수정
        collect_hour_str = datetime.now().strftime("%H") + "00"
        hour_dir = collect_dir / collect_hour_str
        scan_dir = hour_dir if hour_dir.exists() else collect_dir
        for f in sorted(scan_dir.rglob("*_oneway_*.json")):
            try:
                import json as _json
                data = _json.loads(f.read_text(encoding="utf-8"))
                parts = f.stem.split("_")
                if len(parts) >= 4:
                    route = f"{parts[2]}\u2192{parts[3]}"
                    route_counts[route] = route_counts.get(route, 0) + data.get("card_count", 0)
                total_files += 1
            except Exception:
                pass
        total_files += sum(1 for _ in scan_dir.rglob("*_roundtrip_*.json"))

    elapsed_h = elapsed_min // 60
    elapsed_m = elapsed_min % 60
    elapsed_str = f"{elapsed_h}h {elapsed_m}m" if elapsed_h else f"{elapsed_m}m"
    route_lines = "\n".join(
        f"`{route}`: {cnt:,}\uac74" for route, cnt in sorted(route_counts.items())
    ) or "\uc9d1\uacc4 \uc5c6\uc74c"

    collect_hour = datetime.now().hour
    _send({
        "title": f"\uc218\uc9d1 \uc644\ub8cc \u2014 {today} {_hour_label(collect_hour)}",
        "color": 0x57F287,
        "fields": [
            {"name": "\uc18c\uc694 \uc2dc\uac04", "value": elapsed_str, "inline": True},
            {"name": "\uc218\uc9d1 \ud30c\uc77c", "value": f"{total_files}\uac1c", "inline": True},
            {"name": "\ub178\uc120\ubcc4 \uce74\ub4dc \uc218 (\ud3b8\ub3c4)", "value": route_lines, "inline": False},
        ],
        "footer": {"text": f"AirChoice \u00b7 {_now_str()}"},
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
        f"`{r[0]}`: {int(r[1]):,}\uac74 ({int(r[1]) / max(offer_count, 1) * 100:.1f}%)"
        for r in status_rows if len(r) == 2
    ) or "\uc5c6\uc74c"

    price_row = _query_rows(f"""
        SELECT MIN(f.price_krw), MAX(f.price_krw), ROUND(AVG(f.price_krw))
        FROM flight_offer_observation f
        JOIN search_observation s ON f.observation_id = s.observation_id
        WHERE s.route_type = 'oneway' AND s.origin_iata = 'ICN'
        AND s.destination_iata = 'NRT'
        AND DATE(s.observed_at) = '{collect_date}' AND HOUR(s.observed_at) = {collect_hour}
        AND f.price_krw IS NOT NULL
    """)
    price_str = "\uc5c6\uc74c"
    if price_row and len(price_row[0]) == 3:
        try:
            r = price_row[0]
            price_str = f"\ucd5c\uc800 {int(r[0]):,}\uc6d0 / \ucd5c\uace0 {int(r[1]):,}\uc6d0 / \ud3c9\uade0 {int(r[2]):,}\uc6d0"
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
        delta_str = f"\uc804\ud68c\ucc28 \ub300\ube44 {sign}{delta:,}\uac74"

    disk = _get_disk_info()
    _send({
        "title": f"\uc801\uc7ac \uc644\ub8cc \u2014 {collect_date} {_hour_label(collect_hour)}",
        "color": 0x5865F2,
        "fields": [
            {"name": "\uc774\ubc88 \uc801\uc7ac", "value": f"search: {obs_count:,}\uac74 / offer: {offer_count:,}\uac74", "inline": False},
            {"name": "\uac00\uaca9 \uc0c1\ud0dc \ubd84\ud3ec", "value": status_lines, "inline": False},
            {"name": "ICN\u2192NRT \uac00\uaca9 \ubc94\uc704 (\ud3b8\ub3c4)", "value": price_str, "inline": False},
            {"name": "DB \ub204\uc801", "value": f"search: {total_obs:,}\uac74 / offer: {total_offer:,}\uac74", "inline": False},
            {"name": "\ub514\uc2a4\ud06c", "value": disk["display"], "inline": False},
        ],
        "footer": {"text": f"AirChoice \u00b7 {_now_str()}{' \u00b7 ' + delta_str if delta_str else ''}"},
    })


# ---------------------------------------------------------------------------
# pipeline_fail
# ---------------------------------------------------------------------------
def pipeline_fail(stage: str, error: str) -> None:
    _send({
        "title": f"\ud30c\uc774\ud504\ub77c\uc778 \uc2e4\ud328 \u2014 {stage}",
        "color": 0xED4245,
        "fields": [
            {"name": "\uc2e4\ud328 \ub2e8\uacc4", "value": stage, "inline": True},
            {"name": "\uc2dc\uac01", "value": _now_str(), "inline": True},
            {"name": "\uc5d0\ub7ec", "value": f"```{error[:200]}```", "inline": False},
            {"name": "\ub85c\uadf8", "value": "`/srv/Capstone/logs/cron.log`", "inline": False},
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
        "title": f"\ubc31\uc5c5 \uc644\ub8cc \u2014 {_today()} 23:00",
        "color": 0xFEE75C,
        "fields": [
            {"name": "\ud30c\uc77c", "value": f"`{filename}`", "inline": False},
            {"name": "\ud06c\uae30", "value": size, "inline": True},
            {"name": "\uc5c5\ub85c\ub4dc", "value": "Google Drive", "inline": True},
            {"name": "DB \ub204\uc801", "value": f"search: {total_obs:,}\uac74 / offer: {total_offer:,}\uac74", "inline": False},
        ],
        "footer": {"text": f"AirChoice \u00b7 {_now_str()}"},
    })


# ---------------------------------------------------------------------------
# disk_warn
# ---------------------------------------------------------------------------
def disk_warn() -> None:
    disk = _get_disk_info()
    if disk["percent"] < DISK_WARN_THRESHOLD:
        return
    _send({
        "title": f"\u26a0\ufe0f \ub514\uc2a4\ud06c \uacbd\uace0 \u2014 {disk['percent']:.1f}% \uc0ac\uc6a9 \uc911",
        "color": 0xED4245,
        "fields": [
            {"name": "\uc0ac\uc6a9\ub7c9", "value": disk["display"], "inline": False},
            {"name": "\uc870\uce58 \ud544\uc694", "value": "`/srv/Capstone/data/raw/` JSON \uc815\ub9ac \ub610\ub294 \ub85c\uadf8 \ud655\uc778", "inline": False},
        ],
        "footer": {"text": f"AirChoice \u00b7 {_now_str()}"},
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
    p_fail.add_argument("--error", default="\ube44\uc815\uc0c1 \uc885\ub8cc")

    p_backup = sub.add_parser("backup_done")
    p_backup.add_argument("--size", default="?")
    p_backup.add_argument("--file", default="?")

    sub.add_parser("disk_warn")

    args = parser.parse_args()

    if args.event == "startup":        startup()
    elif args.event == "collect_done": collect_done(args.elapsed)
    elif args.event == "insert_done":  insert_done(args.hour, args.date)
    elif args.event == "pipeline_fail": pipeline_fail(args.stage, args.error)
    elif args.event == "backup_done":  backup_done(args.size, args.file)
    elif args.event == "disk_warn":    disk_warn()
    else:                              parser.print_help()


if __name__ == "__main__":
    main()
