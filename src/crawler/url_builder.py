from __future__ import annotations

import base64
from datetime import date

from src.crawler.constants import TFU_BY_AIRPORT


def _ab(code: str) -> bytes:
    return b"\x08\x01\x12\x03" + code.encode()


def _leg(dep_date_str: str, origin: str, dest: str) -> bytes:
    return (
        b"\x12\x0a"
        + dep_date_str.encode()
        + b"\x28\x00"
        + b"\x6a\x07"
        + _ab(origin)
        + b"\x72\x07"
        + _ab(dest)
    )


def get_tfu(origin: str, dest: str) -> str:
    if dest == "ICN":
        return TFU_BY_AIRPORT.get(origin, "EgYIABAAGAA")
    return TFU_BY_AIRPORT.get(dest, "EgYIABAAGAA")


def build_url(dep: date, ret: date | None, origin: str, dest: str) -> str:
    header = b"\x08\x1c\x10\x02"
    leg_tag = b"\x1a\x20"

    if ret is None:
        tail = (
            b"\x40\x01\x48\x01\x70\x01\x82\x01\x0b\x08"
            + b"\xff" * 9
            + b"\x01\x98\x01\x02"
        )
        raw = header + leg_tag + _leg(dep.strftime("%Y-%m-%d"), origin, dest) + tail
    else:
        tail = (
            b"\x40\x01\x48\x01\x70\x01\x82\x01\x0b\x08"
            + b"\xff" * 9
            + b"\x01\x98\x01\x01"
        )
        raw = (
            header
            + leg_tag
            + _leg(dep.strftime("%Y-%m-%d"), origin, dest)
            + leg_tag
            + _leg(ret.strftime("%Y-%m-%d"), dest, origin)
            + tail
        )

    tfs = (
        base64.b64encode(raw)
        .decode()
        .replace("+", "-")
        .replace("/", "_")
        .rstrip("=")
    )
    tfu = get_tfu(origin, dest)

    return (
        f"https://www.google.com/travel/flights/search?"
        f"tfs={tfs}&tfu={tfu}&hl=ko&curr=KRW"
    )