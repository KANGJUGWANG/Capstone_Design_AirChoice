# v0.2 대상 항공사 리스트와 공식 예약 가능 기간

---

## 1. 문서 목적
본 문서는 `ICN ↔ TYO` 구간을 기준으로 현재 프로젝트에서 고려 중인 대상 항공사 후보군과, 각 항공사의 공식 예약 가능 기간(확인 가능한 경우)을 정리하고, 프로젝트 수집 상한 기준을 정리하기 위해 작성한다.

---

## 2. 대상 구간
- 출발 공항: ICN (인천국제공항)
- 도착 권역: TYO (도쿄권 도시코드)
- 세부 공항:
  - HND (하네다공항)
  - NRT (나리타국제공항)

---

## 3. 대상 항공사 후보군

### 3-1. ICN -> HND 직항 기준 확인 항공사
- Asiana Airlines
- Korean Air
- Peach

### 3-2. ICN -> NRT 직항 기준 확인 항공사
- Air Busan
- Air Japan
- Air Premia
- Air Seoul
- Asiana Airlines
- Eastar Jet
- Ethiopian Airlines
- Jeju Air
- Jin Air
- Korean Air
- Thai Smile
- T’way Air
- ZIPAIR

### 3-3. 통합 후보군
- Air Busan
- Air Japan
- Air Premia
- Air Seoul
- Asiana Airlines
- Eastar Jet
- Ethiopian Airlines
- Jeju Air
- Jin Air
- Korean Air
- Peach
- Thai Smile
- T’way Air
- ZIPAIR

### 3-4. 항공사 후보군 확인 출처
- ICN -> HND 직항 노선 참고:
  - https://www.flightconnections.com/ko/%ED%95%AD%EA%B3%B5%ED%8E%B8-%EC%B6%9C%EB%B0%9C%EC%A7%80-icn-%EB%8F%84%EC%B0%A9%EC%A7%80-hnd
- ICN -> NRT 직항 노선 참고:
  - https://www.flightconnections.com/ko/%ED%95%AD%EA%B3%B5%ED%8E%B8-%EC%B6%9C%EB%B0%9C%EC%A7%80-icn-%EB%8F%84%EC%B0%A9%EC%A7%80-nrt

---

## 4. 공식 예약 가능 기간 정리

| 항공사 | 확인 상태 | 확인된 예약 가능 기간 | 근거 URL | 비고 |
|---|---|---:|---|---|
| JAL | 확인 완료 | 360일 전 | https://www.jal.co.jp/jp/en/inter/reservation/ | 국제선 예약, 왕복은 마지막 구간 기준 |
| ANA | 확인 완료 | 355일 전 | https://www.ana.co.jp/en/jp/guide/reservation/international/about/ | 국제선 기준 |
| Asiana Airlines | 확인 완료 | 360일 전 | https://flyasiana.com/C/KR/EN/contents/book-online?tabId=coupons | 국제선 온라인 예약 기준 |
| Korean Air | 확인 완료 | 360일 전 | https://www.koreanair.com/contents/footer/customer-support/notice/2025/2503-reserv-open | 공식 공지 기준 |
| Air Busan | 확인 완료 | 354일 전 | https://story.airbusan.com/content/assets/download/pdf/conditions_01_en.pdf | 운송약관 PDF 기준 |
| Jin Air | 확인 완료 | 361일 후 출발편까지 | https://www.jinair.com/ready/reservation?ctrCd=USA&snsLang=en_US | 예약일 기준 최대 361일 후 출발편 |
| Jeju Air | 부분 확인 | 365일 전(보조 근거) | https://jj.jejuair.net/dom/board/BDC_NOTICE/9306.do | B2B 공지 기준, 일반 소비자용 직접 문구는 추가 확인 필요 |
| Peach | 미확인 | - | - | 공식 소비자용 최대 사전 예약 가능 기간 문구 미확인 |
| Air Japan | 미확인 | - | - | 공식 소비자용 최대 사전 예약 가능 기간 문구 미확인 |
| Air Premia | 미확인 | - | - | 공식 소비자용 최대 사전 예약 가능 기간 문구 미확인 |
| Air Seoul | 미확인 | - | - | 공식 소비자용 최대 사전 예약 가능 기간 문구 미확인 |
| Eastar Jet | 미확인 | - | - | 공식 소비자용 최대 사전 예약 가능 기간 문구 미확인 |
| Ethiopian Airlines | 미확인 | - | - | 공식 소비자용 최대 사전 예약 가능 기간 문구 미확인 |
| Thai Smile | 미확인 | - | - | 브랜드/운항 구조 변동 가능성 포함, 공식 소비자용 최대 사전 예약 가능 기간 문구 미확인 |
| T’way Air | 미확인 | - | - | 공식 소비자용 최대 사전 예약 가능 기간 문구 미확인 |
| ZIPAIR | 미확인 | - | - | 공식 소비자용 최대 사전 예약 가능 기간 문구 미확인 |

---

## 5. 프로젝트 적용 기준

### 5-1. 최대 수집 상한
- 현재 프로젝트의 **최대 수집 상한은 366일**로 설정한다.

### 5-2. 기준 설정 이유
- 확인된 항공사 공식 예약 가능 기간이 354일 ~ 361일 범위로 분포함
- Jeju Air 관련 보조 근거에서 365일 전 예약 오픈 정보가 확인됨
- 운영 과정에서 특정 항공사의 예약 오픈 시점 누락을 줄이기 위해 **버퍼 1일을 포함한 366일**을 프로젝트 기준 상한으로 채택함

### 5-3. 문서 운영 원칙
- 본 문서의 366일 기준은 **현재 프로젝트 운영 기준**으로 적용한다
- 향후 미확인 항공사의 공식 예약 가능 기간 추가 확인 또는 이미 확인된 항공사의 정책 변경이 발생할 경우, 해당 문서를 업데이트하고 최대 수집 상한도 함께 재검토한다
- 실제 수집 파라미터 설계에서는 공급자 API 특성, 응답 구조, 페이지 누락 여부를 함께 고려해 적용 범위를 조정할 수 있다

---

## 6. 현재 해석
- 항공사별 최대 예약 가능 기간은 서로 다르다
- 따라서 단일 항공사 기준이 아니라, `ICN ↔ TYO` 대상 후보군 전체를 고려한 운영 상한이 필요하다
- 현재 프로젝트는 수집 누락 방지 목적에서 366일을 적용한다

---

## 7. 다음 단계
- 미확인 항공사의 공식 예약 가능 기간 지속 추적
- `prices_for_dates` / `get_latest_prices` 수집 범위 설정 시 366일 상한을 실제 파라미터 설계에 반영
- 향후 대상 항공사 후보군 축소 또는 제외 기준 논의 시 본 문서를 기준 자료로 사용
