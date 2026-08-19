---
name: firebase-analytics-plan
description: Plans Firebase Analytics (@react-native-firebase/analytics) integration for React Native Expo projects — decides where to initialize, which GA4 events to log, and exactly where to insert tracking code. Uses a virtual expert agent team (GA4 Strategist, Expo/RN Architect, Privacy Advisor, Growth Analyst) that cross-reviews recommendations before producing a structured plan saved to docs/plan/GA_PLAN.md. Use this skill whenever the user mentions Firebase Analytics, GA4 event design, screen_view tracking, event tracking plans, analytics instrumentation for Expo/RN, @react-native-firebase/analytics, analytics best practices, or wants to update an existing GA_PLAN.md. Also triggers on Korean phrases like "이벤트 트래킹 계획", "Firebase Analytics 어디에 넣을지", "GA4 이벤트 설계", "GA 계획 업데이트", "분석 삽입 위치".
---

# Firebase GA Plan

You are creating a comprehensive Firebase Analytics integration plan for a React Native Expo project. The plan tells the developer **exactly where and what to add** but does not modify source files directly.

Write the plan document in **Korean (한글)**.

**Important: This is a PLAN, not implementation.** Focus on what events to track, where to place them, and why — not on code. Keep code snippets to an absolute minimum (only a brief one-liner example per event if needed). A separate implementation skill will handle the actual coding. The plan should be readable by a product manager, not just an engineer.

## Phase 0: Expert Agent Best Practices

Before analyzing the project, think through four expert perspectives. Each agent contributes domain-specific recommendations. Then resolve conflicts between them.

### The Four Agents

**GA4 Strategist** — Event taxonomy expert

- Prefer GA4 recommended event names (`screen_view`, `select_content`, `search`, `share`, `sign_up`, `tutorial_begin`, `tutorial_complete`, etc.)
- snake_case naming, max 40 chars; custom events get a domain prefix (e.g., `book_register`, `chapter_capture`)
- Use GA4 recommended parameters first (`screen_name`, `screen_class`, `content_type`, `item_id`), add custom params sparingly (max 25/event)
- Design conversion funnels: identify the 3-5 key conversion events

**Expo/RN Architect** — Technical placement expert

- Root `_layout.tsx` is the initialization point; wrap analytics setup in a provider or `useEffect`
- `usePathname()` + `useSegments()` from `expo-router` enable automatic screen tracking
- All `analytics()` calls go in `useEffect`, never in render path
- Create a thin analytics utility module (e.g., `src/analytics/`) with typed helper functions
- `@react-native-firebase/*` requires `expo-dev-client` (not Expo Go)

**Privacy & Compliance Advisor** — Regulatory compliance expert

- Initialize analytics **disabled** (`setAnalyticsCollectionEnabled(false)`), enable after consent
- GDPR: explicit consent required; provide opt-out
- ATT (iOS 14.5+): `requestTrackingPermission` before IDFA tracking; Firebase works without IDFA but attribution is reduced
- No PII in event parameters (no emails, phone numbers, real names)
- Data minimization: only collect what the plan explicitly justifies

**Growth Analyst** — Product metrics expert

- Map events to AARRR funnel (Acquisition, Activation, Retention, Revenue, Referral)
- Identify the "aha moment" — the action that predicts retention
- Prioritize: "core" events (ship immediately) vs "extended" events (add later)
- User properties for cohort analysis (categorical, never PII)

### Conflict Resolution

These three tensions almost always arise. Resolve them upfront:

| Tension                                                      | Resolution                                                                               |
| ------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| Growth wants many events vs Privacy wants minimal collection | Define "core" (ship first) and "extended" (behind consent gate) event tiers              |
| Growth wants user properties vs Privacy forbids PII          | Use anonymized categorical properties (e.g., `books_count_range: "1-5"`, not user email) |
| Architect wants simple init vs Privacy wants consent gating  | Initialize Firebase early but with collection disabled; flip after consent               |

Produce a brief summary of each agent's **top 3 recommendations** and any conflict resolutions.

## Phase 1: Project Structure Analysis

Read the project to understand the analytics insertion points.

### Step 1.1: Expo Router Structure

Use Glob to find all `app/**/*.tsx` files. Map:

- Root `_layout.tsx` → analytics initialization
- Tab/group layouts → section-level tracking
- Individual screen files → `screen_view` event sources

### Step 1.2: Source Organization

Use Glob/Bash to scan `src/` directories:

- Feature modules (e.g., `src/book/`, `src/camera/`) → domain events live here
- Stores (`src/stores/`) → user actions often flow through stores
- Check for existing `src/analytics/` or similar

### Step 1.3: Existing Firebase Setup

Use Grep to check:

- `package.json` for `@react-native-firebase/app`, `@react-native-firebase/analytics`
- `google-services.json` / `GoogleService-Info.plist` existence
- Any existing `analytics`, `logEvent`, `firebase` imports in source files

If analytics code already exists, identify what's in place and focus the plan on **gaps only**.

Produce a structure summary with route-to-screen mapping table.

## Phase 2: Analytics Insertion Plan

### 2.1 Initialization

Describe the initialization approach (no code — just locations and responsibilities):

- **Analytics utility module** location (recommend `src/analytics/`)
  - What it exports: `logEvent`, `enableAnalytics`, `disableAnalytics`, `setUserProperty`
  - Debug mode behavior: log to console in `__DEV__`
- **Root layout integration** — which file and which lifecycle point (e.g., `useEffect` in `app/_layout.tsx`)
- **Consent gating** — where the consent check happens and how it gates collection

### 2.2 Automatic Screen Tracking

Describe the screen tracking approach (no code):

- **Hook name**: `useAnalyticsScreen` (uses `usePathname()` from `expo-router`)
- **Placement**: root `_layout.tsx`
- **Behavior**: fires `screen_view` on route change with mapped `screen_name`
- **Route-to-name mapping table** (generated from Phase 1 analysis):

Example format:

```
/(tabs)          → library
/(tabs)/search   → search
/book/[id]       → book_detail
```

### 2.3 Event Plan Table

For each event, produce a row with these columns:

| Column          | Description                                                                                    |
| --------------- | ---------------------------------------------------------------------------------------------- |
| 파일 경로       | Source file where tracking code goes                                                           |
| 이벤트 이름     | GA4 event name (snake_case)                                                                    |
| GA4 이벤트 타입 | `recommended` or `custom`                                                                      |
| 삽입 위치       | Function, callback, or hook name where the call is placed                                      |
| 파라미터        | Event parameters with types                                                                    |
| 에이전트 의견   | Brief notes from relevant agents (e.g., "GA4: recommended event", "Growth: activation metric") |

Do NOT include full code snippets in the event table. The implementation skill will handle code generation based on this plan.

Read `references/ga4-events.md` for the GA4 recommended events reference to ensure you use standard event names where applicable.

### 2.4 User Properties

Design user properties table:
| Property 이름 | 타입 | 설정 위치 | 설명 |

Properties should be categorical and privacy-safe. Set them in logical locations (e.g., after onboarding completion, after book registration).

### 2.5 AARRR Funnel Mapping

Map all designed events to the AARRR framework:
| AARRR 단계 | 이벤트 | 전환 지표 |

Ensure every funnel stage has at least one event.

## Phase 3: Document Output

### File Management

1. Check if `docs/plan/GA_PLAN.md` exists
2. **If not**: create `docs/plan/` directory and write the full plan
3. **If yes**: read existing file, update only changed sections, preserve unchanged content
4. Always update the `Last Updated` timestamp
5. Append to `## Changelog`

### Document Template

```markdown
# GA Analytics Plan

> Last Updated: YYYY-MM-DD HH:mm

## 0. 전문가 에이전트 베스트 프랙티스 리포트

### GA4 Strategist

1. ...
2. ...
3. ...

### Expo/RN Architect

1. ...
2. ...
3. ...

### Privacy & Compliance Advisor

1. ...
2. ...
3. ...

### Growth Analyst

1. ...
2. ...
3. ...

### 에이전트 간 조율 결과

- (충돌 해소 내역)

## 1. 프로젝트 구조 요약

### Expo Router 구조

(app/ directory tree)

### 라우트-스크린 매핑

| 라우트 경로 | 스크린 이름 | Layout 계층 |
| ----------- | ----------- | ----------- |

## 2. Firebase Analytics 초기화 계획

### 2.1 필요 패키지

- ...

### 2.2 Analytics 유틸리티 모듈

- 파일 경로: ...
- 모듈 역할: ...
- 공개 API: logEvent, enableAnalytics, disableAnalytics, setUserProperty

### 2.3 자동 Screen Tracking

- 훅 이름: useAnalyticsScreen
- 배치 파일: ...
- 사용 API: usePathname() from expo-router

### 2.4 루트 레이아웃 통합

- 파일: ...
- 삽입 위치: ...
- 동의 게이팅 방식: ...

## 3. Analytics 이벤트 계획

### Core 이벤트 (필수 — 1차 구현)

| 파일 경로 | 이벤트 이름 | GA4 타입 | 삽입 위치 | 파라미터 | 에이전트 의견 |
| --------- | ----------- | -------- | --------- | -------- | ------------- |

### Extended 이벤트 (선택 — 2차 구현, 동의 필요)

| 파일 경로 | 이벤트 이름 | GA4 타입 | 삽입 위치 | 파라미터 | 에이전트 의견 |
| --------- | ----------- | -------- | --------- | -------- | ------------- |

### User Properties

| Property 이름 | 타입 | 설정 위치 | 설명 |
| ------------- | ---- | --------- | ---- |

### AARRR 퍼널 매핑

| 단계 | 이벤트 | 전환 지표 |
| ---- | ------ | --------- |

## 4. Privacy & Compliance 검수 결과

### 4.1 GDPR 준수 사항

### 4.2 CCPA 준수 사항

### 4.3 ATT (App Tracking Transparency)

### 4.4 항목별 검수

| 이벤트/Property | PII 포함 여부 | 동의 필요 | 비고 |
| --------------- | ------------- | --------- | ---- |

## 5. 추가 권장사항

### 디버그 모드 설정

### 동의 관리 UI 패턴

### A/B 테스트 연동

### 단계적 구현 로드맵

| 단계 | 작업 | 우선순위 |
| ---- | ---- | -------- |

## Changelog

- YYYY-MM-DD: ...
```

## Incremental Update Logic

When `GA_PLAN.md` already exists and the user requests changes (e.g., "이벤트 추가해줘", "GA_PLAN 수정해줘"):

1. Read the existing `docs/plan/GA_PLAN.md`
2. Re-run Phase 1 to detect any project structure changes (new screens, new files)
3. Identify the specific change requested
4. Update only the affected sections:
   - New events → add rows to the event tables
   - New screens → update route mapping + add `screen_view` entries
   - Changed file paths → update affected rows
   - New user properties → add to properties table
5. Update the `Last Updated` timestamp
6. Add a changelog entry describing the change
7. Show the user a diff summary of what changed
