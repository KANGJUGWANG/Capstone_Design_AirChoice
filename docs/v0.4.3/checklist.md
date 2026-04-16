# v0.4.3 진행 체크리스트

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
- [x] 서버 테스팅 완료
- [x] JSON 저장 경로 회차 구분 구조 적용 (YYYY-MM-DD/HH00/)
- [x] DPD 단위 예외 격리 — 한 DPD 실패가 전체에 영향 없음
- [x] 동적 재시도 — 마감(시작+7h50m) 전까지 실패 DPD 자동 재수집
- [x] systemd timer 등록 완료 (00:00 / 08:00 / 16:00 KST)
- [x] 수집 운영 시작 (2026-04-16)
- [x] 첫 정상 회차 확인 (2026-04-16 08:00)

---

## 2. 로더

- [x] db_insert_oneway.py → gf_insert.py 교체 (편도/왕복 통합)
- [x] route_type 기준 분기 처리
- [x] raw_file_path UNIQUE 기반 중복 처리 확정
- [x] --hour, --date 인자로 회차 기준 INSERT
- [x] capture_file_log 운영 중 확인
- [x] stops, aircraft, seller_type, airline_tag_present 4개 컬럼 INSERT 추가

---

## 3. DB 스키마

- [x] search_observation — raw_file_path 컬럼 추가 및 UNIQUE 제약 적용
- [x] flight_offer_observation — stops, aircraft, seller_type, airline_tag_present 추가
- [x] capture_file_log — 실제 운영 컬럼 기준 확정
- [x] 실서버 DDL 기준 schema.md 전면 갱신
- [-] 중복 판정 UNIQUE 제약 — raw_file_path 기준으로 운영 중 (별도 복합키 불필요)

---

## 4. 서버 인프라

- [x] Oracle Cloud A1 운영 루트 (/srv/Capstone) 구성
- [x] Docker Compose (mysql / crawler / loader) 기동
- [x] deploy.sh 기반 단일 명령 배포 체계 구축
- [x] systemd pipeline timer 등록 (airchoice-pipeline.timer)
- [x] systemd backup timer 등록 (airchoice-backup.timer)
- [x] run_pipeline.sh 한글 인코딩 버그 수정 (영문 주석 전환)
- [x] COLLECT_HOUR — date +%-H 방식 (sed 00→빈문자열 버그 수정)

---

## 5. DB 백업 체계

- [x] scripts/backup_db.sh 작성 완료
- [x] rclone Google Drive 연동 완료
- [x] mysqldump TCP 접속 (-h 127.0.0.1) — 소켓 인증 우회
- [x] 로컬 압축본 업로드 후 자동 삭제
- [x] systemd backup timer 등록 (매일 23:00 KST)
- [x] 수동 테스팅 완료 — Drive 업로드 정상 확인

---

## 6. Discord 웹훅 모니터링

- [x] src/utils/webhook.py 구현
- [x] startup 이벤트 — raw/DB/백업 초기 상태 스냅샷
- [x] collect_done 이벤트 — 노선별 카드 수, 소요 시간
- [x] insert_done 이벤트 — 적재 건수, 가격 분포, DB 누적, 디스크
- [x] pipeline_fail 이벤트 — 실패 단계, 에러
- [x] backup_done 이벤트 — 파일명, 크기, DB 누적
- [x] disk_warn 이벤트 — 80% 초과 시에만 전송
- [x] 포럼 채널 호환 (content: "" + User-Agent: Mozilla/5.0)
- [x] 전체 이벤트 정상 동작 확인

---

## 7. 수집량 및 데이터 품질

- [x] DPD 120 × 4노선 × 3회/일 기준 수집량 추정
- [x] 편도 DPD 1당 약 70건, 왕복 DPD 1당 약 300건 확인
- [x] Kaggle(dilwong/FlightPrices) 불필요 가능성 높음으로 판단
- [ ] 수집 데이터 품질 1차 점검 (약 1주 후)
- [ ] Kaggle 최종 폐기 여부 결정

---

## 8. 다음 단계 (v0.5 진입 조건)

- [ ] 수집 데이터 품질 1차 점검 완료
- [ ] FastAPI 데이터 출구 구축
- [ ] 전처리 파이프 구축 (src/features/build_features.py)
- [ ] 모델 비교 파이프 구축 (src/models/train.py)
- [ ] 라벨 기준 초안 작성 (BUY/WAIT 임계점)
- [ ] v0.5 anchor.md 작성

---

## 9. 보류 항목

- Kaggle(dilwong/FlightPrices) 최종 폐기 여부 — 1차 수집 결과 확인 후 결정
- 라벨 생성 기준(BUY/WAIT 임계점) — 모델링 단계 진입 후 확정
- 최종 모델 구조 및 feature 세트 — 데이터 누적 후 확정
- MVP 앱 기능 범위 — 모델링 단계 이후 확정
- FastAPI 인증 여부 — 팀 내부용이면 생략 가능, 미결정
