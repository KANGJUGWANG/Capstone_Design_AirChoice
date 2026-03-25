# v0.2.1 Project Anchor

---

## 1. 문서 목적
본 문서는 v0.1 이후 진행된 탐색, 시행착오, 수정 이유, 현재까지의 결정 사항을 정리하여 현재 프로젝트의 기준 문서(Anchor)로 사용하기 위해 작성한다.

본 문서는 다음 목적을 가진다.

- v0.1 이후 변경된 방향성과 판단 근거를 정리
- 현재 기준으로 무엇이 확정되었고 무엇이 미확정인지 구분
- 이후 진행 시 판단 기준이 흔들리지 않도록 기준점 역할 수행
- 관련 문서와 외부 근거를 추적 가능하게 정리

---

## 2. 상태 구분 기준
본 문서에서는 아래 구분을 사용한다.

- **확정**: 현재 프로젝트 운영 기준으로 채택한 항목
- **보류**: 후보로 유지하되 현재 메인 진행 대상은 아닌 항목
- **미확정**: 후속 검증 후 결정할 항목

---

## 3. v0.1 이후 변경 요약
v0.1 이후 프로젝트는 **공식 API 중심 접근**에서 **관측 가격 데이터 중심 접근**으로 방향을 수정하였다.

초기에는 항공권 가격 데이터를 직접 제공하는 API를 중심으로 데이터 수집 구조를 설계하려고 했다. 그러나 실제 검토 과정에서 다음 문제가 확인되었다.

- 일부 공식 API는 가입/승인 제약이 있음
- 일부 후보는 접근 가능 여부가 불확실함
- 일부 공급자는 비용/호출 제한/정책 리스크가 큼
- 단일 API에만 의존하는 구조는 프로젝트 안정성이 낮음

이 과정에서 단일 공급자 중심 접근 대신, **관측 가격 데이터 기반의 다중 공급자 검토 + 보조 공개 데이터 활용** 방식으로 방향을 수정했다.

---

## 4. 검토한 방향성과 수정 이유

### 4-1. 초기 방향
- 항공권 가격 API를 직접 사용해 실시간 또는 준실시간 데이터 확보
- 확보된 가격으로 직접 예측 또는 의사결정 모델 구성

### 4-2. 수정 이유
다음 문제로 인해 초기 방향을 그대로 유지하지 않기로 했다.

- **Amadeus**: 현재 프로젝트 조건에서 즉시 사용이 어려움
- **Skyscanner 공식 API**: 승인형 접근 구조로 즉시 사용 어려움
- **Kiwi**: 접근성과 안정성 측면에서 불확실성 존재
- **RapidAPI**: 개별 공급자별 편차와 정책 리스크 큼
- **SerpApi**: 유효한 후보이나 장기 누적용 메인 소스로 보기엔 비용/공급 구조 고려 필요
- **Travelpayouts**: 실제 호출 가능성과 데이터 확보 가능성 확인

### 4-3. 현재 방향
현재 프로젝트는 다음 구조를 기준으로 진행한다.

- **Travelpayouts**: 메인 가격 관측 소스
- **Travelpayouts get_latest_prices**: 보조 분포 보강 소스
- **SerpApi**: 검증/시연용 후보
- **Kaggle Flight Prices**: 베이스라인 학습용 메인 공개 데이터셋

---

## 5. 데이터에 대한 현재 해석

### 5-1. 데이터 성격
현재 프로젝트에서 사용하는 가격 데이터는 모두 **결제 장부 데이터가 아니라 관측 가격 데이터**로 해석한다.

즉, 아래 데이터는 모두 실제 결제 완료 가격이 아니라 특정 시점에 관측된 가격이다.

- Travelpayouts
- SerpApi
- Kaggle Flight Prices

### 5-2. 데이터 분포
위 데이터들은 모두 관측 가격 데이터라는 공통점이 있지만, 동일한 분포라고 가정하지 않는다.

- 공급자별 가격 형성 방식이 다름
- 관측 시점 구조가 다름
- 캐시 기반 / 검색 결과 기반 차이가 있음
- Kaggle 데이터는 과거 공개 데이터셋이라는 차이가 있음

따라서 이후 데이터 활용 시 `provider` 또는 이에 준하는 구분 기준을 유지하는 방향으로 진행한다.

---

## 6. 현재까지의 주요 결정 사항

### 6-1. 프로젝트 목표 방향
- 가격 직접 예측보다 **구매/관망 의사결정 보조**에 초점
- 절대 가격보다 **관측된 가격 위치와 분포 해석**이 중요하다는 방향 유지

### 6-2. 대상 범위
- 현재 MVP 대상 구간: **ICN ↔ TYO**
- 요청 코드 기준: `TYO`, `NRT`, `HND` 병행 검토
- 결과 기준: 도시/공항 구분 필요

### 6-3. 현재 운영 기준 요약

| 구분 | 현재 선택 | 상태 | 역할 |
|---|---|---|---|
| 메인 엔드포인트 | `prices_for_dates` | 확정 | 메인 누적 |
| 보조 엔드포인트 | `get_latest_prices` | 확정 | 분포 보강 |
| 기준점 엔드포인트 | `cheap` | 확정 | 검증용 |
| 보류 엔드포인트 | `month-matrix` | 보류 | 필요 시 재검토 |
| 검증/시연 후보 | SerpApi | 미확정 | 비교 검증 |
| 메인 Kaggle 데이터셋 | Flight Prices | 확정 | 베이스라인 학습 |
| 운영 최대 수집 상한 | 366일 | 확정 | 수집 범위 기준 |

### 6-4. Kaggle 데이터셋
- 메인 Kaggle 데이터셋: **Flight Prices**
- Airfare ML은 후보로 검토했으나, 현재는 메인 진행 대상에서 제외

---

## 7. 엔드포인트 및 데이터셋 선택 이유

### 7-1. prices_for_dates 선택 이유
`prices_for_dates`는 실제 테스트 결과 기준으로 다음 장점이 확인되었다.

- row 수와 정보량이 균형적임
- 도시/공항 정보를 함께 활용 가능
- 항공사/편명/경유/링크 등 필드가 상대적으로 풍부함
- 현재 임시 정규화 스키마에 가장 자연스럽게 매핑 가능

### 7-2. get_latest_prices를 보조로 두는 이유
- `found_at` 기반 기간 내 발견 가격을 다루기 좋음
- `prices_for_dates`보다 row 수가 많아 분포 보강에 유리
- 다만 오퍼 상세 정보는 상대적으로 적음

### 7-3. Flight Prices를 Kaggle 메인으로 선택한 이유
다음 핵심 컬럼이 확인되었다.

- `searchDate`
- `flightDate`
- `startingAirport`
- `destinationAirport`
- `travelDuration`
- `isNonStop`
- `totalFare`

따라서 현재 임시 정규화 스키마와의 적합성이 높다고 판단했다.

---

## 8. 현재 스키마 상태

### 8-1. 정규화 스키마의 상태
**현재 정규화 스키마는 운영 및 검증을 위한 임시 선정안이며, 최종 확정 스키마가 아니다.**

이는 다음 목적을 가진다.

- Travelpayouts 매핑 가능성 확인
- `get_latest_prices` 보조 매핑 가능성 확인
- Kaggle Flight Prices 매핑 가능성 확인

### 8-2. 스키마 운영 원칙
- 원본(raw)은 최대한 원본 그대로 저장
- 정규화(normalized)는 검증/분석 전 단계에서 생성
- 실제 분석 및 학습 직전 스키마를 다시 검토하고 확정

---

## 9. 현재까지 확인된 핵심 관측 사항

### 9-1. query / result 분리 필요
요청한 목적지와 실제 반환된 목적지가 다를 수 있다.

예:
- `query_destination = NRT`
- `result_destination = TYO`

따라서 query 기준과 result 기준을 분리 저장해야 한다.

### 9-2. 공항 / 도시 분리 필요
일부 응답은 도시 코드와 공항 코드를 동시에 가지므로, 도시 기준/공항 기준을 분리 관리하는 방향이 타당하다.

### 9-3. 캐시 기반 데이터의 특성
Travelpayouts는 캐시 기반이므로 다음 특성이 있다.

- 동일 요청에서도 시점에 따라 값이 달라질 수 있음
- `success=True`여도 `data={}` 가능
- 중복되는 값도 제거 대상이 아니라 안정 구간 정보로 해석 가능

---

## 10. 아직 확정되지 않은 것
현재 아래 항목은 아직 확정 상태가 아니다.

- SerpApi 실제 병렬 수집 도입 여부
- 수집 기간 분할 방식 최종 확정
- 최종 확정 스키마
- 라벨 생성 기준
- 최종 모델 구조
- 분석용 최종 feature 세트

---

## 11. 관련 문서
현재 기준 관련 문서는 다음과 같다.

- `docs/v0.2.1/data strategy summary_revised.md`
- `docs/v0.2.1/endpoint observations and roles revised_revised.md`
- `docs/v0.2.1/target airlines and booking windows revised 366_revised.md`
- `docs/v0.2.1/next steps checklist_revised.md`

---

## 12. 참고 링크

### API / 데이터 공급자 관련
- Travelpayouts Data API:  
  https://support.travelpayouts.com/hc/en-us/articles/203956163-Aviasales-Data-API
- SerpApi Google Flights:  
  https://serpapi.com/google-flights-api

### 대상 항공사/노선 관련
- ICN -> HND 직항 노선 참고:  
  https://www.flightconnections.com/ko/%ED%95%AD%EA%B3%B5%ED%8E%B8-%EC%B6%9C%EB%B0%9C%EC%A7%80-icn-%EB%8F%84%EC%B0%A9%EC%A7%80-hnd
- ICN -> NRT 직항 노선 참고:  
  https://www.flightconnections.com/ko/%ED%95%AD%EA%B3%B5%ED%8E%B8-%EC%B6%9C%EB%B0%9C%EC%A7%80-icn-%EB%8F%84%EC%B0%A9%EC%A7%80-nrt

### 항공사 예약 가능 기간 관련
- JAL:  
  https://www.jal.co.jp/jp/en/inter/reservation/
- ANA:  
  https://www.ana.co.jp/en/jp/guide/reservation/international/about/
- Asiana:  
  https://flyasiana.com/C/KR/EN/contents/book-online?tabId=coupons
- Korean Air:  
  https://www.koreanair.com/contents/footer/customer-support/notice/2025/2503-reserv-open
- Air Busan:  
  https://story.airbusan.com/content/assets/download/pdf/conditions_01_en.pdf
- Jin Air:  
  https://www.jinair.com/ready/reservation?ctrCd=USA&snsLang=en_US
- Jeju Air (보조 근거):  
  https://jj.jejuair.net/dom/board/BDC_NOTICE/9306.do

### Kaggle 데이터셋 관련
- Flight Prices:  
  https://www.kaggle.com/datasets/dilwong/flightprices

---

## 13. 다음 진행 스텝
현재 기준 다음 단계는 아래와 같다.

1. `prices_for_dates` raw 수집 구조를 정의한다.
2. `get_latest_prices` 보조 수집 범위를 결정한다.
3. `Flight Prices`의 raw → normalized 변환 규칙을 정리한다.
4. 수집 분할 방식 및 저장 단위를 결정한다.
5. 누적 데이터 확보 후 스키마 1차 수정 여부를 검토한다.

---

## 14. 현재 문서 위치
본 문서는 **v0.2.1 기준 앵커 문서**이며, 추후 진행 기준점으로 사용한다.

프로젝트 기준이 크게 변경될 경우, 본 문서를 수정하거나 후속 버전 앵커 문서를 새로 작성한다.

---
