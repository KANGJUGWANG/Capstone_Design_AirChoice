# v0.5 진행 체크리스트

---

## 상태 표기 기준

- [x] 완료
- [-] 해당 없음 / 보류
- [ ] 미완료 (진행 예정)

---

## 1. 수집 인프라 (v0.4.x 완료 항목)

- [x] Google Flights 인터셉트 방식 수집기 구현 (편도 + 왕복)
- [x] DPD 1~120 루프, 1일 3회 수집 주기
- [x] 서버 배포 및 systemd timer 등록
- [x] 수집 운영 시작 (2026-04-16)
- [x] Discord 웹훅 모니터링 (webhook.py)
- [x] Google Drive DB 자동 백업
- [x] deploy.sh 자동 배포 체계
- [x] daily_stats.py 통계 모듈 추가

---

## 2. DB 스키마

- [x] search_observation 테이블 서버 적용
- [x] flight_offer_observation 테이블 서버 적용 (ret_ 컬럼 포함)
- [x] capture_file_log 테이블 서버 적용
- [x] schema.md 전면 갱신 (docs/v0.4.3/schema.md)
- [ ] FastAPI ↔ MySQL 연결 전환 (현재 JSON 파일 기반)
- [ ] 중복 판정 키 최종안 및 UNIQUE 제약 적용 여부 결정

---

## 3. 프론트엔드

- [x] React + Vite 프로젝트 구조 세팅
- [x] 폴더 구조 확정 (domain / api / hooks / store / shared / web / mobile)
- [x] HomePage 구현
- [x] SearchResultPage 구현
- [x] CardDetailPage 구현
- [x] SearchDetailPage 구현
- [x] SavedListPage 구현
- [x] SettingsPage 구현
- [x] ModelInfoPage 구현
- [x] LoginPage 구현
- [x] AuthCallbackPage 구현
- [x] Vercel deploy 브랜치 Production 고정
- [ ] 앱 이름 / 로고 / 포인트 컬러 확정
- [ ] 피그마 디자인 시스템 세팅
- [ ] 프론트 ↔ FastAPI 실제 API 연동
- [ ] 카드 상세보기 세부 구성 (모델 완성 후)
- [ ] 검색 상세보기 요일 패턴 데이터 연결

---

## 4. 백엔드

- [x] FastAPI 프로젝트 구조 세팅 (backend / auth / core / data / users)
- [x] 카카오 로그인 구현 (kakao.py + router.py)
- [x] JWT 토큰 관리 구조 확정
- [x] 저장 기능 구현 (data/store.py, JSON 파일 기반)
- [x] 카카오 로그인 동작 확인
- [ ] 학교 서버 스펙 확인
- [ ] 백엔드 서버 배포
- [ ] FastAPI ↔ MySQL 연결 전환
- [ ] 검색 API 구현 (DB 조회 + 실시간 크롤 fallback)
- [ ] 모델 추론 엔드포인트 자리 추가

---

## 5. 연동

- [ ] 프론트 ↔ FastAPI 전체 연동
- [ ] 카카오 로그인 프론트 ↔ 백엔드 실제 동작 확인
- [ ] 데이터 없음 / 로딩 / 오류 상태 전수 확인
- [ ] 시연 흐름 테스트

---

## 6. 모델링 (수집 데이터 누적 후)

- [ ] 수집 데이터 1차 EDA
- [ ] Kaggle 보조 데이터 최종 폐기 여부 결정
- [ ] BUY/WAIT 라벨 기준 초안 작성
- [ ] feature 세트 확정
- [ ] 모델 선정 및 학습
- [ ] 평가 지표 설정
- [ ] 모델 추론 API 연결

---

## 7. 미확정 보류 항목

- 앱 이름 / 로고 / 포인트 컬러
- 학교 서버 스펙 (백엔드 서버 위치 결정 블로커)
- 비로그인 사용자 허용 여부
- 상태 관리 라이브러리 (Zustand / Redux / Jotai 등)
- 프론트 배포 서비스 최종 확정 (현재 Vercel 운영 중)
- BUY/WAIT 라벨 기준 및 모델 구조

---

## 8. 다음 버전 진입 조건 (v0.5.1 또는 v0.6)

- [ ] 학교 서버 스펙 확인 완료
- [ ] FastAPI ↔ MySQL 연결 완료
- [ ] 프론트 ↔ FastAPI 실제 연동 완료
- [ ] 시연 흐름 테스트 통과
