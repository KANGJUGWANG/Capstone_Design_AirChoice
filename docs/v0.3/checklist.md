# v0.3 진행 체크리스트

---

## 1. v0.2.1 정리

- [x] Travelpayouts 메인 소스 방향 폐기 확정
- [x] SerpApi 검증 후보 보류
- [x] 366일 DPD 상한 폐기, 120일로 조정
- [x] v0.3 문서 세트 작성

---

## 2. API 검증

- [x] FlightAPI.io 접근 가능 여부 확인
- [x] 크레딧 과금 구조 확인 (요청당 2크레딧)
- [x] `onewaytrip` 엔드포인트 실호출 확인
- [x] ICN → NRT 실제 데이터 반환 확인 (111개 itinerary)
- [x] ICN → HND 실제 데이터 반환 확인 (27개 itinerary)
- [x] `roundtrip` 엔드포인트 실호출 확인 (237개 itinerary, 직항 200개)
- [x] roundtrip leg_ids 2개 구조 확인 (outbound + inbound 분리)
- [x] 직항 필터링 가능 여부 확인 (stop_count 기준)
- [x] KRW 가격 반환 확인
- [x] carrier IATA 코드 매핑 확인 (display_code 기준)
- [x] places[14788] = NRT 확정
- [x] places[12234] = HND 확정
- [x] NRT/HND 별도 요청 구조 확인

---

## 3. Kaggle 데이터 탐색

- [x] 반복 관측 구조 기준으로 후보 탐색
- [x] dilwong/FlightPrices 필드 매핑 확인
- [x] DPD 분포 확인 (DPD 1~65 커버, 66~120 없음)
- [x] DPD vs 가격 패턴 확인 (DPD 감소 → 가격 급등 패턴 유효)
- [x] 직항 필터 후 행 수 확인 (수백만 rows)
- [x] baseFare 사용 권장 확인
- [ ] 직접 수집 30일 후 최종 활용 여부 결정

---

## 4. 스키마 설계

- [ ] raw 스키마 확정 (저장 필드 목록)
- [ ] normalized 스키마 초안 작성
- [ ] raw / interim / processed 단계 분리 정의
- [ ] 편도 / 왕복 공통 스키마 vs 분리 스키마 결정
- [ ] 빈 응답 처리 원칙 정리
- [ ] 중복 응답 처리 원칙 정리

---

## 5. 수집 코드 작성

- [ ] `src/clients/flightapi_client.py` 작성
- [ ] 편도 수집 함수 구현
- [ ] 왕복 수집 함수 구현
- [ ] DPD 기준 출발일 범위 생성 로직 구현
- [ ] raw 응답 저장 로직 구현 (`data/raw/`)
- [ ] 수집 스케줄러 설계 (매일 반복 수집)
- [ ] `requirements.txt` 의존성 반영

---

## 6. 수집 운영

- [ ] 첫 수집 실행 및 결과 확인
- [ ] DPD 분포 확인 (120일 상한 내 분포 여부)
- [ ] 직항 / 경유 비율 확인
- [ ] 왕복 응답 구조 편도 대비 차이 확인
- [ ] 빈 응답 발생 빈도 확인
- [ ] 중복 응답 처리 원칙 결정

---

## 7. 데이터 보조 전략

- [ ] 30일 수집 후 데이터량 평가
- [ ] 학습 가능 수준 여부 판단
- [ ] 부족 시 dilwong/FlightPrices 활용 여부 결정
  - [ ] baseFare 정규화 방식 결정 (노선별 min-max 또는 z-score)
  - [ ] 사전학습 vs 혼합 학습 방식 결정

---

## 8. 분석 / 모델링 (수집 이후 단계)

- [ ] EDA — DPD별 가격 분포 시각화
- [ ] 라벨 생성 기준 정의
  - [ ] 비교 기준 DPD 설정
  - [ ] BUY 임계점 설정
- [ ] feature 세트 확정
- [ ] 모델 선정 및 학습
- [ ] 평가 지표 설정

---

## 9. 문서 관리

- [x] v0.3 anchor.md 최종 수정
- [x] v0.3 baseline.md 최종 수정
- [x] v0.3 api_strategy.md 최종 수정
- [x] v0.3 checklist.md 최종 수정
- [ ] 스키마 확정 후 문서 반영
- [ ] 라벨 생성 기준 확정 후 baseline.md 반영