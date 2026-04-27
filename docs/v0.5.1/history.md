# BARO 프로젝트 진행 이력

---

## 문서 목적

본 문서는 프로젝트 시작부터 현재(v0.5.1)까지의 주요 결정, 방향 전환, 폐기 이력을 시간순으로 정리한다.
이전 문서를 모르는 사람도 전체 흐름을 파악할 수 있도록 작성한다.

작성 기준일: 2026-04-27  
기준 버전: v0.5.1

---

## 전체 흐름 요약

| 버전 | 단계 | 핵심 전환 |
|---|---|---|
| v0.1 | 탐색 | 데이터 바운더리 탐색, 노선 범위 검토 |
| v0.2 / v0.2.1 | API 탐색 | 공식 API 실패 → Travelpayouts 채택 |
| v0.3 | API 전환 | Travelpayouts 폐기 → FlightAPI.io 채택, BUY/WAIT 이진 분류 확정 |
| v0.4 | 수집 방식 전환 | FlightAPI.io 폐기 → Google Flights 인터셉트 기반 직접 수집 |
| v0.4.1 | 구현 완료 | 수집기 구현, DB 스키마 서버 적용, 왕복 단일 테이블 확정 |
| v0.4.3 | 운영 안정화 | 수집 공식 시작, systemd timer, Discord 모니터링, Drive 백업 |
| v0.5 | 앱 개발 | FastAPI + React 앱 개발, Vercel 배포 |
| v0.5.1 | 정체성 확정 | 서비스명 BARO 확정, 피그마 폐기, Claude 바이브코딩 채택 |

---

## v0.1 — 탐색 단계

**핵심 작업**

- 프로젝트 방향 설정: 소비자의 항공권 구매 합리적 의사결정 지원
- 핵심 질문: "지금 예약할지, 더 기다릴지"
- 현재 단계: 데이터 바운더리와 분석 단위 가능 범위를 확인하는 단계

**탐색 항목**

- 한국 측 공항 범위: IIAC, KAC 확인 검토
- 일본 측 도시/공항 코드 후보 검토 (TYO / HND / NRT 분리 필요 인식)
- 가격 API 후보 2~3개 초기 정리

**확정 항목**

- 아직 데이터 바운더리 확인 이전 단계라 확정 항목 없음
- MVP, 모델 방식, 수집 소스 모두 미확정

---

## v0.2 / v0.2.1 — 공식 API 탐색 및 실패

**핵심 전환**

공식 API 중심 접근에서 관측 가격 데이터 중심 접근으로 방향 수정.

**API 탐색 결과**

| API | 결과 | 이유 |
|---|---|---|
| Amadeus | 채택 불가 | 가입/접근 제약, 즉시 사용 불가 |
| Skyscanner 공식 API | 채택 불가 | 파트너 승인형 접근 구조, 즉시 사용 불가 |
| Kiwi | 보류 | 접근성/문서 불안정, 즉시 붙일 수 없음 |
| RapidAPI | 보류 | 공급자별 품질 편차 큼, 단일 API로 취급 불가 |
| Travelpayouts | 채택 | 실제 호출 가능, 데이터 반환 확인 완료 |
| SerpApi | 검토 대상 | 검증/시연용 후보 |

**방향 전환 사유**

- 단일 공급자 의존 구조는 안정성 낮음
- 관측 가격 데이터 (결제 장부가 아님) 기반 분포 학습 방향으로 전환
- 절대 가격 예측보다 구매/관망 이진 판단이 적합하다는 판단

**v0.2.1 확정 사항**

- Travelpayouts `prices_for_dates` — 메인 누적 소스
- Travelpayouts `get_latest_prices` — 보조 분포 보강
- Kaggle dilwong/FlightPrices — 베이스라인 학습 보조 후보
- DPD 상한 366일 (추후 수정)
- MVP 대상: ICN ↔ TYO (NRT / HND 병행 검토)

---

## v0.3 — Travelpayouts 폐기, FlightAPI.io 채택

**핵심 전환**

Travelpayouts 전체 수집 구조 폐기 → FlightAPI.io 기반 신규 수집 구조 채택.

**폐기 사유 (Travelpayouts)**

- Aviasales 사용자 검색 이력 기반 캐시 데이터 구조
- `success=True`여도 `data={}` 빈 응답 빈번
- 요청 목적지와 응답 목적지 불일치 구조적 문제
- DPD 시계열 구성에 부적합

**FlightAPI.io 검증 결과**

| 항목 | 내용 |
|---|---|
| ICN → NRT 실호출 | 정상 데이터 반환 확인 |
| ICN → HND 실호출 | 정상 데이터 반환 확인 |
| 왕복 roundtrip | leg_ids 2개 구조 확인 |
| places 확정 | ICN 12409, NRT 14788, HND 12234 |

**v0.3 확정 사항**

| 항목 | 내용 |
|---|---|
| API | FlightAPI.io (onewaytrip + roundtrip 엔드포인트) |
| 문제 유형 | BUY or WAIT 이진 분류 |
| DPD 상한 | 120일 (366일에서 조정) |
| 왕복 체류 기간 | 7일 고정 |
| 수집 주기 | 매일 반복 |
| Kaggle 후보 | dilwong/FlightPrices (DPD 1~65 커버, 66~120은 직접 수집 필요) |

**폐기 항목**

- Travelpayouts 메인 소스
- SerpApi 검증 후보 (현 단계 불필요)
- 366일 DPD 상한 (근거 없음, 120일로 조정)

---

## v0.4 — Google Flights 인터셉트 전환, 앱 방향 추가

**핵심 전환**

FlightAPI.io 폐기 → Google Flights GetBookingResults 인터셉트 기반 직접 수집.

**폐기 사유 (FlightAPI.io)**

- 캡스톤 운영 관점에서 비용 발생 API 지속 사용 부담
- 지도 교수 권유: 직접 수집 구현 경험 우선
- 직접 수집이 서비스형 결과물과 연결하기에 더 적합하다는 판단

**v0.4 확정 사항**

| 항목 | 내용 |
|---|---|
| 수집 소스 | Google Flights |
| 수집 방식 | GetBookingResults 인터셉트 (HTML 파싱 아님) |
| 수집 서버 | Oracle Cloud A1 Free Tier |
| DB | MySQL, Oracle Cloud 서버 내 Docker 운영 |
| 수집 주기 | 1일 3회 (8시간 간격) |
| 결과물 방향 | 분석 대시보드형 앱 (와이어프레임 초안 Manus 기반 GIF 5종) |

**폐기 항목**

- FlightAPI.io 메인 수집 경로
- HTML 본문 직접 파싱 메인 경로 (인터셉트로 전환)

---

## v0.4.1 — 수집기 구현 완료, DB 서버 적용

**핵심 작업**

- 수집기 구현 완료 (편도 + 왕복)
- DB 스키마 서버 적용 완료 (ALTER TABLE 포함)
- Docker Compose (mysql / app / crawler) 구성 완료

**스키마 확정**

| 항목 | 결정 |
|---|---|
| 테이블 구성 | search_observation, flight_offer_observation, capture_file_log (3개) |
| 편도/왕복 구분 | 단일 테이블, route_type 컬럼 |
| 왕복 확장 필드 | ret_ 컬럼 6개 ALTER TABLE 적용 (2026-04-11) |
| 왕복 별도 테이블 | 폐기 → 단일 테이블 ret_ 컬럼 확장 방식으로 확정 |

**수집량 추정**

| 구분 | DPD 1일당 건수 |
|---|---|
| 편도 | 약 70건 |
| 왕복 | 약 300건 |

3주 수집 기준 충분 수준 판단. Kaggle 보조 데이터 불필요 가능성 높음으로 판단 전환.

---

## v0.4.3 — 수집 운영 공식 시작, 파이프라인 안정화

**핵심 작업**

- 수집 공식 시작: 2026-04-16
- cron → systemd timer 전환
- 모니터링, 백업, 배포 자동화 구축

**인프라 확정**

| 항목 | 내용 |
|---|---|
| 스케줄러 | systemd timer (cron 폐기) |
| JSON 저장 경로 | data/raw/google_flights/YYYY-MM-DD/HH00/ |
| DB 백업 | mysqldump → gzip → rclone → Google Drive (매일 23:00) |
| 배포 자동화 | deploy.sh (GitHub raw 기반 단일 명령) |
| 모니터링 | Discord 웹훅 (startup / collect_done / insert_done / pipeline_fail / backup_done) |
| 로더 | gf_insert.py (편도/왕복 통합, route_type 기준 분기) |

**코드 구조 (src/)**

| 경로 | 역할 |
|---|---|
| src/crawler/ | 수집기 |
| src/loaders/ | DB 적재 |
| src/config/ | 공통 설정 |
| src/utils/ | 웹훅 등 유틸 |
| src/clients/ | 클라이언트 |
| src/stats/ | 통계 |

**폐기 항목 (v0.4.3 시점)**

| 항목 | 이유 |
|---|---|
| cron | systemd timer로 전환 |
| nohup | systemd service로 대체 |
| db_insert_oneway.py | gf_insert.py로 교체 |
| JSON 저장 경로 YYYY-MM-DD/ | 회차 덮어쓰기 문제 → YYYY-MM-DD/HH00/ |

---

## v0.5 — 앱 개발 착수, Vercel 배포

**핵심 작업**

- 프론트엔드: React + Vite, 9개 화면 구현 완료
- 백엔드: FastAPI (auth / core / data / users 구조), 카카오 소셜 로그인 구현
- Vercel 배포 완료 (deploy 브랜치 → Production 고정)

**프론트엔드 화면 구현 상태**

| 화면 | 상태 |
|---|---|
| HomePage | ✅ 완료 |
| SearchResultPage | ✅ 완료 |
| CardDetailPage | ✅ 완료 (모델 영역 "분석 준비 중") |
| SearchDetailPage | ✅ 완료 (요일 패턴 자리 유지) |
| SavedListPage | ✅ 완료 |
| SettingsPage | ✅ 완료 |
| ModelInfoPage | ✅ 완료 (내용 비움) |
| LoginPage | ✅ 완료 |
| AuthCallbackPage | ✅ 완료 |

**백엔드 구현 상태**

| 항목 | 상태 |
|---|---|
| FastAPI 구조 | ✅ 완료 |
| 카카오 로그인 | ✅ 완료 (크롤링 서버 임시 운영) |
| JWT 토큰 관리 | ✅ 완료 |
| 저장 기능 | ✅ 완료 (JSON 파일 기반) |
| MySQL 연결 | ❌ 미완료 |
| 검색 API | ❌ 미완료 |
| 모델 추론 엔드포인트 | ❌ 미완료 |

**미확정 항목 (v0.5 시점)**

- 앱 이름 / 로고 / 포인트 컬러
- 백엔드 서버 배포 위치 (학교 서버 스펙 미확인)
- 비로그인 사용자 허용 여부

---

## v0.5.1 — 서비스 정체성 확정

**핵심 전환**

- 서비스명 AirChoice → **BARO (Price Barometer)** 확정
- 로고 확정
- 디자인 도구: 피그마 → Claude 바이브코딩으로 전환

**앱 정체성 확정 사항**

| 항목 | 내용 |
|---|---|
| 서비스명 | BARO (Price Barometer) |
| 로고 | 확정 (이미지 파일 존재) |
| 메인 컬러 | #1A2B5E (다크 네이비) |
| 서브 컬러 | 라이트 블루 계열 |
| 디자인 방식 | Claude 바이브코딩 |

**폐기 항목**

| 항목 | 이유 |
|---|---|
| 피그마 | Claude 바이브코딩으로 대체, 별도 디자인 시스템 불필요 판단 |

**현재 블로커**

| 블로커 | 영향 범위 |
|---|---|
| 학교 서버 스펙·일정 미확인 | 백엔드 서버 배포, MySQL 연결, 카카오 로그인 이전 |
| 모델 미완성 | 카드 상세보기 세부 구성, 추론 API |

---

## 전체 폐기 이력 요약

| 시점 | 폐기 항목 | 이유 |
|---|---|---|
| v0.2 이전 | Amadeus | 가입/접근 제약 |
| v0.2 이전 | Skyscanner 공식 API | 파트너 승인형 접근 |
| v0.2 | Kiwi | 접근성/안정성 불확실 |
| v0.2 | RapidAPI | 단일 API로 취급 불가 |
| v0.3 | Travelpayouts | 캐시 기반, 빈 응답, 정기 관측 부적합 |
| v0.3 | SerpApi | 현 단계 불필요 |
| v0.3 | 366일 DPD 상한 | 근거 없음, 120일로 조정 |
| v0.4 | FlightAPI.io | 비용 발생, 직접 수집으로 전환 |
| v0.4 | HTML 본문 직접 파싱 | 인터셉트 방식으로 전환 |
| v0.4 | Naver 항공 수집 | OTA 가격 중심, 항공사 직판 불가 |
| v0.4.1 | 왕복 별도 테이블 | ret_ 컬럼 확장 단일 테이블로 대체 |
| v0.4.3 | cron 스케줄 | systemd timer로 전환 |
| v0.4.3 | db_insert_oneway.py | gf_insert.py로 교체 |
| v0.4.3 | JSON 경로 YYYY-MM-DD/ | 덮어쓰기 문제, YYYY-MM-DD/HH00/으로 교체 |
| v0.5.1 | 피그마 | Claude 바이브코딩으로 대체 |

---

## 다음 단계 (v0.6 진입 조건)

- 학교 서버 스펙 확인 완료
- FastAPI ↔ MySQL 연결 완료
- 프론트 ↔ FastAPI 실제 연동 완료
- 시연 흐름 테스트 통과
