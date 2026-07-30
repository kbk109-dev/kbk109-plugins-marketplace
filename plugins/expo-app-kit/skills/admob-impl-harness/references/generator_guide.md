# Generator 구현 상세 가이드

이 문서는 Generator(구현 에이전트)가 각 task를 구현할 때 참조하는 상세 가이드다.

## 구현 순서 및 상세

### 1. 패키지 설치 및 초기 설정

패키지 매니저 감지:

```
yarn.lock 존재 → yarn
pnpm-lock.yaml 존재 → pnpm
기본 → npm (npx expo install 사용)
```

`react-native-google-mobile-ads` 설치 여부 확인. 미설치 시:

```bash
npx expo install react-native-google-mobile-ads
```

`app.json` 또는 `app.config.ts`에 AdMob 플러그인 설정:

- plugins 배열에 `react-native-google-mobile-ads` 추가
- Android/iOS App ID 설정 (ADMOB-PLAN.md Section 5에서 가져옴)
- 정확한 설정 형식은 Context7 문서 기준

`expo-dev-client` 설치 확인 (AdMob은 Expo Go에서 동작하지 않음). 미설치 시 사용자에게 알림.

### 2. 환경변수 설정

`.env.local` 파일에 ADMOB-PLAN.md Section 5의 모든 Ad Unit ID를 추가한다.

- `# ===== AdMob =====` ~ `# ===== End AdMob =====` 마커 사이에 배치
- Google 공식 테스트 ID를 값으로 사용
- 기존 비-AdMob 콘텐츠 보존
- `EXPO_PUBLIC_` 접두사가 필요한 경우 프로젝트 컨벤션 확인

### 3. Ad Utility 모듈

`src/ads/` 디렉토리에 다음 파일을 생성/수정한다:

**`src/ads/adUnitIds.ts`** — Ad Unit ID 상수

- 환경변수에서 ID를 읽음
- `__DEV__` 모드에서 Google 테스트 ID 폴백
- 타입 안전한 상수 export

**`src/ads/adConfig.ts`** — 설정 상수

- ADMOB-PLAN.md Section 6의 빈도 캡핑 값
- `ADS_ENABLED` 플래그
- 최소 간격, 세션당 최대 횟수 등

**`src/ads/initAds.ts`** — SDK 초기화

- `mobileAds().initialize()` 호출
- 에러 핸들링
- `__DEV__` 모드 로그

**`src/ads/index.ts`** — Barrel export

### 4. 광고 컴포넌트 및 훅

ADMOB-PLAN.md에 명시된 광고 타입에 대해서만 구현한다.

**Banner: `src/ads/components/AdBanner.tsx`**

- `BannerAd` 래퍼 컴포넌트
- Props: `adUnitId`, `size` (기본: adaptive), `containerStyle`
- 로딩 상태 관리 (레이아웃 점프 방지)
- 로드 실패 시 graceful 숨김

**Interstitial: `src/ads/hooks/useInterstitialAd.ts`**

- 프리로딩 로직 (광고 표시 후 다음 광고 로드)
- 빈도 캡핑 (최소 간격 + 세션당 최대)
- `{ showAd, isLoaded, isShowable }` 반환

**Rewarded: `src/ads/hooks/useRewardedAd.ts`**

- 마운트 시 프리로드
- 보상 콜백 처리
- `{ showAd, isLoaded, reward }` 반환
- 표시 후 재로드

**App Open: `src/ads/hooks/useAppOpenAd.ts`**

- AppState 리스너로 백그라운드→포어그라운드 감지
- 최소 백그라운드 시간 체크 (plan에서 지정한 값)
- 세션 레벨 캡
- 게임 플레이 중 미표시 로직

### 5. SDK 초기화 배치

루트 레이아웃 (`app/_layout.tsx`):

- `initAds()` import
- `useEffect(() => { initAds(); }, [])` 추가
- 기존 코드에 최소한으로 변경

### 6. 화면별 광고 배치

ADMOB-PLAN.md Section 4 (화면별 광고 배치 맵)을 한 행씩 처리한다.

**Banner 광고 배치:**

1. 해당 화면 파일 열기
2. 기존 레이아웃 구조 파악
3. 지정된 위치에 `AdBanner` 컴포넌트 삽입
4. 적절한 spacing/padding 추가
5. 기존 콘텐츠와 겹치지 않도록 확인

**Interstitial 광고 배치:**

1. 해당 화면에서 interstitial 훅 import
2. 지정된 트리거 시점에 `showAd()` 호출
3. `isShowable` 체크 (로딩 + 빈도 캡핑)

**Rewarded 광고 배치:**

1. 해당 화면에서 rewarded 훅 import
2. opt-in UI 요소 추가 (버튼, 프롬프트)
3. 사용자 자발적 선택만 (자동 재생 금지)
4. 보상 콜백에서 지정된 보상 지급
5. 로드 실패 시 대안 메시지

**App Open 광고 배치:**

1. 루트 레이아웃에서 app open 훅 import
2. AppState 전환 전역 관리
3. 지정된 조건(최소 백그라운드 시간, 제외 화면) 적용

### 7. 기존 광고 코드 정리

ADMOB-PLAN.md에서 제거가 명시된 항목 처리:

- 종료 다이얼로그 배너 제거
- `ALWAYS_SHOW_INTERSTITIAL` → `false` 변경
- 기타 plan에서 변경이 명시된 설정값 수정

## 코딩 컨벤션 체크리스트

구현 시 반드시 확인:

- [ ] TypeScript 사용, Props interface 정의
- [ ] `@/` 절대 경로 import (상대 경로 금지)
- [ ] 프로젝트 CLAUDE.md의 스타일링 방식 준수
- [ ] arrow function 컴포넌트
- [ ] 한글 주석 (코드 주석은 영어)
- [ ] 파일 명명: 컴포넌트 `PascalCase.tsx`, 유틸 `camelCase.ts`, 상수 `SCREAMING_SNAKE_CASE.ts`
