# Evaluator 검증 상세 가이드

이 문서는 Evaluator(검증 에이전트)가 각 task를 독립적으로 평가할 때 참조하는 상세 가이드다.

## 핵심 원칙

- **회의적 평가자** 톤 유지 — 관대한 판정 금지
- 겉보기에 작동하는 것과 실제로 작동하는 것을 구분
- 파일 내용을 직접 확인하여 검증 (기억이나 추론에 의존하지 않음)
- 사소한 문제는 넘어가되, acceptance_criteria에 영향을 미치는 문제는 반드시 지적

## 검증 절차

### Step 1: Acceptance Criteria 검증

`ADMOB_TASKS.json`에서 해당 task의 `acceptance_criteria` 배열을 읽는다.

각 criterion에 대해:

1. 해당 파일을 직접 Read 또는 Grep으로 확인
2. 충족 여부를 **Pass/Fail**로 판정
3. Fail인 경우 구체적인 위치와 이유 기록

예시 검증 방법:

| Acceptance Criterion                                                | 검증 방법                                                |
| ------------------------------------------------------------------- | -------------------------------------------------------- |
| "react-native-google-mobile-ads가 package.json dependencies에 존재" | `package.json` Read → dependencies 섹션 확인             |
| "app.json에 react-native-google-mobile-ads 플러그인 설정 존재"      | `app.json` 또는 `app.config.ts` Read → plugins 배열 확인 |
| "mobileAds().initialize() 호출이 앱 진입점에 존재"                  | `app/_layout.tsx` Grep → `initialize` 패턴 검색          |
| "BannerAd가 MainScreen 하단에 배치됨"                               | 해당 화면 파일 Read → BannerAd import 및 JSX 배치 확인   |
| "빈도 캡핑 상수가 plan 값과 일치"                                   | `src/ads/adConfig.ts` Read → 값 비교                     |
| "TypeScript 타입 에러 없음"                                         | `npx tsc --noEmit` 실행 → 에러 출력 확인                 |

**하나라도 Fail이면 task 전체가 Fail이다.**

### Step 2: TypeScript 컴파일 검증

```bash
npx tsc --noEmit
```

에러가 있으면:

- 에러 메시지에서 파일 위치, 라인 번호, 에러 내용 추출
- 해당 task가 생성/수정한 파일과 관련된 에러만 해당 task의 Fail 사유로 기록
- 기존 코드의 pre-existing 에러는 무시 (단, 기록은 남김)

### Step 3: 아키텍처 준수 확인

다음을 점검한다:

1. **파일 배치**: 광고 관련 파일이 `src/ads/` 하위에 있는가
2. **Import 경로**: `@/` 절대 경로 사용하고 있는가
3. **스타일링**: 프로젝트 CLAUDE.md에 명시된 스타일링 방식을 따르는가
4. **네이밍**: 컴포넌트 PascalCase, 유틸 camelCase, 상수 SCREAMING_SNAKE_CASE
5. **TypeScript**: Props interface 정의, 타입 안전성

### Step 4: 회귀 확인

- 기존 import가 깨지지 않았는가 (Grep으로 확인)
- 기존 화면의 레이아웃이 변경되지 않았는가 (광고 삽입 외)
- 기존 테스트가 깨지지 않는가 (가능하면 `npm test` 실행)

### Step 5: 결과 기록

**Pass인 경우:**

```json
{
  "status": "pass",
  "evaluator_feedback": null,
  "retry_count": 0
}
```

**Fail인 경우:**

```json
{
  "status": "fail",
  "evaluator_feedback": "구체적이고 실행 가능한 피드백. 예: 'src/ads/adUnitIds.ts:15에서 ADMOB_BANNER_MAIN_ANDROID 환경변수를 읽고 있으나, .env.local에 해당 키가 없음. .env.local에 ADMOB_BANNER_MAIN_ANDROID=ca-app-pub-3940256099942544/9214589741 추가 필요'",
  "retry_count": 1
}
```

피드백은 **추가 조사 없이 문제를 해결할 수 있는 수준**으로 작성한다:

- 어떤 파일의 몇 번째 줄인지
- 무엇이 잘못되었는지
- 어떻게 수정해야 하는지

### Step 6: 재시도 처리

Fail 판정 후:

1. `retry_count` 증가
2. Generator에게 피드백 전달 → 재구현
3. Evaluator 재검증

`retry_count`가 2에 도달하면:

- task status를 `"blocked"`로 변경
- 사용자에게 에스컬레이션:
  > "Task [ID]: [제목]에서 반복적으로 실패하고 있습니다. [구체적 이슈]. 어떻게 진행할까요?"

## 흔한 실패 패턴과 대응

| 패턴                | 증상                                       | 대응                              |
| ------------------- | ------------------------------------------ | --------------------------------- |
| Import 누락         | 컴포넌트를 추가했지만 import문 누락        | tsc 에러로 감지                   |
| 환경변수 불일치     | adUnitIds.ts의 키와 .env.local의 키가 다름 | 양쪽 파일 직접 비교               |
| Plan 값과 다른 설정 | 빈도 캡핑 값이 plan과 다름                 | plan Section 6과 adConfig.ts 비교 |
| 레이아웃 깨짐       | Banner 삽입 후 기존 콘텐츠 겹침            | 해당 화면의 전체 JSX 구조 확인    |
| 기존 코드 덮어쓰기  | 이미 존재하는 광고 코드를 새로 작성        | git diff로 불필요한 변경 감지     |
