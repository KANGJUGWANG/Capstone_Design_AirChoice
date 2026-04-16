# v0.4.3 Project Anchor

---

## 1. 문서 목적

본 문서는 v0.4.2(운영 시작) 이후 수집 파이프라인 안정화, 인프라 자동화, 모니터링 체계 구축이 완료된 시점을 반영하여 현재 기준점(Anchor)으로 사용한다.

v0.4.3은 수집이 실제로 동작 중인 첫 번째 안정화 버전이다. 이후 단계는 데이터 누적을 전제로 FastAPI 출구 구축, 전처리 파이프, 모델 비교 파이프로 진행한다.

---

## 2. 상태 구분 기준

- **확정**: 현재 운영 기준으로 채택한 항목
- **보류**: 후보로 유지하되 현재 메인 진행 대상이 아닌 항목
- **미확정**: 후속 검증 또는 구현 결과 확인 후 결정할 항목
- **폐기**: 이전 버전에서 검토했으나 현재 진행 대상에서 제외한 항목

---

## 3. v0.4.1 대비 주요 변경 사항

| 구분 | v0.4.1 상태 | v0.4.3 상태 |
|---|---|---|
| 서버 수집 테스팅 | 미완료 | 완료 |
| 수집 스케줄 등록 | cron 예정 | systemd timer 완료 |
| JSON 저장 경로 | YYYY-MM-DD/ | YYYY-MM-DD/HH00/ (회차 구분) |
| DPD 예외 처리 | 없음 | DPD 단위 격리 + 동적 재시도 |
| DB 백업 체계 | 미구성 | mysqldump → Google Drive 무기한 |
| 배포 자동화 | 미구성 | deploy.sh 기반 단일 명령 배포 |
| 모니터링 | 없음 | Discord 웹훅 전체 이벤트 커버 |
| 수집 운영 | 미시작 | 2026-04-16 공식 시작 |
| 로더 | db_insert_oneway.py (편도 전용) | gf_insert.py (편도/왕복 통합) |
| schema.md | v0.4.1 기준 | 실서버 DDL 기준 전면 갱신 |

---

## 4. 현재 확정 사항

### 4-1. 수집 파이프라인

| 항목 | 내용 | 상태 |
|---|---|---|
| 수집기 | Google Flights GetBookingResults 인터셉트 | 확정 |
| 편도 4노선 | ICN→NRT, ICN→HND, NRT→ICN, HND→ICN | 확정 |
| 왕복 수집 | 편도 노선 기반 동일 4노선 | 확정 |
| DPD 범위 | 1~120 매 회차 전체 수집 | 확정 |
| 수집 주기 | 매일 00:00 / 08:00 / 16:00 KST | 확정 |
| JSON 저장 경로 | data/raw/google_flights/YYYY-MM-DD/HH00/ | 확정 |
| 예외 처리 | DPD 단위 격리 — 한 DPD 실패가 전체에 영향 없음 | 확정 |
| 재시도 방식 | 동적 대기 (남은 시간 / 실패 DPD 수 + 1), 최소 30초 | 확정 |
| 재시도 마감 | 수집 시작 + 7시간 50분 (다음 회차 10분 전) | 확정 |
| 서버 수집 정상 확인 | 2026-04-16 08:00 회차 웹훅 정상 수신 | 확정 |

### 4-2. 로더

| 항목 | 내용 | 상태 |
|---|---|---|
| 로더 파일 | src/loaders/gf_insert.py | 확정 |
| 처리 방식 | 편도/왕복 통합 (route_type 기준 분기) | 확정 |
| 중복 처리 | raw_file_path UNIQUE 기반 INSERT IGNORE | 확정 |
| CLI | --hour, --date 인자로 회차 기준 INSERT | 확정 |
| capture_file_log | offer 1건당 1건 INSERT — 운영 중 | 확정 |

### 4-3. 서버 배포 자동화

| 항목 | 내용 | 상태 |
|---|---|---|
| 배포 방식 | deploy.sh — GitHub raw 기반 단일 명령 | 확정 |
| 실행 방법 | curl -fsSL .../deploy.sh \| bash | 확정 |
| 코드 업데이트 | 동일 명령 재실행으로 즉시 반영 | 확정 |
| systemd unit | 4개 파일 deploy.sh에 포함 | 확정 |

### 4-4. 수집/적재 스케줄

| 항목 | 내용 | 상태 |
|---|---|---|
| 스케줄 방식 | systemd timer (cron 미사용) | 확정 |
| pipeline timer | airchoice-pipeline.timer — 00:00/08:00/16:00 | 확정 |
| 실행 대상 | run_pipeline.sh (수집 → INSERT 순차) | 확정 |
| 서버 timezone | Asia/Seoul (KST) 확인 완료 | 확정 |
| observed_at 기준 | 수집 시작 시각 고정 (분/초 00) | 확정 |

### 4-5. DB 백업 체계

| 항목 | 내용 | 상태 |
|---|---|---|
| 백업 대상 | capstone_db 전체 (mysqldump) | 확정 |
| 백업 흐름 | docker exec mysqldump → gzip → rclone → 로컬 삭제 | 확정 |
| 업로드 대상 | Google Drive (AirChoice_Backup/db/) 무기한 누적 | 확정 |
| 실행 주기 | 매일 23:00 KST | 확정 |
| mysqldump 접속 | TCP (-h 127.0.0.1) — 소켓 인증 우회 | 확정 |
| rclone remote | gdrive | 확정 |

### 4-6. Discord 웹훅 모니터링

| 이벤트 | 내용 | 상태 |
|---|---|---|
| startup | raw/DB/백업 초기 상태 스냅샷 | 확정 |
| collect_done | 노선별 카드 수, 소요 시간 | 확정 |
| insert_done | 적재 건수, 가격 분포, DB 누적, 디스크 | 확정 |
| pipeline_fail | 실패 단계, 에러 메시지 | 확정 |
| backup_done | 파일명, 크기, DB 누적 | 확정 |
| disk_warn | 80% 초과 시에만 전송 | 확정 |

### 4-7. 수집 운영 시작

| 항목 | 내용 | 상태 |
|---|---|---|
| 공식 시작일 | 2026-04-16 | 확정 |
| 첫 정상 회차 | 2026-04-16 08:00 KST | 확정 |
| 목표 수집 기간 | 30일 (2026-05-16 전후) | 미확정 |

---

## 5. 현재 미확정 항목

- 수집 데이터 품질 1차 점검 (약 1주 후)
- Kaggle 보조 데이터 최종 폐기 여부
- FastAPI 데이터 출구 구축
- 전처리 파이프 (build_features.py)
- 모델 비교 파이프 (train.py)
- 라벨 기준 초안 (BUY/WAIT 임계점)
- 최종 모델 구조 및 feature 세트
- MVP 앱 기능 범위 확정

---

## 6. 폐기 항목

| 항목 | 폐기 사유 |
|---|---|
| cron 기반 스케줄 | systemd timer로 전환 — 재부팅 자동 복구, 로그 통합 |
| nohup 백그라운드 실행 | systemd service로 대체 |
| db_insert_oneway.py | gf_insert.py (편도/왕복 통합)로 교체 |
| JSON 저장 경로 YYYY-MM-DD/ | 회차 덮어쓰기 문제 → YYYY-MM-DD/HH00/ 로 교체 |
| FlightAPI.io 메인 수집 경로 | 비용 발생, 직접 수집으로 전환 |
| Travelpayouts 메인 소스 | 캐시 기반, 빈 응답 문제 |
| HTML 본문 직접 파싱 | 인터셉트 방식으로 전환 |
| 왕복 별도 테이블 방식 | 단일 테이블 ret_ 컬럼 확장으로 대체 |

---

## 7. 다음 진행 스텝 (v0.5 기준)

1. 수집 데이터 품질 1차 점검 (약 1주 후)
2. FastAPI 데이터 출구 구축
3. 전처리 파이프 구축 (build_features.py)
4. 모델 비교 파이프 구축 (train.py)
5. 라벨 기준 초안 작성
6. v0.5 문서 작성

---

## 8. 관련 문서 및 코드 위치

- `docs/v0.4.3/schema.md` — 실서버 DDL 기준 확정 스키마
- `docs/v0.4/product.md` — 와이어프레임 및 앱 구조
- `docs/v0.4/data_pipeline.md` — 수집/파싱/적재 흐름
- `src/crawler/collector.py` — 수집기 (DPD 격리 + 동적 재시도)
- `src/loaders/gf_insert.py` — 로더 (편도/왕복 통합)
- `src/utils/webhook.py` — Discord 웹훅
- `scripts/backup_db.sh` — DB 백업
- `deploy/systemd/` — systemd unit 4개
- `deploy.sh` — 배포 자동화
- `run_pipeline.sh` — 수집 → INSERT 파이프라인

---

## 9. 현재 문서 위치

본 문서는 **v0.4.3 기준 앵커 문서**이며, 수집 운영 안정화 완료 시점의 기준점으로 사용한다.
데이터 누적 후 FastAPI/모델링 단계 진입 시점에 v0.5 앵커 문서를 새로 작성한다.
