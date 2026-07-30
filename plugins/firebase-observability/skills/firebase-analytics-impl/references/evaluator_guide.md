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

`ga-feature-list.json`에서 해당 task의 `acceptance_criteria` 배열을 읽는다.

각 criterion에 대해:

1. 해당 파일을 직접 Read 또는 Grep으로 확인
2. 충족 여부를 **Pass/Fail**로 판정
3. Fail인 경우 구체적인 위치와 이유 기록

예시 검증 방법:

| Acceptance Criterion                                 | 검증 방법                                                   |
| ---------------------------------------------------- | ----------------------------------------------------------- |
| "src/utils/analytics.ts 파일이 존재한다"             | 파일 Read → 존재 여부 확인                                  |
| "logEvent 래퍼 함수가 export된다"                    | `grep -n "export.*logEvent" src/utils/analytics.ts`         |
| "@react-native-firebase/analytics import가 정확하다" | 파일 Read → import 문 확인                                  |
| "TypeScript 타입 정의가 포함된다"                    | 파일 Read → interface/type 키워드 확인                      |
| "Context7 최신 API 시그니처와 일치한다"              | Context7 재조회 → 시그니처 비교                             |
| "app/\_layout.tsx에 초기화 코드가 삽입된다"          | `grep -n "initAnalytics\|analytics" app/_layout.tsx`        |
| "기존 코드와 충돌하지 않는다"                        | 파일 전체 Read → import 충돌, 네이밍 충돌 확인              |
| "중복 이벤트 로깅이 없다"                            | `grep -rn "logEvent.*이벤트명" src/ app/` → 1회만 존재 확인 |

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

### Step 4: 중복 이벤트 확인

같은 이벤트가 두 번 로깅되는 것은 analytics 데이터를 오염시킨다.

```
grep -rn "logEvent\|logScreenView" src/ app/
```

결과에서:

- 동일한 이벤트명으로 `logEvent`가 2회 이상 호출되는지 확인
- 스크린 트래킹이 자동 + 수동으로 중복 발화되는지 확인
- 중복 발견 시 Fail + 어떤 파일에서 중복인지 명시

### Step 5: 아키텍처 준수 확인

다음을 점검한다:

1. **파일 배치**: analytics 관련 파일이 GA_PLAN.md에 명시된 디렉토리에 있는가
2. **Import 경로**: `@/` 절대 경로 사용하고 있는가
3. **네이밍**: 컴포넌트 PascalCase, 유틸 camelCase, 상수 SCREAMING_SNAKE_CASE
4. **TypeScript**: 타입 정의가 포함되어 있는가 (any 사용 금지)
5. **기존 코드 비침범**: analytics 코드 외에 기존 로직을 변경하지 않았는가

### Step 6: 회귀 확인

- 기존 import가 깨지지 않았는가 (Grep으로 확인)
- 기존 파일의 기능이 변경되지 않았는가 (analytics 삽입 외)
- 가능하면 `npm run typecheck` 실행하여 타입 에러 확인

### Step 7: 결과 기록

**Pass인 경우:**

- `ga-feature-list.json`에서 status → `"pass"`
- `ga-progress.txt`에 통과 기록

**Fail인 경우:**

- 구체적이고 실행 가능한 피드백 작성
- `ga-feature-list.json`의 `evaluator_feedback` 필드에 기록
- `retry_count` 증가

피드백은 **추가 조사 없이 문제를 해결할 수 있는 수준**으로 작성한다:

- 어떤 파일의 몇 번째 줄인지
- 무엇이 잘못되었는지
- 어떻게 수정해야 하는지

예시:

> "src/utils/analytics.ts:15에서 `analytics().logEvent`를 호출하고 있으나, Context7 최신 문서에 따르면 `import analytics from '@react-native-firebase/analytics'` 후 `analytics().logEvent(name, params)` 패턴이어야 함. 현재 코드는 named import를 사용 중. default import로 변경 필요."

### Step 8: 루프 처리

Fail 판정 후:

1. `retry_count` 증가
2. Generator에게 피드백 전달 → 재구현
3. Evaluator 재검증

Generator-Evaluator 루프가 **3회** 반복되면:

- task status를 `"blocked"`로 변경
- 차단 사유를 `ga-progress.txt`에 기록
- 사용자에게 에스컬레이션:
  > "Task [ID]: [제목]에서 반복적으로 실패하고 있습니다. [구체적 이슈]. 어떻게 진행할까요?"
- 다음 task로 이동

## 흔한 실패 패턴과 대응

| 패턴                | 증상                                                | 대응                                    |
| ------------------- | --------------------------------------------------- | --------------------------------------- |
| Import 경로 오류    | `@react-native-firebase/analytics` 대신 잘못된 경로 | Context7으로 정확한 import 확인         |
| API 시그니처 불일치 | 파라미터명이 Context7 문서와 다름                   | Context7 재조회 후 정확한 시그니처 제공 |
| 중복 이벤트 로깅    | 같은 이벤트가 2곳에서 발화                          | grep으로 전체 스캔, 중복 위치 명시      |
| 타입 정의 누락      | any 타입 사용 또는 타입 미정의                      | 이벤트 파라미터 interface 작성 요구     |
| 기존 코드 변경      | analytics 외 로직 수정                              | git diff로 불필요한 변경 감지           |
| 스크린 매핑 누락    | 일부 화면이 매핑에서 빠짐                           | GA_PLAN.md 매핑 테이블과 1:1 비교       |
| 동의 관리 누락      | setAnalyticsCollectionEnabled 미호출                | plan의 동의 관리 섹션 대조              |

## Reasoning Sandwich — Evaluator 단계

Evaluator는 **최대 노력** 단계다. Generator보다 더 꼼꼼하게 검증한다.

- 각 criterion을 별도의 검증 단계로 분리
- "아마 괜찮겠지"라는 판단 금지
- 파일 내용을 실제로 읽어서 확인
- 엣지 케이스 고려 (동적 라우트 매핑, **DEV** 분기 등)
- Context7 문서와의 일치 여부를 실제로 비교 (기억에 의존하지 않음)
