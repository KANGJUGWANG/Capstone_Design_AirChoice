# v0.2 엔드포인트 관측 내용과 역할 정리

## 1. 문서 목적
ICN ↔ TYO MVP 범위를 기준으로 Travelpayouts 가격 엔드포인트를 비교 테스트한 결과를 정리하고, 각 엔드포인트의 역할을 잠정 정의한다.

---

## 2. 비교 대상 엔드포인트
- `v1/prices/cheap`
- `aviasales/v3/prices_for_dates`
- `v2/prices/month-matrix`
- `aviasales/v3/get_latest_prices`

공식 참고 문서:
- Travelpayouts Aviasales Data API: https://support.travelpayouts.com/hc/en-us/articles/203956163-Aviasales-Data-API

---

## 3. 관측된 핵심 사실

### 3.1 공통 관측
- 모든 비교 대상 엔드포인트는 테스트 시점에 200 응답을 반환함.
- Travelpayouts Data API는 캐시 기반 관측 데이터이며, 실시간 결제 장부 데이터가 아님.
- `query_destination`과 `result_destination`이 다를 수 있음.
  - 예: `NRT`로 요청했으나 결과는 `TYO`로 집계되어 반환됨.
- 특정 일자(`YYYY-MM-DD`)로 좁히면 `data = {}`가 나올 수 있고, 월 단위(`YYYY-MM`)로 넓히면 응답이 잡히는 패턴을 확인함.

### 3.2 `v1/prices/cheap`
- 특징:
  - 대표 최저가 스냅샷에 가까움.
  - 응답 구조가 단순함.
- 관측 결과:
  - 월 단위 요청에서는 응답 가능.
  - 행 수는 적음(대표값 수준).
  - `price`, `airline`, `departure_at`, `return_at`, `expires_at`, `duration` 등을 확인함.
- 해석:
  - 기준점 확인용 / sanity check 용도에는 적합.
  - 메인 누적용 DB 엔드포인트로는 정보량이 부족함.

### 3.3 `aviasales/v3/prices_for_dates`
- 특징:
  - 공식 문서상 `cheap` 대체용으로 권장됨.
  - 특정 날짜 범위에 대한 오퍼형 데이터를 반환.
- 관측 결과:
  - 비교 테스트에서 가장 정보가 풍부했음.
  - 공항/도시가 동시에 관측됨.
    - 예: `origin = SEL`, `origin_airport = ICN`
    - 예: `destination = TYO`, `destination_airport = NRT`
  - `price`, `airline`, `flight_number`, `departure_at`, `return_at`, `transfers`, `duration`, `gate`, `link` 등 확인.
  - 테스트 결과 기준 `data length`가 `cheap`보다 많았음.
- 해석:
  - 메인 누적용 엔드포인트 1순위.
  - 공통 스키마 설계 시 가장 기준이 되기 좋음.

### 3.4 `v2/prices/month-matrix`
- 특징:
  - 월 단위 가격 달력형 데이터.
  - 날짜 분포를 넓게 볼 수 있음.
- 관측 결과:
  - `depart_date`, `return_date`, `value`, `found_at`, `number_of_changes`, `actual` 등의 필드 확인.
  - 테스트 결과 기준 `data length`는 `prices_for_dates`보다 적고 `cheap`보다 많았음.
- 해석:
  - 달력형 가격 분포 확인용으로 유용.
  - 다만 메인 원천 테이블로 쓰기에는 오퍼 상세가 부족할 수 있음.

### 3.5 `aviasales/v3/get_latest_prices`
- 특징:
  - 특정 기간에 발견된 가격들을 기간형으로 반환.
  - `found_at` 기반 추적이 가능.
- 관측 결과:
  - 비교 테스트에서 행 수가 가장 많았음.
  - `depart_date`, `return_date`, `value`, `found_at`, `number_of_changes`, `actual`, `trip_class` 계열 필드 확인.
- 해석:
  - 분포 보강 / 보조 가격 테이블 후보.
  - 메인 엔드포인트보다 보조 엔드포인트로 더 적합.

---

## 4. 엔드포인트별 역할 잠정안

### 4.1 메인 엔드포인트
- `aviasales/v3/prices_for_dates`

선정 이유:
- `cheap`보다 데이터 밀도가 높음.
- 공항/도시 분리 정보가 함께 옴.
- 항공사/편명/경유/링크까지 포함되어 학습용 원천 관측 테이블 구축에 유리함.

### 4.2 보조 엔드포인트
- `aviasales/v3/get_latest_prices`

선정 이유:
- 기간 내 발견된 가격을 넓게 제공함.
- `found_at`이 있어 가격 발견 시점 추적에 유리함.
- 메인 테이블의 가격 분포 보강용으로 적합함.

### 4.3 기준점 / 비교용
- `v1/prices/cheap`

선정 이유:
- 대표 최저가 관측값 확인용으로 간단하고 안정적임.
- 메인 원천 테이블로는 정보량 부족.

### 4.4 보류
- `v2/prices/month-matrix`

보류 이유:
- 달력형으로 의미는 있으나, 현재 MVP 단계에서는 `get_latest_prices`와 역할이 일부 겹침.
- 우선 메인 + 보조 2개 구조로 단순화하는 방향을 고려 중.

---

## 5. 현재 단계의 정리
- 확정된 것은 아직 아님.
- 다만 현재 비교 결과만 보면 아래 구조가 가장 유력함.

### 유력 구조
- 메인: `prices_for_dates`
- 보조: `get_latest_prices`
- 기준점: `cheap`
- 보류: `month-matrix`

---

## 6. 후속 검토 사항
- `prices_for_dates`와 `get_latest_prices`를 병행 수집할지 여부
- limit/page 구조상 성수기 월(예: 7~8월)에서 잘림 가능성 검토
- 월 단위 분할 수집 필요성 검토
- 공통 스키마를 `prices_for_dates` 기준으로 먼저 고정할지 여부

---

## 7. 참고 URL
- Travelpayouts Aviasales Data API:
  - https://support.travelpayouts.com/hc/en-us/articles/203956163-Aviasales-Data-API
