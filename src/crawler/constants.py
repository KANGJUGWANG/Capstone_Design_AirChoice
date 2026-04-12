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