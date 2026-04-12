from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pymysql
import pymysql.cursors

from src.config import settings

# ------------------------------------------------------------------
# 로그 설정
# ------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# DB 연결
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
# 가격 판정 코드 생성
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
# observed_at 정규화
# ------------------------------------------------------------------
def normalize_observed_at(value: str) -> str:
    value = value.strip()
    if len(value) == 10:
        return f"{value} 00:00:00"
    return value


# ------------------------------------------------------------------
# search_observation INSERT
# ------------------------------------------------------------------
def insert_observation(cur, data: dict) -> int:
    sql = """
        INSERT INTO search_observation
            (observed_at, source, route_type,
             origin_iata, destination_iata,
             departure_date, return_date, stay_nights,
             dpd, search_url, crawl_status)
        VALUES
            (%(observed_at)s, %(source)s, %(route_type)s,
             %(origin_iata)s, %(destination_iata)s,
             %(departure_date)s, %(return_date)s, %(stay_nights)s,
             %(dpd)s, %(search_url)s, %(crawl_status)s)
    """

    params = {
        "observed_at": normalize_observed_at(data["observed_at"]),
        "source": "google_flights",
        "route_type": data["route_type"],
        "origin_iata": data["origin"],
        "destination_iata": data["dest"],
        "departure_date": data["dep_date"],
        "return_date": data.get("ret_date"),
        "stay_nights": data.get("stay_nights"),
        "dpd": data["dpd"],
        "search_url": data.get("search_url", ""),
        "crawl_status": "success",
    }

    cur.execute(sql, params)
    return cur.lastrowid


# ------------------------------------------------------------------
# flight_offer_observation INSERT — 편도
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
             seller_domain, selected_seller_name,
             price_krw,
             price_source, price_status, parse_status, price_selection_reason,
             ret_airline_code, ret_airline_name, ret_flight_number,
             ret_dep_time_local, ret_arr_time_local, ret_duration_min)
        VALUES
            (%(observation_id)s, %(card_index)s,
             %(airline_code)s, %(airline_name)s,
             %(flight_number)s,
             %(dep_time_local)s, %(arr_time_local)s, %(duration_min)s,
             %(seller_domain)s, %(selected_seller_name)s,
             %(price_krw)s,
             %(price_source)s, %(price_status)s, %(parse_status)s, %(price_selection_reason)s,
             NULL, NULL, NULL, NULL, NULL, NULL)
    """

    params = {
        "observation_id": observation_id,
        "card_index": card.get("card_index", 0),
        "airline_code": card.get("airline_code"),
        "airline_name": card.get("airline_name"),
        "flight_number": dep.get("flight_no"),
        "dep_time_local": dep.get("dep_time"),
        "arr_time_local": dep.get("arr_time"),
        "duration_min": dep.get("duration_min"),
        "seller_domain": seller.get("url"),
        "selected_seller_name": seller.get("name"),
        "price_krw": card.get("price_krw"),
        **meta,
    }

    cur.execute(sql, params)
    return cur.lastrowid


# ------------------------------------------------------------------
# flight_offer_observation INSERT — 왕복
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
             seller_domain, selected_seller_name,
             price_krw,
             price_source, price_status, parse_status, price_selection_reason,
             ret_airline_code, ret_airline_name, ret_flight_number,
             ret_dep_time_local, ret_arr_time_local, ret_duration_min)
        VALUES
            (%(observation_id)s, %(card_index)s,
             %(airline_code)s, %(airline_name)s,
             %(flight_number)s,
             %(dep_time_local)s, %(arr_time_local)s, %(duration_min)s,
             %(seller_domain)s, %(selected_seller_name)s,
             %(price_krw)s,
             %(price_source)s, %(price_status)s, %(parse_status)s, %(price_selection_reason)s,
             %(ret_airline_code)s, %(ret_airline_name)s, %(ret_flight_number)s,
             %(ret_dep_time_local)s, %(ret_arr_time_local)s, %(ret_duration_min)s)
    """

    params = {
        "observation_id": observation_id,
        "card_index": card_idx,
        "airline_code": combo.get("airline_code"),
        "airline_name": combo.get("airline_name"),
        "flight_number": combo.get("outbound_flight_no"),
        "dep_time_local": combo.get("outbound_dep_time"),
        "arr_time_local": combo.get("outbound_arr_time"),
        "duration_min": combo.get("outbound_duration_min"),
        "seller_domain": seller.get("url"),
        "selected_seller_name": seller.get("name"),
        "price_krw": combo.get("price_krw"),
        "ret_airline_code": combo.get("airline_code"),
        "ret_airline_name": combo.get("airline_name"),
        "ret_flight_number": combo.get("inbound_flight_no"),
        "ret_dep_time_local": combo.get("inbound_dep_time"),
        "ret_arr_time_local": combo.get("inbound_arr_time"),
        "ret_duration_min": combo.get("inbound_duration_min"),
        **meta,
    }

    cur.execute(sql, params)
    return cur.lastrowid


# ------------------------------------------------------------------
# 파일 1개 처리
# ------------------------------------------------------------------
def process_file(path: Path, conn) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    route_type = data["route_type"]
    tag = f"{route_type} {data['origin']}→{data['dest']} {data['dep_date']}"

    inserted_obs = 0
    inserted_offer = 0
    skipped = 0

    log.info("처리 시작: %s", path)

    try:
        with conn.cursor() as cur:
            obs_id = insert_observation(cur, data)
            inserted_obs = 1

            if route_type == "oneway":
                for card in data.get("cards", []):
                    if not card.get("price_krw"):
                        skipped += 1
                        continue
                    insert_oneway_offer(cur, obs_id, card)
                    inserted_offer += 1

            else:
                for i, combo in enumerate(data.get("combos", [])):
                    if not combo.get("price_krw"):
                        skipped += 1
                        continue
                    insert_roundtrip_offer(cur, obs_id, combo, i)
                    inserted_offer += 1

        conn.commit()
        log.info(
            "[%s] observation=%s  offer=%s건  skip=%s건",
            tag,
            obs_id,
            inserted_offer,
            skipped,
        )
        return {
            "status": "ok",
            "obs_id": obs_id,
            "offer": inserted_offer,
            "skip": skipped,
        }

    except Exception as e:
        conn.rollback()
        log.error("[%s] INSERT 실패: %s", tag, e)
        return {
            "status": "error",
            "error": str(e),
            "obs": inserted_obs,
            "offer": inserted_offer,
        }


# ------------------------------------------------------------------
# 대상 파일 해석
# ------------------------------------------------------------------
def resolve_target_files(args) -> list[Path]:
    if args.file:
        file_path = Path(args.file)
        if not file_path.is_absolute():
            file_path = settings.project_root / file_path
        return [file_path]

    collect_dir = settings.raw_google_flights_dir / args.date
    files = sorted(collect_dir.glob("*.json"))
    log.info("대상 파일: %s개  (%s)", len(files), collect_dir)
    return files


# ------------------------------------------------------------------
# 메인
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--date", help="수집일 (예: 2026-04-12) — 해당 날짜 폴더 전체 처리")
    group.add_argument("--file", help="단일 JSON 파일 경로")
    args = parser.parse_args()

    files = resolve_target_files(args)

    if not files:
        log.warning("처리할 파일 없음")
        return

    conn = get_conn()
    total = {"ok": 0, "error": 0, "offer": 0}

    try:
        for file_path in files:
            result = process_file(file_path, conn)
            if result["status"] == "ok":
                total["ok"] += 1
                total["offer"] += result["offer"]
            else:
                total["error"] += 1
    finally:
        conn.close()

    log.info(
        "완료  성공=%s  실패=%s  총 offer=%s건",
        total["ok"],
        total["error"],
        total["offer"],
    )


if __name__ == "__main__":
    main()