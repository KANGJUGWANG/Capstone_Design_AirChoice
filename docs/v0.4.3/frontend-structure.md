# v0.4.3 Frontend Structure

---

## 1. 문서 목적

본 문서는 프론트엔드 프로젝트 구조 기준을 정리한다.
React 웹앱 우선 구현, APK 전환 가능성을 고려한 폴더 분리 기준을 명시한다.

---

## 2. 기술 스택 확정

| 항목 | 내용 | 상태 |
|---|---|---|
| 1차 구현 | React (웹앱) | 확정 |
| 발표 방식 | 웹 브라우저 시연 | 확정 |
| APK 대응 | 구조로 가능성 열어둠, 요구 확정 시 Expo/RN 진입 | 보류 |
| 배포 | Vercel 또는 Netlify | 미확정 |

---

## 3. 폴더 구조

```
frontend/
  src/
    domain/      # 비즈니스 로직, 타입, 계산
    api/         # 서버 통신 (FastAPI 호출)
    store/       # 상태 관리
    hooks/       # UI 비의존 커스텀 훅
    shared/      # 공통 유틸, 상수, config

    web/         # React 웹 전용 구현
      components/  # 공통 UI 컴포넌트
      pages/       # 화면 단위
      routes/      # 라우팅
      auth/        # 카카오 웹 로그인

    mobile/      # APK 요구 확정 시 Expo/RN 구현
```

---

## 4. 레이어별 재사용 기준

| 레이어 | 웹→앱 전환 시 | 비고 |
|---|---|---|
| domain/ | 재사용 | 플랫폼 독립 |
| api/ | 재사용 | 플랫폼 독립 |
| store/ | 재사용 | 플랫폼 독립 |
| hooks/ | 재사용 | UI 비의존 훅 한정 |
| shared/ | 재사용 | 플랫폼 독립 |
| web/ | 재사용 불가 | mobile/로 재작성 |
| web/auth/ | 재사용 불가 | 카카오 SDK 플랫폼별 상이 |
| mobile/ | APK 확정 시 신규 작성 | |

---

## 5. 웹→앱 전환 시 재작성 범위

재작성 필요 항목:
- 화면 컴포넌트 (div → View, CSS → StyleSheet)
- 스타일링 전체
- 라우팅 (React Router → React Navigation)
- 카카오 로그인 (JS SDK → react-native-kakao-login + EAS Build)
- 딥링크 / Redirect URI 처리

재사용 가능 항목:
- API 호출 로직
- 상태 관리
- 도메인 로직
- 데이터 타입
- UI 비의존 훅

---

## 6. 현재 미확정 항목

- APK 제출 요구 여부 (교수 확인 필요)
- 배포 서비스 (Vercel / Netlify)
- 앱 이름 / 로고 / 포인트 컬러
- 상태 관리 라이브러리 (Zustand / Redux / Jotai 등)

---

## 7. 작성 규칙

- domain/, api/, store/, hooks/, shared/ 는 웹 전용 코드 혼입 금지
- web/ 안에서 domain/ 로직을 직접 구현하지 않고 import해서 사용
- 컴포넌트와 로직 분리 원칙 유지
- config 값 (API base URL 등) 은 shared/ 에서 관리
