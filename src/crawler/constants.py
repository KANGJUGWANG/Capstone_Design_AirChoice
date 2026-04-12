from __future__ import annotations

ONEWAY_ROUTES = [
    ("ICN", "NRT"),
    ("ICN", "HND"),
    ("NRT", "ICN"),
    ("HND", "ICN"),
]

ROUNDTRIP_ROUTES = [
    ("ICN", "NRT"),
    ("ICN", "HND"),
    ("NRT", "ICN"),
    ("HND", "ICN"),
]

STAY_NIGHTS = 7
DPD_MIN = 1
DPD_MAX = 120

# DPD 동시 수집 수
# 편도 4 + 왕복 4 = 노선 8개가 각 DPD에서 병렬 실행되므로
# DPD_PARALLEL=3 기준 최대 동시 컨텍스트: 3 × 8 = 24개
# 서버 메모리 24GB 기준 안전 범위
DPD_PARALLEL = 3

INTERCEPT = "_/FlightsFrontendUi/data"

TFU_BY_AIRPORT = {
    "NRT": "EgYIABAAGAA",
    "HND": "EgIIACIA",
    "ICN": "EgYIABAAGAA",
}

CARD_SELECTORS = [
    "ul.Rk10dc > li",
    "li.pIav2d",
    "li[jsname='TTtNVe']",
]

PLAYWRIGHT_LOCALE = "ko-KR"
PLAYWRIGHT_TIMEZONE = "Asia/Seoul"
PLAYWRIGHT_VIEWPORT = {"width": 1280, "height": 900}
PLAYWRIGHT_LAUNCH_ARGS = [
    "--lang=ko-KR",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]
