---
name: firebase-crashlytics-plan
description: Plans Firebase Crashlytics (@react-native-firebase/crashlytics) integration for React Native Expo projects — decides where to initialize, which Error Boundaries to place, where to insert recordError/log/setAttribute calls, and how to structure crash reporting across the app. Uses a virtual expert agent team (Crashlytics Strategist, Expo/RN Architect, Privacy & Compliance Advisor, Reliability Engineer) that cross-reviews recommendations before producing a structured plan saved to docs/plan/CRASHLYTICS_PLAN.md. Use this skill whenever the user mentions Firebase Crashlytics, crash reporting planning, Error Boundary placement strategy, recordError design, crash monitoring setup, non-fatal error classification, or wants to update an existing CRASHLYTICS_PLAN.md. Also triggers on Korean phrases like "Crashlytics 어디에 넣을지", "크래시 리포팅 계획 세워줘", "Error Boundary 어디에 넣어야 해?", "에러 추적 설정 도와줘", "crash-free rate 전략", "CRASHLYTICS_PLAN 수정해줘", "non-fatal 에러 어떻게 기록해?", "커스텀 키 뭐 넣어야 해?", "앱 안정성 모니터링 설정하고 싶어".
---

# Firebase Crashlytics Plan

You are creating a comprehensive Firebase Crashlytics integration plan for a React Native Expo project. The plan tells the developer **exactly where and what to add** — Error Boundary placement, global error handler setup, recordError insertion points, custom keys/logs, and monitoring strategy — but does not modify source files directly.

Write the plan document in **Korean (한글)**.

**Important: This is a PLAN, not implementation.** Focus on where to place crash reporting, what errors to capture, and why — not on code. Keep code snippets to brief one-liner examples. A separate implementation skill (`firebase-crashlytics-impl`) will handle the actual coding. The plan should be readable by a product manager, not just an engineer.

## Phase 0: Expert Agent Best Practices

Before analyzing the project, think through four expert perspectives. Each agent contributes domain-specific recommendations. Then resolve conflicts between them.

### The Four Agents

**Crashlytics Strategist** — Crash reporting taxonomy expert

- Design a crash/non-fatal classification system: what constitutes a fatal crash vs a non-fatal error vs a warning log
- Custom key/value taxonomy: which keys to set, when, and why (e.g., `screen_name`, `last_action`, `network_status`, `app_state`)
- Breadcrumb (log) strategy: what user actions to log before a crash occurs, to provide context for debugging
- crash-free users target: industry standard is 99.5%+; set a realistic target for the app's maturity
- Alert threshold design: when to trigger notifications for crash spikes (Velocity Alerts)

**Expo/RN Architect** — Technical placement expert

- Root `_layout.tsx` is the initialization point; Crashlytics setup goes in a `useEffect` or provider
- Expo Router layout hierarchy determines Error Boundary placement: root → route group → screen level
- JS vs Native crash separation: `ErrorUtils.setGlobalHandler()` catches JS exceptions; native crashes are caught automatically by the SDK
- `expo-dev-client` is required (not Expo Go) since `@react-native-firebase/crashlytics` is a native module
- Hermes engine source map upload pipeline for symbolicated stack traces
- Error handler chaining: if an existing global handler exists, chain onto it rather than replacing it

**Privacy & Compliance Advisor** — Regulatory compliance expert

- Initialize Crashlytics with collection **disabled** or **enabled** depending on app's consent model; recommend opt-out (enabled by default) for crash data since it contains no PII by default, but flag if the plan adds PII-adjacent custom keys
- GDPR: crash data is generally legitimate interest, but custom keys/user IDs need consent justification
- No PII in custom keys, log messages, or error metadata (no emails, phone numbers, real names, book titles with personal content)
- `setUserId()` requires justification: anonymous device IDs are preferred over auth user IDs
- Data scrubbing rules: define what must be sanitized before passing to `recordError()` or `log()`
- ATT (iOS): Crashlytics does not use IDFA, so ATT is not required — note this explicitly to avoid unnecessary consent dialogs

**Reliability Engineer** — App stability & SRE expert

- crash-free rate target: define per-release and rolling targets (e.g., 99.5% 7-day rolling)
- Crash priority classification: P0 (app-killing, >1% users), P1 (frequent non-fatal, >0.5%), P2 (edge case), P3 (cosmetic)
- Velocity Alert configuration: crash count threshold and percentage increase threshold
- Release regression detection: compare crash-free rate between releases
- ANR (Application Not Responding) detection strategy for Android
- OOM (Out of Memory) patterns to monitor
- Monitoring/alerting channels: Slack integration, email, PagerDuty for P0

### Conflict Resolution

These tensions almost always arise. Resolve them upfront:

| Tension                                                                                       | Resolution                                                                                                                                                                                   |
| --------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Reliability wants detailed custom keys for debugging vs Privacy wants minimal data collection | Define a "safe keys" allowlist (screen_name, app_state, network_status) that carry no PII risk. Keys that could leak PII (user content, search queries) go through scrubbing or are excluded |
| Architect wants a single global error handler vs Strategist wants granular Error Boundaries   | Use both: global handler as a safety net for uncaught exceptions + Error Boundaries at strategic layout levels for graceful recovery and granular error attribution                          |
| Reliability wants setUserId for crash-to-user correlation vs Privacy wants anonymity          | Use anonymous device ID or hashed user ID, never raw auth ID. Clear on logout. Document the justification                                                                                    |

Produce a brief summary of each agent's **top 3 recommendations** and any conflict resolutions.

## Phase 1: Project Structure Analysis

Read the project to understand the crash reporting insertion points.

### Step 1.1: Expo Router Structure

Use Glob to find all `app/**/*.tsx` files. Map:

- Root `_layout.tsx` → Crashlytics initialization + root Error Boundary
- Tab/group layouts → group-level Error Boundaries
- Individual screen files → identify critical screens needing dedicated Error Boundaries (e.g., camera, OCR, AI processing)

### Step 1.2: Source Organization

Use Glob/Bash to scan `src/` directories:

- Feature modules (e.g., `src/camera/`, `src/ocr/`, `src/summary/`) → domain-specific errors originate here
- Stores (`src/stores/`) → business logic errors flow through stores
- Existing monitoring code: check for `src/monitoring/`, Error Boundary components, Sentry integration
- API client / data fetching patterns: identify where network errors are caught

### Step 1.3: Existing Firebase & Error Handling Setup

Use Grep to check:

- `package.json` for `@react-native-firebase/app`, `@react-native-firebase/crashlytics`, `@sentry/react-native`
- `app.json` / `app.config.js` for Firebase plugins configuration
- `eas.json` for build configuration (source map upload related)
- `google-services.json` / `GoogleService-Info.plist` existence
- Existing `ErrorBoundary`, `captureException`, `ErrorUtils`, `crashlytics` imports in source files
- Existing try-catch patterns and Promise rejection handling

If crash reporting code already exists, identify what's in place and focus the plan on **gaps only**.

Produce a structure summary with:

- Layout hierarchy diagram
- Critical screen identification (screens with heavy native module usage, async operations, or user-critical flows)
- Existing error handling inventory

## Phase 2: Crashlytics Insertion Plan

### 2.1 SDK Initialization & Configuration

Describe the initialization approach (minimal code — just locations and responsibilities):

- **Crashlytics utility module** location (recommend `src/monitoring/` or existing module)
  - What it exports: `initCrashlytics`, `reportError`, `logBreadcrumb`, `setUserContext`, `clearUserContext`, `updateCrashlyticsConsent`
  - Debug mode behavior: log to console in `__DEV__`, send to Crashlytics in production
- **Root layout integration** — which file and which lifecycle point
- **Consent gating** — whether to use opt-in or opt-out model, and where the consent check happens
- **app.json plugins** — confirm `@react-native-firebase/crashlytics` plugin registration

### 2.2 Error Boundary Placement

Design a layered Error Boundary strategy:

| Level       | Description                                             | When to use                                                                                |
| ----------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Root        | Wraps entire app in root `_layout.tsx`                  | Catches any unhandled render error; shows "app crashed" fallback                           |
| Route Group | Wraps a route group layout (e.g., `(tabs)/_layout.tsx`) | Isolates feature sections; one section crashing doesn't bring down the app                 |
| Screen      | Wraps individual critical screens                       | For screens with heavy processing (camera, OCR, AI inference) where errors are more likely |

For each Error Boundary placement, specify:

- File path
- What it protects (component scope)
- Fallback UI description (what the user sees)
- Crashlytics integration: `recordError()` in `componentDidCatch`, `log()` for component stack
- Whether it's a new component or integrating into an existing one

### 2.3 Global Error Handlers

Plan the global error capture layer:

| Handler Type                | File Path | Insertion Point                 | What It Catches                       | Notes                                  |
| --------------------------- | --------- | ------------------------------- | ------------------------------------- | -------------------------------------- |
| JS Unhandled Exception      | (specify) | `ErrorUtils.setGlobalHandler()` | Uncaught JS errors outside React tree | Chain with existing handler if present |
| Unhandled Promise Rejection | (specify) | Global rejection tracker        | Forgotten `.catch()` on Promises      | Log breadcrumb + recordError           |

### 2.4 Custom Key/Value Design

Design the custom key taxonomy — which keys to set, when, and where:

| Key Name         | Value Type | Set When            | File Path | Insertion Point    | Agent Notes                    |
| ---------------- | ---------- | ------------------- | --------- | ------------------ | ------------------------------ |
| `screen_name`    | string     | Navigation change   | (specify) | usePathname effect | Auto-updated on route change   |
| `last_action`    | string     | User interaction    | (specify) | Event handlers     | Last significant user action   |
| `app_state`      | string     | App lifecycle       | (specify) | AppState listener  | foreground/background/inactive |
| `network_status` | string     | Connectivity change | (specify) | NetInfo listener   | online/offline/cellular        |
| ...              | ...        | ...                 | ...       | ...                | ...                            |

### 2.5 Breadcrumb (Log) Strategy

Plan which user actions to log as breadcrumbs, providing crash context:

| Log Category  | Log Message Pattern                   | File Path | Insertion Point        | Agent Notes                         |
| ------------- | ------------------------------------- | --------- | ---------------------- | ----------------------------------- |
| Navigation    | `"navigate: {screen_name}"`           | (specify) | usePathname effect     | Automatic on route change           |
| User Action   | `"action: {action_name}"`             | (specify) | Event handlers         | Major button taps, form submissions |
| API Call      | `"api: {method} {endpoint} {status}"` | (specify) | API client/interceptor | Start, success, failure             |
| App Lifecycle | `"lifecycle: {event}"`                | (specify) | AppState listener      | Foreground, background              |
| ...           | ...                                   | ...       | ...                    | ...                                 |

### 2.6 Non-Fatal Error Reporting (recordError)

Plan which errors to record as non-fatal:

| Error Type           | Severity | File Path | Insertion Point         | Custom Attributes             | Agent Notes                             |
| -------------------- | -------- | --------- | ----------------------- | ----------------------------- | --------------------------------------- |
| API 4xx/5xx          | warning  | (specify) | API interceptor/catch   | endpoint, status_code, method | Network errors that don't crash the app |
| Database error       | critical | (specify) | Repository catch blocks | table, operation, error_code  | Data layer failures                     |
| OCR failure          | warning  | (specify) | OCR engine catch        | image_size, language          | ML Kit processing errors                |
| AI inference timeout | warning  | (specify) | Summary engine catch    | model_name, input_length      | SLM processing failures                 |
| ...                  | ...      | ...       | ...                     | ...                           | ...                                     |

Severity levels:

- **critical**: App functionality severely degraded, user cannot complete core task
- **warning**: Non-ideal path taken, fallback logic activated, but user can continue
- **info**: Unexpected but handled gracefully, worth monitoring for trends

### 2.7 User Identification

Plan the `setUserId()` strategy:

- Where to set: auth success handler (if auth exists)
- Where to clear: logout handler
- ID format: anonymous device ID, hashed user ID, or no user ID (Privacy Advisor decides)
- Justification for the chosen approach

### 2.8 Native Crash Configuration

Plan the build pipeline for symbolicated stack traces:

- **iOS dSYM upload**: `app.json` plugin configuration or EAS Build hook
- **Android ProGuard/R8 mapping**: `app.json` plugin configuration
- **Hermes source map upload**: EAS Build integration or CI/CD step
- **eas.json** configuration changes needed (if any)

### 2.9 Monitoring & Alerting

Plan the monitoring strategy:

- **crash-free rate target**: e.g., 99.5% 7-day rolling
- **Velocity Alert**: recommended threshold (e.g., >5 crashes in 1 hour for same issue)
- **Notification channels**: Slack webhook, email, or PagerDuty integration
- **Release comparison**: how to detect regression crashes between versions
- **Dashboard setup**: which Firebase Console Crashlytics views to monitor regularly

## Phase 3: Document Output

### File Management

1. Check if `docs/plan/CRASHLYTICS_PLAN.md` exists
2. **If not**: create `docs/plan/` directory and write the full plan
3. **If yes**: read existing file, update only changed sections, preserve unchanged content
4. Always update the `Last Updated` timestamp
5. Append to `## Changelog`

### Document Template

```markdown
# Crashlytics Plan

> Last Updated: YYYY-MM-DD HH:mm

## 0. 전문가 에이전트 베스트 프랙티스 리포트

### 0-1. Crashlytics Strategist

1. ...
2. ...
3. ...

### 0-2. Expo/RN Architect

1. ...
2. ...
3. ...

### 0-3. Privacy & Compliance Advisor

1. ...
2. ...
3. ...

### 0-4. Reliability Engineer

1. ...
2. ...
3. ...

### 0-5. 에이전트 간 조율 결과

- (충돌 해소 내역)

## 1. 프로젝트 구조 요약

### Expo Router 구조

(app/ directory tree)

### 크리티컬 스크린 식별

| 스크린 | 파일 경로 | 위험 요소 | Error Boundary 필요 |
| ------ | --------- | --------- | ------------------- |

### 기존 에러 핸들링 현황

- (existing Error Boundaries, Sentry, try-catch patterns)

## 2. Firebase Crashlytics 초기화 계획

### 2.1 필요 패키지

- ...

### 2.2 Crashlytics 유틸리티 모듈

- 파일 경로: ...
- 모듈 역할: ...
- 공개 API: initCrashlytics, reportError, logBreadcrumb, ...

### 2.3 루트 레이아웃 통합

- 파일: ...
- 삽입 위치: ...
- 동의 게이팅 방식: ...

### 2.4 app.json 플러그인 설정

- ...

## 3. Error Boundary 배치 계획

| 레벨 | 파일 경로 | 보호 범위 | Fallback UI | Crashlytics 연동 | 에이전트 의견 |
| ---- | --------- | --------- | ----------- | ---------------- | ------------- |

## 4. 글로벌 에러 핸들러 계획

| 핸들러 유형 | 파일 경로 | 삽입 위치 | 캡처 대상 | 에이전트 의견 |
| ----------- | --------- | --------- | --------- | ------------- |

## 5. Custom Key/Value 및 브레드크럼 계획

### 5.1 Custom Keys

| Key 이름 | 값 타입 | 설정 시점 | 파일 경로 | 삽입 위치 | 에이전트 의견 |
| -------- | ------- | --------- | --------- | --------- | ------------- |

### 5.2 브레드크럼 (Log)

| 카테고리 | 메시지 패턴 | 파일 경로 | 삽입 위치 | 에이전트 의견 |
| -------- | ----------- | --------- | --------- | ------------- |

## 6. Non-Fatal Error 리포팅 계획

| 에러 유형 | 심각도 | 파일 경로 | 삽입 위치 | Custom Attributes | 에이전트 의견 |
| --------- | ------ | --------- | --------- | ----------------- | ------------- |

## 7. 사용자 식별 전략

- setUserId 방식: ...
- 설정 위치: ...
- 초기화 위치: ...
- Privacy 검수: ...

## 8. 네이티브 크래시 대응

### 8.1 iOS dSYM 업로드

### 8.2 Android ProGuard/R8 매핑

### 8.3 Hermes 소스맵 업로드

### 8.4 EAS Build 연동

## 9. 모니터링 및 알림 체계

### 9.1 crash-free rate 목표

### 9.2 Velocity Alert 설정

### 9.3 알림 채널 연동

### 9.4 Release 별 회귀 크래시 탐지

## 10. Privacy & Compliance 검수 결과

### 10.1 항목별 PII 유출 위험 평가

| 항목 | PII 위험 | 조치 | 비고 |
| ---- | -------- | ---- | ---- |

### 10.2 GDPR 대응

### 10.3 ATT (App Tracking Transparency)

### 10.4 데이터 스크러빙 규칙

## 11. 추가 권장사항

### 테스트 크래시 유발 방법

### CI/CD 연동

### 단계적 구현 로드맵

| 단계 | 작업 | 우선순위 |
| ---- | ---- | -------- |

## Changelog

- YYYY-MM-DD: ...
```

## Incremental Update Logic

When `CRASHLYTICS_PLAN.md` already exists and the user requests changes (e.g., "Error Boundary 추가해줘", "커스텀 키 변경해줘", "CRASHLYTICS_PLAN 수정해줘"):

1. Read the existing `docs/plan/CRASHLYTICS_PLAN.md`
2. Re-run Phase 1 to detect any project structure changes (new screens, new files, new error handling code)
3. Identify the specific change requested
4. Update only the affected sections:
   - New Error Boundaries → add rows to the boundary table
   - New non-fatal errors → add rows to the recordError table
   - New custom keys → add to custom key table
   - New screens → update critical screen identification
   - Changed file paths → update affected rows
5. Update the `Last Updated` timestamp
6. Add a changelog entry describing the change
7. Show the user a diff summary of what changed
