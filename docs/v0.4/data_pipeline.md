# v0.4 Data Pipeline — 수집 · 저장 · 파싱 · 적재 흐름

---

## 1. 문서 목적

본 문서는 v0.4 기준 프로젝트의 데이터 파이프라인 흐름을 정리한다.

본 문서의 목적은 아래와 같다.

- 수집 실행 단위와 반복 주기 정의
- 브라우저 자동화 기반 인터셉트 흐름 정리
- raw 저장 → 파싱 → 정규화 → DB 적재 순서 정의
- 실패 처리, 재시도, 재처리 기준 정리
- 구현 단계에서 각 모듈의 역할 분리 기준 제공

---

## 2. 파이프라인 개요

v0.4 기준 데이터 파이프라인은 아래 흐름을 따른다.

> 스케줄 생성 → 크롤링 실행 → 인터셉트 raw 저장 → parser 실행 → 정규화 → MySQL 적재 → 분석/앱 조회

전체 흐름은 아래 7단계로 해석한다.

1. 수집 대상 조합 생성
2. 브라우저 자동화 실행
3. 인터셉트 응답 확보
4. raw 파일 저장
5. parser 실행 및 중간 구조 생성
6. 정규화 데이터 생성 및 DB 적재
7. 실패/중복/운영 상태 기록

---

## 3. 실행 주기 및 수집 단위

## 3-1. 실행 주기

기준 수집 주기는 **1일 3회 (8시간 간격)** 으로 둔다.

예시:
- 00:00
- 08:00
- 16:00

정확한 시각은 운영 환경 기준으로 조정 가능하나,  
하루 3회 반복 수집 원칙은 유지한다.

## 3-2. 수집 대상 단위

수집 대상은 아래 조합을 기준으로 생성한다.

- trip_type: `oneway` / `roundtrip`
- route: 인천 ↔ 도쿄 기준 노선 조합
- departure_date: 현재일 + 1 ~ DPD 120
- return_date: 왕복일 경우 체류 7일 고정
- scheduled_at: 각 실행 시각

## 3-3. 수집 범위 해석

현재 기준 수집 범위는 아래를 포함한다.

- 편도
- 왕복
- DPD 120
- 1일 3회
- 다중 노선 조합

따라서 파이프라인은 단일 페이지 수집이 아니라,  
**반복 조합 생성 기반 수집 시스템**으로 해석한다.

---

## 4. 파이프라인 단계별 정의

## 4-1. Step 1 — 수집 대상 조합 생성

역할:
- 해당 실행 시각에 수집할 요청 조합 생성
- `crawl_jobs` 입력 데이터 생성

입력:
- 현재 시각
- 기준 노선 목록
- trip_type 목록
- DPD 상한
- 왕복 체류 규칙

출력:
- 실행 대상 job 목록

예시:
- ICN → NRT / 편도 / 2026-06-01
- ICN → HND / 편도 / 2026-06-01
- ICN ↔ NRT / 왕복 / 2026-06-01 / 2026-06-08

운영 원칙:
- 조합 생성은 deterministic 해야 함
- 동일 실행 시각 기준으로 재현 가능해야 함

---

## 4-2. Step 2 — 브라우저 자동화 실행

역할:
- 대상 검색 페이지 진입
- 조건 입력
- 결과 페이지 도달
- 인터셉트 가능한 요청/응답 확보

입력:
- crawl job 1건

출력:
- raw capture 후보 응답
- 화면 상태 정보
- 성공/실패 상태

운영 원칙:
- 브라우저 자동화는 수집 수단이지 최종 저장 단위가 아님
- 최종 저장 기준은 HTML 본문이 아니라 인터셉트 응답
- HTML 자체는 필요 시 디버깅 목적으로만 제한 저장 가능

---

## 4-3. Step 3 — 인터셉트 응답 확보

역할:
- 브라우저 실행 중 필요한 요청/응답을 가로채기
- 저장 가치가 있는 응답만 선별

입력:
- 브라우저 세션
- 인터셉트 필터 기준

출력:
- raw response payload
- request metadata
- capture status

현재 기준:
- HTML 전체보다 응답 payload를 우선 저장
- 어떤 요청을 저장 대상으로 삼을지는 실제 응답 구조 확인 후 고정

운영 원칙:
- 인터셉트는 raw 확보 수단
- 최종 필드 추출은 parser가 담당
- 수집과 파싱을 분리

---

## 4-4. Step 4 — raw 파일 저장

역할:
- 인터셉트 원본 저장
- 재파싱 가능 상태 유지

입력:
- 인터셉트 응답
- job metadata

출력:
- raw JSON 파일
- `raw_capture_files` 메타데이터 레코드

저장 원칙:
- 원본 응답 본문은 JSON 파일로 저장
- DB에는 파일 경로, capture 상태, 추적 정보만 기록
- 빈 응답, 차단 추정 응답, 실패 응답도 가능하면 저장

예시 저장 정보:
- file_path
- capture_id
- observed_at
- trip_type
- route
- departure_date
- return_date
- capture_status

---

## 4-5. Step 5 — parser 실행

역할:
- raw 파일에서 필요한 필드 추출
- 상품 단위 observation 후보 생성

입력:
- raw file
- parser version

출력:
- parsed record 목록
- parse status
- parse failure 정보

parser 책임 범위:
- 가격 추출
- carrier tag 추출
- 직항/경유 정보 추출
- departure/arrival 정보 추출
- itinerary key 생성 후보 계산

운영 원칙:
- parser는 raw를 수정하지 않음
- parser는 버전 관리 대상
- parser 변경 후 raw 재처리가 가능해야 함

---

## 4-6. Step 6 — 정규화 및 DB 적재

역할:
- parser 결과를 DB 스키마에 맞게 변환
- `flight_observations`, `flight_segments` 등 테이블 적재

입력:
- parsed records

출력:
- MySQL insert/update 결과
- 적재 건수
- 중복 처리 결과

정규화 대상:
- route
- trip_type
- departure_date / return_date
- observed_at / dpd
- carrier_tag
- stop_count / is_direct
- duration
- price
- itinerary key
- segment 정보

운영 원칙:
- raw와 processed를 혼동하지 않음
- 최종 분석/앱 조회는 DB 적재 결과 기준
- 필요 시 processed export는 별도 수행

---

## 4-7. Step 7 — 운영 상태 기록

역할:
- 성공/실패/중복/차단 상태 추적
- 이후 재시도 및 원인 분석 가능하게 함

입력:
- crawl 결과
- parse 결과
- insert 결과

출력:
- `crawl_jobs` 상태 업데이트
- `parse_runs` 기록
- `parse_failures` 기록

운영 원칙:
- 조용한 실패를 허용하지 않음
- 모든 실패는 최소한 job 단위에서 흔적을 남김

---

## 5. 실패 처리 흐름

## 5-1. 실패 단계 구분

실패는 아래 단계로 구분한다.

- `capture` 실패: 페이지 진입/응답 확보 실패
- `raw` 실패: 파일 저장 실패
- `parse` 실패: parser가 구조를 해석하지 못함
- `insert` 실패: DB 적재 실패

## 5-2. 실패 기록 원칙

모든 실패는 아래 중 최소 하나에 기록되어야 한다.

- `crawl_jobs.job_status`
- `raw_capture_files.capture_status`
- `parse_runs.parse_status`
- `parse_failures.failure_type`

## 5-3. 차단 추정 응답 처리

아래 상황은 차단 추정으로 분류할 수 있다.

- 반복적으로 빈 응답만 발생
- 응답 구조가 정상 결과와 현저히 다름
- 브라우저는 성공처럼 보이나 유효 payload 없음
- 동일 조건 재시도 시 지속 실패

차단 추정은 즉시 폐기하지 않고,  
운영 로그와 raw 흔적을 남기는 것을 우선한다.

---

## 6. 재시도 및 재처리 기준

## 6-1. 수집 재시도

기본 원칙:
- 동일 job 실패 시 즉시 무한 재시도하지 않음
- 재시도 횟수는 제한
- 재시도 실패 후 `failed` 또는 `partial` 상태 기록

## 6-2. 파싱 재처리

raw는 보존하므로 parser 개선 후 재처리가 가능하다.

재처리 대상:
- parse 실패 raw
- parser 개선 후 다시 읽을 필요가 있는 raw
- 과거 raw를 새 규칙으로 정규화해야 하는 경우

## 6-3. DB 재적재

중복 정책과 parser version에 따라 아래를 구분한다.

- 동일 데이터의 중복 insert 방지
- parser 변경에 따른 재적재 허용 여부
- 과거 observation overwrite 금지 여부

현재 우선안:
- raw는 보존
- parse_run은 누적 가능
- processed는 중복 키 기준 통제

---

## 7. 디렉토리 구조 기준

예시 구조는 아래를 우선안으로 둔다.

```text
data/
  raw/
    google_flights/
      2026-04-08/
        gf_...json
  interim/
    google_flights/
      2026-04-08/
        parsed_...jsonl
  processed/
    2026-04-08/
      observations_...csv
outputs/
  logs/
    crawler/
    parser/
```

원칙:
- raw는 날짜별 분리
- interim은 parser 중간 산출 분리
- processed는 export가 필요할 때만 생성 가능
- 로그는 outputs 기준으로 분리

---

## 8. 모듈 역할 분리 기준

구현 시 모듈 역할은 아래처럼 분리하는 방향을 우선한다.

| 모듈 | 역할 |
|---|---|
| scheduler | 실행 시각별 job 생성 |
| crawler | 브라우저 자동화 및 인터셉트 |
| raw_writer | raw 파일 저장 |
| parser | 필드 추출 |
| normalizer | observation 구조 정규화 |
| db_writer | MySQL 적재 |
| monitor/logger | 실행 상태 기록 |

원칙:
- 한 모듈이 수집, 파싱, 적재를 모두 담당하지 않음
- parser는 raw 입력을 받아 구조화 결과만 반환
- DB writer는 parser 내부에 넣지 않음

---

## 9. 앱 연결 기준

앱은 raw 데이터를 직접 읽지 않는다.  
앱 조회 기준은 정규화 후 DB에 적재된 데이터로 둔다.

현재 앱 연결 방향:
- 홈/검색 요약 → observation 요약 조회
- BUY/WAIT 화면 → 점수/현재 가격 조회
- 요인 분석 → feature 또는 explanation 결과 조회
- 알림 설정 → 별도 알림 기준 테이블 또는 규칙 로직 연결

즉 파이프라인은 단순 저장이 아니라,  
**앱이 바로 소비할 수 있는 데이터 계층을 만드는 것**까지 포함한다.

---

## 10. 운영 상의 확인 포인트

초기 운영 단계에서 확인할 항목은 아래와 같다.

- job 1회당 평균 실행 시간
- 인터셉트 성공률
- raw 파일 크기와 저장량
- parser 성공률
- 중복 발생 비율
- 빈 응답/차단 추정 비율
- Oracle A1 환경에서의 부하
- 1일 3회 스케줄 지속 가능성

---

## 11. 현재 미확정 항목

- 인터셉트 대상 요청 식별 규칙
- 재시도 횟수 기준
- 차단 추정 응답 판별 규칙
- interim 저장 포맷 최종안
- parser version 관리 방식
- DB insert vs upsert 정책
- processed export 필요 여부
- 운영 로그 세분화 수준

---

## 12. 다음 단계

1. 실제 raw 샘플 확보
2. crawler → raw_writer 최소 경로 구현
3. parser 최소 버전 구현
4. DB writer 최소 버전 구현
5. 소규모 범위로 첫 수집 테스트
6. 실패/중복/속도 기준 확인 후 파이프라인 조정
