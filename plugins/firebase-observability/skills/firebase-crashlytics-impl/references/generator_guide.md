# Generator 구현 상세 가이드

이 문서는 Generator(구현 에이전트)가 각 task를 구현할 때 참조하는 상세 가이드다.

## 코드 생성 3원칙

1. **CRASHLYTICS_PLAN.md가 명세서**: 에러 분류, 속성 키, 로그 포인트, recordError 삽입 위치, Error Boundary 배치는 CRASHLYTICS_PLAN.md를 따른다
2. **Context7이 API 레퍼런스**: 함수 시그니처, 사용법, 최신 패턴은 Context7을 따른다
3. **프로젝트 코드가 스타일 가이드**: 네이밍, 포매팅, 디렉토리 구조는 기존 프로젝트 패턴을 따른다

CRASHLYTICS_PLAN.md의 코드 스니펫이 Context7 최신 문서와 상이하면 **Context7을 우선**하고, 차이점을 `CRASHLYTICS_PROGRESS.txt`에 기록한다.

## 구현 순서 및 상세

### 1. 패키지 설치 및 Expo 네이티브 통합

`package.json`에서 `@react-native-firebase/app`과 `@react-native-firebase/crashlytics` 확인. 미설치 시:

```bash
npx expo install @react-native-firebase/app @react-native-firebase/crashlytics
```

**app.config.js 필수 설정** (이 단계를 빠뜨리면 네이티브 SDK가 포함되지 않아 크래시 리포팅이 작동하지 않음):

```js
plugins: [
  '@react-native-firebase/app',          // 반드시 등록
  '@react-native-firebase/crashlytics',  // dSYM 자동 업로드 등 네이티브 설정
  // ...
],
android: {
  googleServicesFile: './google-services.json',
},
ios: {
  googleServicesFile: './GoogleService-Info.plist',
},
```

`@react-native-firebase/app` 플러그인이 plugins에 없으면 `npx expo prebuild`가 Firebase 네이티브 SDK를 포함하지 않는다. `@react-native-firebase/crashlytics`도 Expo config plugin이 있으므로 함께 등록한다.

설정 후 사용자에게 안내:

1. `npx expo prebuild --clean` — 네이티브 프로젝트 재생성
2. `npx expo run:android` (또는 `run:ios`) — **dev client 새로 빌드**

`google-services.json` / `GoogleService-Info.plist` 누락 시 사용자에게 Firebase Console에서 다운로드하도록 안내한다.

### 2. 에러 도메인 상수 및 타입 정의

CRASHLYTICS_PLAN.md의 에러 분류 섹션에서 추출하여 상수 파일을 생성한다:

**상수/타입 파일** (e.g., `src/constants/crashlyticsKeys.ts`)

- 에러 도메인 상수 (e.g., `NETWORK_ERROR`, `DATABASE_ERROR`, `GAME_ENGINE_ERROR`, `AUTH_ERROR`)
- 심각도 레벨 (e.g., `critical`, `warning`, `info`)
- 커스텀 속성 키 TypeScript interface
- 모든 키는 이 파일에서만 정의 — 하드코딩 금지

### 3. Crashlytics 유틸리티 모듈

CRASHLYTICS_PLAN.md의 모듈 구조 섹션에 명시된 파일 경로에 생성한다:

**핵심 서비스 파일** (e.g., `src/utils/crashlytics.ts`)

- `initCrashlytics()`: 환경 체크 (`__DEV__`) + 동의 상태 확인 + `setCrashlyticsCollectionEnabled()` 호출
- `reportError(error, options?)`: `isEnabled` 가드 + 에러 도메인 분류 + 커스텀 속성 첨부 + `recordError()` 호출
- `logBreadcrumb(message)`: `isEnabled` 가드 + `log()` 호출
- `setUserContext(userId)`: `setUserId()` + 관련 사용자 속성 설정
- `clearUserContext()`: 로그아웃 시 userId 및 사용자 속성 초기화
- `updateCrashlyticsConsent(consent)`: 동의 토글 + `setCrashlyticsCollectionEnabled()` + 저장소 영속화
- `testCrash()`: `crashlytics().crash()` (DEV/테스트 전용, 가드 필수)
- `__DEV__` 모드: 콘솔 로그를 **추가**하되 Firebase SDK도 **반드시 호출**

**에러 처리 — 조용한 실패 방지:**

- `initCrashlytics()` 실패 시 `console.error`로 명확히 표시 + "dev client 재빌드" 안내 포함
- `isEnabled` 가드에서 `return`할 때 DEV 모드에서 경고 출력:
  ```typescript
  if (!isEnabled) {
    if (__DEV__)
      console.warn(`[Crashlytics] 무시됨 (초기화 실패): ${error.message}`);
    return;
  }
  ```

### 4. 글로벌 에러 핸들러

**글로벌 에러 핸들러 파일** (e.g., `src/utils/errorHandler.ts`)

- `ErrorUtils.setGlobalHandler()` 래핑
- **체이닝 필수**: 이전 핸들러를 저장하고, Crashlytics 리포팅 후 이전 핸들러를 호출
  ```typescript
  const previousHandler = ErrorUtils.getGlobalHandler();
  ErrorUtils.setGlobalHandler((error, isFatal) => {
    // Crashlytics 리포팅
    reportError(error, { severity: isFatal ? 'critical' : 'warning' });
    logBreadcrumb(`Global error: ${error.message} (fatal: ${isFatal})`);
    // 기존 핸들러 체이닝
    if (previousHandler) {
      previousHandler(error, isFatal);
    }
  });
  ```
- 미처리 Promise rejection 캡처:
  ```typescript
  // Promise rejection 전역 캡처 등록
  ```
- 개발 모드에서 `console.error` 추가 호출

### 5. Error Boundary 컴포넌트

**Error Boundary 파일** (e.g., `src/components/CrashBoundary.tsx`)

- **React Class Component 필수** (componentDidCatch는 클래스 컴포넌트에서만 지원)
- `getDerivedStateFromError()`: 에러 상태 설정 → 폴백 UI 렌더링
- `componentDidCatch(error, errorInfo)`:
  - `crashlytics().recordError(error)` 호출
  - `crashlytics().log(errorInfo.componentStack)` 호출
  - `crashlytics().setAttribute('error_boundary_name', this.props.name)` 호출
- 폴백 UI: 에러 메시지, "다시 시도" 버튼, "에러 리포트 전송됨" 안내
- `onReset` 콜백 지원
- `name` prop으로 Error Boundary 식별 (디버깅용)

**기존 Error Boundary가 있는 경우:**

- 기존 컴포넌트를 유지하고, `componentDidCatch`에 Crashlytics 호출만 추가
- 새 Error Boundary를 만들어 같은 트리를 감싸지 않음

**중복 리포팅 방지:**

- Error Boundary가 잡은 에러는 하위 try-catch에서 이미 recordError했을 수 있음
- 에러 객체에 `_crashlyticsReported` 플래그를 부착하여 중복 방지:
  ```typescript
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    if (!(error as any)._crashlyticsReported) {
      crashlytics().recordError(error);
      (error as any)._crashlyticsReported = true;
    }
    crashlytics().log(`ErrorBoundary [${this.props.name}]: ${errorInfo.componentStack}`);
  }
  ```

### 6. 루트 레이아웃 통합 (SDK 초기화 + 배치)

`app/_layout.tsx` 수정:

- `useEffect(() => { initCrashlytics(); setupGlobalErrorHandler(); }, [])` 추가
- `CrashBoundary`로 루트 콘텐츠 래핑
- 화면 전환 시 `screen_name` 속성 업데이트 (usePathname 활용, plan에 있으면)
- 기존 hooks (fonts, splash screen 등) 뒤에 배치
- **변경 최소화** — crashlytics 초기화 라인과 Error Boundary 래핑만 추가

### 7. 수동 에러 리포팅 (recordError)

CRASHLYTICS_PLAN.md의 recordError 삽입 테이블을 행 단위로 처리:

**각 삽입 위치에 대해:**

1. "파일 경로" 컬럼의 파일을 열기
2. "삽입 위치" 컬럼의 함수/catch 블록 찾기
3. `reportError(error, { domain, severity, ...customAttributes })` 호출 추가
4. 커스텀 속성 첨부 (에러 도메인, API 엔드포인트, HTTP 상태코드 등)

**에러 유형별 처리:**

- API 호출 에러: API 클라이언트/인터셉터의 catch 블록에 삽입
- 비즈니스 로직 에러: 게임 엔진, 퍼즐 생성/검증 등의 catch 블록에 삽입
- 네트워크 에러: 오프라인/타임아웃 캡처
- 비치명적 에러: 데이터 파싱 실패, 캐시 미스, 폴백 로직 실행

**중복 확인:**

- 삽입 전 `grep -rn "recordError\|reportError" <target_file>` 실행
- 이미 리포팅 코드가 있으면 스킵
- Error Boundary 범위 안의 try-catch에서 recordError할 경우 `_crashlyticsReported` 플래그 설정

### 8. 커스텀 로그 (Breadcrumb)

CRASHLYTICS_PLAN.md의 로그 포인트 테이블 처리:

- **사용자 행동**: 버튼 탭, 폼 제출, 게임 액션 — `logBreadcrumb()` 삽입
- **앱 상태 변경**: 포그라운드/백그라운드 전환 (AppState 리스너), 네트워크 상태 변경
- **화면 전환**: 주요 화면 진입 시 로그 (스크린 트래킹 훅이 별도로 있으면 중복 방지)
- **비즈니스 흐름 마일스톤**: 게임 시작, 퍼즐 로드, 결과 저장 등

메시지 형식: 구조화된 짧은 문자열 (e.g., `"user_action:start_game level=3 difficulty=hard"`)

### 9. 커스텀 속성

CRASHLYTICS_PLAN.md의 속성 테이블 처리:

- `setAttribute()` / `setAttributes()` 호출을 지정된 위치에 삽입
- 주요 속성: `screen_name`, `user_role`, `game_difficulty`, `puzzle_id`, `app_version`
- **화면 전환 시 `screen_name` 자동 업데이트**: usePathname + setAttribute 연동
- 모든 키는 `crashlyticsKeys.ts`에서 import — 하드코딩 금지

### 10. 사용자 식별

CRASHLYTICS_PLAN.md의 사용자 식별 섹션 처리:

- 로그인 성공 시 `setUserId(userId)` 호출
- 로그아웃 시 `setUserId('')` 호출 + 사용자 관련 속성 초기화
- 익명/게스트 사용자: plan 명세에 따라 처리 (e.g., `guest_<random>` 또는 빈 문자열)
- 인증 흐름이 없는 프로젝트: 이 단계 스킵, 리포트에 기록

### 11. 동의 관리

CRASHLYTICS_PLAN.md의 동의 관리 섹션 처리:

- `setCrashlyticsCollectionEnabled(consent)` 호출
- 프로젝트의 기존 저장소 패턴 사용 (MMKV, AsyncStorage, expo-secure-store 등)
- Settings 화면에 토글 UI 추가 (plan에 있으면)
- 기본값: plan에 명시된 대로 (보통 opt-out = 기본 활성화)

### 12. 네이티브 크래시 빌드 설정 (plan에 있으면)

- `@react-native-firebase/crashlytics`의 Expo config plugin이 dSYM 업로드를 자동 처리
- `eas.json`에 소스맵 업로드 설정 확인 (plan 명세에 따라)
- 수동 설정이 필요한 항목은 리포트에 "다음 단계"로 기록

---

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

**동일 파일 5회 이상 편집 감지 시:**

1. 즉시 중단
2. 근본 원인 재분석
3. 완전히 다른 접근 방식 시도
4. 2번의 접근 전환 후에도 실패 → 사용자 에스컬레이션

**Generator-Evaluator 루프 3회 반복 감지 시:**

1. 해당 task를 `"blocked"`로 표시
2. 차단 사유를 `CRASHLYTICS_PROGRESS.txt`에 기록
3. 다음 task로 이동

## 코딩 컨벤션 체크리스트

구현 시 반드시 확인:

- [ ] TypeScript 사용, Props/State interface 정의
- [ ] `@/` 절대 경로 import (상대 경로 금지, `@/*` → `./src/*`)
- [ ] arrow function 컴포넌트 (Error Boundary는 class 컴포넌트 예외)
- [ ] 한글 주석
- [ ] 파일 명명: 컴포넌트 `PascalCase.tsx`, 유틸리티 `camelCase.ts`, 상수 `SCREAMING_SNAKE_CASE.ts`
- [ ] `StyleSheet.create()` 사용
- [ ] 기존 코드의 import 순서 패턴 준수
- [ ] 중복 에러 리포팅 없음 (삽입 전 `grep` 확인)
- [ ] 기존 코드 로직 변경 없음 (crashlytics 코드만 추가)
- [ ] 에러 핸들러 체이닝 (기존 핸들러 덮어쓰지 않음)

## 증분 구현

이미 crashlytics/에러 핸들링 코드가 존재하는 프로젝트에서:

- 기존 코드를 덮어쓰지 않음
- 기존 Error Boundary에 Crashlytics 연동만 추가 (구조 유지)
- 기존 글로벌 에러 핸들러에 체이닝 방식으로 추가
- 기존 Sentry 등 에러 트래커와 공존 (제거하지 않음)
- 기존 구현이 acceptance_criteria를 충족하면 Evaluator에게 검증 요청
- 누락된 항목만 추가 구현
- 기존 코드와의 일관성 유지 (같은 import 패턴, 같은 유틸리티 함수 사용)
