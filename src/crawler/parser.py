from __future__ import annotations

import json


def parse_chunks(text: str) -> list[dict]:
    clean = text.lstrip(")]}'\n").lstrip()
    decoder = json.JSONDecoder()
    chunks: list[dict] = []
    pos = 0

    while pos < len(clean):
        while pos < len(clean) and clean[pos] in " \t\r\n":
            pos += 1
        if pos >= len(clean):
            break

        nl = clean.find("\n", pos)
        if nl == -1:
            nl = len(clean)

        if clean[pos:nl].strip().isdigit():
            pos = nl + 1
            continue

        try:
            obj, idx = decoder.raw_decode(clean, pos)
            pos = idx
            inner = None

            if (
                isinstance(obj, list)
                and obj
                and isinstance(obj[0], list)
                and len(obj[0]) > 2
                and obj[0][0] == "wrb.fr"
                and isinstance(obj[0][2], str)
            ):
                try:
                    inner = json.loads(obj[0][2])
                except Exception:
                    pass

            chunks.append({"inner": inner})
        except json.JSONDecodeError:
            break

    return chunks


def _is_hm(value) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], int)
        and isinstance(value[1], int)
        and 0 <= value[0] <= 23
        and 0 <= value[1] <= 59
    )


def _hm(value) -> str | None:
    return f"{value[0]:02d}:{value[1]:02d}" if _is_hm(value) else None


def _ymd(value) -> str | None:
    if isinstance(value, list) and len(value) == 3:
        return f"{value[0]}-{value[1]:02d}-{value[2]:02d}"
    return None


def _find_hm(arr: list, start: int, end: int, skip: int = -1) -> str | None:
    for i in range(start, min(end, len(arr))):
        if i != skip and _is_hm(arr[i]):
            return _hm(arr[i])
    return None


def parse_seg(seg: list) -> dict | None:
    if not seg or not isinstance(seg, list):
        return None

    try:
        fn_field = seg[22] if len(seg) > 22 else None
        flight_no = None
        if isinstance(fn_field, list) and len(fn_field) > 1:
            flight_no = f"{fn_field[0] or ''}{fn_field[1] or ''}".strip() or None

        dep_time = _find_hm(seg, 7, 12)
        dep_idx = next((i for i in range(7, min(12, len(seg))) if _is_hm(seg[i])), -1)
        arr_time = _find_hm(seg, dep_idx + 1, 14, skip=dep_idx)

        return {
            "dep_iata": seg[3] if len(seg) > 3 else None,
            "arr_iata": seg[6] if len(seg) > 6 else None,
            "dep_time": dep_time,
            "arr_time": arr_time,
            "duration_min": seg[11] if len(seg) > 11 else None,
            "dep_date": _ymd(seg[20] if len(seg) > 20 else None),
            "arr_date": _ymd(seg[21] if len(seg) > 21 else None),
            "flight_no": flight_no,
        }
    except Exception:
        return None


def parse_seg_from_fi(fi: list) -> dict | None:
    try:
        segs = fi[2] if len(fi) > 2 else []
        flight_no = None

        if segs and isinstance(segs[0], list) and len(segs[0]) > 22:
            fn_field = segs[0][22]
            if isinstance(fn_field, list) and len(fn_field) > 1:
                flight_no = f"{fn_field[0] or ''}{fn_field[1] or ''}".strip() or None

        dep_time = _find_hm(fi, 4, 10)
        dep_idx = next((i for i in range(4, min(10, len(fi))) if _is_hm(fi[i])), -1)
        arr_time = _find_hm(fi, dep_idx + 1, 12, skip=dep_idx)

        return {
            "dep_iata": fi[3] if len(fi) > 3 else None,
            "arr_iata": fi[6] if len(fi) > 6 else None,
            "dep_time": dep_time,
            "arr_time": arr_time,
            "duration_min": fi[9] if len(fi) > 9 else None,
            "dep_date": _ymd(fi[4] if len(fi) > 4 and not _is_hm(fi[4]) else None),
            "arr_date": _ymd(fi[7] if len(fi) > 7 and not _is_hm(fi[7]) else None),
            "flight_no": flight_no,
        }
    except Exception:
        return None


def parse_card(card: list, idx: int) -> dict | None:
    try:
        fi = card[0]
        pi = card[1] if len(card) > 1 else None

        airline_code = fi[0] if len(fi) > 0 else None
        airline_name = fi[1][0] if (len(fi) > 1 and isinstance(fi[1], list) and fi[1]) else None
        segs = fi[2] if len(fi) > 2 else []

        dep = parse_seg(segs[0]) if len(segs) > 0 else None
        if dep is None or dep.get("dep_time") is None:
            fallback = parse_seg_from_fi(fi)
            if fallback and fallback.get("dep_time") is not None:
                dep = fallback

        ret = parse_seg(segs[1]) if len(segs) > 1 else None

        price = None
        try:
            price = pi[0][1]
        except Exception:
            pass

        official_seller = None
        try:
            if len(fi) > 24 and isinstance(fi[24], list):
                for seller in fi[24]:
                    if isinstance(seller, list) and seller and seller[0] == airline_code:
                        official_seller = {
                            "code": seller[0],
                            "name": seller[1] if len(seller) > 1 else None,
                            "url": seller[2] if len(seller) > 2 else None,
                        }
                        break
        except Exception:
            pass

        return {
            "card_index": idx,
            "airline_code": airline_code,
            "airline_name": airline_name,
            "dep": dep,
            "ret": ret,
            "price_krw": price,
            "official_seller": official_seller,
        }
    except Exception:
        return None


def _is_card_list(obj: list) -> bool:
    if not obj or not isinstance(obj, list):
        return False

    card = obj[0]
    if not isinstance(card, list) or not card:
        return False

    fi = card[0]
    if not isinstance(fi, list) or not fi:
        return False

    airline_code = fi[0]
    return isinstance(airline_code, str) and 2 <= len(airline_code) <= 3 and airline_code.isupper()


def extract_cards(inner: list) -> list[dict]:
    cards: list[dict] = []

    if not isinstance(inner, list):
        return cards

    for section in inner:
        if not isinstance(section, list):
            continue

        for sub in section:
            if not isinstance(sub, list):
                continue

            if _is_card_list(sub):
                for j, raw_card in enumerate(sub):
                    parsed = parse_card(raw_card, j)
                    if parsed:
                        cards.append(parsed)
                break

    return cards