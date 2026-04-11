# v0.4 Schema — DB 스키마 기준 (확정)

---

## 문서 용도

현재 서버에 적용된 MySQL 스키마 기준을 정리한다.
v0.4 이전 schema.md의 테이블 구성(crawl_jobs, flight_observations 등)은
실제 구현 과정에서 아래 구조로 변경 확정되었다.

---

## 1. 설계 원칙

- 편도/왕복을 같은 테이블에 저장한다. `route_type`으로 구분.
- 신규 테이블 추가 없이 `flight_offer_observation`에 복귀편 컬럼(`ret_`)을 추가하는 방식으로 왕복을 확장한다.
- `price_krw`는 편도/왕복 모두 해당 row의 총가격을 의미한다. 조회 시 `route_type` 조건 필수.
- 편도 row의 `ret_` 컬럼은 전부 NULL.
- 왕복 row의 `ret_` 컬럼은 전부 채운다. 일부만 채워진 경우 `parse_status`로 실패 표기.
- `price_krw` (왕복) = Google Flights stage2 응답 `pi[0][1]` = 동일 항공사 출발+복귀 조합의 왕복 총가격 (공식 항공사 최저).
- `outbound_ref_price` = stage1 출발 카드 표시가. 복귀편 미확정 상태의 잠정가이므로 분석 대상 가격이 아님.

---

## 2. 테이블 구성

| 테이블 | 역할 |
|---|---|
| `search_observation` | 검색 1회 부모 관측 단위 (편도/왕복 공통) |
| `flight_offer_observation` | offer 행 (편도: 1카드 1행 / 왕복: 조합 1건 1행) |
| `capture_file_log` | raw 파일 경로 및 parser 추적 |

---

## 3. search_observation

검색 1회의 부모 관측 단위. 편도/왕복 공통.

| Field | Type | Null | 내용 |
|---|---|---|---|
| observation_id | BIGINT | NO | PK |
| observed_at | DATETIME | NO | 실제 수집 시각 |
| source | VARCHAR(50) | NO | 수집 소스. 현재 기준값: `google_flights` |
| route_type | VARCHAR(20) | NO | 노선 유형. `oneway` / `roundtrip` |
| origin_iata | CHAR(3) | NO | 출발 공항 IATA |
| destination_iata | CHAR(3) | NO | 도착 공항 IATA |
| departure_date | DATE | NO | 출발일 |
| return_date | DATE | YES | 왕복일 때만 사용. 편도는 NULL |
| stay_nights | INT | YES | 왕복 숙박일 수. 편도는 NULL |
| dpd | INT | NO | Departure Prior Days |
| search_url | TEXT | NO | 수집에 사용한 Google Flights tfs URL |
| crawl_status | VARCHAR(20) | NO | 수집 상태. `success` / `partial` / `failed` |
| created_at | DATETIME | YES | DB 기본 생성값 |

---

## 4. flight_offer_observation

편도: 출발편 카드 1개 = 1행.
왕복: (출발편 × 복귀편) 조합 1건 = 1행.

### 4-1. 기존 필드 (편도 기준 확정)

| Field | Type | Null | 내용 |
|---|---|---|---|
| offer_observation_id | BIGINT | NO | PK |
| observation_id | BIGINT | NO | search_observation FK |
| card_index | INT | NO | 결과 리스트 기준 카드 순번 (보조값, 식별자 아님) |
| airline_code | VARCHAR(10) | YES | 출발편 항공사 코드 |
| airline_name | VARCHAR(100) | YES | 출발편 항공사명 |
| flight_number | VARCHAR(20) | YES | 출발편 편명 |
| dep_time_local | TIME | YES | 출발편 출발 시각 |
| arr_time_local | TIME | YES | 출발편 도착 시각 |
| duration_min | INT | YES | 출발편 소요 시간(분) |
| seller_domain | VARCHAR(255) | YES | 공식 판매처 URL (fi[24]에서 추출) |
| selected_seller_name | VARCHAR(100) | YES | 공식 판매처 항공사명 |
| price_krw | INT | YES | 해당 row 상품 총가격. 편도: 편도 가격 / 왕복: 왕복 총가격 |
| price_source | VARCHAR(80) | NO | 가격 출처 코드 |
| price_status | VARCHAR(80) | NO | 가격 판정 상태 |
| parse_status | VARCHAR(20) | NO | 파싱 결과 상태 |
| price_selection_reason | VARCHAR(80) | YES | 가격 선택 근거 |
| created_at | DATETIME | YES | DB 기본 생성값 |

### 4-2. 왕복 확장 필드 (ALTER TABLE 적용 완료, 2026-04-11)

편도 row에서는 전부 NULL. 왕복 row에서는 전부 채운다.

| Field | Type | Null | 내용 |
|---|---|---|---|
| ret_airline_code | VARCHAR(10) | YES | 복귀편 항공사 코드 (출발편과 동일 항공사) |
| ret_airline_name | VARCHAR(100) | YES | 복귀편 항공사명 |
| ret_flight_number | VARCHAR(20) | YES | 복귀편 편명 |
| ret_dep_time_local | TIME | YES | 복귀편 출발 시각 |
| ret_arr_time_local | TIME | YES | 복귀편 도착 시각 |
| ret_duration_min | INT | YES | 복귀편 소요 시간(분) |

### 4-3. price_source / price_status 코드 기준

| route_type | price_source | price_status | price_selection_reason |
|---|---|---|---|
| oneway | `oneway_stage2_card_price` | `official_price` / `no_seller_tag` | `oneway_official_seller_card` |
| roundtrip | `roundtrip_stage2_card_price` | `official_price` / `no_seller_tag` | `same_airline_stage2_roundtrip_total` |

### 4-4. 왕복 상품 식별 키

DPD 시계열 추적 시 동일 상품 기준:

```
(route_type, origin_iata, destination_iata,
 departure_date, return_date,
 flight_number, dep_time_local,
 ret_flight_number, ret_dep_time_local)
```

---

## 5. capture_file_log

raw 파일 경로 및 parser 추적.

| Field | Type | Null | 내용 |
|---|---|---|---|
| capture_log_id | BIGINT | NO | PK |
| observation_id | BIGINT | NO | search_observation FK |
| offer_observation_id | BIGINT | NO | flight_offer_observation FK |
| captured_at | DATETIME | NO | request/response 저장 시각 |
| capture_type | VARCHAR(50) | NO | 현재 기준값: `getbookingresults` |
| request_url | TEXT | NO | 실제 인터셉트 request URL |
| request_json_path | TEXT | NO | request raw 파일 경로 |
| response_json_path | TEXT | NO | response raw 파일 경로 |
| summary_json_path | TEXT | NO | summary 파일 경로 |
| parser_version | VARCHAR(50) | NO | 적용 파서 버전 |
| created_at | DATETIME | YES | DB 기본 생성값 |

---

## 6. DDL

### 6-1. search_observation

```sql
CREATE TABLE search_observation (
  observation_id   BIGINT       NOT NULL AUTO_INCREMENT,
  observed_at      DATETIME     NOT NULL,
  source           VARCHAR(50)  NOT NULL,
  route_type       VARCHAR(20)  NOT NULL,
  origin_iata      CHAR(3)      NOT NULL,
  destination_iata CHAR(3)      NOT NULL,
  departure_date   DATE         NOT NULL,
  return_date      DATE         DEFAULT NULL,
  stay_nights      INT          DEFAULT NULL,
  dpd              INT          NOT NULL,
  search_url       TEXT         NOT NULL,
  crawl_status     VARCHAR(20)  NOT NULL,
  created_at       DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (observation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 6-2. flight_offer_observation (왕복 컬럼 포함 전체)

```sql
CREATE TABLE flight_offer_observation (
  offer_observation_id    BIGINT        NOT NULL AUTO_INCREMENT,
  observation_id          BIGINT        NOT NULL,
  card_index              INT           NOT NULL,
  airline_code            VARCHAR(10)   DEFAULT NULL,
  airline_name            VARCHAR(100)  DEFAULT NULL,
  flight_number           VARCHAR(20)   DEFAULT NULL,
  dep_time_local          TIME          DEFAULT NULL,
  arr_time_local          TIME          DEFAULT NULL,
  duration_min            INT           DEFAULT NULL,
  ret_airline_code        VARCHAR(10)   DEFAULT NULL,
  ret_airline_name        VARCHAR(100)  DEFAULT NULL,
  ret_flight_number       VARCHAR(20)   DEFAULT NULL,
  ret_dep_time_local      TIME          DEFAULT NULL,
  ret_arr_time_local      TIME          DEFAULT NULL,
  ret_duration_min        INT           DEFAULT NULL,
  seller_domain           VARCHAR(255)  DEFAULT NULL,
  selected_seller_name    VARCHAR(100)  DEFAULT NULL,
  price_krw               INT           DEFAULT NULL,
  price_source            VARCHAR(80)   NOT NULL,
  price_status            VARCHAR(80)   NOT NULL,
  parse_status            VARCHAR(20)   NOT NULL,
  price_selection_reason  VARCHAR(80)   DEFAULT NULL,
  created_at              DATETIME      DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (offer_observation_id),
  KEY idx_observation_id (observation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 6-3. 왕복 컬럼 추가 (서버 적용 완료)

```sql
ALTER TABLE flight_offer_observation
  ADD COLUMN ret_airline_code    VARCHAR(10)  NULL AFTER duration_min,
  ADD COLUMN ret_airline_name    VARCHAR(100) NULL AFTER ret_airline_code,
  ADD COLUMN ret_flight_number   VARCHAR(20)  NULL AFTER ret_airline_name,
  ADD COLUMN ret_dep_time_local  TIME         NULL AFTER ret_flight_number,
  ADD COLUMN ret_arr_time_local  TIME         NULL AFTER ret_dep_time_local,
  ADD COLUMN ret_duration_min    INT          NULL AFTER ret_arr_time_local;
```

### 6-4. capture_file_log

```sql
CREATE TABLE capture_file_log (
  capture_log_id        BIGINT       NOT NULL AUTO_INCREMENT,
  observation_id        BIGINT       NOT NULL,
  offer_observation_id  BIGINT       NOT NULL,
  captured_at           DATETIME     NOT NULL,
  capture_type          VARCHAR(50)  NOT NULL,
  request_url           TEXT         NOT NULL,
  request_json_path     TEXT         NOT NULL,
  response_json_path    TEXT         NOT NULL,
  summary_json_path     TEXT         NOT NULL,
  parser_version        VARCHAR(50)  NOT NULL,
  created_at            DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (capture_log_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

## 7. 수집기 → DB 컬럼 매핑

### 7-1. 편도 (`cards[]` 기준)

| 수집기 JSON 키 | DB 컬럼 |
|---|---|
| `observed_at` | `search_observation.observed_at` |
| `origin` | `search_observation.origin_iata` |
| `dest` | `search_observation.destination_iata` |
| `dep_date` | `search_observation.departure_date` |
| `dpd` | `search_observation.dpd` |
| `search_url` | `search_observation.search_url` |
| `card_index` | `flight_offer_observation.card_index` |
| `airline_code` | `flight_offer_observation.airline_code` |
| `dep.flight_no` | `flight_offer_observation.flight_number` |
| `dep.dep_time` | `flight_offer_observation.dep_time_local` |
| `dep.arr_time` | `flight_offer_observation.arr_time_local` |
| `dep.duration_min` | `flight_offer_observation.duration_min` |
| `official_seller.url` | `flight_offer_observation.seller_domain` |
| `official_seller.name` | `flight_offer_observation.selected_seller_name` |
| `price_krw` | `flight_offer_observation.price_krw` |
| ret_ 컬럼 전체 | NULL |

### 7-2. 왕복 (`combos[]` 기준)

| 수집기 JSON 키 | DB 컬럼 |
|---|---|
| `ret_date` | `search_observation.return_date` |
| `stay_nights` | `search_observation.stay_nights` |
| `outbound_flight_no` | `flight_offer_observation.flight_number` |
| `outbound_dep_time` | `flight_offer_observation.dep_time_local` |
| `outbound_arr_time` | `flight_offer_observation.arr_time_local` |
| `outbound_duration_min` | `flight_offer_observation.duration_min` |
| `airline_code` | `flight_offer_observation.airline_code` (+ `ret_airline_code` 동일값) |
| `inbound_flight_no` | `flight_offer_observation.ret_flight_number` |
| `inbound_dep_time` | `flight_offer_observation.ret_dep_time_local` |
| `inbound_arr_time` | `flight_offer_observation.ret_arr_time_local` |
| `inbound_duration_min` | `flight_offer_observation.ret_duration_min` |
| `price_krw` | `flight_offer_observation.price_krw` (stage2 왕복 총가격) |
| `outbound_ref_price` | 저장 안 함 (잠정가) |

---

## 8. 미확정 항목

- `capture_file_log` 실제 운영 여부 (현재 수집기는 JSON 파일 직접 저장 구조)
- 중복 판정 키 최종안 및 UNIQUE 제약 적용 여부
- 라벨 생성 기준 (BUY/WAIT 임계점) — 모델링 단계에서 확정

---

## 9. 변경 이력

| 날짜 | 내용 |
|---|---|
| 2026-04-11 | `flight_offer_observation`에 `ret_` 컬럼 6개 추가 (ALTER TABLE 서버 적용) |
| 2026-04-11 | schema.md 전면 갱신 — 실제 서버 확정 구조 반영 |
