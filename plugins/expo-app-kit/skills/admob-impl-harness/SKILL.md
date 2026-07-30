---
name: admob-impl-harness
description: "Harness Engineering 기반 AdMob 광고 구현 스킬. ADMOB-PLAN.md 계획 문서를 읽고 Three-Agent Architecture(Planner-Generator-Evaluator)와 Task State Machine으로 안정적으로 AdMob 광고를 구현합니다. 각 기능을 개별 task로 분해하고, acceptance_criteria 기반 독립 검증 루프를 실행하여 조기 완료 선언과 미완성 상태를 구조적으로 방지합니다. 반드시 이 스킬을 사용해야 하는 경우: 'admob-impl-harness', 'AdMob 구현해줘', 'AdMob 적용해줘', '광고 구현해줘', '광고 적용해줘', '애드몹 구현', '애드몹 적용', 'ADMOB-PLAN 기반으로 구현', 'ADMOB-PLAN 구현해줘', '광고 계획 실행', '광고 계획 구현', 'implement AdMob', 'apply AdMob ads', '배너 광고 코드 넣어줘', '전면 광고 구현해줘', '보상형 광고 컴포넌트 만들어줘', '나머지 광고도 구현해줘', 'AdMob harness', '하네스로 광고 구현'. AdMob/광고 구현/적용 관련 키워드가 포함된 모든 한국어/영어 요청에 트리거."
compatibility: 'mcp: context7'
---

# AdMob Implementation — Harness Engineering

ADMOB-PLAN.md 계획 문서를 기반으로 AdMob 광고를 구현한다. 더 똑똑한 모델이 아니라, 모델을 둘러싼 **더 똑똑한 환경(Harness)** 이 성공을 결정한다.

모든 사용자 대화는 **한국어**로, 코드 주석은 **영어**로 작성한다.

## LLM 구조적 실패 모드와 대응

이 스킬이 해결하는 4가지 구조적 실패 패턴:

| 실패 모드               | 대응                                            |
| ----------------------- | ----------------------------------------------- |
| 세션 간 상태 유실       | `ADMOB_PROGRESS.md` + git log로 상태 복원       |
| 전체를 한번에 구현 시도 | Task State Machine — 한 번에 하나의 task만 작업 |
| 코드 작성 = 완료 선언   | Evaluator가 acceptance_criteria 기반 독립 검증  |
| 같은 접근 반복 루프     | Loop Detection — 동일 파일 5회 편집 시 개입     |

---

## Hard Gate

**가장 먼저** `docs/plan/ADMOB-PLAN.md` 파일 존재 여부를 확인한다.

파일이 없으면:

> "ADMOB-PLAN.md 파일이 존재하지 않습니다. 먼저 admob-plan 스킬로 계획 문서를 작성해주세요."

**즉시 종료.** 이후 어떤 구현도 진행하지 않는다.

---

## Phase 1: PLANNER (계획 분석)

코드를 한 줄도 작성하지 않는다. 환경을 읽고 구현 가능한 상태로 준비한다.

### 1.1 Readable Environment 구축

다음 파일을 순서대로 읽는다:

1. `docs/plan/ADMOB-PLAN.md` — 전체 정독. 구현 범위, 광고 타입, 배치 맵, Unit ID 목록, 빈도 캡핑 추출
2. `CLAUDE.md` — 기술 스택, 코딩 규칙, 디렉토리 구조
3. `package.json` — 설치된 의존성, 스크립트
4. `app.json` 또는 `app.config.ts` — Expo 설정, 기존 플러그인
5. `.env` / `.env.local` — 기존 AdMob 환경변수
6. `src/ads/` 디렉토리 탐색 — 이미 구현된 광고 코드 파악
7. `docs/plan/ADMOB_TASKS.json` — 이전 세션 task 상태 (있으면 재개, 없으면 신규 생성)

### 1.2 Context7 API 검증

훈련 데이터에 절대 의존하지 않는다. Context7 MCP로 최신 API를 조회한다.

1. `mcp__context7__resolve-library-id` 또는 `mcp__plugin_context7_context7__resolve-library-id`로 `react-native-google-mobile-ads` 라이브러리 ID를 조회
2. 다음 쿼리를 **병렬로** 실행:
   - `"BannerAd component props sizes adaptive banner"`
   - `"InterstitialAd createForAdRequest load show event listeners"`
   - `"RewardedAd createForAdRequest load show onUserEarnedReward"`
   - `"AppOpenAd createForAdRequest load show"`
   - `"mobileAds initialize requestConfiguration TestIds"`
   - `"useInterstitialAd useRewardedAd hooks"`

Context7와 ADMOB-PLAN.md가 API 세부사항에서 충돌하면 **Context7이 우선**한다.

Context7 호출 실패 시: ADMOB-PLAN.md 기준으로 진행하되, 최종 보고서에 "API 검증 미완료" 경고를 기록한다.

### 1.3 Task State Machine 생성

`ADMOB_TASKS.json`이 이미 존재하면 기존 상태를 로드한다 (세션 재개). 없으면 새로 생성한다.

ADMOB-PLAN.md의 모든 구현 항목을 개별 task로 분해하여 `docs/plan/ADMOB_TASKS.json`을 생성한다.

**핵심 규칙:**

- 모든 task의 status 기본값은 **`"fail"`** ("아직 통과하지 못함"이라는 부정적 상태)
- 각 task에 기계 판독 가능한 `acceptance_criteria` 포함
- task 우선순위(priority)는 ADMOB-PLAN.md의 구현 우선순위를 따름

스키마: `references/task_schema.json` 참조

**task 분해 기준** (ADMOB-PLAN.md에서 추출):

1. 패키지 설치 및 초기 설정
2. 환경변수 설정 (.env.local)
3. Ad Utility 모듈 (adUnitIds, adConfig)
4. SDK 초기화 (initAds)
5. 각 광고 타입별 컴포넌트/훅 (Banner, Interstitial, Rewarded, App Open)
6. 각 화면별 광고 배치 (MainScreen, LevelMapScreen, GamePlayScreen, GameResultScreen 등)
7. 빈도 캡핑 로직
8. 기존 광고 코드 정리 (종료 다이얼로그 배너 제거 등)

### 1.4 Progress 파일 초기화

`docs/plan/ADMOB_PROGRESS.md`를 생성(또는 업데이트)한다:

```markdown
# AdMob Implementation Progress

> Last Updated: YYYY-MM-DD HH:mm
> Total Tasks: N | Pass: 0 | Fail: N | Blocked: 0

## Current State

- 현재 상태 요약
- 다음 작업할 task ID와 제목

## Session Log

- [YYYY-MM-DD] 세션 시작. N개 task 생성.
```

이 파일은 다음 세션이 **30초 이내에** 프로젝트 상태를 재구성할 수 있어야 한다.

---

## Phase 2: TASK LOOP (Generator + Evaluator)

한 번에 하나의 task만 작업한다. 우선순위가 가장 높은 `status: "fail"` task부터 처리한다.

### Generator (구현)

**매 task 시작 전 — 오리엔테이션:**

1. `ADMOB_PROGRESS.md` + `git log --oneline -5` 확인 → 현재 상태 파악
2. `ADMOB_TASKS.json`에서 최우선 `"fail"` task 선택
3. 해당 task 관련 기존 코드 확인 (Incremental Implementation — 기존 코드 덮어쓰지 않음)

**구현 규칙:**

- 패키지 매니저 자동 감지: `yarn.lock` → yarn, `pnpm-lock.yaml` → pnpm, 기본 → npm. 패키지 설치는 `npx expo install` 사용
- Context7 검증 API 기반 구현
- 프로젝트의 기존 스타일링 방식을 따름 (CLAUDE.md 참조)
- TypeScript 필수, `@/` 절대 경로 임포트
- ADMOB-PLAN.md에 없는 항목은 임의로 추가하지 않음

**Architecture Enforcement:**

- 프로젝트의 기존 디렉토리 구조 및 네이밍 컨벤션을 따름
- 광고 컴포넌트는 `src/ads/` 하위에 배치
- 단방향 의존성: 광고 컴포넌트가 비즈니스 로직에 의존하지 않음
- 기존 코드베이스의 좋은 패턴을 따르되, 안티 패턴은 복제하지 않음

**구현 상세 가이드:** `references/generator_guide.md` 참조

**Loop Detection:**

- 동일 파일을 **5회 이상** 편집할 경우: 현재 접근을 중단하고 완전히 다른 접근 시도, 또는 사용자에게 보고
- 동일 에러를 **3회 이상** 반복 시: 해당 task를 `"blocked"`로 표시하고 다음 task로 이동

### Evaluator (검증)

Generator가 구현을 마치면, 역할을 전환하여 **독립적이고 회의적으로** 검증한다.

**검증 체크리스트 — 모든 항목 통과해야 pass:**

1. **Acceptance Criteria**: `ADMOB_TASKS.json`의 해당 task의 모든 criteria를 파일 내용을 직접 확인하여 검증
2. **TypeScript 컴파일**: `npx tsc --noEmit` 실행하여 타입 에러 없음 확인
3. **아키텍처 준수**: 파일 배치 컨벤션, import 경로, 스타일링 패턴 확인
4. **회귀 없음**: 기존 코드에 대한 부작용 없음 확인

**검증 결과 처리:**

- **통과**: `ADMOB_TASKS.json`에서 해당 task status를 `"pass"`로 변경
- **실패**: 구체적이고 실행 가능한 피드백 기록 후 Generator 재시도 (최대 2회)
- **2회 재시도 후 실패**: `"blocked"` 표시, 사용자에게 에스컬레이션

**상세 검증 가이드:** `references/evaluator_guide.md` 참조

### Task 완료 처리

Evaluator 검증 통과 후에만:

1. `ADMOB_TASKS.json`에서 status → `"pass"`
2. `ADMOB_PROGRESS.md` 업데이트 (pass/fail 카운트, 로그)
3. `git push`는 **절대 자동 실행하지 않음**

다음 `"fail"` task로 반복한다.

---

## Phase 3: 최종 보고

모든 task 처리 완료 후 `docs/plan/ADMOB_IMPL_REPORT.md`를 생성한다:

```markdown
# AdMob 구현 리포트

> Implemented: YYYY-MM-DD HH:mm
> Based on: ADMOB-PLAN.md (Last Updated: <plan 타임스탬프>)

## 구현 요약

- 설치된 패키지 목록 및 버전
- 구현된 광고 유형 및 배치 위치
- 수정된 파일 목록

## Task 최종 상태

| Task ID | 제목 | Status | 비고 |
| ------- | ---- | ------ | ---- |

## 미구현 항목 및 사유

## Changelog

## 다음 단계
```

---

## 기계적 제약 (절대 규칙)

이 규칙들은 어떤 상황에서도 재정의할 수 없다:

1. **"한 번에 하나의 task"** — Generator는 절대 여러 task를 동시에 작업하지 않는다
2. **"criteria 삭제 금지"** — acceptance_criteria를 수정하거나 삭제하지 않는다
3. **"검증 없이 pass 금지"** — Evaluator 검증 통과 후에만 status를 "pass"로 변경한다
4. **"스텁 금지"** — TODO, placeholder, mock 구현으로 task를 통과시키지 않는다
5. **"진행 기록 필수"** — 매 task 완료 시 ADMOB_PROGRESS.md 업데이트를 누락하지 않는다
6. **"JSON 형식 유지"** — ADMOB_TASKS.json은 항상 유효한 JSON 형식을 유지한다
7. **"재시도 상한"** — 동일 task 최대 2회 재시도 후 "blocked" 처리 및 사용자 에스컬레이션
8. **"git push 금지"** — 자동으로 git push를 실행하지 않는다

왜 이 규칙이 필요한가: 에이전트는 컨텍스트가 쌓이면 "거의 됐으니 넘어가자"는 유혹에 빠지기 쉽다. 기계적 제약은 이 경향을 구조적으로 차단한다.

---

## 산출물

| 파일                             | 생성 시점 | 용도               |
| -------------------------------- | --------- | ------------------ |
| `docs/plan/ADMOB_TASKS.json`     | Phase 1   | Task State Machine |
| `docs/plan/ADMOB_PROGRESS.md`    | Phase 1   | 세션 간 인수인계   |
| `docs/plan/ADMOB_IMPL_REPORT.md` | Phase 3   | 최종 구현 보고서   |
| `src/ads/**`                     | Phase 2   | 광고 구현 코드     |

---

## 참고 자료

- `references/task_schema.json` — ADMOB_TASKS.json 스키마 및 예시
- `references/generator_guide.md` — Generator 구현 상세 가이드
- `references/evaluator_guide.md` — Evaluator 검증 상세 가이드
