# v0.4 Schema — 저장 구조 및 DB 스키마 기준

---

## 1. 문서 목적

본 문서는 v0.4 기준 프로젝트의 데이터 저장 계층, raw 보존 원칙, 파싱 결과 구조, DB 테이블 및 주요 컬럼 기준을 정리한다.

본 문서의 목적은 아래와 같다.

- 원본 인터셉트 데이터 저장 기준 확정
- 파싱 결과와 DB 적재 대상 구분
- raw / interim / processed 계층 정의
- MySQL 테이블 구조 및 핵심 컬럼 기준 정리
- 중복 처리, 실패 처리, 추적 정보 저장 원칙 정리

---

## 2. 설계 원칙

### 2-1. 원본 우선 보존

원본 인터셉트 데이터는 재파싱 가능성을 고려하여 반드시 보존한다.

### 2-2. 저장 계층 분리

저장 구조는 아래 세 계층으로 분리한다.

- `raw` : 브라우저 인터셉트 원본
- `interim` : 파싱 결과 또는 중간 정규화 결과
- `processed` : 최종 분석/앱 조회/모델 입력용 데이터

### 2-3. DB와 파일의 역할 분리

원본 응답 전체를 MySQL 본문 컬럼에 직접 저장하지 않는다.  
원본 응답은 파일(JSON)로 저장하고, DB에는 원본 추적에 필요한 메타데이터와 파싱 결과만 저장한다.

### 2-4. 파싱 실패도 기록

성공한 관측만 저장하지 않는다.  
파싱 실패, 빈 응답, 차단 추정 응답도 별도 기록하여 운영 상태를 추적 가능하도록 한다.

### 2-5. 편도/왕복 공통 구조 우선

가능한 한 공통 스키마를 우선 사용하고, 왕복 특이 정보만 별도 필드 또는 별도 테이블로 분리한다.

---

## 3. 저장 계층 정의

## 3-1. raw 계층

역할:
- 인터셉트된 원본 요청/응답 저장
- 재파싱, 디버깅, 장애 분석, 파싱 규칙 변경 대응

저장 형태:
- JSON 파일
- 요청 단위 또는 응답 단위 파일

예시 경로:
- `data/raw/google_flights/yyyy-mm-dd/`
- `data/raw/google_flights/yyyy-mm-dd/<capture_id>.json`

raw 계층에 저장하는 항목:
- observed_at
- source_page
- request metadata
- response body
- capture status
- parser input reference

## 3-2. interim 계층

역할:
- raw 응답에서 필요한 구조를 1차 파싱한 중간 결과 저장
- DB 적재 직전 검증/정제 단계

저장 형태:
- JSONL / CSV / parquet 중 택1
- 필요 시 생략 가능하나, 초기 개발 단계에서는 유지 권장

예시 경로:
- `data/interim/google_flights/yyyy-mm-dd/`

## 3-3. processed 계층

역할:
- 최종 분석, 앱 조회, 모델 입력에 사용되는 정규화 데이터
- MySQL 적재 결과와 동기화 가능해야 함

저장 형태:
- MySQL 우선
- 보조적으로 CSV / parquet export 가능

예시 경로:
- `data/processed/yyyy-mm-dd/`

---

## 4. 수집 단위 정의

## 4-1. 관측 단위

본 프로젝트의 기본 관측 단위는 아래 조합으로 정의한다.

- source
- trip_type
- origin
- destination
- departure_date
- return_date (왕복일 경우)
- observed_at
- itinerary key 또는 parser 기준 상품 식별자

## 4-2. 요청 단위

요청 단위는 아래 기준으로 구성한다.

- 편도 / 왕복
- 노선
- 출발일
- 귀국일 (왕복)
- 수집 시각

요청 1회에서 다수 상품(itinerary/offer)이 반환될 수 있다.

## 4-3. 상품 단위

상품 단위는 최종적으로 아래 정보를 기준으로 식별하는 방향을 우선 검토한다.

- carrier tag
- 출발/도착 공항
- 출발 시각
- 경유 여부
- segment 조합
- trip_type
- departure_date
- return_date (왕복)

최종 상품 키는 실제 인터셉트 응답 구조 확인 후 확정한다.

---

## 5. 파일 저장 기준

## 5-1. raw 파일명 기준

raw 파일명에는 최소 아래 정보가 포함되어야 한다.

- source
- observed_at
- trip_type
- route
- departure_date
- return_date (왕복)
- capture_id

예시:
- `gf_2026-04-08T08-00-00_oneway_ICN-NRT_2026-06-01_cap0001.json`
- `gf_2026-04-08T08-00-00_roundtrip_ICN-NRT_2026-06-01_2026-06-08_cap0002.json`

## 5-2. 원본 응답 저장 원칙

raw 파일에는 아래를 포함한다.

- request url 또는 route context
- request parameters 또는 탐색 조건
- intercepted response body
- capture status
- parser version (가능할 경우)
- created_at

## 5-3. DB와의 연결

각 raw 파일은 DB에서 `capture_id` 또는 `raw_file_id`로 추적 가능해야 한다.

---

## 6. DB 테이블 개요

v0.4 기준 DB는 아래 테이블 구성을 우선안으로 둔다.

| 테이블 | 역할 |
|---|---|
| `crawl_jobs` | 수집 작업 단위 기록 |
| `raw_capture_files` | raw 파일 메타데이터 기록 |
| `parse_runs` | 파싱 실행 기록 |
| `flight_observations` | 최종 관측 가격 데이터 저장 |
| `flight_segments` | 개별 구간(segment) 정보 저장 |
| `airports` | 공항 기준 정보 |
| `carriers` | 항공사 기준 정보 |
| `parse_failures` | 파싱 실패/빈 응답/차단 추정 기록 |

필요 시 이후 아래 테이블을 추가 검토한다.

- `routes`
- `alert_targets`
- `buy_wait_scores`
- `feature_snapshots`

---

## 7. 테이블 상세 기준

## 7-1. `crawl_jobs`

역할:
- 수집 작업 단위 관리
- 스케줄 실행 결과 추적

주요 컬럼:

| 컬럼 | 설명 |
|---|---|
| `job_id` | PK |
| `source` | `google_flights` |
| `trip_type` | `oneway` / `roundtrip` |
| `origin_iata` | 출발 공항 |
| `destination_iata` | 도착 공항 |
| `departure_date` | 출발일 |
| `return_date` | 귀국일, 편도는 NULL |
| `scheduled_at` | 예정 실행 시각 |
| `started_at` | 실제 시작 시각 |
| `finished_at` | 종료 시각 |
| `job_status` | success / failed / partial / blocked |
| `error_code` | 실패 코드 |
| `error_message` | 실패 메시지 |
| `created_at` | 생성 시각 |

## 7-2. `raw_capture_files`

역할:
- raw 파일 추적
- 원본 파일 경로와 수집 컨텍스트 저장

주요 컬럼:

| 컬럼 | 설명 |
|---|---|
| `raw_file_id` | PK |
| `job_id` | FK → crawl_jobs |
| `capture_id` | 원본 캡처 식별자 |
| `file_path` | JSON 파일 경로 |
| `content_type` | 응답 타입 |
| `byte_size` | 파일 크기 |
| `capture_status` | captured / empty / blocked / failed |
| `source_page` | 기준 페이지 |
| `request_signature` | 요청 식별용 요약값 |
| `observed_at` | 관측 시각 |
| `created_at` | 생성 시각 |

## 7-3. `parse_runs`

역할:
- 어떤 raw 파일을 어떤 parser 버전으로 처리했는지 기록

주요 컬럼:

| 컬럼 | 설명 |
|---|---|
| `parse_run_id` | PK |
| `raw_file_id` | FK → raw_capture_files |
| `parser_version` | parser 버전 |
| `started_at` | 파싱 시작 시각 |
| `finished_at` | 종료 시각 |
| `parse_status` | success / partial / failed |
| `record_count` | 생성된 observation 수 |
| `error_message` | 실패 메시지 |
| `created_at` | 생성 시각 |

## 7-4. `flight_observations`

역할:
- 최종 관측 가격 데이터 저장
- 앱 조회 및 모델 입력의 핵심 테이블

주요 컬럼:

| 컬럼 | 설명 |
|---|---|
| `observation_id` | PK |
| `parse_run_id` | FK → parse_runs |
| `job_id` | FK → crawl_jobs |
| `raw_file_id` | FK → raw_capture_files |
| `source` | `google_flights` |
| `trip_type` | `oneway` / `roundtrip` |
| `observed_at` | 관측 시각 |
| `departure_date` | 출발일 |
| `return_date` | 귀국일, 편도는 NULL |
| `dpd` | departure_date - observed_at |
| `origin_iata` | 출발 공항 |
| `destination_iata` | 도착 공항 |
| `carrier_tag` | 항공사 태그 또는 대표 항공사 |
| `marketing_carrier` | 가능할 경우 대표 항공사 코드 |
| `stop_count` | 경유 횟수 |
| `is_direct` | 직항 여부 |
| `departure_time` | 대표 출발 시각 |
| `arrival_time` | 대표 도착 시각 |
| `duration_min` | 총 소요 시간 |
| `price_krw` | 저장 기준 가격 |
| `currency` | 기본 `KRW` |
| `price_source_type` | official / tagged / fallback / unknown |
| `airline_tagged` | 항공사 태그 존재 여부 |
| `itinerary_key` | 상품 식별 키 |
| `raw_rank` | 원본 내 정렬 순서 |
| `created_at` | 생성 시각 |

## 7-5. `flight_segments`

역할:
- 개별 상품을 구성하는 구간 저장
- 왕복/경유 구조 복원 가능성 확보

주요 컬럼:

| 컬럼 | 설명 |
|---|---|
| `segment_id` | PK |
| `observation_id` | FK → flight_observations |
| `segment_order` | 구간 순서 |
| `leg_type` | outbound / inbound |
| `origin_iata` | 구간 출발 공항 |
| `destination_iata` | 구간 도착 공항 |
| `departure_time` | 구간 출발 시각 |
| `arrival_time` | 구간 도착 시각 |
| `carrier_tag` | 구간 항공사 |
| `flight_no` | 가능할 경우 항공편 번호 |
| `duration_min` | 구간 소요 시간 |
| `created_at` | 생성 시각 |

## 7-6. `airports`

역할:
- 공항 기준 정보 저장

주요 컬럼:

| 컬럼 | 설명 |
|---|---|
| `airport_id` | PK |
| `iata_code` | IATA 코드 |
| `city_code` | 도시 코드 |
| `airport_name` | 공항명 |
| `city_name` | 도시명 |
| `country_name` | 국가명 |
| `created_at` | 생성 시각 |

## 7-7. `carriers`

역할:
- 항공사 기준 정보 저장

주요 컬럼:

| 컬럼 | 설명 |
|---|---|
| `carrier_id` | PK |
| `carrier_code` | 항공사 코드 |
| `carrier_name` | 항공사명 |
| `display_name` | 화면 표기명 |
| `created_at` | 생성 시각 |

## 7-8. `parse_failures`

역할:
- 실패 유형 기록
- 운영 중 문제 유형 추적

주요 컬럼:

| 컬럼 | 설명 |
|---|---|
| `failure_id` | PK |
| `job_id` | FK → crawl_jobs |
| `raw_file_id` | FK → raw_capture_files, NULL 가능 |
| `parse_run_id` | FK → parse_runs, NULL 가능 |
| `failure_stage` | capture / parse / insert |
| `failure_type` | empty / blocked / malformed / duplicate / unknown |
| `message` | 상세 메시지 |
| `observed_at` | 관측 시각 |
| `created_at` | 생성 시각 |

---

## 8. 가격 저장 기준

## 8-1. 기준 가격

저장 기준 가격은 **현재 관측 시점에서 사용자에게 노출되는 대표 가격**으로 둔다.

## 8-2. 가격 우선순위

현재 우선안은 아래와 같다.

1. 항공사 태그가 붙은 상세 가격
2. 응답 내 항공사 공식 도메인과 연결된 가격
3. 그 외 가격
4. 없으면 NULL

이 우선순위는 parser 구현 시 실제 필드 구조 확인 후 최종 확정한다.

## 8-3. 가격 타입 표기

가격 저장 시 아래 구분값을 함께 저장한다.

- `official`
- `tagged`
- `fallback`
- `unknown`

이를 통해 앱과 모델에서 가격 신뢰도 차이를 반영할 수 있도록 한다.

---

## 9. 중복 처리 기준

## 9-1. 중복 판정 목적

동일 시점 동일 상품의 중복 삽입을 방지한다.

## 9-2. 현재 우선안

중복 판정 키는 아래 조합을 우선 검토한다.

- `source`
- `trip_type`
- `observed_at`
- `origin_iata`
- `destination_iata`
- `departure_date`
- `return_date`
- `itinerary_key`

실제 중복 키는 인터셉트 응답 구조와 parser 결과를 확인한 뒤 최종 확정한다.

## 9-3. 처리 원칙

- 동일 키 재수집 시 기본 원칙은 insert 방지
- 단, parser 개선에 따른 재적재는 별도 parse_run 기준으로 허용 가능
- 운영 단계에서는 raw는 중복 보존 가능, processed는 중복 통제 우선

---

## 10. 빈 응답 / 차단 응답 처리 기준

## 10-1. 저장 원칙

빈 응답과 차단 추정 응답도 버리지 않는다.

저장 방향:
- raw 파일 저장 가능 시 저장
- DB에는 `capture_status`, `failure_type` 등으로 기록

## 10-2. 처리 목적

- 운영 안정성 추적
- 차단 패턴 분석
- 스케줄 주기 조정 근거 확보
- parser 개선 대상 식별

---

## 11. 편도 / 왕복 처리 기준

## 11-1. 공통 필드

편도와 왕복 모두 아래 필드는 공통으로 유지한다.

- observed_at
- departure_date
- dpd
- origin_iata
- destination_iata
- carrier_tag
- stop_count
- is_direct
- duration_min
- price_krw
- itinerary_key

## 11-2. 왕복 전용 정보

왕복은 아래 정보를 추가로 가진다.

- return_date
- inbound segment
- 왕복 총 가격
- outbound / inbound leg 구분

## 11-3. 저장 방식

최종 관측 레코드는 `flight_observations`에 공통 저장하고,  
세부 구간은 `flight_segments`에 분리 저장한다.

---

## 12. 앱 조회를 위한 최소 출력 필드

대시보드형 앱에서 최소 필요 필드는 아래와 같다.

- route
- departure_date
- return_date (왕복)
- current_price
- price_change_indicator
- carrier_tag
- stop_count
- buy_wait_score (후속 단계)
- reason_summary (후속 단계)
- observed_at

현재 단계에서는 우선 `flight_observations`에서 직접 조회 가능한 구조를 우선한다.

---

## 13. 현재 미확정 항목

- 실제 인터셉트 응답 구조 기준 최종 필드명
- `itinerary_key` 생성 규칙
- carrier_tag 필드의 실제 파싱 방식
- 공식 가격 판정 규칙 확정
- 중복 키 최종안
- raw를 JSON 단일 파일로 둘지 JSONL로 둘지
- interim 계층 유지 여부
- 정규화된 DB 테이블의 인덱스 설계

---

## 14. 다음 단계

1. 실제 인터셉트 응답 예시 확보
2. raw 파일 샘플 기준 parser 입력 정의
3. `flight_observations` 최소 필드 확정
4. `flight_segments` 필요성 최종 확인
5. MySQL DDL 초안 작성
6. `data_pipeline.md`에 흐름 기준 반영
