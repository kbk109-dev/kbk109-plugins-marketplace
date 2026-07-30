# Evaluator 검증 상세 가이드

이 문서는 Evaluator(검증 에이전트)가 각 task를 독립적으로 평가할 때 참조하는 상세 가이드다.

## 핵심 원칙

- **회의적 평가자** 톤 유지 — 관대한 판정 금지
- 겉보기에 작동하는 것과 실제로 작동하는 것을 구분
- 파일 내용을 직접 확인하여 검증 (기억이나 추론에 의존하지 않음)
- Generator의 자체 평가를 신뢰하지 않음 — 독립적으로 재검증
- soso한 문제는 넘어가되, acceptance_criteria에 영향을 미치는 문제는 반드시 지적

## 검증 절차

### Step 1: Acceptance Criteria 전수 검사

`CRASHLYTICS_FEATURES.json`에서 해당 task의 `acceptance_criteria` 배열을 읽는다.

각 criterion에 대해:

1. 해당 파일을 직접 Read 또는 Grep으로 확인
2. 충족 여부를 **Pass/Fail**로 판정
3. Fail인 경우 구체적인 위치와 이유 기록

예시 검증 방법:

| Acceptance Criterion                                   | 검증 방법                                                               |
| ------------------------------------------------------ | ----------------------------------------------------------------------- |
| "src/utils/crashlytics.ts 파일이 존재한다"             | 파일 Read → 존재 여부 확인                                              |
| "reportError 함수가 export된다"                        | `grep -n "export.*reportError" src/utils/crashlytics.ts`                |
| "@react-native-firebase/crashlytics import가 정확하다" | 파일 Read → import 문 확인 (default import 여부)                        |
| "TypeScript 타입 정의가 포함된다"                      | 파일 Read → interface/type 키워드 확인                                  |
| "ErrorUtils.setGlobalHandler가 호출된다"               | `grep -n "ErrorUtils.setGlobalHandler" src/utils/errorHandler.ts`       |
| "기존 핸들러가 체이닝된다"                             | `grep -n "getGlobalHandler\|previousHandler" src/utils/errorHandler.ts` |
| "componentDidCatch에서 recordError를 호출한다"         | `grep -n "recordError" src/components/CrashBoundary.tsx`                |
| "CrashBoundary가 루트에 배치된다"                      | `grep -n "CrashBoundary" app/_layout.tsx`                               |
| "중복 리포팅이 없다"                                   | `grep -rn "recordError\|reportError" src/ app/` → 동일 에러 2회 확인    |
| "개발 모드 분기가 있다"                                | `grep -n "__DEV__" src/utils/crashlytics.ts`                            |
| "Context7 최신 API 시그니처와 일치한다"                | Context7 재조회 → 시그니처 비교                                         |

**하나라도 Fail이면 task 전체가 Fail이다.**

### Step 2: 코드 존재 확인

Generator가 작성했다고 주장하는 코드가 실제로 존재하는지 `grep -rn`으로 확인한다.

- 새 파일 생성 task: 파일이 존재하고 내용이 비어있지 않은지 확인
- 기존 파일 수정 task: 삽입된 코드가 정확한 위치에 있는지 확인
- import 문: 참조하는 모듈이 실제로 존재하는 경로인지 확인

### Step 3: Context7 API 일치 확인

해당 task의 `context7_apis` 필드에 나열된 API에 대해:

1. Context7에서 최신 시그니처 재조회
2. Generator가 작성한 코드의 API 호출이 최신 시그니처와 일치하는지 확인
3. deprecated API 사용 여부 확인
4. 불일치 시 Fail + 정확한 시그니처를 피드백에 포함

### Step 4: 에러 핸들러 체이닝 확인

Crashlytics 특유의 핵심 검증 항목:

**글로벌 에러 핸들러:**

- `ErrorUtils.getGlobalHandler()` 또는 이전 핸들러 참조를 저장하는 코드가 있는지 확인
- Crashlytics 리포팅 후 이전 핸들러를 호출하는 코드가 있는지 확인
- 기존 핸들러를 덮어쓰는 패턴 (`ErrorUtils.setGlobalHandler(myHandler)` 만 있고 이전 핸들러 체이닝이 없는 경우) → Fail

**Error Boundary:**

- `componentDidCatch`가 React Class Component에서 구현되어 있는지 확인
- `getDerivedStateFromError`가 `static` 메서드로 정의되어 있는지 확인
- 폴백 UI에 재시도 메커니즘이 있는지 확인

### Step 5: 중복 에러 리포팅 확인

같은 에러가 두 번 recordError되는 것은 Crashlytics 대시보드를 오염시킨다.

```
grep -rn "recordError\|reportError" src/ app/
```

결과에서:

- **Error Boundary + try-catch 중복**: 하위 컴포넌트의 catch 블록에서 recordError한 에러가 상위 Error Boundary의 componentDidCatch에서 다시 recordError되는지 확인
- `_crashlyticsReported` 플래그 또는 동등한 중복 방지 메커니즘이 있는지 확인
- 동일한 에러 도메인에 대해 2곳 이상에서 recordError하는지 확인
- 중복 발견 시 Fail + 어떤 파일에서 중복인지 명시

### Step 6: 아키텍처 준수 확인

다음을 점검한다:

1. **파일 배치**: crashlytics 관련 파일이 CRASHLYTICS_PLAN.md에 명시된 디렉토리에 있는가
2. **Import 경로**: `@/` 절대 경로 사용하고 있는가
3. **네이밍**: 컴포넌트 PascalCase, 유틸 camelCase, 상수 SCREAMING_SNAKE_CASE
4. **TypeScript**: 타입 정의가 포함되어 있는가 (any 사용 금지)
5. **기존 코드 비침범**: crashlytics 코드 외에 기존 로직을 변경하지 않았는가
6. **단방향 의존성**: `utils/crashlytics.ts` → `@react-native-firebase/crashlytics` (역방향 확인)
7. **상수 하드코딩 금지**: 커스텀 속성 키가 `crashlyticsKeys.ts`에서 import되는가
8. **Error Boundary가 Class Component인가**: functional component로 구현하지 않았는가

### Step 7: 회귀 확인

- 기존 import가 깨지지 않았는가 (Grep으로 확인)
- 기존 파일의 기능이 변경되지 않았는가 (crashlytics 삽입 외)
- 기존 에러 핸들러가 여전히 작동하는가 (체이닝 확인)
- 가능하면 `npm run typecheck` 실행하여 타입 에러 확인

### Step 8: 4가지 기준 점수 매기기

각 task에 대해 4가지 기준으로 판정:

| 기준                             | 검증 항목                                             |
| -------------------------------- | ----------------------------------------------------- |
| **완성도** (Completeness)        | 모든 acceptance_criteria 충족 여부                    |
| **코드 품질** (Code Quality)     | TS 타입 에러 없음, 프로젝트 스타일 준수, DEV 분기     |
| **아키텍처 준수** (Architecture) | 핸들러 체이닝, 의존성 방향, 중복 코드 없음, 상수 관리 |
| **기능성** (Functionality)       | import 정확성, API 시그니처 일치, 런타임 에러 가능성  |

**하나라도 Fail이면 task 전체가 Fail이다.**

### Step 9: 결과 기록

**Pass인 경우:**

- `CRASHLYTICS_FEATURES.json`에서 status → `"pass"`
- `CRASHLYTICS_PROGRESS.txt`에 통과 기록
- `CRASHLYTICS_EVAL_LOG.md`에 평가 결과 기록

**Fail인 경우:**

- 구체적이고 실행 가능한 피드백 작성
- `CRASHLYTICS_FEATURES.json`의 `evaluator_feedback` 필드에 기록
- `retry_count` 증가
- `CRASHLYTICS_EVAL_LOG.md`에 실패 사유 및 피드백 기록

피드백은 **추가 조사 없이 문제를 해결할 수 있는 수준**으로 작성한다:

- 어떤 파일의 몇 번째 줄인지
- 무엇이 잘못되었는지
- 어떻게 수정해야 하는지

예시:

> "src/utils/errorHandler.ts:12에서 `ErrorUtils.setGlobalHandler()`를 호출하고 있으나, 이전 핸들러 참조를 저장하지 않고 있음. 11번 줄에 `const previousHandler = ErrorUtils.getGlobalHandler();`를 추가하고, 핸들러 함수 마지막에 `if (previousHandler) previousHandler(error, isFatal);`를 추가해야 함."

> "src/components/CrashBoundary.tsx:25의 componentDidCatch에서 recordError를 호출하고 있으나, 하위 try-catch의 recordError와 중복 리포팅 가능성 있음. \_crashlyticsReported 플래그 체크를 추가해야 함."

### Step 10: 루프 처리

Fail 판정 후:

1. `retry_count` 증가
2. Generator에게 피드백 전달 → 재구현
3. Evaluator 재검증

Generator-Evaluator 루프가 **3회** 반복되면:

- task status를 `"blocked"`로 변경
- 차단 사유를 `CRASHLYTICS_PROGRESS.txt`에 기록
- `CRASHLYTICS_EVAL_LOG.md`에 blocked 기록
- 사용자에게 에스컬레이션:
  > "Task [ID]: [제목]에서 반복적으로 실패하고 있습니다. [구체적 이슈]. 어떻게 진행할까요?"
- 다음 task로 이동

## 흔한 실패 패턴과 대응

| 패턴                                | 증상                                                  | 대응                                              |
| ----------------------------------- | ----------------------------------------------------- | ------------------------------------------------- |
| 에러 핸들러 덮어쓰기                | 기존 핸들러 무시, 체이닝 없음                         | 이전 핸들러 저장 + 체이닝 코드 요구               |
| Error Boundary functional component | hooks로 구현 시도                                     | Class Component 필수, componentDidCatch 사용 요구 |
| Import 경로 오류                    | `@react-native-firebase/crashlytics` 대신 잘못된 경로 | Context7으로 정확한 import 확인                   |
| API 시그니처 불일치                 | recordError 파라미터가 Context7과 다름                | Context7 재조회 후 정확한 시그니처 제공           |
| 중복 에러 리포팅                    | Error Boundary + catch에서 같은 에러 2회 기록         | \_crashlyticsReported 플래그 요구                 |
| 타입 정의 누락                      | any 타입 사용, 에러 도메인 타입 미정의                | TypeScript interface 작성 요구                    |
| 기존 코드 변경                      | crashlytics 외 로직 수정                              | git diff로 불필요한 변경 감지                     |
| 커스텀 키 하드코딩                  | 문자열 리터럴로 setAttribute 호출                     | crashlyticsKeys.ts에서 import 요구                |
| DEV 모드 SDK 스킵                   | **DEV**에서 return으로 SDK 호출 건너뜀                | SDK 호출 유지, console.log는 추가만               |
| 동의 관리 누락                      | setCrashlyticsCollectionEnabled 미호출                | plan의 동의 관리 섹션 대조                        |

## Reasoning Sandwich — Evaluator 단계

Evaluator는 **최대 노력** 단계다. Generator보다 더 꼼꼼하게 검증한다.

- 각 criterion을 별도의 검증 단계로 분리
- "아마 괜찮겠지"라는 판단 금지
- 파일 내용을 실제로 읽어서 확인
- 엣지 케이스 고려 (에러 핸들러 체이닝, 중복 리포팅, **DEV** 분기 등)
- Context7 문서와의 일치 여부를 실제로 비교 (기억에 의존하지 않음)

## CRASHLYTICS_EVAL_LOG.md 기록 형식

매 스프린트 검증 시 다음 형식으로 기록:

```markdown
## Sprint N 평가

> Evaluated: YYYY-MM-DD HH:mm

### crash-NNN: [태스크 제목]

| 기준          | 결과      | 상세                                  |
| ------------- | --------- | ------------------------------------- |
| 완성도        | PASS/FAIL | N/N acceptance_criteria 충족          |
| 코드 품질     | PASS/FAIL | TS 타입 에러, 스타일 준수, DEV 분기   |
| 아키텍처 준수 | PASS/FAIL | 핸들러 체이닝, 의존성 방향, 중복 없음 |
| 기능성        | PASS/FAIL | import 정확성, API 시그니처 일치      |

**결과: PASS/FAIL**
**피드백:** (FAIL인 경우)

- [ ] 구체적 수정 항목 1
- [ ] 구체적 수정 항목 2
```
