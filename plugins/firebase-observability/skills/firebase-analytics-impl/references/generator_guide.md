# Generator 구현 상세 가이드

이 문서는 Generator(구현 에이전트)가 각 task를 구현할 때 참조하는 상세 가이드다.

## 코드 생성 3원칙

1. **GA_PLAN.md가 명세서**: 이벤트명, 파라미터, 삽입 위치는 GA_PLAN.md를 따른다
2. **Context7이 API 레퍼런스**: 함수 시그니처, 사용법, 최신 패턴은 Context7을 따른다
3. **프로젝트 코드가 스타일 가이드**: 네이밍, 포매팅, 디렉토리 구조는 기존 프로젝트 패턴을 따른다

GA_PLAN.md의 코드 스니펫이 Context7 최신 문서와 상이하면 **Context7을 우선**하고, 차이점을 `ga-progress.txt`에 기록한다.

## 구현 순서 및 상세

### 1. 패키지 설치 및 Expo 네이티브 통합

`package.json`에서 `@react-native-firebase/app`과 `@react-native-firebase/analytics` 확인. 미설치 시:

```bash
npx expo install @react-native-firebase/app @react-native-firebase/analytics
```

**app.config.js 필수 설정** (이 단계를 빠뜨리면 네이티브 SDK가 포함되지 않아 이벤트가 조용히 버려짐):

```js
plugins: [
  '@react-native-firebase/app',  // 반드시 등록 — analytics는 plugin 없으므로 추가 불필요
  // ...
],
android: {
  googleServicesFile: './google-services.json',
},
ios: {
  googleServicesFile: './GoogleService-Info.plist',
},
```

설정 후 반드시:

1. `npx expo prebuild --clean` — 네이티브 프로젝트 재생성
2. `npx expo run:android` (또는 `run:ios`) — **dev client 새로 빌드**

`prebuild`만으로는 기기의 앱이 갱신되지 않는다. `run:android`로 실제 빌드해야 네이티브 모듈이 포함된다.

### 2. Analytics 유틸리티 모듈

GA_PLAN.md의 모듈 구조 섹션에 명시된 파일 경로에 생성한다. 일반적 구조:

**이벤트 상수 및 타입 정의 파일**

- GA_PLAN.md의 이벤트 테이블에서 이벤트명 상수 추출
- 각 이벤트의 파라미터에 대한 TypeScript interface 정의
- 이벤트명 union type export

**Analytics 서비스 파일**

- `initAnalytics()`: 환경 체크 + 동의 상태 확인 + `setAnalyticsCollectionEnabled(true)` 호출
- `logEvent(name, params)`: `isEnabled` 가드 + Firebase SDK 위임
- `logScreenView(screenName, screenClass)`: 스크린 트래킹 래퍼
- `setUserProperty(name, value)`: 사용자 속성 래퍼
- `__DEV__` 모드: 콘솔 로그를 **추가**하되 Firebase SDK도 **반드시 호출** (DebugView 테스트를 위해 `return`으로 건너뛰지 않음)
- 에러 처리: `initAnalytics()` 실패 시 `console.error`로 명확히 표시 + `collectionEnabled` 가드에서 무시될 때 DEV에서 경고 출력

**스크린 트래커 파일**

- GA_PLAN.md의 "라우트-스크린 매핑" 테이블을 기반으로 매핑 객체 생성
- 정적 라우트: 직접 lookup
- 동적 라우트 (`[id]`, `[chapterId]` 등): 패턴 매칭
- `logScreenView(routeName)` 함수 export

**스크린 트래킹 훅 파일**

- `usePathname()` from `expo-router` 사용
- 이전 경로를 추적하여 중복 발화 방지
- 경로 변경 시 `logScreenView()` 호출

**동의 관리 파일** (plan에 있으면)

- 프로젝트의 기존 저장소 패턴 사용 (MMKV, AsyncStorage 등)
- `getAnalyticsConsent()` / `setAnalyticsConsent(consent)` export

**Barrel export 파일** (`index.ts`)

### 3. 루트 레이아웃 통합

`app/_layout.tsx` 수정:

- `useEffect(() => { initAnalytics(); }, [])` 추가
- 스크린 트래킹 훅 호출 추가
- 기존 hooks (fonts, splash screen 등) 뒤에 배치
- **변경 최소화** — analytics 초기화 라인만 추가

### 4. 이벤트 구현

GA_PLAN.md의 이벤트 테이블을 행 단위로 처리:

**각 이벤트에 대해:**

1. "파일 경로" 컬럼의 파일을 열기
2. "삽입 위치" 컬럼의 함수/콜백 찾기
3. `logEvent()` 호출 추가 (지정된 파라미터 포함)
4. 기존 콜백 로직 뒤에 배치 (render path에는 넣지 않음)

**Zustand 스토어 액션의 경우:**

- 미들웨어 접근 (plan에서 지정 시) 또는 직접 삽입
- 스토어의 `create()` 호출에 analytics 미들웨어 래핑

**UI 콜백의 경우:**

- `@/` 절대 경로로 `logEvent` import
- 기존 핸들러 함수 내에 호출 추가

### 5. 사용자 속성

GA_PLAN.md의 "User Properties" 테이블 처리:

- 각 속성의 "설정 위치"에 `setUserProperty()` 호출 추가
- range 기반 속성은 count → range 변환 헬퍼 구현

### 6. 동의 관리 UI 통합 (plan에 있으면)

- Settings 화면에 analytics 동의 토글 추가
- `updateAnalyticsConsent()` 연결
- Privacy 화면 업데이트 (plan 요구 시)

## Reasoning Sandwich

3단계로 인지 노력을 분배한다:

**1단계 — 계획 (최대 노력):**

- acceptance_criteria를 하나씩 분석
- 의존성, 연결 지점 파악
- 접근 방식 결정, 예상 난관 파악
- "이 접근으로 모든 criteria를 충족할 수 있는가?" 자문

**2단계 — 구현 (중간 노력):**

- 계획에 따라 코드 작성
- 불필요한 탐색 최소화
- 계획과 불일치 발견 시 1단계로 복귀

**3단계 — 자체 검증 (최대 노력):**

- "코드를 작성했으므로 완료"라는 판단 금지
- 각 criterion을 개별적으로 확인
- "코드가 존재하니 작동할 것이다" 편향 경계
- Evaluator에게 넘기기 전 1차 필터링

## Ralph Loop Pattern (목표 재주입)

매 task 시작 시 명시적으로 재선언:

- 현재 task ID, 제목, acceptance_criteria
- 이전 피드백 (있으면) 요약
- 이번 task의 구체적 목표

이는 여러 task를 거치면서 발생하는 "목표 표류(goal drift)"를 방지한다.

## Loop Detection 대응

**동일 파일 3회 이상 편집 감지 시:**

1. 즉시 중단
2. 근본 원인 재분석
3. 완전히 다른 접근 방식 시도
4. 2번의 접근 전환 후에도 실패 → 사용자 에스컬레이션

**Generator-Evaluator 루프 3회 반복 감지 시:**

1. 해당 task를 `"blocked"`로 표시
2. 차단 사유를 `ga-progress.txt`에 기록
3. 다음 task로 이동

## 코딩 컨벤션 체크리스트

구현 시 반드시 확인:

- [ ] TypeScript 사용, Props interface 정의
- [ ] `@/` 절대 경로 import (상대 경로 금지, `@/*` → `./src/*`)
- [ ] arrow function 컴포넌트
- [ ] 한글 주석
- [ ] 파일 명명: 컴포넌트 `PascalCase.tsx`, 유틸리티 `camelCase.ts`, 상수 `SCREAMING_SNAKE_CASE.ts`
- [ ] `StyleSheet.create()` 사용
- [ ] 기존 코드의 import 순서 패턴 준수
- [ ] 중복 이벤트 로깅 없음 (삽입 전 `grep` 확인)
- [ ] 기존 코드 로직 변경 없음 (analytics 코드만 추가)

## 증분 구현

이미 analytics 코드가 존재하는 프로젝트에서:

- 기존 코드를 덮어쓰지 않음
- 기존 구현이 acceptance_criteria를 충족하면 Evaluator에게 검증 요청
- 누락된 항목만 추가 구현
- 기존 코드와의 일관성 유지 (같은 import 패턴, 같은 유틸리티 함수 사용)
