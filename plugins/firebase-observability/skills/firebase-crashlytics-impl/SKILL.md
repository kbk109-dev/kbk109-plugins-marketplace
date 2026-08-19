---
name: firebase-crashlytics-impl
description: "Harness Engineering 기반 Firebase Crashlytics 구현 스킬. CRASHLYTICS_PLAN.md 계획 문서를 읽고 Three-Agent Architecture(Planner-Generator-Evaluator)와 Task State Machine으로 안정적으로 Firebase Crashlytics를 구현합니다. 각 구현 항목을 개별 task로 분해하고, acceptance_criteria 기반 독립 검증 루프를 실행하여 조기 완료 선언과 미완성 상태를 구조적으로 방지합니다. 반드시 이 스킬을 사용해야 하는 경우: 'firebase-crashlytics-impl', 'CRASHLYTICS_PLAN 기반으로 구현해줘', 'Firebase Crashlytics 코드 넣어줘', '크래시 리포팅 코드 구현해줘', 'CRASHLYTICS_PLAN.md 보고 구현해줘', 'Error Boundary 만들어줘', '에러 핸들링 코드 넣어줘', 'crashlytics 구현 시작해줘', '크래시 리포팅 설정해줘', 'crashlytics 구현 이어서 해줘', '나머지 에러 핸들링도 구현해줘', 'recordError 코드 넣어줘', '글로벌 에러 핸들러 설정해줘', '비치명적 에러 리포팅 구현해줘', '크래시 추적 코드 추가해줘', '@react-native-firebase/crashlytics 구현', 'Firebase Crashlytics 구현해줘', 'crashlytics 적용해줘', '하네스로 crashlytics 구현'. Firebase Crashlytics/크래시 리포팅 구현/적용 관련 키워드가 포함된 모든 한국어/영어 요청에 트리거."
compatibility: 'mcp: context7'
---

# Firebase Crashlytics Implementation — Harness Engineering

CRASHLYTICS_PLAN.md 계획 문서를 기반으로 Firebase Crashlytics를 구현한다. 더 똑똑한 모델이 아니라, 모델을 둘러싼 **더 똑똑한 환경(Harness)** 이 성공을 결정한다.

모든 사용자 대화는 **한국어**로, 코드 주석은 **한글**로 작성한다 (CLAUDE.md 규칙).

## LLM 구조적 실패 모드와 대응

이 스킬이 해결하는 4가지 구조적 실패 패턴:

| 실패 모드               | 대응                                                                   |
| ----------------------- | ---------------------------------------------------------------------- |
| 세션 간 상태 유실       | `CRASHLYTICS_PROGRESS.txt` + `CRASHLYTICS_FEATURES.json`으로 상태 복원 |
| 전체를 한번에 구현 시도 | Task State Machine — 한 번에 하나의 task만 작업                        |
| 코드 작성 = 완료 선언   | Evaluator가 acceptance_criteria 기반 독립 검증                         |
| 같은 접근 반복 루프     | Loop Detection — 동일 파일 5회 편집 또는 검증 루프 3회 반복 시 개입    |

---

## Hard Gate

**가장 먼저** `docs/plan/CRASHLYTICS_PLAN.md` 파일 존재 여부를 확인한다.

파일이 없으면:

> "CRASHLYTICS_PLAN.md 파일이 존재하지 않습니다. 먼저 firebase-crashlytics-plan 스킬로 계획 문서를 작성해주세요."

**즉시 종료.** 이후 어떤 구현도 진행하지 않는다.

또한 확인:

- `package.json`에서 `@react-native-firebase/crashlytics` 설치 여부 → 미설치 시 안내
- `app.config.js` (또는 `app.json`) plugins 배열에 `@react-native-firebase/app` 존재 여부 → 미등록 시 **반드시 추가** (이 플러그인 없이 prebuild하면 Firebase 네이티브 SDK가 포함되지 않아 런타임에 조용히 실패함)
- `app.config.js`의 `android.googleServicesFile` / `ios.googleServicesFile` 경로 설정 여부 확인
- `docs/harness/firebase/crashlytics/CRASHLYTICS_FEATURES.json` 존재 여부 → 있으면 **이어하기 모드** 진입
- `docs/harness/firebase/crashlytics/` 디렉토리 존재 여부 → 없으면 자동 생성

---

## Harness 디렉토리 구조

```
docs/
├── plan/
│   └── CRASHLYTICS_PLAN.md                   ← 계획 원본 (읽기 전용 참조)
└── harness/
    └── firebase/
        └── crashlytics/
            ├── CRASHLYTICS_FEATURES.json     ← Task State Machine
            ├── CRASHLYTICS_PROGRESS.txt      ← 세션 간 인수인계 로그
            ├── CRASHLYTICS_EVAL_LOG.md       ← Evaluator 평가 로그 (스프린트별 점수/피드백)
            └── CRASHLYTICS_IMPL_REPORT.md    ← 구현 완료 리포트 (최종 산출물)
```

- 계획 원본(`CRASHLYTICS_PLAN.md`)은 `docs/plan/`에 유지 — harness 폴더로 복사하지 않는다
- harness 산출물은 모두 `docs/harness/firebase/crashlytics/`에 위치한다
- `docs/harness/firebase/crashlytics/` 디렉토리가 없으면 Planner가 자동 생성한다

---

## Phase 1: PLANNER (계획 분석)

코드를 한 줄도 작성하지 않는다. 환경을 읽고 구현 가능한 상태로 준비한다.

### 1.1 Readable Environment 구축

다음 파일을 순서대로 읽는다:

1. `docs/plan/CRASHLYTICS_PLAN.md` — 전체 정독. 구현 범위, 에러 분류, Error Boundary 배치, recordError 삽입 위치, 커스텀 속성, 로그 포인트, 동의 관리 추출
2. `CLAUDE.md` — 기술 스택, 코딩 규칙, 디렉토리 구조
3. `package.json` — 설치된 의존성, 스크립트
4. `app.json` 또는 `app.config.js` — Expo 설정, 기존 플러그인
5. `app/` 디렉토리 구조 — layout 파일, 스크린 목록 파악
6. 기존 crashlytics/에러 핸들링 코드 스캔:
   - `grep -rn "crashlytics\|recordError\|ErrorBoundary\|ErrorUtils\|setGlobalHandler" src/ app/`
   - `grep -rn "captureException\|Sentry" src/ app/` (기존 에러 트래커 확인)
7. `docs/harness/firebase/crashlytics/CRASHLYTICS_FEATURES.json` — 이전 세션 task 상태 (있으면 재개, 없으면 신규 생성)

**Progressive Disclosure (점진적 정보 공개):**

- Planner는 CRASHLYTICS_PLAN.md 전체를 읽는다
- Generator는 현재 태스크에 필요한 섹션만 참조한다
- Evaluator는 acceptance_criteria와 대상 파일만 참조한다

### 1.2 Context7 API 검증

훈련 데이터에 절대 의존하지 않는다. Context7 MCP로 최신 API를 조회한다.

1. `mcp__context7__resolve-library-id` 또는 `mcp__plugin_context7_context7__resolve-library-id`로 다음 라이브러리 ID를 조회:
   - `@react-native-firebase/crashlytics`
   - `@react-native-firebase/app`
   - `expo-router`
   - `react`

2. 다음 쿼리를 **병렬로** 실행:
   - `"recordError log setAttribute setUserId example"` — 핵심 에러 리포팅 및 메타데이터 API
   - `"setCrashlyticsCollectionEnabled crash checkForUnsentReports"` — 동의 제어 및 테스트 크래시
   - `"setAttributes custom keys non-fatal error"` — 배치 속성 및 에러 분류
   - `"initialize Firebase app React Native setup"` — Firebase 초기화
   - `"ErrorBoundary error handling layout error boundary"` — Expo Router Error Boundary 패턴
   - `"componentDidCatch getDerivedStateFromError Error Boundary class component"` — 클래스 기반 Error Boundary

Context7와 CRASHLYTICS_PLAN.md가 API 세부사항에서 충돌하면 **Context7이 우선**한다. 차이점을 기록한다.

Context7 호출 실패 시: CRASHLYTICS_PLAN.md 기준으로 진행하되, 최종 보고서에 "API 검증 미완료" 경고를 기록한다.

### 1.3 Task State Machine 생성

`CRASHLYTICS_FEATURES.json`이 이미 존재하면 기존 상태를 로드한다 (세션 재개). 없으면 새로 생성한다.

CRASHLYTICS_PLAN.md의 모든 구현 항목을 개별 task로 분해하여 `docs/harness/firebase/crashlytics/CRASHLYTICS_FEATURES.json`을 생성한다.

**핵심 규칙:**

- 모든 task의 status 기본값은 **`"fail"`** ("아직 통과하지 못함"이라는 부정적 상태)
- 각 task에 기계 판독 가능한 `acceptance_criteria` 포함
- 스프린트 단위로 태스크 그룹핑, 태스크 간 의존성(`depends_on`) 설정
- 각 태스크에 `context7_apis`와 `plan_reference` 필드 포함

스키마: `references/task_schema.json` 참조

**task 분해 기준** (CRASHLYTICS_PLAN.md에서 추출):

1. 패키지 설치 및 Expo 설정 파일 업데이트
2. Crashlytics 유틸리티 모듈 생성 (래퍼 함수, 에러 분류 상수, 타입 정의)
3. 글로벌 에러 핸들러 (ErrorUtils.setGlobalHandler 체이닝, Promise rejection)
4. Error Boundary 컴포넌트 생성 + Crashlytics 연동
5. Error Boundary 배치 (루트 + 피처별)
6. 수동 에러 리포팅 (recordError) — 각 삽입 위치별 task
7. 커스텀 로그 (breadcrumb) — 사용자 행동, 앱 상태 변경
8. 커스텀 속성 (setAttribute/setAttributes)
9. 사용자 식별 (setUserId 연동)
10. 동의 관리 (setCrashlyticsCollectionEnabled)
11. 디버그 설정 (개발/프로덕션 분기, 테스트 크래시)
12. 네이티브 크래시 빌드 설정 (dSYM, 소스맵 — plan에 있으면)

**스프린트 구성** (CRASHLYTICS_PLAN.md 내용에 따라 유동 조정):

- Sprint 1: 패키지 설치 + SDK 초기화 + 유틸리티 셋업
- Sprint 2: 글로벌 에러 핸들링 + Error Boundary
- Sprint 3: recordError 삽입 + 커스텀 로그
- Sprint 4: 커스텀 속성 + 사용자 식별
- Sprint 5: 동의 관리 + 네이티브 빌드 설정 + 마무리

**Architecture Enforcement — 참조할 패턴 파일 지정:**
Planner는 코드 생성 시 참조할 "좋은 패턴" 파일 목록을 지정한다. Generator는 이 목록의 파일만 스타일 참조로 사용한다. 이는 나쁜 패턴 복제를 방지한다.

### 1.4 Progress 파일 초기화

`docs/harness/firebase/crashlytics/CRASHLYTICS_PROGRESS.txt`를 생성(또는 업데이트)한다:

```
# Crashlytics Implementation Progress
> Started: YYYY-MM-DD HH:mm
> Plan Source: docs/plan/CRASHLYTICS_PLAN.md
> Harness Dir: docs/harness/firebase/crashlytics/
> Context7 Checked: Yes (YYYY-MM-DD)

## Session 1
- Planner: CRASHLYTICS_FEATURES.json 생성 (N개 태스크, M개 스프린트)
- Context7 차이점: [차이 있으면 기록, 없으면 "없음"]
- 다음 작업: Sprint 1 시작
```

이 파일은 다음 세션이 **30초 이내에** 프로젝트 상태를 재구성할 수 있어야 한다.

---

## Phase 2: TASK LOOP (Generator + Evaluator)

한 번에 하나의 task만 작업한다. 스프린트 내에서 우선순위가 가장 높은 `status: "fail"` task부터 처리한다.

### Generator (구현)

**매 task 시작 전 — 오리엔테이션:**

1. `CRASHLYTICS_FEATURES.json` + `CRASHLYTICS_PROGRESS.txt` 확인 → 현재 상태 파악
2. 현재 스프린트의 최우선 `"fail"` task 선택
3. 해당 task의 `depends_on` 확인 → 의존 task가 모두 `"pass"`인지 확인
4. 해당 task의 `context7_apis`에 대해 Context7 조회 (최신성 확보)
5. 해당 task 관련 기존 코드 확인 (기존 코드 덮어쓰지 않음)

**구현 규칙:**

- Context7 검증 API 기반 구현
- CRASHLYTICS_PLAN.md가 명세서 (에러 분류, 속성 키, 로그 포인트, 삽입 위치)
- Context7이 API 레퍼런스 (함수 시그니처, 최신 패턴)
- 프로젝트 코드가 스타일 가이드 (네이밍, 포매팅, 구조)
- TypeScript 필수, `@/` 절대 경로 임포트
- CRASHLYTICS_PLAN.md에 없는 항목은 임의로 추가하지 않음
- 기존 파일 수정 시 crashlytics 관련 코드만 추가 (기존 로직 변경 금지)
- **에러 핸들러 체이닝 필수**: 기존 글로벌 에러 핸들러가 있으면 덮어쓰지 않고 체이닝
- **Error Boundary는 React Class Component**: componentDidCatch는 클래스 컴포넌트에서만 지원
- **중복 리포팅 방지**: Error Boundary + try-catch에서 같은 에러를 두 번 recordError하지 않음

**Architecture Enforcement:**

- Planner가 지정한 "참조할 패턴 파일 목록"의 스타일을 따름
- crashlytics 유틸리티 코드는 CRASHLYTICS_PLAN.md에 명시된 디렉토리에 생성
- 단방향 의존성: `utils/crashlytics.ts` → `@react-native-firebase/crashlytics` (역방향 금지)
- 커스텀 속성 키는 상수 파일에서만 정의, 하드코딩 금지
- import 순서, 코드 스타일은 프로젝트 기존 패턴을 따름

**구현 상세 가이드:** `references/generator_guide.md` 참조

**Loop Detection:**

- 동일 파일을 **5회 이상** 편집할 경우: "이 파일을 N회 편집했습니다. 완전히 다른 접근 방식을 고려하거나, 이 태스크를 'blocked'로 표시하고 다음으로 넘어가세요."
- Generator-Evaluator 루프가 **3회** 반복될 경우: 해당 task를 `"blocked"`로 표시하고 다음 task로 이동

### Evaluator (검증)

Generator가 구현을 마치면, 역할을 전환하여 **독립적이고 회의적으로** 검증한다. Generator의 자체 평가를 신뢰하지 않는다.

**검증 체크리스트 — 모든 항목 통과해야 pass:**

1. **코드 존재 확인**: `grep -rn`으로 대상 파일에 해당 코드가 실제로 삽입되었는지 확인
2. **Acceptance Criteria 전수 검사**: `CRASHLYTICS_FEATURES.json`의 해당 task의 모든 criteria를 파일 내용을 직접 확인하여 검증
3. **import 정확성**: 모든 import 문이 실제 존재하는 모듈을 참조하는지 확인
4. **Context7 API 일치**: 사용된 API가 Context7 최신 문서와 일치하는지 확인
5. **중복 리포팅 없음**: Error Boundary + try-catch에서 같은 에러를 두 번 recordError하지 않는지 확인
6. **에러 핸들러 체이닝**: 기존 핸들러가 보존되는지 확인
7. **회귀 없음**: 기존 코드에 대한 부작용 없음 확인

**Reasoning Sandwich 적용:**

- Planner 단계: 추론 최대 (전체 CRASHLYTICS_PLAN.md 분석, 태스크 분해)
- Generator 단계: 추론 중간 (코드 작성에 집중)
- Evaluator 단계: 추론 최대 (각 criteria 꼼꼼히 검증, 엣지 케이스 확인)

**검증 결과 처리:**

- **통과**: `CRASHLYTICS_FEATURES.json`에서 해당 task status를 `"pass"`로 변경
- **실패**: 구체적이고 실행 가능한 피드백 기록 후 Generator 재시도
- **3회 루프 반복 후 실패**: `"blocked"` 표시, 차단 사유를 `CRASHLYTICS_PROGRESS.txt`에 기록, 사용자에게 에스컬레이션

**Evaluator 평가 로그** (`CRASHLYTICS_EVAL_LOG.md`):

매 스프린트 검증 시 `docs/harness/firebase/crashlytics/CRASHLYTICS_EVAL_LOG.md`에 기록:

```markdown
## Sprint N 평가

> Evaluated: YYYY-MM-DD HH:mm

### crash-001: [태스크 제목]

| 기준          | 결과      | 상세                                  |
| ------------- | --------- | ------------------------------------- |
| 완성도        | PASS/FAIL | N/N acceptance_criteria 충족          |
| 코드 품질     | PASS/FAIL | TS 타입 에러, 스타일 준수 여부        |
| 아키텍처 준수 | PASS/FAIL | 핸들러 체이닝, 의존성 방향, 중복 없음 |
| 기능성        | PASS/FAIL | import 정확성, API 시그니처 일치      |

**결과: PASS/FAIL**
**피드백:** (FAIL인 경우 구체적 수정 항목)
```

**상세 검증 가이드:** `references/evaluator_guide.md` 참조

### Task 완료 처리

Evaluator 검증 통과 후에만:

1. `CRASHLYTICS_FEATURES.json`에서 status → `"pass"`
2. `CRASHLYTICS_PROGRESS.txt` 업데이트 (pass/fail 카운트, 로그)
3. `CRASHLYTICS_FEATURES.json`의 summary 갱신
4. `CRASHLYTICS_EVAL_LOG.md` 업데이트
5. `git push`는 **절대 자동 실행하지 않음**

다음 `"fail"` task로 반복한다.

### 스프린트 완료

스프린트 내 모든 태스크가 `pass` 또는 `blocked`이면:

- `CRASHLYTICS_FEATURES.json`의 summary 업데이트
- `CRASHLYTICS_PROGRESS.txt`에 스프린트 결과 기록
- `CRASHLYTICS_EVAL_LOG.md`에 스프린트별 평가 요약 기록
- 다음 스프린트로 이동

**컨텍스트 소진 방지:**

- 컨텍스트 창의 약 70%를 소모하면 현재 스프린트를 완료하고 중간 저장
- `CRASHLYTICS_FEATURES.json` + `CRASHLYTICS_PROGRESS.txt` 업데이트 + 사용자에게 진행 상황 보고
- 다음 세션에서 이어서 작업할 수 있도록 모든 상태를 외부화

---

## Phase 3: 최종 검증 및 리포트

모든 스프린트 완료 후:

### 3.1 전체 검증 (Evaluator)

- `CRASHLYTICS_FEATURES.json`의 전체 태스크에 대해 최종 확인
- 파일 간 일관성 확인 (import, 타입, 상수 등)
- 중복 에러 리포팅 전체 스캔: `grep -rn "recordError\|crashlytics()" src/ app/`
- Error Boundary와 try-catch의 recordError 중복 여부 확인

### 3.2 구현 리포트 생성

`docs/harness/firebase/crashlytics/CRASHLYTICS_IMPL_REPORT.md`를 생성한다:

**리포트 템플릿:** `references/report_template.md` 참조 — 구현 요약부터 항목별 체크리스트,
Blocked 태스크, Changelog 까지 전체 골격이 들어 있다.

### 3.3 최종 상태 확정

- `CRASHLYTICS_FEATURES.json`의 summary 섹션 최종 갱신
- 모든 상태를 확정

---

## 세션 연속성 (이어하기 모드)

기존 `docs/harness/firebase/crashlytics/CRASHLYTICS_FEATURES.json`이 있는 상태에서 스킬이 재실행되면:

**오리엔테이션 순서:**

1. `CRASHLYTICS_FEATURES.json` 확인 — 전체 태스크 현황 파악
2. `CRASHLYTICS_PROGRESS.txt` 확인 — 마지막 세션 내용 파악
3. CRASHLYTICS_PLAN.md 변경 여부 확인 (`plan_last_updated` 비교)
4. **Planner를 재실행하지 않고** 남은 `fail` 태스크부터 Generator-Evaluator 루프를 이어서 실행
5. CRASHLYTICS_PLAN.md가 업데이트된 경우에만 Planner를 재실행하여 새 태스크를 추가

**CRASHLYTICS_PLAN.md 업데이트 감지 시:**

- 이전 `CRASHLYTICS_FEATURES.json`과 현재 CRASHLYTICS_PLAN.md를 비교
- 새로 추가된 항목 → 새 태스크 추가 (status: `"fail"`)
- 삭제된 항목 → 사용자에게 확인 후 태스크 제거
- 변경된 항목 → 해당 태스크의 status를 `"fail"`로 리셋

---

## 증분 구현 지원

**이미 일부 구현이 되어 있는 프로젝트:**

- Planner가 기존 crashlytics/에러 핸들링 코드를 감지 (`grep -rn "crashlytics\|recordError\|ErrorBoundary\|ErrorUtils" src/ app/`)
- 이미 구현된 항목은 Evaluator가 검증 후 `status: "pass"` 또는 `"existing"`으로 표시
- 누락된 항목만 Generator가 추가 구현
- 기존 Error Boundary가 있으면 Crashlytics 연동만 추가, 구조 유지
- 기존 글로벌 에러 핸들러가 있으면 체이닝 방식으로 추가
- Sentry 등 기존 에러 트래커가 있으면 함께 공존 (제거하지 않음)

---

## 기계적 제약 (절대 규칙)

이 규칙들은 어떤 상황에서도 재정의할 수 없다:

1. **"한 번에 하나의 task"** — Generator는 절대 여러 task를 동시에 작업하지 않는다
2. **"criteria 삭제 금지"** — acceptance_criteria를 수정하거나 삭제하지 않는다
3. **"검증 없이 pass 금지"** — Evaluator 검증 통과 후에만 status를 "pass"로 변경한다
4. **"스텁 금지"** — TODO, placeholder, mock 구현으로 task를 통과시키지 않는다
5. **"진행 기록 필수"** — 매 task 완료 시 CRASHLYTICS_PROGRESS.txt 업데이트를 누락하지 않는다
6. **"JSON 형식 유지"** — CRASHLYTICS_FEATURES.json은 항상 유효한 JSON 형식을 유지한다
7. **"루프 상한"** — Generator-Evaluator 루프 3회 반복 후 "blocked" 처리 및 사용자 에스컬레이션
8. **"git push 금지"** — 자동으로 git push를 실행하지 않는다
9. **"에러 핸들러 체이닝 필수"** — 기존 글로벌 에러 핸들러를 절대 덮어쓰지 않는다
10. **"중복 리포팅 금지"** — 같은 에러를 두 번 recordError하지 않는다

에이전트는 컨텍스트가 쌓이면 "거의 됐으니 넘어가자"는 유혹에 빠지기 쉽다. 기계적 제약은 이 경향을 구조적으로 차단한다.

---

## Expo 네이티브 통합 주의사항

`@react-native-firebase/crashlytics`는 네이티브 모듈이므로 JS 코드 작성만으로는 동작하지 않는다. 다음을 반드시 확인/수행해야 한다:

### app.config.js 필수 설정

```js
plugins: [
  '@react-native-firebase/app',          // 반드시 plugins에 등록
  '@react-native-firebase/crashlytics',  // Crashlytics Expo config plugin (dSYM 업로드 등)
  // ... 다른 플러그인들
],
android: {
  googleServicesFile: './google-services.json',  // 경로 명시
},
ios: {
  googleServicesFile: './GoogleService-Info.plist',  // 경로 명시
},
```

`@react-native-firebase/app` 플러그인이 plugins에 없으면 `npx expo prebuild`가 Firebase 네이티브 SDK를 포함하지 않는다. `@react-native-firebase/crashlytics`도 Expo config plugin이 있으므로 함께 등록해야 dSYM 자동 업로드 등 네이티브 크래시 리포팅 설정이 적용된다.

### Dev Client 재빌드

네이티브 패키지 추가 후에는 반드시:

1. `npx expo prebuild --clean` — 네이티브 프로젝트 재생성
2. `npx expo run:android` 또는 `npx expo run:ios` — **dev client 새로 빌드 및 설치**

`prebuild`만으로는 기기의 앱이 갱신되지 않는다. `run:android`로 실제 빌드해야 네이티브 모듈이 포함된다.

### Crashlytics **DEV** 모드 규칙

DEV 모드에서도 `recordError()`를 **실제로 호출**해야 한다. console.error는 디버깅 보조로만 사용하고, `return`으로 SDK 호출을 건너뛰지 않는다:

```typescript
// 올바른 패턴
if (__DEV__) {
  console.error(`[Crashlytics] recordError:`, error);
}
// return 없이 아래 SDK 호출로 진행
crashlytics().recordError(error);

// 잘못된 패턴 — 프로덕션에서만 리포팅됨, 개발 중 검증 불가
if (__DEV__) {
  console.error(error);
  return; // ❌ Crashlytics SDK 호출을 건너뜀
}
```

단, `setCrashlyticsCollectionEnabled(false)`를 통해 DEV에서 실제 전송을 비활성화할 수 있다. 이 경우 SDK 호출은 실행되지만 데이터가 전송되지 않아 코드 경로 검증이 가능하다.

---

## 산출물

| 파일                                                           | 생성 시점 | 용도                |
| -------------------------------------------------------------- | --------- | ------------------- |
| `docs/harness/firebase/crashlytics/CRASHLYTICS_FEATURES.json`  | Phase 1   | Task State Machine  |
| `docs/harness/firebase/crashlytics/CRASHLYTICS_PROGRESS.txt`   | Phase 1   | 세션 간 인수인계    |
| `docs/harness/firebase/crashlytics/CRASHLYTICS_EVAL_LOG.md`    | Phase 2   | Evaluator 평가 로그 |
| `docs/harness/firebase/crashlytics/CRASHLYTICS_IMPL_REPORT.md` | Phase 3   | 최종 구현 보고서    |
| `src/` 내 crashlytics 관련 파일들                              | Phase 2   | 구현 코드           |

---

## 참고 자료

- `references/task_schema.json` — CRASHLYTICS_FEATURES.json 스키마 및 예시
- `references/generator_guide.md` — Generator 구현 상세 가이드
- `references/evaluator_guide.md` — Evaluator 검증 상세 가이드
- `references/report_template.md` — CRASHLYTICS_IMPL_REPORT.md 문서 템플릿
