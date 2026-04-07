# v0.3 API 전략 및 응답 구조

---

## 1. 문서 목적

본 문서는 FlightAPI.io를 메인 수집 API로 채택하기까지의 탐색 과정, 실호출 검증 결과, 응답 구조 분석 내용을 정리한다.

---

## 2. v0.2.1 폐기 배경

v0.2.1에서 채택한 Travelpayouts는 다음 이유로 폐기되었다.

| 문제 | 내용 |
|---|---|
| 빈 응답 | `success=True`여도 `data={}`가 빈번하게 발생 |
| 목적지 불일치 | 요청 목적지와 응답 목적지가 다르게 반환됨 (예: NRT 요청 → TYO 반환) |
| 캐시 의존 | 실시간 가격이 아닌 Aviasales 사용자 검색 캐시 기반으로 수집 안정성 낮음 |
| 구조 부적합 | DPD 기반 시계열 누적 수집 구조에 적합하지 않음 |

---

## 3. FlightAPI.io 선택 이유

| 항목 | 내용 |
|---|---|
| 즉시 접근 가능 | 가입 후 즉시 사용 가능, 별도 승인 절차 없음 |
| 명확한 과금 구조 | 요청당 2크레딧 (Standard 플랜 기준) |
| ICN-NRT 데이터 반환 확인 | 실호출에서 111개 itinerary 반환 확인 |
| ICN-HND 데이터 반환 확인 | 실호출에서 27개 itinerary 반환 확인 |
| 구조화된 응답 | itinerary / leg / segment / places / carriers 구조 분리 제공 |
| KRW 반환 | 가격 통화 KRW 직접 반환 확인 |

---

## 4. 실호출 검증 결과

### 4-1. onewaytrip (ICN → NRT)

| 항목 | 결과 |
|---|---|
| 전체 itinerary | 111개 |
| 직항 leg | 42개 |
| 최저가 | 243,360 KRW |

### 4-2. onewaytrip (ICN → HND)

| 항목 | 결과 |
|---|---|
| 전체 itinerary | 27개 |
| 직항 leg | 4개 |
| 최저가 | 156,583 KRW |

> NRT 노선이 HND 대비 itinerary 수와 직항 수 모두 압도적으로 많다. 수집 메인 노선은 NRT, HND는 보조 노선으로 운영한다.

### 4-3. roundtrip (ICN → NRT, 7일 체류)

| 항목 | 결과 |
|---|---|
| 전체 itinerary | 237개 |
| 직항 | 200개 |
| 최저가 | 379,000 KRW |

roundtrip itinerary의 `leg_ids`는 2개로 구성된다 (outbound + inbound 분리).
```
"leg_ids": [
  "12409-2606010725--32361-0-14788-2606010950",   // 출발편 (ICN→NRT)
  "14788-2606081050--32361-0-12409-2606081330"    // 귀국편 (NRT→ICN)
]
```

leg 구조 자체는 onewaytrip과 동일하다.

---

## 5. Places 확정

| place_id | display_code | name | type |
|---|---|---|---|
| 12409 | ICN | Incheon International | Airport |
| 14788 | NRT | Tokyo Narita | Airport |
| 12234 | HND | Tokyo Haneda | Airport |
| 7968 | TYO | Tokyo | City |

NRT(14788)와 HND(12234)는 모두 parent_id=7968(Tokyo)에 속하며, 별도 요청으로만 구분된다. ICN→NRT 요청과 ICN→HND 요청은 각각 독립적으로 수집해야 한다.

---

## 6. 응답 구조 분석

### 6-1. 최상위 키 구조
```
query, context, itineraries, legs, segments,
places, carriers, alliances, brands, agents,
stats, quote_requests, quotes, repro_urls,
rejected_itineraries, pricing_variants_filters,
plugins, degradedResponseReasons
```

수집에 활용하는 핵심 키: `itineraries`, `legs`, `segments`, `places`, `carriers`

---

### 6-2. itinerary 구조
```json
{
  "id": "12409-2605051745--31880-1-14788-2605061800",
  "leg_ids": ["..."],
  "cheapest_price": {
    "amount": 1163008.14,
    "update_status": "current",
    "last_updated": "2026-03-28T04:11:16"
  },
  "pricing_options": [...],
  "score": 0.18306
}
```

| 필드 | 설명 |
|---|---|
| `id` | itinerary 고유 ID |
| `cheapest_price.amount` | agent 중 최저가 (KRW). 수집 기준 가격으로 사용 |
| `leg_ids` | onewaytrip은 1개, roundtrip은 2개 (outbound + inbound) |
| `pricing_options` | agent별 가격 옵션 목록. 수집 기준 가격은 `cheapest_price.amount`로 통일 |

---

### 6-3. leg 구조
```json
{
  "id": "12409-2605051745--31880-1-14788-2605061800",
  "origin_place_id": 12409,
  "destination_place_id": 14788,
  "departure": "2026-05-05T17:45:00",
  "arrival": "2026-05-06T18:00:00",
  "duration": 1455,
  "stop_count": 1,
  "marketing_carrier_ids": [-31880],
  "self_transfer": false
}
```

| 필드 | 설명 |
|---|---|
| `origin_place_id` / `destination_place_id` | places 테이블에서 IATA 코드 매핑 |
| `departure` | 출발 datetime (ISO 8601) |
| `duration` | 총 소요 시간 (분 단위) |
| `stop_count` | 경유 횟수. `0` = 직항 |
| `marketing_carrier_ids` | carriers 테이블에서 IATA 매핑 |

---

### 6-4. carriers 주의사항

`alt_id`와 `display_code`가 다른 케이스 존재한다.

| 항공사 | alt_id | display_code |
|---|---|---|
| ANA Wings | ZX | EH |
| Air Seoul | S~ | RS |
| Air Premia | 0_ | YP |

IATA 코드 기준 필드는 `display_code`를 사용한다.

---

### 6-5. 직항 필터링

`leg.stop_count == 0`인 leg만 직항으로 처리한다.

---

## 7. 수집 기준 필드 (raw 저장 대상)

> 아래 필드 목록은 현재 운영안이다. 실제 누적 수집 후 재검토하며 최종 스키마는 별도 확정한다.

| 필드명 | 출처 | 용도 |
|---|---|---|
| `observed_at` | 수집 시점 주입 | DPD 계산 기준 |
| `departure_date` | `leg.departure` 날짜 파싱 | DPD 계산 기준 |
| `dpd` | `departure_date - observed_at` | 핵심 feature |
| `price_krw` | `itinerary.cheapest_price.amount` | 타겟 변수 |
| `origin_iata` | `places[origin_place_id].display_code` | 노선 식별 |
| `destination_iata` | `places[destination_place_id].display_code` | 노선 식별 |
| `stop_count` | `leg.stop_count` | 직항 여부 feature |
| `carrier_iata` | `carriers[id].display_code` | 항공사 feature |
| `duration_min` | `leg.duration` | feature 후보 |
| `departure_weekday` | `leg.departure` 요일 파싱 | feature |
| `trip_type` | 수집 시 주입 (`oneway` / `roundtrip`) | 편도/왕복 구분 |
| `raw_json` | 응답 전체 | 원본 보존 |

---

## 8. 운영 원칙

- raw 응답은 반드시 저장. 정규화 스키마는 raw 기반으로 재생성 가능해야 함
- DPD = `departure_date - observed_at` (일 단위 정수)
- 수집 기준 가격은 `cheapest_price.amount`로 통일
- DPD 상한 120일 / 왕복 체류 7일 고정 / 매일 반복 수집

---

## 9. 미확정 항목

- 빈 응답 처리 원칙
- 중복 응답 처리 원칙
- 수집 기간 분할 방식 (월 단위 / 주 단위)
- normalized 스키마 최종 확정