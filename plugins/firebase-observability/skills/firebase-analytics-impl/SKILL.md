---
name: firebase-analytics-impl
description: "Harness Engineering 기반 Firebase Analytics 구현 스킬. GA_PLAN.md 계획 문서를 읽고 Three-Agent Architecture(Planner-Generator-Evaluator)와 Task State Machine으로 안정적으로 Firebase Analytics를 구현합니다. 각 구현 항목을 개별 task로 분해하고, acceptance_criteria 기반 독립 검증 루프를 실행하여 조기 완료 선언과 미완성 상태를 구조적으로 방지합니다. 반드시 이 스킬을 사용해야 하는 경우: 'firebase-analytics-impl', 'GA_PLAN 기반으로 구현해줘', 'Firebase Analytics 코드 넣어줘', 'analytics 이벤트 코드 구현해줘', 'GA_PLAN.md 보고 구현해줘', '스크린 트래킹 코드 추가해줘', '커스텀 이벤트 로깅 코드 넣어줘', 'analytics 구현 시작해줘', 'GA 이벤트 코드 작성해줘', 'analytics 구현 이어서 해줘', '나머지 이벤트도 구현해줘', 'logEvent 코드 넣어줘', 'screen_view 트래킹 구현해줘', 'GA_PLAN 기반으로 analytics 구현해줘', '@react-native-firebase/analytics 구현', 'Firebase Analytics 구현해줘', 'analytics 적용해줘', '하네스로 analytics 구현'. Firebase Analytics/GA 구현/적용 관련 키워드가 포함된 모든 한국어/영어 요청에 트리거."
compatibility: 'mcp: context7'
---

# Firebase Analytics Implementation — Harness Engineering

GA_PLAN.md 계획 문서를 기반으로 Firebase Analytics를 구현한다. 더 똑똑한 모델이 아니라, 모델을 둘러싼 **더 똑똑한 환경(Harness)** 이 성공을 결정한다.

모든 사용자 대화는 **한국어**로, 코드 주석은 **한글**로 작성한다 (CLAUDE.md 규칙).

## LLM 구조적 실패 모드와 대응

이 스킬이 해결하는 4가지 구조적 실패 패턴:

| 실패 모드               | 대응                                                                |
| ----------------------- | ------------------------------------------------------------------- |
| 세션 간 상태 유실       | `ga-progress.txt` + `ga-feature-list.json`으로 상태 복원            |
| 전체를 한번에 구현 시도 | Task State Machine — 한 번에 하나의 task만 작업                     |
| 코드 작성 = 완료 선언   | Evaluator가 acceptance_criteria 기반 독립 검증                      |
| 같은 접근 반복 루프     | Loop Detection — 동일 파일 3회 편집 또는 검증 루프 3회 반복 시 개입 |

---

## Hard Gate

**가장 먼저** `docs/plan/GA_PLAN.md` 파일 존재 여부를 확인한다.

파일이 없으면:

> "GA_PLAN.md 파일이 존재하지 않습니다. 먼저 firebase-analytics-plan 스킬로 계획 문서를 작성해주세요."

**즉시 종료.** 이후 어떤 구현도 진행하지 않는다.

또한 확인:

- `package.json`에서 `@react-native-firebase/analytics` 설치 여부 → 미설치 시 안내
- `app.config.js` (또는 `app.json`) plugins 배열에 `@react-native-firebase/app` 존재 여부 → 미등록 시 **반드시 추가** (이 플러그인 없이 prebuild하면 Firebase 네이티브 SDK가 포함되지 않아 런타임에 조용히 실패함)
- `app.config.js`의 `android.googleServicesFile` / `ios.googleServicesFile` 경로 설정 여부 확인
- `docs/harness/firebase/analytics/ga-feature-list.json` 존재 여부 → 있으면 **이어하기 모드** 진입
- `docs/harness/firebase/analytics/` 디렉토리 존재 여부 → 없으면 자동 생성

---

## Harness 디렉토리 구조

```
docs/
├── plan/
│   └── GA_PLAN.md                          ← 계획 원본 (읽기 전용 참조)
└── harness/
    └── firebase/
        └── analytics/
            ├── ga-feature-list.json        ← Task State Machine
            ├── ga-progress.txt             ← 세션 간 인수인계 로그
            └── GA_IMPL_REPORT.md           ← 구현 완료 리포트 (최종 산출물)
```

- 계획 원본(`GA_PLAN.md`)은 `docs/plan/`에 유지 — harness 폴더로 복사하지 않는다
- harness 산출물은 모두 `docs/harness/firebase/analytics/`에 위치한다
- `docs/harness/firebase/analytics/` 디렉토리가 없으면 Planner가 자동 생성한다

---

## Phase 1: PLANNER (계획 분석)

코드를 한 줄도 작성하지 않는다. 환경을 읽고 구현 가능한 상태로 준비한다.

### 1.1 Readable Environment 구축

다음 파일을 순서대로 읽는다:

1. `docs/plan/GA_PLAN.md` — 전체 정독. 구현 범위, 이벤트 목록, 스크린 매핑, 사용자 속성, 동의 관리 추출
2. `CLAUDE.md` — 기술 스택, 코딩 규칙, 디렉토리 구조
3. `package.json` — 설치된 의존성, 스크립트
4. `app.json` 또는 `app.config.js` — Expo 설정, 기존 플러그인
5. `app/` 디렉토리 구조 — layout 파일, 스크린 목록 파악
6. 기존 analytics 코드 스캔 — `grep -rn "analytics\|logEvent\|logScreenView" src/ app/`
7. `docs/harness/firebase/analytics/ga-feature-list.json` — 이전 세션 task 상태 (있으면 재개, 없으면 신규 생성)

**Progressive Disclosure (점진적 정보 공개):**

- Planner는 GA_PLAN.md 전체를 읽는다
- Generator는 현재 태스크에 필요한 섹션만 참조한다
- Evaluator는 acceptance_criteria와 대상 파일만 참조한다

### 1.2 Context7 API 검증

훈련 데이터에 절대 의존하지 않는다. Context7 MCP로 최신 API를 조회한다.

1. `mcp__context7__resolve-library-id` 또는 `mcp__plugin_context7_context7__resolve-library-id`로 다음 라이브러리 ID를 조회:
   - `@react-native-firebase/analytics`
   - `@react-native-firebase/app`
   - `expo-router`

2. 다음 쿼리를 **병렬로** 실행:
   - `"logEvent custom event with parameters example"` — 커스텀 이벤트 API
   - `"logScreenView screen_name screen_class"` — 스크린 트래킹 API
   - `"setUserProperty setAnalyticsCollectionEnabled consent"` — 사용자 속성 및 동의 제어
   - `"initialize Firebase app React Native setup"` — Firebase 초기화
   - `"usePathname hook route change detection"` — Expo Router 라우트 변경 감지

Context7와 GA_PLAN.md가 API 세부사항에서 충돌하면 **Context7이 우선**한다. 차이점을 기록한다.

Context7 호출 실패 시: GA_PLAN.md 기준으로 진행하되, 최종 보고서에 "API 검증 미완료" 경고를 기록한다.

### 1.3 Task State Machine 생성

`ga-feature-list.json`이 이미 존재하면 기존 상태를 로드한다 (세션 재개). 없으면 새로 생성한다.

GA_PLAN.md의 모든 구현 항목을 개별 task로 분해하여 `docs/harness/firebase/analytics/ga-feature-list.json`을 생성한다.

**핵심 규칙:**

- 모든 task의 status 기본값은 **`"fail"`** ("아직 통과하지 못함"이라는 부정적 상태)
- 각 task에 기계 판독 가능한 `acceptance_criteria` 포함
- 스프린트 단위로 태스크 그룹핑, 태스크 간 의존성(`depends_on`) 설정
- 각 태스크에 `context7_apis`와 `plan_reference` 필드 포함

스키마: `references/task_schema.json` 참조

**task 분해 기준** (GA_PLAN.md에서 추출):

1. Analytics 유틸리티 파일 생성 (이벤트 상수, 래퍼 함수, 타입 정의)
2. SDK 초기화 코드 삽입 (app/\_layout.tsx)
3. 스크린 트래킹 훅 및 매핑 테이블
4. Core 이벤트 — 각 이벤트별 또는 카테고리별 task
5. Extended 이벤트 (plan에 있으면)
6. 사용자 속성 설정
7. 동의 관리 (consent management)
8. 기존 analytics 코드 정리/마이그레이션 (있으면)

**스프린트 구성 예시:**

- Sprint 1: SDK 초기화 및 유틸리티 셋업
- Sprint 2: 스크린 트래킹
- Sprint 3: 커스텀 이벤트
- Sprint 4: 사용자 속성 및 퍼널 이벤트

**Architecture Enforcement — 참조할 패턴 파일 지정:**
Planner는 코드 생성 시 참조할 "좋은 패턴" 파일 목록을 지정한다. Generator는 이 목록의 파일만 스타일 참조로 사용한다. 이는 나쁜 패턴 복제를 방지한다.

### 1.4 Progress 파일 초기화

`docs/harness/firebase/analytics/ga-progress.txt`를 생성(또는 업데이트)한다:

```
# Firebase Analytics Implementation Progress
> Started: YYYY-MM-DD HH:mm
> Plan Source: docs/plan/GA_PLAN.md
> Harness Dir: docs/harness/firebase/analytics/
> Context7 Checked: Yes (YYYY-MM-DD)

## Session 1
- Planner: ga-feature-list.json 생성 (N개 태스크, M개 스프린트)
- Context7 차이점: [차이 있으면 기록, 없으면 "없음"]
- 다음 작업: Sprint 1 시작
```

이 파일은 다음 세션이 **30초 이내에** 프로젝트 상태를 재구성할 수 있어야 한다.

---

## Phase 2: TASK LOOP (Generator + Evaluator)

한 번에 하나의 task만 작업한다. 스프린트 내에서 우선순위가 가장 높은 `status: "fail"` task부터 처리한다.

### Generator (구현)

**매 task 시작 전 — 오리엔테이션:**

1. `ga-feature-list.json` + `ga-progress.txt` 확인 → 현재 상태 파악
2. 현재 스프린트의 최우선 `"fail"` task 선택
3. 해당 task의 `depends_on` 확인 → 의존 task가 모두 `"pass"`인지 확인
4. 해당 task의 `context7_apis`에 대해 Context7 조회 (최신성 확보)
5. 해당 task 관련 기존 코드 확인 (기존 코드 덮어쓰지 않음)

**구현 규칙:**

- Context7 검증 API 기반 구현
- GA_PLAN.md가 명세서 (이벤트명, 파라미터, 삽입 위치)
- Context7이 API 레퍼런스 (함수 시그니처, 최신 패턴)
- 프로젝트 코드가 스타일 가이드 (네이밍, 포매팅, 구조)
- TypeScript 필수, `@/` 절대 경로 임포트
- GA_PLAN.md에 없는 항목은 임의로 추가하지 않음
- 기존 파일 수정 시 analytics 관련 코드만 추가 (기존 로직 변경 금지)

**Architecture Enforcement:**

- Planner가 지정한 "참조할 패턴 파일 목록"의 스타일을 따름
- analytics 유틸리티 코드는 GA_PLAN.md에 명시된 디렉토리에 생성
- import 순서, 코드 스타일은 프로젝트 기존 패턴을 따름
- 새 파일 생성 시 프로젝트의 기존 파일 구조를 따름

**구현 상세 가이드:** `references/generator_guide.md` 참조

**Loop Detection:**

- 동일 파일을 **3회 이상** 편집할 경우: "이 파일을 N회 편집했습니다. 완전히 다른 접근 방식을 고려하거나, 이 태스크를 'blocked'로 표시하고 다음으로 넘어가세요."
- Generator-Evaluator 루프가 **3회** 반복될 경우: 해당 task를 `"blocked"`로 표시하고 다음 task로 이동

### Evaluator (검증)

Generator가 구현을 마치면, 역할을 전환하여 **독립적이고 회의적으로** 검증한다. Generator의 자체 평가를 신뢰하지 않는다.

**검증 체크리스트 — 모든 항목 통과해야 pass:**

1. **코드 존재 확인**: `grep -rn`으로 대상 파일에 해당 코드가 실제로 삽입되었는지 확인
2. **Acceptance Criteria 전수 검사**: `ga-feature-list.json`의 해당 task의 모든 criteria를 파일 내용을 직접 확인하여 검증
3. **import 정확성**: 모든 import 문이 실제 존재하는 모듈을 참조하는지 확인
4. **Context7 API 일치**: 사용된 API가 Context7 최신 문서와 일치하는지 확인
5. **중복 이벤트 없음**: 같은 이벤트가 두 번 로깅되지 않는지 `grep`으로 확인
6. **회귀 없음**: 기존 코드에 대한 부작용 없음 확인

**Reasoning Sandwich 적용:**

- Planner 단계: 추론 최대 (전체 GA_PLAN.md 분석, 태스크 분해)
- Generator 단계: 추론 중간 (코드 작성에 집중)
- Evaluator 단계: 추론 최대 (각 criteria 꼼꼼히 검증, 엣지 케이스 확인)

**검증 결과 처리:**

- **통과**: `ga-feature-list.json`에서 해당 task status를 `"pass"`로 변경
- **실패**: 구체적이고 실행 가능한 피드백 기록 후 Generator 재시도
- **3회 루프 반복 후 실패**: `"blocked"` 표시, 차단 사유를 `ga-progress.txt`에 기록, 사용자에게 에스컬레이션

**상세 검증 가이드:** `references/evaluator_guide.md` 참조

### Task 완료 처리

Evaluator 검증 통과 후에만:

1. `ga-feature-list.json`에서 status → `"pass"`
2. `ga-progress.txt` 업데이트 (pass/fail 카운트, 로그)
3. `ga-feature-list.json`의 summary 갱신
4. `git push`는 **절대 자동 실행하지 않음**

다음 `"fail"` task로 반복한다.

### 스프린트 완료

스프린트 내 모든 태스크가 `pass` 또는 `blocked`이면:

- `ga-feature-list.json`의 summary 업데이트
- `ga-progress.txt`에 스프린트 결과 기록
- 다음 스프린트로 이동

**컨텍스트 소진 방지:**

- 컨텍스트 창의 약 70%를 소모하면 현재 스프린트를 완료하고 중간 저장
- `ga-feature-list.json` + `ga-progress.txt` 업데이트 + 사용자에게 진행 상황 보고
- 다음 세션에서 이어서 작업할 수 있도록 모든 상태를 외부화

---

## Phase 3: 최종 검증 및 리포트

모든 스프린트 완료 후:

### 3.1 전체 검증 (Evaluator)

- `ga-feature-list.json`의 전체 태스크에 대해 최종 확인
- 파일 간 일관성 확인 (import, 타입, 이벤트명 상수 등)
- 중복 이벤트 로깅 전체 스캔: `grep -rn "logEvent\|logScreenView" src/ app/`

### 3.2 구현 리포트 생성

`docs/harness/firebase/analytics/GA_IMPL_REPORT.md`를 생성한다:

```markdown
# Firebase Analytics 구현 리포트

> Implemented: YYYY-MM-DD HH:mm
> Based on: GA_PLAN.md (Last Updated: <plan의 타임스탬프>)
> Harness Dir: docs/harness/firebase/analytics/
> Harness: Three-Agent Architecture (Planner → Generator → Evaluator)

## 구현 요약

| 항목                          | 수치             |
| ----------------------------- | ---------------- |
| 총 태스크                     | N개              |
| 통과(pass)                    | N개              |
| 차단(blocked)                 | N개              |
| 생성된 파일                   | N개              |
| 수정된 파일                   | N개              |
| 구현된 이벤트                 | N개 / 계획된 N개 |
| Generator-Evaluator 루프 횟수 | N회              |

## Context7 문서 기준 변경사항

| 항목 | GA_PLAN.md 기준 | Context7 최신 문서 기준 | 적용된 버전 |
| ---- | --------------- | ----------------------- | ----------- |

## 스프린트별 결과

### Sprint 1: SDK 초기화

| Task ID | 제목 | Status | 검증 횟수 |
| ------- | ---- | ------ | --------- |

### Sprint 2: 스크린 트래킹

...

## 생성된 파일 목록

| 파일 경로 | 설명 |
| --------- | ---- |

## 수정된 파일 목록

| 파일 경로 | 변경 내용 |
| --------- | --------- |

## Blocked 태스크 (미완료)

| Task ID | 제목 | 차단 사유 | 권장 조치 |
| ------- | ---- | --------- | --------- |

## 다음 단계

- DebugView로 이벤트 전송 확인
- Firebase Console에서 이벤트 수신 확인
- Blocked 태스크 수동 검토 및 해결
```

### 3.3 최종 상태 확정

- `ga-feature-list.json`의 summary 섹션 최종 갱신
- 모든 상태를 확정

---

## 세션 연속성 (이어하기 모드)

기존 `docs/harness/firebase/analytics/ga-feature-list.json`이 있는 상태에서 스킬이 재실행되면:

**오리엔테이션 순서:**

1. `ga-feature-list.json` 확인 — 전체 태스크 현황 파악
2. `ga-progress.txt` 확인 — 마지막 세션 내용 파악
3. GA_PLAN.md 변경 여부 확인 (`plan_last_updated` 비교)
4. **Planner를 재실행하지 않고** 남은 `fail` 태스크부터 Generator-Evaluator 루프를 이어서 실행
5. GA_PLAN.md가 업데이트된 경우에만 Planner를 재실행하여 새 태스크를 추가

**GA_PLAN.md 업데이트 감지 시:**

- 이전 `ga-feature-list.json`과 현재 GA_PLAN.md를 비교
- 새로 추가된 항목 → 새 태스크 추가 (status: `"fail"`)
- 삭제된 항목 → 사용자에게 확인 후 태스크 제거
- 변경된 항목 → 해당 태스크의 status를 `"fail"`로 리셋

---

## 증분 구현 지원

**이미 일부 구현이 되어 있는 프로젝트:**

- Planner가 기존 analytics 코드를 감지 (`grep -rn "logEvent\|logScreenView\|analytics" src/ app/`)
- 이미 구현된 항목은 Evaluator가 검증 후 `status: "pass"` 또는 `"existing"`으로 표시
- 누락된 항목만 Generator가 추가 구현

---

## 기계적 제약 (절대 규칙)

이 규칙들은 어떤 상황에서도 재정의할 수 없다:

1. **"한 번에 하나의 task"** — Generator는 절대 여러 task를 동시에 작업하지 않는다
2. **"criteria 삭제 금지"** — acceptance_criteria를 수정하거나 삭제하지 않는다
3. **"검증 없이 pass 금지"** — Evaluator 검증 통과 후에만 status를 "pass"로 변경한다
4. **"스텁 금지"** — TODO, placeholder, mock 구현으로 task를 통과시키지 않는다
5. **"진행 기록 필수"** — 매 task 완료 시 ga-progress.txt 업데이트를 누락하지 않는다
6. **"JSON 형식 유지"** — ga-feature-list.json은 항상 유효한 JSON 형식을 유지한다
7. **"루프 상한"** — Generator-Evaluator 루프 3회 반복 후 "blocked" 처리 및 사용자 에스컬레이션
8. **"git push 금지"** — 자동으로 git push를 실행하지 않는다

에이전트는 컨텍스트가 쌓이면 "거의 됐으니 넘어가자"는 유혹에 빠지기 쉽다. 기계적 제약은 이 경향을 구조적으로 차단한다.

---

## Expo 네이티브 통합 주의사항

`@react-native-firebase/analytics`는 네이티브 모듈이므로 JS 코드 작성만으로는 동작하지 않는다. 다음을 반드시 확인/수행해야 한다:

### app.config.js 필수 설정

```js
plugins: [
  '@react-native-firebase/app',  // 반드시 plugins에 등록
  // ... 다른 플러그인들
],
android: {
  googleServicesFile: './google-services.json',  // 경로 명시
},
ios: {
  googleServicesFile: './GoogleService-Info.plist',  // 경로 명시
},
```

`@react-native-firebase/app` 플러그인이 plugins에 없으면 `npx expo prebuild`가 Firebase 네이티브 SDK를 포함하지 않는다. 코드는 에러 없이 실행되지만 **이벤트가 조용히 버려지는** 가장 흔한 원인이다.

`@react-native-firebase/analytics`는 Expo config plugin이 없으므로 plugins에 추가하지 않는다 — `@react-native-firebase/app` 하나만 등록하면 된다.

### Dev Client 재빌드

네이티브 패키지(`@react-native-firebase/analytics`) 추가 후에는 반드시:

1. `npx expo prebuild --clean` — 네이티브 프로젝트 재생성
2. `npx expo run:android` 또는 `npx expo run:ios` — **dev client 새로 빌드 및 설치**

`prebuild`만으로는 부족하다. 기기에 설치된 앱을 실제로 다시 빌드해야 새 네이티브 모듈이 포함된다.

### Analytics 서비스 모듈 — `__DEV__` 모드 규칙

DEV 모드에서도 Firebase SDK를 **실제로 호출**해야 한다. console.log는 디버깅 보조로만 사용하고, `return`으로 SDK 호출을 건너뛰지 않는다. DEV에서 SDK를 호출하지 않으면 DebugView 테스트가 불가능하다.

```typescript
// 올바른 패턴
if (__DEV__) {
  console.log(`[Analytics] logEvent: ${name}`, params);
}
// return 없이 아래 SDK 호출로 진행
await analytics().logEvent(name, params);

// 잘못된 패턴 — DebugView 테스트 불가
if (__DEV__) {
  console.log(`[Analytics] logEvent: ${name}`, params);
  return; // ❌ Firebase SDK 호출을 건너뜀
}
```

### 초기화 에러 처리 — 조용한 실패 방지

`initAnalytics()`가 실패하면 `collectionEnabled`가 `false`로 유지되고, 이후 모든 `logEvent()` 호출이 조용히 무시된다. 이 "조용한 캐스케이드 실패"를 방지하기 위해:

1. `initAnalytics()` catch 블록에서 `console.error`를 사용하고, "dev client 재빌드" 안내를 포함한다
2. `collectionEnabled` 가드에서 `return`할 때 DEV 모드에서 경고를 출력한다:
   ```typescript
   if (!collectionEnabled) {
     if (__DEV__)
       console.warn(`[Analytics] 이벤트 무시됨 (초기화 실패): ${name}`);
     return;
   }
   ```

### DebugView 테스트 안내

구현 리포트(GA_IMPL_REPORT.md)의 "다음 단계" 섹션에 반드시 포함:

```
1. dev client 재빌드: npx expo run:android (또는 ios)
2. DebugView 활성화: adb shell setprop debug.firebase.analytics.app <package-name>
3. 앱 재시작 후 Firebase Console > DebugView에서 실시간 이벤트 확인
4. DebugView 비활성화: adb shell setprop debug.firebase.analytics.app .none.
```

`<package-name>`은 `app.config.js`의 `android.package` 값을 사용한다.

---

## 산출물

| 파일                                                   | 생성 시점 | 용도               |
| ------------------------------------------------------ | --------- | ------------------ |
| `docs/harness/firebase/analytics/ga-feature-list.json` | Phase 1   | Task State Machine |
| `docs/harness/firebase/analytics/ga-progress.txt`      | Phase 1   | 세션 간 인수인계   |
| `docs/harness/firebase/analytics/GA_IMPL_REPORT.md`    | Phase 3   | 최종 구현 보고서   |
| `src/` 내 analytics 관련 파일들                        | Phase 2   | 구현 코드          |

---

## 참고 자료

- `references/task_schema.json` — ga-feature-list.json 스키마 및 예시
- `references/generator_guide.md` — Generator 구현 상세 가이드
- `references/evaluator_guide.md` — Evaluator 검증 상세 가이드
