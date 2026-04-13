from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, timedelta

from playwright.async_api import Browser, Page, async_playwright

from src.config import settings
from src.crawler.constants import (
    CARD_SELECTORS,
    DPD_MAX,
    DPD_MIN,
    DPD_PARALLEL,
    INTERCEPT,
    ONEWAY_ROUTES,
    PLAYWRIGHT_LAUNCH_ARGS,
    PLAYWRIGHT_LOCALE,
    PLAYWRIGHT_TIMEZONE,
    PLAYWRIGHT_VIEWPORT,
    ROUNDTRIP_ROUTES,
    STAY_NIGHTS,
)
from src.crawler.parser import extract_cards, parse_chunks
from src.crawler.url_builder import build_url


_log_file = settings.logs_dir / f"collect_{date.today().isoformat()}.log"

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_log_file, encoding="utf-8"),
    ],
)

log = logging.getLogger(__name__)


async def _wait_for_response(page: Page, min_ms: int = 2_000, networkidle_timeout: int = 10_000) -> None:
    """
    최소 대기 후 networkidle 동적 대기.

    병렬 수집 시 networkidle만 사용하면 다른 컨텍스트의 네트워크 상태가
    조용해지는 시점에 premature trigger가 발생할 수 있음.
    최소 대기(min_ms)로 인터셉트 대상 응답을 먼저 확보한 뒤 networkidle 적용.
    """
    await page.wait_for_timeout(min_ms)
    try:
        await page.wait_for_load_state("networkidle", timeout=networkidle_timeout)
    except Exception:
        pass


async def get_card_els(page: Page) -> list:
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(1_200)
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(400)

    for selector in CARD_SELECTORS:
        els = await page.query_selector_all(selector)
        if els:
            return els

    return []


async def collect_oneway(
    browser: Browser,
    dep_date: date,
    origin: str,
    dest: str,
) -> tuple[str, list[dict]]:
    tag = f"OW {origin}→{dest} {dep_date}"
    url = build_url(dep_date, None, origin, dest)
    texts: list[str] = []

    async def capture(resp):
        if INTERCEPT in resp.url:
            try:
                body = await resp.body()
                texts.append(body.decode("utf-8", errors="replace"))
            except Exception:
                pass

    ctx = await browser.new_context(
        locale=PLAYWRIGHT_LOCALE,
        timezone_id=PLAYWRIGHT_TIMEZONE,
    )
    page = await ctx.new_page()
    page.on("response", capture)

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await _wait_for_response(page, min_ms=2_000, networkidle_timeout=10_000)
    finally:
        page.remove_listener("response", capture)
        await ctx.close()

    cards: list[dict] = []
    for text in texts:
        for chunk in parse_chunks(text):
            if chunk["inner"]:
                cards.extend(extract_cards(chunk["inner"]))

    seen: set[str] = set()
    unique: list[dict] = []

    for card in cards:
        flight_no = (card.get("dep") or {}).get("flight_no")
        if flight_no and flight_no not in seen:
            seen.add(flight_no)
            unique.append(card)

    log.info("[%s] %s건", tag, len(unique))
    return url, unique


async def process_roundtrip_card(
    page: Page,
    card_el,
    outbound: dict,
    card_idx: int,
    tag: str,
) -> list[dict]:
    texts: list[str] = []
    ob_fn = (outbound.get("dep") or {}).get("flight_no", "?")
    ob_time = (outbound.get("dep") or {}).get("dep_time", "")
    ob_name = outbound.get("airline_name", "")

    def to_display_time(t: str) -> str:
        if not t or ":" not in t:
            return t
        hour, minute = map(int, t.split(":"))
        period = "오전" if hour < 12 else "오후"
        display_hour = hour if hour <= 12 else hour - 12
        if display_hour == 0:
            display_hour = 12
        return f"{period} {display_hour}:{minute:02d}"

    try:
        card_text = await card_el.inner_text()
        if ob_name not in card_text or to_display_time(ob_time) not in card_text:
            log.warning("[%s] 카드 %s 텍스트 불일치 ⚠️  %s", tag, card_idx, ob_fn)
    except Exception:
        pass

    try:
        await card_el.scroll_into_view_if_needed()
        async with page.expect_response(
            lambda r: INTERCEPT in r.url,
            timeout=10_000,
        ) as resp_info:
            await card_el.click()

        first = await resp_info.value
        try:
            body = await first.body()
            texts.append(body.decode("utf-8", errors="replace"))
        except Exception:
            pass
    except Exception as e:
        if "Timeout" in str(e):
            log.debug("[%s] 카드 %s 타임아웃 (%s)", tag, card_idx, ob_fn)

        await page.go_back()
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=8_000)
        except Exception:
            pass
        return []

    async def capture_extra(resp):
        if INTERCEPT in resp.url:
            try:
                body = await resp.body()
                texts.append(body.decode("utf-8", errors="replace"))
            except Exception:
                pass

    page.on("response", capture_extra)
    await _wait_for_response(page, min_ms=500, networkidle_timeout=5_000)
    page.remove_listener("response", capture_extra)

    ret_cards: list[dict] = []
    for text in texts:
        for chunk in parse_chunks(text):
            if chunk["inner"]:
                ret_cards.extend(extract_cards(chunk["inner"]))

    outbound_airline_code = outbound.get("airline_code")
    same_airline = [
        card for card in ret_cards
        if card.get("airline_code") == outbound_airline_code
    ]

    await page.go_back()
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=8_000)
    except Exception:
        pass

    return [
        {
            "outbound_flight_no":    (outbound.get("dep") or {}).get("flight_no"),
            "outbound_dep_time":     (outbound.get("dep") or {}).get("dep_time"),
            "outbound_arr_time":     (outbound.get("dep") or {}).get("arr_time"),
            "outbound_dep_date":     (outbound.get("dep") or {}).get("dep_date"),
            "outbound_duration_min": (outbound.get("dep") or {}).get("duration_min"),
            "airline_code":          outbound.get("airline_code"),
            "airline_name":          outbound.get("airline_name"),
            "inbound_flight_no":     (rc.get("dep") or {}).get("flight_no"),
            "inbound_dep_time":      (rc.get("dep") or {}).get("dep_time"),
            "inbound_arr_time":      (rc.get("dep") or {}).get("arr_time"),
            "inbound_dep_date":      (rc.get("dep") or {}).get("dep_date"),
            "inbound_duration_min":  (rc.get("dep") or {}).get("duration_min"),
            "price_krw":             rc.get("price_krw"),
            "outbound_ref_price":    outbound.get("price_krw"),
            "official_seller":       rc.get("official_seller"),
            # 출발편 기준 파생 필드 패스스루
            "stops":               outbound.get("stops", 0),
            "aircraft":            (outbound.get("dep") or {}).get("aircraft"),
            "airline_tag_present": outbound.get("airline_tag_present", False),
            "seller_type":         outbound.get("seller_type", "unknown"),
        }
        for rc in same_airline
    ]


async def collect_roundtrip(
    browser: Browser,
    dep_date: date,
    ret_date: date,
    origin: str,
    dest: str,
) -> tuple[str, list[dict]]:
    tag = f"RT {origin}↔{dest} {dep_date}"
    url = build_url(dep_date, ret_date, origin, dest)

    stage1_raw: list[str] = []

    async def capture_stage1(resp):
        if INTERCEPT in resp.url:
            try:
                body = await resp.body()
                stage1_raw.append(body.decode("utf-8", errors="replace"))
            except Exception:
                pass

    ctx = await browser.new_context(
        locale=PLAYWRIGHT_LOCALE,
        timezone_id=PLAYWRIGHT_TIMEZONE,
        viewport=PLAYWRIGHT_VIEWPORT,
    )
    page = await ctx.new_page()
    page.on("response", capture_stage1)

    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    await _wait_for_response(page, min_ms=2_000, networkidle_timeout=10_000)
    page.remove_listener("response", capture_stage1)

    stage1_cards: list[dict] = []
    for text in stage1_raw:
        for chunk in parse_chunks(text):
            if chunk["inner"]:
                stage1_cards.extend(extract_cards(chunk["inner"]))

    seen: set[str] = set()
    outbound_unique: list[dict] = []

    for card in stage1_cards:
        flight_no = (card.get("dep") or {}).get("flight_no")
        if flight_no and flight_no not in seen:
            seen.add(flight_no)
            outbound_unique.append(card)

    log.info("[%s] 출발편: %s건", tag, len(outbound_unique))

    all_combos: list[dict] = []
    for i, outbound in enumerate(outbound_unique):
        card_els = await get_card_els(page)
        if i >= len(card_els):
            break

        combos = await process_roundtrip_card(page, card_els[i], outbound, i, tag)
        all_combos.extend(combos)

    await ctx.close()

    seen_combo: set[tuple] = set()
    unique: list[dict] = []

    for combo in all_combos:
        key = (combo.get("outbound_flight_no"), combo.get("inbound_flight_no"))
        if key not in seen_combo:
            seen_combo.add(key)
            unique.append(combo)

    log.info("[%s] 왕복 조합: %s건", tag, len(unique))
    return url, unique


async def collect_date(
    browser: Browser,
    dep_date: date,
    sem: asyncio.Semaphore,
) -> None:
    async with sem:
        ret_date = dep_date + timedelta(days=STAY_NIGHTS)
        dpd = (dep_date - date.today()).days
        observed_at = date.today().isoformat()

        output_dir = settings.raw_google_flights_dir / date.today().isoformat()
        output_dir.mkdir(parents=True, exist_ok=True)

        oneway_results = await asyncio.gather(*[
            collect_oneway(browser, dep_date, origin, dest)
            for origin, dest in ONEWAY_ROUTES
        ])

        roundtrip_results = await asyncio.gather(*[
            collect_roundtrip(browser, dep_date, ret_date, origin, dest)
            for origin, dest in ROUNDTRIP_ROUTES
        ])

        for (origin, dest), (ow_url, ow_cards) in zip(ONEWAY_ROUTES, oneway_results):
            file_name = f"{dep_date.isoformat()}_oneway_{origin}_{dest}.json"
            (output_dir / file_name).write_text(
                json.dumps(
                    {
                        "observed_at": observed_at,
                        "route_type": "oneway",
                        "origin": origin,
                        "dest": dest,
                        "dep_date": dep_date.isoformat(),
                        "ret_date": None,
                        "stay_nights": None,
                        "dpd": dpd,
                        "search_url": ow_url,
                        "card_count": len(ow_cards),
                        "cards": ow_cards,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        for (origin, dest), (rt_url, rt_combos) in zip(ROUNDTRIP_ROUTES, roundtrip_results):
            file_name = f"{dep_date.isoformat()}_roundtrip_{origin}_{dest}.json"
            (output_dir / file_name).write_text(
                json.dumps(
                    {
                        "observed_at": observed_at,
                        "route_type": "roundtrip",
                        "origin": origin,
                        "dest": dest,
                        "dep_date": dep_date.isoformat(),
                        "ret_date": ret_date.isoformat(),
                        "stay_nights": STAY_NIGHTS,
                        "dpd": dpd,
                        "search_url": rt_url,
                        "combo_count": len(rt_combos),
                        "combos": rt_combos,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        oneway_total = sum(len(cards) for _, cards in oneway_results)
        roundtrip_total = sum(len(combos) for _, combos in roundtrip_results)

        log.info(
            "[DPD=%s %s] 완료  편도=%s건  왕복=%s건",
            dpd,
            dep_date,
            oneway_total,
            roundtrip_total,
        )


async def run_collection() -> None:
    today = date.today()
    dep_dates = [
        today + timedelta(days=dpd)
        for dpd in range(DPD_MIN, DPD_MAX + 1)
    ]

    output_dir = settings.raw_google_flights_dir / today.isoformat()

    log.info("=== 수집 시작: %s ===", today.isoformat())
    log.info("DPD 범위: %s~%s  (%s일)", DPD_MIN, DPD_MAX, len(dep_dates))
    log.info("편도 노선: %s", [f"{o}→{d}" for o, d in ONEWAY_ROUTES])
    log.info("왕복 노선: %s", [f"{o}↔{d}" for o, d in ROUNDTRIP_ROUTES])
    log.info("출력 경로: %s", output_dir)
    log.info("로그 파일: %s", _log_file)
    log.info("DPD 병렬 수: %s", DPD_PARALLEL)

    sem = asyncio.Semaphore(DPD_PARALLEL)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=PLAYWRIGHT_LAUNCH_ARGS,
        )
        try:
            await asyncio.gather(*[
                collect_date(browser, dep_date, sem)
                for dep_date in dep_dates
            ])
        finally:
            await browser.close()

    log.info("=== 수집 완료: %s ===", today.isoformat())
