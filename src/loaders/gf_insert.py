from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime
from pathlib import Path

import pymysql
import pymysql.cursors

from src.config import settings

# ------------------------------------------------------------------
# \ub85c\uadf8 \uc124\uc815
# ------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

PARSER_VERSION = "v1.0.0"


# ------------------------------------------------------------------
# DB \uc5f0\uacb0
# ------------------------------------------------------------------
def get_conn():
    return pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        db=settings.mysql_database,
        user=settings.mysql_user or "root",
        password=settings.mysql_password or "",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


# ------------------------------------------------------------------
# \uac00\uaca9 \ud310\uc815 \ucf54\ub4dc \uc0dd\uc131
# ------------------------------------------------------------------
def make_price_meta(route_type: str, has_seller: bool) -> dict:
    if route_type == "oneway":
        return {
            "price_source": "oneway_stage2_card_price",
            "price_status": "official_price" if has_seller else "no_seller_tag",
            "parse_status": "success",
            "price_selection_reason": "oneway_official_seller_card",
        }

    return {
        "price_source": "roundtrip_stage2_card_price",
        "price_status": "official_price" if has_seller else "no_seller_tag",
        "parse_status": "success",
        "price_selection_reason": "same_airline_stage2_roundtrip_total",
    }


# ------------------------------------------------------------------
# observed_at \uc815\uaddc\ud654
# ------------------------------------------------------------------
def normalize_observed_at(value: str) -> str:
    value = value.strip()
    if len(value) == 10:
        return f"{value} 00:00:00"
    return value


# ------------------------------------------------------------------
# search_observation INSERT IGNORE
# raw_file_path UNIQUE \ud0a4 \uae30\uc900\uc73c\ub85c \uc911\ubcf5 \ubc29\uc9c0
# \ubc18\ud658\uac12: observation_id (\uc911\ubcf5 \uc2dc 0)
# ------------------------------------------------------------------
def insert_observation(cur, data: dict, raw_file_path: str) -> int:
    sql = """
        INSERT IGNORE INTO search_observation
            (observed_at, source, route_type,
             origin_iata, destination_iata,
             departure_date, return_date, stay_nights,
             dpd, search_url, crawl_status, raw_file_path)
        VALUES
            (%(observed_at)s, %(source)s, %(route_type)s,
             %(origin_iata)s, %(destination_iata)s,
             %(departure_date)s, %(return_date)s, %(stay_nights)s,
             %(dpd)s, %(search_url)s, %(crawl_status)s, %(raw_file_path)s)
    """

    params = {
        "observed_at":      normalize_observed_at(data["observed_at"]),
        "source":           "google_flights",
        "route_type":       data["route_type"],
        "origin_iata":      data["origin"],
        "destination_iata": data["dest"],
        "departure_date":   data["dep_date"],
        "return_date":      data.get("ret_date"),
        "stay_nights":      data.get("stay_nights"),
        "dpd":              data["dpd"],
        "search_url":       data.get("search_url", ""),
        "crawl_status":     "success",
        "raw_file_path":    raw_file_path,
    }

    cur.execute(sql, params)
    return cur.lastrowid


# ------------------------------------------------------------------
# flight_offer_observation INSERT \u2014 \ud3b8\ub3c4
# ------------------------------------------------------------------
def insert_oneway_offer(cur, observation_id: int, card: dict) -> int:
    dep = card.get("dep") or {}
    seller = card.get("official_seller") or {}
    meta = make_price_meta("oneway", bool(seller))

    sql = """
        INSERT INTO flight_offer_observation
            (observation_id, card_index,
             airline_code, airline_name,
             flight_number,
             dep_time_local, arr_time_local, duration_min,
             stops, aircraft,
             seller_domain, selected_seller_name,
             seller_type, airline_tag_present,
             price_krw,
             price_source, price_status, parse_status, price_selection_reason,
             ret_airline_code, ret_airline_name, ret_flight_number,
             ret_dep_time_local, ret_arr_time_local, ret_duration_min)
        VALUES
            (%(observation_id)s, %(card_index)s,
             %(airline_code)s, %(airline_name)s,
             %(flight_number)s,
             %(dep_time_local)s, %(arr_time_local)s, %(duration_min)s,
             %(stops)s, %(aircraft)s,
             %(seller_domain)s, %(selected_seller_name)s,
             %(seller_type)s, %(airline_tag_present)s,
             %(price_krw)s,
             %(price_source)s, %(price_status)s, %(parse_status)s, %(price_selection_reason)s,
             NULL, NULL, NULL, NULL, NULL, NULL)
    """

    params = {
        "observation_id":       observation_id,
        "card_index":           card.get("card_index", 0),
        "airline_code":         card.get("airline_code"),
        "airline_name":         card.get("airline_name"),
        "flight_number":        dep.get("flight_no"),
        "dep_time_local":       dep.get("dep_time"),
        "arr_time_local":       dep.get("arr_time"),
        "duration_min":         dep.get("duration_min"),
        "stops":                card.get("stops", 0),
        "aircraft":             dep.get("aircraft"),
        "seller_domain":        seller.get("url"),
        "selected_seller_name": seller.get("name"),
        "seller_type":          card.get("seller_type", "unknown"),
        "airline_tag_present":  card.get("airline_tag_present", False),
        "price_krw":            card.get("price_krw"),
        **meta,
    }

    cur.execute(sql, params)
    return cur.lastrowid


# ------------------------------------------------------------------
# flight_offer_observation INSERT \u2014 \uc655\ubcf5
# ------------------------------------------------------------------
def insert_roundtrip_offer(cur, observation_id: int, combo: dict, card_idx: int) -> int:
    seller = combo.get("official_seller") or {}
    meta = make_price_meta("roundtrip", bool(seller))

    sql = """
        INSERT INTO flight_offer_observation
            (observation_id, card_index,
             airline_code, airline_name,
             flight_number,
             dep_time_local, arr_time_local, duration_min,
             stops, aircraft,
             seller_domain, selected_seller_name,
             seller_type, airline_tag_present,
             price_krw,
             price_source, price_status, parse_status, price_selection_reason,
             ret_airline_code, ret_airline_name, ret_flight_number,
             ret_dep_time_local, ret_arr_time_local, ret_duration_min)
        VALUES
            (%(observation_id)s, %(card_index)s,
             %(airline_code)s, %(airline_name)s,
             %(flight_number)s,
             %(dep_time_local)s, %(arr_time_local)s, %(duration_min)s,
             %(stops)s, %(aircraft)s,
             %(seller_domain)s, %(selected_seller_name)s,
             %(seller_type)s, %(airline_tag_present)s,
             %(price_krw)s,
             %(price_source)s, %(price_status)s, %(parse_status)s, %(price_selection_reason)s,
             %(ret_airline_code)s, %(ret_airline_name)s, %(ret_flight_number)s,
             %(ret_dep_time_local)s, %(ret_arr_time_local)s, %(ret_duration_min)s)
    """

    params = {
        "observation_id":       observation_id,
        "card_index":           card_idx,
        "airline_code":         combo.get("airline_code"),
        "airline_name":         combo.get("airline_name"),
        "flight_number":        combo.get("outbound_flight_no"),
        "dep_time_local":       combo.get("outbound_dep_time"),
        "arr_time_local":       combo.get("outbound_arr_time"),
        "duration_min":         combo.get("outbound_duration_min"),
        "stops":                combo.get("stops", 0),
        "aircraft":             combo.get("aircraft"),
        "seller_domain":        seller.get("url"),
        "selected_seller_name": seller.get("name"),
        "seller_type":          combo.get("seller_type", "unknown"),
        "airline_tag_present":  combo.get("airline_tag_present", False),
        "price_krw":            combo.get("price_krw"),
        "ret_airline_code":     combo.get("airline_code"),
        "ret_airline_name":     combo.get("airline_name"),
        "ret_flight_number":    combo.get("inbound_flight_no"),
        "ret_dep_time_local":   combo.get("inbound_dep_time"),
        "ret_arr_time_local":   combo.get("inbound_arr_time"),
        "ret_duration_min":     combo.get("inbound_duration_min"),
        **meta,
    }

    cur.execute(sql, params)
    return cur.lastrowid


# ------------------------------------------------------------------
# capture_file_log INSERT
# ------------------------------------------------------------------
def insert_capture_log(
    cur,
    observation_id: int,
    offer_observation_id: int,
    file_path: Path,
    search_url: str,
) -> int:
    sql = """
        INSERT INTO capture_file_log
            (observation_id, offer_observation_id,
             captured_at, capture_type,
             request_url, response_json_path,
             parser_version)
        VALUES
            (%(observation_id)s, %(offer_observation_id)s,
             %(captured_at)s, %(capture_type)s,
             %(request_url)s, %(response_json_path)s,
             %(parser_version)s)
    """

    params = {
        "observation_id":       observation_id,
        "offer_observation_id": offer_observation_id,
        "captured_at":          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "capture_type":         "getbookingresults",
        "request_url":          search_url,
        "response_json_path":   str(file_path),
        "parser_version":       PARSER_VERSION,
    }

    cur.execute(sql, params)
    return cur.lastrowid


# ------------------------------------------------------------------
# \ud30c\uc77c 1\uac1c \ucc98\ub9ac
# ------------------------------------------------------------------
def process_file(path: Path, conn) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    route_type = data["route_type"]
    tag = f"{route_type} {data['origin']}\u2192{data['dest']} {data['dep_date']}"
    search_url = data.get("search_url", "")
    raw_file_path = str(path)

    inserted_obs = 0
    inserted_offer = 0
    inserted_log = 0
    skipped = 0

    log.info("\ucc98\ub9ac \uc2dc\uc791: %s", path)

    try:
        with conn.cursor() as cur:
            obs_id = insert_observation(cur, data, raw_file_path)

            if obs_id == 0:
                log.info("[%s] \uc911\ubcf5 \ud30c\uc77c \uac10\uc9c0 \u2014 skip", tag)
                conn.commit()
                return {"status": "skip", "obs_id": 0, "offer": 0, "log": 0, "skip": 0}

            inserted_obs = 1

            if route_type == "oneway":
                for card in data.get("cards", []):
                    if not card.get("price_krw"):
                        skipped += 1
                        continue
                    offer_id = insert_oneway_offer(cur, obs_id, card)
                    insert_capture_log(cur, obs_id, offer_id, path, search_url)
                    inserted_offer += 1
                    inserted_log += 1

            else:
                for i, combo in enumerate(data.get("combos", [])):
                    if not combo.get("price_krw"):
                        skipped += 1
                        continue
                    offer_id = insert_roundtrip_offer(cur, obs_id, combo, i)
                    insert_capture_log(cur, obs_id, offer_id, path, search_url)
                    inserted_offer += 1
                    inserted_log += 1

        conn.commit()
        log.info(
            "[%s] observation=%s  offer=%s\uac74  log=%s\uac74  skip=%s\uac74",
            tag, obs_id, inserted_offer, inserted_log, skipped,
        )
        return {
            "status": "ok",
            "obs_id": obs_id,
            "offer":  inserted_offer,
            "log":    inserted_log,
            "skip":   skipped,
        }

    except Exception as e:
        conn.rollback()
        log.error("[%s] INSERT \uc2e4\ud328: %s", tag, e)
        return {
            "status": "error",
            "error":  str(e),
            "obs":    inserted_obs,
            "offer":  inserted_offer,
        }


# ------------------------------------------------------------------
# \ub300\uc0c1 \ud30c\uc77c \ud574\uc11d
# ------------------------------------------------------------------
def resolve_target_files(args) -> list[Path]:
    if args.file:
        file_path = Path(args.file)
        if not file_path.is_absolute():
            file_path = settings.project_root / file_path
        return [file_path]

    target_date = args.date or date.today().isoformat()
    base_dir = settings.raw_google_flights_dir / target_date

    if args.hour is not None:
        # \ud68c\ucc28 \uc9c0\uc815: YYYY-MM-DD/HH00/ \ud558\uc704 \ud3f4\ub354\uc5d0\uc11c \ucc3e\uc74c
        hour_str = f"{args.hour:02d}00"
        collect_dir = base_dir / hour_str
        files = sorted(collect_dir.glob("*.json"))
        log.info("\ub300\uc0c1: %s/%s  \ud30c\uc77c: %s\uac1c", target_date, hour_str, len(files))
    else:
        # \uc2dc\uac04 \ubbf8\uc9c0\uc815: \ud558\uc704 \ud3f4\ub354 \uc804\uccb4 \ud0d0\uc0c9
        files = sorted(base_dir.glob("*/*.json"))
        log.info("\ub300\uc0c1: %s \uc804\uccb4  \ud30c\uc77c: %s\uac1c", target_date, len(files))

    return files


# ------------------------------------------------------------------
# \uba54\uc778
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Google Flights INSERT")
    parser.add_argument(
        "--date",
        default=None,
        help="\uc218\uc9d1\uc77c (\uc608: 2026-04-16). \uc0dd\ub7b5 \uc2dc \uc624\ub298 \ub0a0\uc9dc \uc790\ub3d9 \ucc98\ub9ac.",
    )
    parser.add_argument(
        "--hour",
        type=int,
        default=None,
        help="\uc218\uc9d1 \uc2dc\uc791 \uc2dc\uac01 (0/8/16). \uc0dd\ub7b5 \uc2dc \ud574\ub2f9 \ub0a0\uc9dc \uc804\uccb4 \uc2dc\uac04 \ubaa8\ub450 \ucc98\ub9ac.",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="\ub2e8\uc77c JSON \ud30c\uc77c \uacbd\ub85c (\ud14c\uc2a4\ud2b8\uc6a9).",
    )
    args = parser.parse_args()

    files = resolve_target_files(args)

    if not files:
        log.warning("\ucc98\ub9ac\ud560 \ud30c\uc77c \uc5c6\uc74c")
        return

    conn = get_conn()
    total = {"ok": 0, "skip": 0, "error": 0, "offer": 0}

    try:
        for file_path in files:
            result = process_file(file_path, conn)
            if result["status"] == "ok":
                total["ok"] += 1
                total["offer"] += result["offer"]
            elif result["status"] == "skip":
                total["skip"] += 1
            else:
                total["error"] += 1
    finally:
        conn.close()

    log.info(
        "\uc644\ub8cc  \uc131\uacf5=%s  \uc911\ubcf5skip=%s  \uc2e4\ud328=%s  \uc785\ub825 offer=%s\uac74",
        total["ok"], total["skip"], total["error"], total["offer"],
    )


if __name__ == "__main__":
    main()
