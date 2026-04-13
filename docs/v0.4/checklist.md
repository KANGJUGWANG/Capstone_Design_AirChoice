# v0.4 진행 체크리스트

---

## 1. v0.3 정리 및 v0.4 전환

- [x] v0.3 유지 항목 / 변경 항목 최종 구분
- [x] FlightAPI.io 메인 수집 경로 종료를 문서 기준으로 명시
- [x] Google Flights 크롤링/인터셉트 방향 전환 사유 정리
- [x] v0.4 문서 세트 초안 작성
  - [x] anchor.md
  - [x] baseline.md
  - [x] research.md
  - [x] schema.md
  - [x] data_pipeline.md
  - [x] checklist.md
- [x] product.md 추가

---

## 2. 수집 대상 및 실행 범위 고정

- [x] 기준 대상 페이지를 Google Flights로 고정
- [x] 편도 / 왕복 수집 범위 확정
- [x] 인천 ↔ 도쿄 기준 노선 조합 최종 정리
  - 편도 4노선: ICN→NRT, ICN→HND, NRT→ICN, HND→ICN
  - 왕복 4노선: ICN↔NRT, ICN↔HND, NRT↔ICN, HND↔ICN
- [x] DPD 상한 120 기준 확정
- [x] 왕복 체류 7일 고정 확정
- [x] 1일 3회 (08:00, 16:00, 00:00) 수집 주기 확정 (cron 미등록)

---

## 3. 인터셉트 가능 여부 검증

- [x] 브라우저 자동화 환경 구성 (Playwright + Chromium)
- [x] 대상 페이지 진입 가능 여부 확인
- [x] 인터셉트 대상 요청/응답 후보 식별 (GetBookingResults)
- [x] 실제 필요한 응답 payload 확보 가능 여부 확인
- [x] HTML 직접 파싱 없이 필요한 정보 확보 가능 확인
- [x] 차단/탐지 발생 여부 1차 점검 (미발생)
- [x] raw 저장 가치가 있는 응답 단위 정의 (JSON 파일 단위)

---

## 4. raw 저장 구조 구현

- [x] raw 파일 저장 디렉토리 구조 확정
  - `/workspace/data/raw/google_flights/<observed_date>/`
- [x] raw 파일명 규칙 확정
  - `<dep_date>_<route_type>_<origin>_<dest>.json`
- [x] raw 파일에 저장할 필드 목록 확정
- [x] raw 메타데이터를 DB에 연결 (capture_file_log)

---

## 5. DB 스키마 확정 및 적용

- [x] `search_observation` 테이블 확정 및 서버 적용
- [x] `flight_offer_observation` 테이블 확정 및 서버 적용
  - [x] 왕복 `ret_*` 컬럼 6개 추가 (ALTER TABLE 서버 적용)
  - [x] `stops`, `aircraft`, `seller_type`, `airline_tag_present` 컬럼 포함
- [x] `capture_file_log` 테이블 확정 및 서버 적용
- [x] schema.md 갱신 (v0.4 실제 구조 반영)

---

## 6. 파싱 규칙 확정

- [x] 가격 우선순위: stage2 pi[0][1] = 왕복 총가격 확인
- [x] `price_source` / `price_status` 코드값 확정
- [x] 공식 판매처(official_seller) 추출 방식 확정 (fi[24])
- [x] `aircraft` 추출 위치 확정 (seg[17])
- [x] `stops` 파생 기준 확정 (세그먼트 수 - 1)
- [x] `airline_tag_present` / `seller_type` 파생 기준 확정
- [x] 직항 필터 TFU 공항별 분리 확정 (NRT: EgYIABAAGAA / HND: EgIIACIA)

---

## 7. 파이프라인 구현

- [x] `src/crawler/constants.py` — 노선, DPD, TFU, 병렬 설정
- [x] `src/crawler/url_builder.py` — tfs protobuf URL 빌더
- [x] `src/crawler/parser.py` — 멀티청크 파서, 카드 파싱, 신규 필드 포함
- [x] `src/crawler/collector.py` — 편도/왕복 수집, DPD 3병렬, networkidle 동적 대기
- [x] `src/crawler/gf_collect.py` — 엔트리포인트 (--dep-date 테스트 인자 포함)
- [x] `src/loaders/gf_insert.py` — observation/offer/capture_log INSERT
- [x] `docker/crawler/Dockerfile` — ARM64 Playwright 컨테이너
- [x] `deploy.sh` — GitHub raw 배포 스크립트

---

## 8. 수집 + INSERT 테스트

- [x] 서버 컨테이너 빌드 및 실행 확인
- [x] 단일 날짜 수집 테스트 (--dep-date)
- [x] 4노선 편도 + 4노선 왕복 정상 수집 확인
- [x] DPD 3병렬 수집 동작 확인
- [x] networkidle 동적 대기 적용 확인
- [x] gf_insert.py 단일 파일 INSERT 테스트
- [x] search_observation 적재 확인 (8건)
- [x] flight_offer_observation 적재 확인 (344건, 전 컬럼 채워짐)
- [x] capture_file_log 적재 확인 (344건, offer와 1:1)

---

## 9. 운영 자동화 (미완)

- [ ] cron 등록 (1일 3회: 08:00, 16:00, 00:00)
- [ ] 수집 → INSERT 연결 스크립트 (run_pipeline.sh 또는 cron 2단계)
- [ ] 로그 보존 정책 확정
- [ ] 수집 실패 시 재시도 정책 확정

---

## 10. 운영 가능성 점검 (미완)

- [ ] DPD 120 전체 수집 1회 실행 시간 측정
- [ ] 메모리/CPU 사용량 확인
- [ ] raw 저장량 추정 (1회 수집 기준)
- [ ] 1일 3회 실행 지속 가능성 확인
- [ ] MySQL 저장량/속도 병목 여부 확인

---

## 11. 데이터 누적 (미시작)

- [ ] 공식 수집 시작 (cron 등록 후)
- [ ] 7일 누적 후 데이터량 평가
- [ ] 30일 누적 후 모델 학습 가능 여부 판단

---

## 12. 외부 보조 데이터 판단

- [ ] 직접 수집 데이터 1차 누적량 확인 후 재검토
- [ ] 부족 시 `dilwong/FlightPrices` 재검토
  - 절대 가격 이전 금지 원칙 유지
  - 사전학습 / 패턴 학습 보조 용도만 허용

---

## 13. 라벨 및 모델링 준비 (미시작)

- [ ] BUY/WAIT 라벨 생성 기준 초안 작성
- [ ] 비교 horizon 후보 정리
- [ ] feature 세트 초안 작성
- [ ] 직접 수집 데이터 기준 베이스라인 EDA
- [ ] 앱 표시용 점수화 방식 후보 정리

---

## 14. 앱 연결 준비 (미시작)

- [ ] 대시보드에서 필요한 최소 필드 정리
- [ ] BUY/WAIT 결과 표시용 필드 후보 정리
- [ ] raw가 아니라 DB 계층으로 조회 연결 가능한지 확인

---

## 15. 문서 반영 (일부 완료)

- [x] DB 스키마 확정 후 schema.md 반영
- [ ] 파이프라인 구조 확정 후 data_pipeline.md 갱신
- [ ] 첫 수집 테스트 결과 anchor.md 반영
- [ ] 라벨 기준 확정 후 baseline.md 반영
- [ ] 앱 구조 구체화 후 product.md 반영

---

## 현재 우선순위

### 즉시
- [ ] cron 등록 (수집 자동화)
- [ ] 수집 → INSERT 연결 (파이프라인 완성)

### 다음 단계
- [ ] DPD 120 전체 수집 1회 실행 + 시간/리소스 측정
- [ ] 데이터 누적 시작

### 후속
- [ ] 라벨 기준 설계
- [ ] 모델링
- [ ] 앱 연결
