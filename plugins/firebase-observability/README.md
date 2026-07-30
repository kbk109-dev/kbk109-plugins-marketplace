# firebase-observability

React Native Expo 프로젝트에 Firebase Analytics(GA4)와 Crashlytics 를 도입하는 스킬 4개.
계획(plan)과 구현(impl)이 짝을 이룬다.

## 설치

```
/plugin install firebase-observability@kbk109-plugins-marketplace
```

## 선행 요건

| 요건 | 쓰는 곳 | 비고 |
|---|---|---|
| context7 MCP | `*-impl` 두 스킬 | `@react-native-firebase/*` 최신 API 확인 |
| Expo 프로젝트 | 전부 | `app.json` / `app.config.js` 존재 |
| Firebase 프로젝트 | 구현 단계 | `google-services.json` / `GoogleService-Info.plist` |

## 스킬

### `firebase-analytics-plan`
어디서 초기화할지, 어떤 GA4 이벤트를 남길지, 트래킹 코드를 정확히 어느 위치에 삽입할지 결정한다.
가상 전문가 팀(GA4 Strategist, Expo/RN Architect, Privacy Advisor, Growth Analyst)이 교차 검토한 뒤
`docs/plan/GA_Plan.md` 에 저장한다.

트리거 — "GA4 이벤트 설계", "이벤트 트래킹 계획", "Firebase Analytics 어디에 넣을지",
"분석 삽입 위치"

### `firebase-analytics-impl`
`GA_PLAN.md` 를 읽고 Harness 구조(Three-Agent + Task State Machine)로 구현한다. 각 구현 항목을
개별 task 로 분해하고 `acceptance_criteria` 기반 독립 검증 루프를 실행한다.

트리거 — "GA_PLAN 기반으로 구현해줘", "screen_view 트래킹 구현해줘", "logEvent 코드 넣어줘",
"나머지 이벤트도 구현해줘"

### `firebase-crashlytics-plan`
초기화 위치, Error Boundary 배치, `recordError`/`log`/`setAttribute` 삽입 지점, 앱 전체의 크래시
리포팅 구조를 설계한다. 가상 전문가 팀(Crashlytics Strategist, Expo/RN Architect,
Privacy & Compliance Advisor, Reliability Engineer)이 교차 검토한 뒤
`docs/plan/CRASHLYTICS_PLAN.md` 에 저장한다.

트리거 — "크래시 리포팅 계획 세워줘", "Error Boundary 어디에 넣어야 해?", "crash-free rate 전략",
"non-fatal 에러 어떻게 기록해?"

### `firebase-crashlytics-impl`
`CRASHLYTICS_PLAN.md` 를 읽고 Harness 구조로 구현한다. Error Boundary, 글로벌 에러 핸들러,
비치명적 에러 리포팅까지 다룬다.

트리거 — "CRASHLYTICS_PLAN 기반으로 구현해줘", "Error Boundary 만들어줘",
"글로벌 에러 핸들러 설정해줘", "recordError 코드 넣어줘"

## 권장 흐름

```
firebase-analytics-plan    →  firebase-analytics-impl
firebase-crashlytics-plan  →  firebase-crashlytics-impl
```

계획 없이 구현 스킬을 부르면 계획 문서를 먼저 요구한다 — 계획을 상태 저장소로 쓰는 구조이기 때문이다.
