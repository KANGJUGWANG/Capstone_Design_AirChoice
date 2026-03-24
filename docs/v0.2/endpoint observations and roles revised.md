# v0.2 엔드포인트 관측 내용과 역할

---

## 1. 문서 목적
본 문서는 Travelpayouts 가격 관련 엔드포인트를 실제 호출하여 확인한 관측 결과를 정리하고,
현재 프로젝트에서 각 엔드포인트를 어떤 역할로 사용할지 고정하기 위해 작성한다.

---

## 2. 비교 대상 엔드포인트

- `v1/prices/cheap`
- `aviasales/v3/prices_for_dates`
- `v2/prices/month-matrix`
- `aviasales/v3/get_latest_prices`

---

## 3. 공통 전제

- Travelpayouts Data API는 **Aviasales 사용자 검색 이력 기반 캐시 데이터**이다.
- 따라서 실시간 결제 장부 데이터가 아니라 **관측 가격 데이터**로 해석한다.
- 캐시 기반 특성상 `success=True`여도 `data={}`가 나올 수 있다.
- 요청한 목적지 코드와 실제 응답 목적지 코드가 다를 수 있다.
  - 예: `query_destination=NRT`인데 `result_destination=TYO`

---

## 4. 실제 호출 관측 결과 요약

### 4-1. `v1/prices/cheap`
#### 관측 내용
- 정상 응답 확인
- `YYYY-MM-DD`처럼 특정 날짜를 넣으면 `data={}`가 자주 발생
- `YYYY-MM`처럼 월 단위 요청 시 데이터가 잡히는 경우 확인
- 결과는 대표 최저가 1건 수준으로 반환되는 경향 확인
- `query_destination=NRT`로 요청해도 `result_destination=TYO`로 반환되는 경우 확인

#### 반환 특징
- 필드가 단순함
- 대표 가격 스냅샷 확인에 적합
- row 수가 적어 누적 DB의 메인 엔드포인트로는 약함

#### 주요 반환 필드 예시
- `price`
- `airline`
- `departure_at`
- `return_at`
- `expires_at`
- `flight_number`
- `duration`
- `duration_to`
- `duration_back`

---

### 4-2. `aviasales/v3/prices_for_dates`
#### 관측 내용
- 정상 응답 확인
- 비교 테스트 결과 row 수와 정보량이 가장 균형적이었음
- 공항/도시 코드가 동시에 제공되는 패턴 확인
- 항공사, 편명, 경유 정보, 링크 등 학습 및 분석에 유리한 필드 포함

#### 반환 특징
- `cheap`보다 더 많은 row 반환
- 정보량이 풍부함
- 메인 누적용 엔드포인트 후보로 가장 적합

#### 주요 반환 필드 예시
- `origin`
- `destination`
- `origin_airport`
- `destination_airport`
- `price`
- `airline`
- `flight_number`
- `departure_at`
- `return_at`
- `transfers`
- `return_transfers`
- `duration`
- `duration_to`
- `duration_back`
- `gate`
- `link`

---

### 4-3. `v2/prices/month-matrix`
#### 관측 내용
- 정상 응답 확인
- 날짜 단위 가격 분포를 확인하는 데 유리한 구조
- 비교 테스트에서 row 수는 확보되었으나,
  현재 프로젝트 기준에서는 `prices_for_dates`와 `get_latest_prices` 사이에서 역할이 애매함

#### 반환 특징
- 달력형/월별 분포형 데이터
- 날짜별 가격 흐름 파악에는 유리
- 현재 단계에서는 보류 대상

#### 주요 반환 필드 예시
- `origin`
- `destination`
- `depart_date`
- `return_date`
- `value`
- `found_at`
- `number_of_changes`
- `distance`
- `actual`
- `trip_class`

---

### 4-4. `aviasales/v3/get_latest_prices`
#### 관측 내용
- 정상 응답 확인
- 비교 테스트 기준 row 수가 가장 많았음
- `found_at`이 포함되어 “언제 발견된 가격인지”를 추적할 수 있음
- 다만 개별 오퍼 상세는 `prices_for_dates`보다 단순함

#### 반환 특징
- 기간 내 발견된 가격 분포 보강에 적합
- 메인 DB보다는 보조 누적/보강용으로 적합

#### 주요 반환 필드 예시
- `origin`
- `destination`
- `depart_date`
- `return_date`
- `value`
- `found_at`
- `number_of_changes`
- `distance`
- `actual`
- `trip_class`

---

## 5. 엔드포인트 역할 잠정 확정

### 5-1. 메인 누적 엔드포인트
- `aviasales/v3/prices_for_dates`

#### 선정 이유
- row 수와 정보량이 가장 균형적임
- 공항/도시 정보를 동시에 제공
- 항공사/편명/경유/링크 등 분석에 유용한 필드 포함
- 현재 프로젝트의 공통 스키마로 가장 자연스럽게 매핑 가능

---

### 5-2. 보조 누적 엔드포인트
- `aviasales/v3/get_latest_prices`

#### 선정 이유
- row 수가 많음
- `found_at` 기반으로 발견 시점 추적 가능
- 가격 분포 보강 데이터로 활용 가능

---

### 5-3. 기준점 / 검증용 엔드포인트
- `v1/prices/cheap`

#### 역할
- 대표 최저가 스냅샷 확인
- 간단한 sanity check
- 메인/보조 엔드포인트 결과와 비교용 기준점

---

### 5-4. 현재 보류 엔드포인트
- `v2/prices/month-matrix`

#### 보류 이유
- 날짜 분포 확인에는 장점이 있으나
- 현재 단계에서는 `prices_for_dates` + `get_latest_prices` 조합과 역할이 일부 중복됨
- 향후 달력형 분석이 필요해질 경우 재검토 가능

---

## 6. 스키마 관점에서 확인된 핵심 사항

### 6-1. query / result 분리 필요
- 요청 목적지와 응답 목적지가 다를 수 있으므로 분리 저장 필요
- 예:
  - `query_destination = NRT`
  - `result_destination = TYO`

### 6-2. 공항 / 도시 분리 필요
- 일부 엔드포인트는 `destination`과 `destination_airport`를 동시에 제공
- 따라서 결과 테이블에서 도시 기준과 공항 기준을 분리 관리할 수 있음

### 6-3. raw 응답 보존 필요
- 엔드포인트마다 필드 구조 차이가 있으므로
  원본 응답(raw_json)은 반드시 저장하는 것을 기본 원칙으로 한다

---

## 7. 운영 적용 메모

### 7-1. 최대 수집 상한
- 현재 프로젝트의 최대 수집 상한은 **366일** 기준을 적용한다.
- 해당 기준은 대상 항공사 공식 예약 가능 기간 및 보조 근거를 반영한 운영 기준이다.

### 7-2. 수집 기간 분할
- 장기 수집 시 `limit` / `page` 누락 가능성이 있으므로
  한 번에 긴 기간을 요청하기보다 **분할 수집 방식**을 우선 검토한다.
- 단, 분할 방식(월 단위 / 주 단위)은 추가 비교 후 확정한다.

### 7-3. 캐시 기반 특성
- 동일한 요청이라도 시점에 따라 값이 바뀔 수 있다.
- 반대로 같은 값이 반복될 수도 있다.
- 따라서 중복 값도 제거 대상이 아니라 **가격 안정 구간 정보**로 해석한다.

---

## 8. 현재 해석

- `prices_for_dates`는 **메인 누적용**
- `get_latest_prices`는 **보조 분포 보강용**
- `cheap`은 **기준점/검증용**
- `month-matrix`는 **현재 보류**

이 기준은 현재 프로젝트 운영 기준이며,
향후 테스트 결과 누락/중복/행 수 분포가 달라질 경우 문서를 업데이트한다.

---

## 9. 다음 단계

- `prices_for_dates` 기준 공통 스키마 정교화
- `get_latest_prices`를 같은 스키마에 보조 테이블로 매핑 가능 여부 검토
- 항공사 예약 가능 기간 기준을 반영한 실제 수집 범위 설계
- 수집 기간 분할 방식(월 단위/주 단위) 최종 결정

---
