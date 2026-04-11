# v0.4.1 진행 체크리스트

---

## 상태 표기 기준

- [x] 완료
- [-] 미진행 또는 해당 없음
- [ ] 미완료 (진행 예정)

---

## 1. 수집 코드 구현

- [x] Google Flights 인터셉트 방식 확인 (GetBookingResults)
- [x] 편도 수집기 구현 완료 (ICN→NRT, ICN→HND, NRT→ICN, HND→ICN)
- [x] 왕복 수집기 구현 완료 (편도 노선 기반 왕복 조합)
- [x] DPD 1~120 루프 구조 구현
- [x] 1일 3회 수집 주기 구현
- [x] 로컬 테스팅 완료
- [ ] 서버 테스팅
- [ ] cron 등록

---

## 2. DB 스키마

- [x] search_observation 테이블 설계 및 서버 적용
- [x] flight_offer_observation 테이블 설계 및 서버 적용
- [x] capture_file_log 테이블 설계 및 서버 적용
- [x] 왕복 확장 컬럼(ret_) ALTER TABLE 서버 적용 (2026-04-11)
- [x] 편도/왕복 단일 테이블 방식 확정
- [x] price_source / price_status 코드 기준 확정
- [x] 왕복 상품 식별 키 기준 확정
- [x] schema.md 전면 갱신 (2026-04-11)
- [ ] 중복 판정 키 최종안 및 UNIQUE 제약 적용 여부 결정
- [ ] capture_file_log 실제 운영 여부 결정

---

## 3. 서버 인프라

- [x] Oracle Cloud A1 운영 루트(/srv/Capstone) 구성
- [x] docker-compose.yml 구성 완료 (mysql / app / crawler 3개)
- [x] MySQL 컨테이너 기동 및 정상 확인
- [x] capstone_db 생성 완료
- [x] DB 계정 구조 확정 (관리자 / 팀원 작업 / 앱 연결 계정 분리)
- [x] 팀원 DB 계정 권한 설정 완료
- [ ] cron 등록
- [ ] 실제 수집 적재 연동 확인

---

## 4. 수집량 재평가

- [x] DPD 120 × 4노선 × 3회/일 기준 수집량 추정
- [x] 편도 DPD 1당 약 70건, 왕복 DPD 1당 약 300건 확인
- [x] 3주 수집 후 노선 정보 충분 수준 판단
- [x] Kaggle(dilwong/FlightPrices) 불필요 가능성 높음으로 판단 전환
- [ ] 1차 수집 결과 확인 후 Kaggle 최종 폐기 여부 결정

---

## 5. 와이어프레임 및 결과물

- [x] Manus 기반 와이어프레임 5종 확정
- [x] docs/v0.4/assets/ 에 GIF 5종 등록
- [ ] MVP 앱 기능 범위 확정 (다음 단계)
- [ ] 화면별 최소 필요 데이터 필드 정리
- [ ] 앱 기반 UI/UX 고도화 방향 확정

---

## 6. 다음 단계 (v0.4.2 진입 조건)

- [ ] 서버에서 수집기 테스팅 완료
- [ ] cron 등록 및 운영 시작
- [ ] 초기 수집 데이터 적재 확인
- [ ] 수집량 및 품질 1차 점검
- [ ] v0.4.2 anchor.md 작성

---

## 7. 보류 항목

- Kaggle(dilwong/FlightPrices) 최종 폐기 여부 — 1차 수집 결과 확인 후 결정
- 라벨 생성 기준(BUY/WAIT 임계점) — 모델링 단계 진입 후 확정
- 최종 모델 구조 및 feature 세트 — 데이터 누적 후 확정
- 앱 MVP 기능 범위 — 다음 단계에서 확정
