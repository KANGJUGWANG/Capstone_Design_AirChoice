# AirChoice / BARO 세션 인수인계 메모
> 작성 기준: 2026-04-27

---

## 프로젝트 개요

- **앱명**: BARO (Price Barometer) — 확정
- **팀명**: 둥근해가 떴습니다
- **팀원**: 강주광, 이수진, 노경엽
- **목표**: ICN↔Tokyo(NRT/HND) 항공권 BUY/WAIT 이진 분류 서비스

---

## 저장소

| 구분 | 저장소 | 용도 |
|---|---|---|
| 공개 | `KANGJUGWANG/Capstone_Design_AirChoice` | 서버 수집 파이프라인 기준 코드 |
| 비공개 | `KANGJUGWANG/Capstone_Design` | 프론트엔드 + 백엔드 (앱/웹) |

---

## 서버 정보

- **Oracle Cloud A1 ARM64** (Ubuntu 24, headless)
- 공인 IP: `134.185.108.71`
- 프로젝트 루트: `/srv/Capstone` (수집 서버)
- 백엔드 위치: `~/capstone-web` (FastAPI)
- 백엔드 포트: `8000`
- Docker Compose: `capstone-mysql`, `capstone-crawler`, `capstone-loader`

---

## 수집 파이프라인 현황

### 수집 시스템 (AirChoice v3)
- 파일: `src/crawler/collector.py`
- 4-way 병렬 Playwright (ICN→NRT, ICN→HND, NRT→ICN, HND→ICN)
- JSON 저장 경로: `data/raw/google_flights/YYYY-MM-DD/HH00/`
- 수집 스케줄: 08:00 / 16:00 / 00:00 KST (systemd timer)
- 가격 선택: `choose_official_price_v1` — 항공사 직접판매 rows만

### DB (MySQL 8.0.45, capstone_db)
- 테이블: `search_observation` (1) ↔ `flight_offer_observation` (N)
- 누적 (2026-04-27 기준): search ~5,760건, offer ~210,000건 이상
- 수집 시작일: 2026-04-16

### 웹훅 이벤트 (Discord)
- `startup` / `collect_done` / `insert_done` / `pipeline_fail` / `backup_done` / `disk_warn`
- 파일: `src/utils/webhook.py`
- Python 3.11 호환 (f-string 백슬래시 금지 → `BULLET` 변수 분리)

### 백업
- 스크립트: `scripts/backup_db.sh`
- rclone → Google Drive (`gdrive:AirChoice_Backup/db`)
- `--tpslimit 1 --retries 5 --retries-sleep 30s` (rateLimitExceeded 대응)
- 스케줄: 23:00 KST

### Daily Stats
- 파일: `src/stats/daily_stats.py`
- Daily 10패널 + Cumulative 10패널 PNG 2장 → Discord 웹훅
- 스케줄: 23:10 KST
- 한글 폰트: NanumGothic

---

## 백엔드 (FastAPI, ~/capstone-web)

### 인증
- 카카오 OAuth2 (REST API 키 방식, redirect URI)
- JWT 발급 — 카카오 ID(`sub`)만 포함, 닉네임/이메일 미사용
- 토큰 만료: 60분 (시연 전 1440분으로 늘릴 것)
- 클라이언트 시크릿: **비활성화** 상태 (카카오 디벨로퍼스)

### 유저 데이터
- JSON 파일 단일 관리: `backend/data/users.json`
- 구조: `{ kakao_id: { kakao_id, created_at, last_login, saved: [], settings: {} } }`
- 서버 이전 시 파일만 복사하면 됨

### API 엔드포인트
- `GET /auth/kakao/login` → 카카오 인증 페이지 리다이렉트
- `GET /auth/kakao/callback` → JWT 발급 → 프론트 `/auth/callback?token=JWT`
- `POST /users/me` → 유저 등록/last_login 갱신
- `GET/PUT /users/me/settings` → 설정 조회/수정
- `GET/POST /users/me/saved` → 저장 항공편
- `DELETE /users/me/saved/{id}` → 삭제

### 환경변수 (.env.backend)
```
KAKAO_REST_API_KEY=...
KAKAO_REDIRECT_URI=http://134.185.108.71:8000/auth/kakao/callback
JWT_SECRET=...
JWT_EXPIRE_MINUTES=60
FRONTEND_URL=https://airchoice.vercel.app
ALLOWED_ORIGINS=http://localhost:5173,https://airchoice.vercel.app
```

### systemd
- `airchoice-backend.service` — 포트 8000 상시 실행
- `airchoice-pipeline.timer` — 수집 파이프라인 3회/일
- `airchoice-backup.timer` — 23:00 백업
- `airchoice-daily-stats.timer` — 23:10 stats

---

## 프론트엔드 (Capstone_Design 비공개 레포)

### 기술 스택
- Vite + React, React Router
- CSS Modules
- 배포: Vercel (`airchoice.vercel.app`)

### 브랜치 전략
- `main` — 개발 작업
- `deploy` — Vercel Production 배포 고정 브랜치
- 배포 시: `git checkout deploy && git merge main && git push origin deploy`

### 컬러/디자인
- Primary: `#1A2B5E` (네이비)
- Accent: `#7EB3E8`
- BG: `#f0f4f8`
- 카카오 버튼: `#FEE500`
- CSS 변수: `--primary`, `--bg`, `--muted` 등 `index.css`에 정의

### 구현 완료 화면
- LoginPage (BARO 로고, 카카오 버튼)
- AuthCallbackPage (await 처리 완료)
- HomePage (편도/왕복, 공항 선택, 날짜 선택, 설정 기본값 연동)
- SearchResultPage (편도 단일카드 / 왕복 항공사 그룹카드)
- RoundTripCard (출발편+귀국편 1카드, 합계가격)
- CardDetailPage (가격카드, 구매판단, 가격추이, 북마크 저장)
- SavedListPage (저장 목록 CRUD, 왕복 배지)
- SettingsPage (알림, 기본 편도/왕복, 카카오 ID 표시, 로그아웃)
- ModelInfoPage
- DrawerMenu (BARO 타이틀, 저장목록/설정/모델정보/로그아웃)

### Mixed Content 해결
- Vercel `vercel.json`에 `/api/*` → `http://134.185.108.71:8000/*` 프록시 rewrite
- `frontend/src/api/client.js`: `VITE_BACKEND_URL` 없으면 `/api` 경로 사용
- Vercel 환경변수 `VITE_BACKEND_URL` 삭제 필요 (로컬만 설정)

### 401 처리
- `apiCall()`에서 401 응답 시 localStorage 초기화 → `/login` 자동 이동

---

## 현재 미완/다음 단계

### 즉시 필요
- [ ] Vercel 환경변수 `VITE_BACKEND_URL` 삭제 (Mixed Content 완전 해결)
- [ ] 시연 전 JWT_EXPIRE_MINUTES=1440으로 변경 후 백엔드 재시작

### 단기 (다음주)
- [ ] 실제 DB 데이터 API 연결 (현재 모의 데이터 MOCK_ONEWAY/MOCK_RETURN)
- [ ] FastAPI에 `/flights/search` 엔드포인트 구축 (DB 쿼리 → 프론트)
- [ ] BARO 로고 이미지 파일 적용 (현재 텍스트 로고)
- [ ] 드롭다운 커스텀 UI (OS 기본 select → 커스텀 버튼)

### 중기 (데이터 1주+ 누적 후)
- [ ] 전처리 파이프라인 (`build_features.py`)
- [ ] 모델 비교 파이프라인 (`train.py`)
- [ ] BUY/WAIT 라벨 기준 초안 확정
- [ ] CardDetailPage 구매판단 실제 연결

### 문서
- [ ] 공개 레포 docs에 앱명 BARO 반영
- [ ] 카카오 디벨로퍼스 앱명 변경 ("항공권 의사결정 보조" → "BARO")

---

## 참고 문헌
- Groves & Gini (2013/2015)
- Domínguez-Menchero et al. (2014)
- Cao & Xu (2021)
- Abdella et al. (2021)
- Korkmaz (2024)

---

## MySQL 접속 (관계형 선택 근거)
수집 구조가 1(search):N(offer) 고정 스키마이며, 모델 입력 피처가 DPD·노선·route_type + price_krw JOIN 기반 집계. MongoDB 대비 관계형이 적합 — 발표 시 설명 근거로 사용.
