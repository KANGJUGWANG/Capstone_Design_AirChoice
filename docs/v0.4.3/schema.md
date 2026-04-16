# v0.4.3 Schema — DB 스키마 기준 (실서버 DDL 확정)

---

## 문서 용도

실서버에 적용된 MySQL DDL을 기준으로 작성한다.
v0.4.1 schema.md 대비 실운영 과정에서 추가/변경된 컬럼과 제약이 반영되어 있다.

---

## 1. 설계 원칙

- 편도/왕복을 같은 테이블에 저장한다. `route_type`으로 구분.
- `flight_offer_observation`에 복귀편 컬럼(`ret_`)을 추가하는 방식으로 왕복을 확장한다.
- `price_krw`는 편도/왕복 모두 해당 row의 총가격. 조회 시 `route_type` 조건 필수.
- 편도 row의 `ret_` 컬럼은 전부 NULL.
- 왕복 row의 `ret_` 컬럼은 전부 채운다.
- 중복 판정 기준: `search_observation.raw_file_path` UNIQUE 제약.

---

## 2. 테이블 구성

| 테이블 | 역할 |
|---|---|
| `search_observation` | 검색 1회 부모 관측 단위 (편도/왕복 공통) |
| `flight_offer_observation` | offer 행 (편도: 1카드 1행 / 왕복: 조합 1건 1행) |
| `capture_file_log` | JSON 파일 경로 및 parser 추적 |

---

## 3. search_observation

| Field | Type | Null | 제약 | 내용 |
|---|---|---|---|---|
| observation_id | BIGINT | NO | PK, AUTO_INCREMENT | |
| observed_at | DATETIME | NO | | 수집 시작 시각 (분/초 00 고정) |
| source | VARCHAR(50) | NO | | 현재 기준값: `google_flights` |
| route_type | VARCHAR(20) | NO | | `oneway` / `roundtrip` |
| origin_iata | CHAR(3) | NO | | 출발 공항 IATA |
| destination_iata | CHAR(3) | NO | | 도착 공항 IATA |
| departure_date | DATE | NO | | 출발일 |
| return_date | DATE | YES | | 왕복만 사용. 편도는 NULL |
| stay_nights | INT | YES | | 왕복 숙박일 수. 편도는 NULL |
| dpd | INT | NO | | Departure Prior Days |
| search_url | TEXT | NO | | 수집에 사용한 Google Flights URL |
| raw_file_path | VARCHAR(500) | YES | UNIQUE | 수집 JSON 파일 경로. 중복 판정 기준 |
| crawl_status | VARCHAR(20) | NO | | `success` / `partial` / `failed` |
| created_at | DATETIME | YES | DEFAULT CURRENT_TIMESTAMP | |

**DDL:**
```sql
CREATE TABLE `search_observation` (
  `observation_id`   BIGINT        NOT NULL AUTO_INCREMENT,
  `observed_at`      DATETIME      NOT NULL,
  `source`           VARCHAR(50)   NOT NULL,
  `route_type`       VARCHAR(20)   NOT NULL,
  `origin_iata`      CHAR(3)       NOT NULL,
  `destination_iata` CHAR(3)       NOT NULL,
  `departure_date`   DATE          NOT NULL,
  `return_date`      DATE          DEFAULT NULL,
  `stay_nights`      INT           DEFAULT NULL,
  `dpd`              INT           NOT NULL,
  `search_url`       TEXT          NOT NULL,
  `raw_file_path`    VARCHAR(500)  DEFAULT NULL,
  `crawl_status`     VARCHAR(20)   NOT NULL,
  `created_at`       DATETIME      DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`observation_id`),
  UNIQUE KEY `uq_raw_file` (`raw_file_path`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

## 4. flight_offer_observation

### 4-1. 전체 컬럼

| Field | Type | Null | 내용 |
|---|---|---|---|
| offer_observation_id | BIGINT | NO | PK |
| observation_id | BIGINT | NO | search_observation FK |
| card_index | INT | NO | 결과 리스트 카드 순번 |
| airline_code | VARCHAR(10) | YES | 출발편 항공사 코드 |
| airline_name | VARCHAR(100) | YES | 출발편 항공사명 |
| flight_number | VARCHAR(20) | YES | 출발편 편명 |
| dep_time_local | TIME | YES | 출발편 출발 시각 |
| arr_time_local | TIME | YES | 출발편 도착 시각 |
| duration_min | INT | YES | 출발편 소요 시간(분) |
| ret_airline_code | VARCHAR(10) | YES | 복귀편 항공사 코드 (편도: NULL) |
| ret_airline_name | VARCHAR(100) | YES | 복귀편 항공사명 (편도: NULL) |
| ret_flight_number | VARCHAR(20) | YES | 복귀편 편명 (편도: NULL) |
| ret_dep_time_local | TIME | YES | 복귀편 출발 시각 (편도: NULL) |
| ret_arr_time_local | TIME | YES | 복귀편 도착 시각 (편도: NULL) |
| ret_duration_min | INT | YES | 복귀편 소요 시간(분) (편도: NULL) |
| stops | INT | YES | 경유 횟수 (직항=0) |
| aircraft | VARCHAR(100) | YES | 기종 문자열 (seg[17]) |
| seller_domain | VARCHAR(255) | YES | 공식 판매처 URL |
| selected_seller_name | VARCHAR(100) | YES | 공식 판매처 항공사명 |
| seller_type | VARCHAR(20) | YES | `airline_official` / `unknown` |
| airline_tag_present | TINYINT(1) | YES | 항공사 태그 존재 여부 (DEFAULT 0) |
| price_krw | INT | YES | 해당 row 총가격 |
| price_source | VARCHAR(80) | NO | 가격 출처 코드 |
| price_status | VARCHAR(80) | NO | 가격 판정 상태 |
| parse_status | VARCHAR(20) | NO | 파싱 결과 상태 |
| price_selection_reason | VARCHAR(80) | YES | 가격 선택 근거 |
| created_at | DATETIME | YES | DEFAULT CURRENT_TIMESTAMP |

### 4-2. price_source / price_status 코드 기준

| route_type | price_source | price_status | price_selection_reason |
|---|---|---|---|
| oneway | `oneway_stage2_card_price` | `official_price` / `no_seller_tag` | `oneway_official_seller_card` |
| roundtrip | `roundtrip_stage2_card_price` | `official_price` / `no_seller_tag` | `same_airline_stage2_roundtrip_total` |

### 4-3. 왕복 상품 식별 키

DPD 시계열 추적 시 동일 상품 기준:

```
(route_type, origin_iata, destination_iata,
 departure_date, return_date,
 flight_number, dep_time_local,
 ret_flight_number, ret_dep_time_local)
```

**DDL:**
```sql
CREATE TABLE `flight_offer_observation` (
  `offer_observation_id`  BIGINT        NOT NULL AUTO_INCREMENT,
  `observation_id`        BIGINT        NOT NULL,
  `card_index`            INT           NOT NULL,
  `airline_code`          VARCHAR(10)   DEFAULT NULL,
  `airline_name`          VARCHAR(100)  DEFAULT NULL,
  `flight_number`         VARCHAR(20)   DEFAULT NULL,
  `dep_time_local`        TIME          DEFAULT NULL,
  `arr_time_local`        TIME          DEFAULT NULL,
  `duration_min`          INT           DEFAULT NULL,
  `ret_airline_code`      VARCHAR(10)   DEFAULT NULL,
  `ret_airline_name`      VARCHAR(100)  DEFAULT NULL,
  `ret_flight_number`     VARCHAR(20)   DEFAULT NULL,
  `ret_dep_time_local`    TIME          DEFAULT NULL,
  `ret_arr_time_local`    TIME          DEFAULT NULL,
  `ret_duration_min`      INT           DEFAULT NULL,
  `stops`                 INT           DEFAULT NULL,
  `aircraft`              VARCHAR(100)  DEFAULT NULL,
  `seller_domain`         VARCHAR(255)  DEFAULT NULL,
  `selected_seller_name`  VARCHAR(100)  DEFAULT NULL,
  `seller_type`           VARCHAR(20)   DEFAULT NULL,
  `airline_tag_present`   TINYINT(1)    DEFAULT '0',
  `price_krw`             INT           DEFAULT NULL,
  `price_source`          VARCHAR(80)   NOT NULL,
  `price_status`          VARCHAR(80)   NOT NULL,
  `parse_status`          VARCHAR(20)   NOT NULL,
  `price_selection_reason` VARCHAR(80)  DEFAULT NULL,
  `created_at`            DATETIME      DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`offer_observation_id`),
  KEY `idx_observation_id` (`observation_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

## 5. capture_file_log

실제 운영 컬럼 기준. v0.4.1 schema.md의 `request_json_path`, `summary_json_path`는 미사용으로 제거됨.

| Field | Type | Null | 내용 |
|---|---|---|---|
| capture_log_id | BIGINT | NO | PK |
| observation_id | BIGINT | NO | search_observation FK |
| offer_observation_id | BIGINT | NO | flight_offer_observation FK |
| captured_at | DATETIME | NO | INSERT 실행 시각 |
| capture_type | VARCHAR(50) | NO | 현재 기준값: `getbookingresults` |
| request_url | TEXT | NO | 수집에 사용한 search_url |
| response_json_path | TEXT | NO | 수집 JSON 파일 경로 |
| parser_version | VARCHAR(50) | NO | 적용 파서 버전 |
| created_at | DATETIME | YES | DEFAULT CURRENT_TIMESTAMP |

**DDL:**
```sql
CREATE TABLE `capture_file_log` (
  `capture_log_id`        BIGINT       NOT NULL AUTO_INCREMENT,
  `observation_id`        BIGINT       NOT NULL,
  `offer_observation_id`  BIGINT       NOT NULL,
  `captured_at`           DATETIME     NOT NULL,
  `capture_type`          VARCHAR(50)  NOT NULL,
  `request_url`           TEXT         NOT NULL,
  `response_json_path`    TEXT         NOT NULL,
  `parser_version`        VARCHAR(50)  NOT NULL,
  `created_at`            DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`capture_log_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

## 6. 수집기 → DB 컬럼 매핑

### 6-1. 편도 (cards[] 기준)

| 수집기 JSON 키 | DB 컬럼 |
|---|---|
| observed_at | search_observation.observed_at |
| origin | search_observation.origin_iata |
| dest | search_observation.destination_iata |
| dep_date | search_observation.departure_date |
| dpd | search_observation.dpd |
| search_url | search_observation.search_url |
| raw_file_path (파일 경로) | search_observation.raw_file_path |
| card_index | flight_offer_observation.card_index |
| airline_code | flight_offer_observation.airline_code |
| dep.flight_no | flight_offer_observation.flight_number |
| dep.dep_time | flight_offer_observation.dep_time_local |
| dep.arr_time | flight_offer_observation.arr_time_local |
| dep.duration_min | flight_offer_observation.duration_min |
| dep.aircraft | flight_offer_observation.aircraft |
| stops | flight_offer_observation.stops |
| official_seller.url | flight_offer_observation.seller_domain |
| official_seller.name | flight_offer_observation.selected_seller_name |
| seller_type | flight_offer_observation.seller_type |
| airline_tag_present | flight_offer_observation.airline_tag_present |
| price_krw | flight_offer_observation.price_krw |
| ret_ 컬럼 전체 | NULL |

### 6-2. 왕복 (combos[] 기준)

| 수집기 JSON 키 | DB 컬럼 |
|---|---|
| ret_date | search_observation.return_date |
| stay_nights | search_observation.stay_nights |
| outbound_flight_no | flight_offer_observation.flight_number |
| outbound_dep_time | flight_offer_observation.dep_time_local |
| outbound_arr_time | flight_offer_observation.arr_time_local |
| outbound_duration_min | flight_offer_observation.duration_min |
| airline_code | flight_offer_observation.airline_code (+ ret_airline_code 동일값) |
| inbound_flight_no | flight_offer_observation.ret_flight_number |
| inbound_dep_time | flight_offer_observation.ret_dep_time_local |
| inbound_arr_time | flight_offer_observation.ret_arr_time_local |
| inbound_duration_min | flight_offer_observation.ret_duration_min |
| price_krw | flight_offer_observation.price_krw (stage2 왕복 총가격) |
| outbound_ref_price | 저장 안 함 (잠정가) |

---

## 7. 변경 이력

| 날짜 | 내용 |
|---|---|
| 2026-04-11 | flight_offer_observation에 ret_ 컬럼 6개 추가 (ALTER TABLE 서버 적용) |
| 2026-04-11 | schema.md 전면 갱신 (v0.4.1) |
| 2026-04-13 | flight_offer_observation에 stops, aircraft, seller_type, airline_tag_present 추가 |
| 2026-04-13 | search_observation에 raw_file_path 추가 및 UNIQUE 제약 적용 |
| 2026-04-16 | capture_file_log 실제 운영 컬럼 기준 정리 (request_json_path, summary_json_path 제거) |
| 2026-04-16 | v0.4.3 기준으로 실서버 DDL 전면 재확인 및 갱신 |
