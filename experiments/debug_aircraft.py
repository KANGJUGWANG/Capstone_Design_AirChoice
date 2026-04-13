"""
항공기 기종(aircraft) 필드 위치 탐색 스크립트

실행:
    python experiments/debug_aircraft.py

출력:
    - fi 배열 원본 (첫 3카드)
    - aircraft 관련 키워드 탐색 결과
    - outputs/debug_aircraft.json (fi 전체 원본)
"""

import asyncio
import base64
import json
from datetime import date, timedelta
from pathlib import Path

from playwright.async_api import async_playwright

# ------------------------------------------------------------------
# 설정
# ------------------------------------------------------------------
DEPARTURE = date.today() + timedelta(days=30)
ORIGIN    = "ICN"
DEST      = "NRT"
INTERCEPT = "_/FlightsFrontendUi/data"
TFU       = "EgYIABAAGAA"
OUTPUT    = Path("outputs/debug_aircraft.json")

# aircraft 관련 탐색 키워드
AIRCRAFT_KEYWORDS = ["737", "320", "321", "350", "787", "777", "A32", "B73", "aircraft"]

# ------------------------------------------------------------------
# URL 빌더
# ------------------------------------------------------------------
def _ab(c): return b'\x08\x01\x12\x03' + c.encode()
def _leg(ds, o, d): return b'\x12\x0a'+ds.encode()+b'\x28\x00'+b'\x6a\x07'+_ab(o)+b'\x72\x07'+_ab(d)

def build_url(dep, origin, dest):
    h = b'\x08\x1c\x10\x02'; lt = b'\x1a\x20'
    t = b'\x40\x01\x48\x01\x70\x01\x82\x01\x0b\x08'+b'\xff'*9+b'\x01\x98\x01\x02'
    raw = h+lt+_leg(dep.strftime("%Y-%m-%d"), origin, dest)+t
    tfs = base64.b64encode(raw).decode().replace('+','-').replace('/','_').rstrip('=')
    return f"https://www.google.com/travel/flights/search?tfs={tfs}&tfu={TFU}&hl=ko&curr=KRW"

# ------------------------------------------------------------------
# 파서
# ------------------------------------------------------------------
def parse_chunks(text):
    clean = text.lstrip(")]}'\n").lstrip()
    dec = json.JSONDecoder(); chunks = []; pos = 0
    while pos < len(clean):
        while pos < len(clean) and clean[pos] in ' \t\r\n': pos += 1
        if pos >= len(clean): break
        nl = clean.find('\n', pos)
        if nl == -1: nl = len(clean)
        if clean[pos:nl].strip().isdigit(): pos = nl+1; continue
        try:
            obj, idx = dec.raw_decode(clean, pos); pos = idx
            inner = None
            if (isinstance(obj,list) and obj and isinstance(obj[0],list)
                    and len(obj[0])>2 and obj[0][0]=="wrb.fr"
                    and isinstance(obj[0][2],str)):
                try: inner = json.loads(obj[0][2])
                except: pass
            chunks.append({"inner": inner})
        except json.JSONDecodeError: break
    return chunks

def _is_card_list(obj):
    if not obj or not isinstance(obj, list): return False
    card = obj[0]
    if not isinstance(card, list) or not card: return False
    fi = card[0]
    if not isinstance(fi, list) or not fi: return False
    ac = fi[0]
    return isinstance(ac, str) and 2 <= len(ac) <= 3 and ac.isupper()

def find_in_value(obj, keywords, path="", results=None, max_depth=15):
    """값 안에서 키워드가 포함된 문자열 경로를 모두 찾는다."""
    if results is None: results = []
    if max_depth == 0: return results
    if isinstance(obj, str):
        for kw in keywords:
            if kw.lower() in obj.lower():
                results.append((path, obj))
                break
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            find_in_value(v, keywords, f"{path}[{i}]", results, max_depth-1)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            find_in_value(v, keywords, f"{path}.{k}", results, max_depth-1)
    return results


# ------------------------------------------------------------------
# 메인
# ------------------------------------------------------------------
async def main():
    url = build_url(DEPARTURE, ORIGIN, DEST)
    print(f"URL: {url[:80]}...")
    print(f"출발일: {DEPARTURE}")

    texts = []
    async def cap(resp):
        if INTERCEPT in resp.url:
            try: b = await resp.body(); texts.append(b.decode("utf-8","replace"))
            except: pass

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--lang=ko-KR"])
        ctx = await browser.new_context(locale="ko-KR", timezone_id="Asia/Seoul")
        page = await ctx.new_page()
        page.on("response", cap)
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(3_000)
        try:
            await page.wait_for_load_state("networkidle", timeout=8_000)
        except: pass
        await browser.close()

    print(f"\n인터셉트 응답: {len(texts)}개")

    raw_cards = []
    for text in texts:
        for chunk in parse_chunks(text):
            if not chunk["inner"]: continue
            inner = chunk["inner"]
            for section in inner:
                if not isinstance(section, list): continue
                for sub in section:
                    if not isinstance(sub, list): continue
                    if _is_card_list(sub):
                        raw_cards.extend(sub)
                        break

    print(f"원시 카드 수: {len(raw_cards)}")

    output = {"cards": []}

    for i, card in enumerate(raw_cards[:3]):  # 첫 3카드만
        fi = card[0] if card else []
        pi = card[1] if len(card) > 1 else None
        ac = fi[0] if fi else "?"

        print(f"\n{'='*60}")
        print(f"카드 {i}  항공사: {ac}")
        print(f"fi 배열 길이: {len(fi)}")

        # aircraft 키워드 탐색
        found = find_in_value(fi, AIRCRAFT_KEYWORDS, "fi")
        if found:
            print(f"\n✅ aircraft 관련 값 발견:")
            for path, val in found:
                print(f"  경로: {path}  값: {val}")
        else:
            print(f"\n❌ aircraft 키워드 미발견")

        # 세그먼트 배열 구조 확인 (문자열 값만)
        segs = fi[2] if len(fi) > 2 else []
        print(f"\n세그먼트 수: {len(segs)}")
        if segs and isinstance(segs[0], list):
            seg0 = segs[0]
            print(f"seg[0] 배열 길이: {len(seg0)}")
            print("seg[0] 문자열 인덱스:")
            for idx, val in enumerate(seg0):
                if isinstance(val, str) and val:
                    print(f"  [{idx}]: {val!r}")
                elif isinstance(val, list) and any(isinstance(v, str) for v in val):
                    print(f"  [{idx}]: {val}")

        output["cards"].append({
            "card_idx": i,
            "airline_code": ac,
            "fi_full": fi,
            "pi": pi,
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n\nfi 원본 저장: {OUTPUT}")
    print("전체 fi 배열은 outputs/debug_aircraft.json 에서 확인 가능")


if __name__ == "__main__":
    asyncio.run(main())
