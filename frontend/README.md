# AirChoice Frontend

## 구조 원칙

```
src/
  domain/      # 비즈니스 로직, 타입, 계산 — 플랫폼 독립
  api/         # 서버 통신 — 플랫폼 독립
  store/       # 상태 관리 — 플랫폼 독립
  hooks/       # UI 비의존 훅 — 플랫폼 독립
  shared/      # 공통 유틸, 상수 — 플랫폼 독립

  web/         # React 웹 전용
    components/
    pages/
    routes/
    auth/

  mobile/      # APK 요구 확정 시 Expo/RN 구현
```

## 재사용 가능 범위

| 폴더 | 웹→앱 전환 시 재사용 여부 |
|---|---|
| domain/ | 그대로 재사용 |
| api/ | 그대로 재사용 |
| store/ | 그대로 재사용 |
| hooks/ | 그대로 재사용 |
| shared/ | 그대로 재사용 |
| web/ | 재사용 불가 (mobile/로 재작성) |
| mobile/ | APK 확정 시 신규 작성 |

## 현재 단계

- React 웹앱 MVP 구현 중
- mobile/ 은 APK 요구 확정 시 진입
