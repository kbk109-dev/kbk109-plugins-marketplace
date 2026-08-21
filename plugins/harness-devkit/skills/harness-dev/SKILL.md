---
name: harness-dev
description: "3-에이전트 아키텍처(Planner-Generator-Evaluator) 기반 자율 개발 워크플로. 복잡한 앱/서비스 요구사항을 스프린트 단위로 분해하고, 각 스프린트마다 구현→독립 평가→피드백 루프를 실행하여 품질을 보장합니다. 반드시 이 스킬을 사용해야 하는 경우: 'harness-dev', '하네스 개발', '3-에이전트로 만들어줘', '복잡한 앱 만들어줘', '풀스택 개발', '대규모 기능 구현', '스프린트로 나눠서 개발해줘', '단계별로 구현하고 평가해줘', '계획-구현-평가 루프', 'generator-evaluator 패턴', '제대로 된 앱 만들어줘', '품질 높게 개발해줘', '평가까지 해줘', 'build a complex app', 'full-stack development with evaluation', 'sprint-based development with quality gates', 'plan-implement-evaluate loop'. 한 문장짜리 요구사항이지만 기능이 5개 이상 필요해 보이는 복잡한 빌드 요청에도 사용. 단순 버그 수정, 한 파일 리팩토링, 간단한 스크립트, 질문/답변에는 사용하지 않음."
---

# Harness-Dev: 3-에이전트 자율 개발 워크플로

## 철학

"더 똑똑한 모델이 아니라, 모델을 둘러싼 더 똑똑한 환경"

에이전트 실패의 5가지 패턴을 구조적으로 방지한다:

1. **한 번에 모든 것 처리** → 스프린트 단위 분해로 해결
2. **컨텍스트 불안** → progress.md로 세션 연속성 확보
3. **조기 성공 선언** → 독립 Evaluator가 검증
4. **자기 평가 편향** → Generator의 자체 평가는 참고만, Evaluator 판단이 최종
5. **목표 표류** → Ralph Loop 패턴으로 매 스프린트 목표 재주입

---

## Phase 0: 복잡도 판단

요구사항을 받으면 먼저 이 스킬이 적합한지 판단한다.

**이 스킬을 사용하는 경우:**

- 기능이 5개 이상 필요한 앱/서비스 빌드
- 여러 모듈이 서로 의존하는 복잡한 구현
- 품질 게이트가 필요한 대규모 개발

**일반 개발로 전환하는 경우:**

- 단순 버그 수정, 단일 파일 리팩토링
- 간단한 스크립트, 질문/답변, 문서 작성
- 기능 3개 이하의 소규모 작업

---

## Phase 0.5: 상태 복원 (재개할 때만)

`docs/harness/` 아래에 폴더가 이미 있으면 **새로 시작하는 것이 아니다.** 진행 중이던 작업을
이어받는 것이므로, 상태를 복원하기 전에는 아무것도 구현하지 않는다.

```bash
ls docs/harness/                       # 진행 중인 slug 목록
```

해당 slug 폴더에서 **`progress.md` → `feature_list.json` 순으로 읽는다.** progress.md 가 어디까지
갔는지 말해 주고, feature_list.json 이 무엇이 남았는지 말해 준다.

**상태 파일 확인 없이 Phase 2 로 진행하지 않는다.** LLM 은 세션 간 영구 메모리가 없어서, 복원을
건너뛰면 이미 끝난 기능을 다시 만들거나 끝나지 않은 기능을 끝난 것으로 취급한다 — 상태를 파일로
외부화한 이유가 그것을 막는 것인데, 읽지 않으면 외부화가 무의미하다.

slug 가 여러 개면 어느 것을 이어갈지 사용자에게 묻는다. 새 작업이면 Phase 1 로 간다.

---

## Phase 1: PLANNER (계획 에이전트)

사용자의 1~4문장 요구사항을 완전한 제품 사양으로 확장한다.

### 수행 순서

1. **프로젝트 슬러그(slug) 생성** — 요구사항의 핵심을 2~4단어 영문 kebab-case로 요약
   - 예: `todo-manager`, `retro-game-maker`, `realtime-chat`
   - `docs/harness/` 아래에 동일 이름 폴더가 이미 있으면 숫자 접미사 추가 (`todo-manager-2`)
   - 이 slug가 `docs/harness/{slug}/` 프로젝트 전용 폴더명이 됨
2. 요구사항을 개별 기능(feature) 목록으로 분해
3. `docs/harness/{slug}/feature_list.json` 생성 (`references/feature_list_template.json` 참조)
4. 기능을 스프린트에 배분 (1 스프린트 = 2~4개 기능)
5. `docs/harness/{slug}/project_spec.md` 생성 (전체 제품 사양, 기술 스택, 디자인 방향, 제약 조건)
6. `docs/harness/{slug}/progress.md` 초기화

### 핵심 원칙

- 구현 세부사항을 과도하게 명시하지 않는다 (상위 단계 오류가 전체에 영향)
- 제품 범위와 전반적 방향에 집중한다
- 기능 수는 복잡도에 비례: 단순 5~8개, 중간 10~15개, 복잡 15~25개

### 기능 분해 기준

각 기능에 반드시 포함할 필드:

- `id`: F001, F002, ... 형식
- `name`: 기능명
- `description`: 상세 설명
- `acceptance_criteria`: 통과/실패 판단 기준 (구체적, 측정 가능, 수정/삭제 불가)
- `priority`: high / medium / low
- `sprint`: 스프린트 번호
- `status`: `"fail"` (기본값 — 에이전트는 통과를 *증명*해야 한다). 허용값은 `fail`/`pass`/`blocked`
- `attempts`: 재시도 횟수. `0` 으로 시작하고 재작업할 때마다 +1 — 제약 7 의 상한을 파일에
  남기기 위한 필드다. 세션 안에만 있으면 세션이 끊길 때 카운터가 사라진다
- `dependencies`: 선행 기능 ID 목록

### 사용자 확인 (필수)

Planner 완료 후, feature_list.json과 스프린트 계획을 사용자에게 보여주고 확인을 받는다:

> "이 계획으로 진행할까요? 수정할 부분이 있으면 알려주세요."

사용자 승인 없이 Phase 2로 넘어가지 않는다.

### 승인 직후 (필수)

승인을 받은 **뒤에** 두 가지를 실행한다. 순서가 중요하다 — 승인 전에 잠그면 사용자의 계획 수정이
그대로 제약 위반으로 잡힌다.

```bash
# 1. acceptance_criteria 잠금 생성 — 제약 2 를 검사 가능하게 만든다
python3 ${CLAUDE_PLUGIN_ROOT}/skills/harness-dev/scripts/validate_feature_list.py \
  docs/harness/{slug}/feature_list.json --update-lock

# 2. 작업 규율을 대상 프로젝트의 AGENTS.md 에 설치 (멱등, 이미 있으면 그대로)
python3 ${CLAUDE_PLUGIN_ROOT}/skills/harness-dev/scripts/harness_agents_block.py \
  --install --project-root .
```

`--update-lock` 은 잠금을 새로 쓰는 **유일한** 경로다. 스프린트 도중에 부르면 제약 2 가
무의미해지므로 여기서만 쓴다.

2번 블록은 **항구적 규약이지 진행 기록이 아니다.** slug 도 "진행 중" 도 쓰지 않는다 — 그건
`docs/harness/*/` 를 보면 아는 사실이고, 두 번째 사본을 만들면 중단된 작업에서 AGENTS.md 가 틀린
지시를 하게 된다. 그래서 작업이 끝나도 **제거하지 않는다.** 코드가 검사할 수 없는 제약
1·3·5 가 컨텍스트 압축을 견디게 하는 것이 이 블록의 유일한 목적이다.

---

## Phase 2~N: Sprint Loop (Generator → Evaluator)

각 스프린트마다 Generator가 구현하고, Evaluator가 독립적으로 평가한다.

### Generator (구현 에이전트)

**매 스프린트 시작 시 (Ralph Loop 패턴):**

1. `docs/harness/{slug}/progress.md` 읽기 — 이전 스프린트 결과 파악
2. `docs/harness/{slug}/feature_list.json` 읽기 — 현재 스프린트 대상 기능 확인
3. **목표 재주입** — feature_list에서 현재 스프린트의 대상 기능과 acceptance_criteria를 명시적으로 재선언 (목표 표류 방지)
4. 스프린트 "완료 기준"을 명시적으로 선언 (스프린트 계약)
5. **한 번에 하나의 기능만 작업** (가장 중요한 규칙)

**Reasoning Sandwich (추론 노력 차등 배분):**

- **계획 단계**: 최대 노력 (꼼꼼한 분석, 전략 수립)
- **구현 단계**: 중간 노력 (코드 작성에 집중)
- **검증 단계**: 최대 노력 (코드가 작성되었다고 추론을 생략하지 않음)

**구현 규칙:**

- 각 기능 구현 후 즉시 동작 테스트 수행
- 실제 동작 확인 후에만 기능을 "pass"로 표시
- 스텁(stub), TODO, placeholder, mock 구현 금지 — 모든 기능은 실제로 동작해야 함
- 기능 간 의존성 순서 준수

**Loop Detection:**

- 동일 파일을 5회 이상 수정하면 루프로 간주
- 즉시 현재 접근을 중단하고, 완전히 다른 접근 시도
- 2번의 접근 전환 후에도 실패 → 사용자에게 에스컬레이션

**매 스프린트 종료 시:**

1. `docs/harness/{slug}/feature_list.json` 업데이트 — status를 "pass" 또는 유지("fail"),
   재시도했다면 `attempts` 증가
2. `docs/harness/{slug}/progress.md` 업데이트 — 작업 요약, 이슈, 다음 스프린트 참고사항
3. **검증 실행** — 통과해야 스프린트가 끝난다

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/harness-dev/scripts/validate_feature_list.py \
  docs/harness/{slug}/feature_list.json
```

종료코드 1(위반 있음)이면 스프린트는 끝나지 않았다. 위반을 고치고 다시 돌린다. 이 검사는
PreToolUse 훅과 같은 규칙을 쓰므로, 훅이 쓰기를 막았다면 여기서도 잡힌다.

상세 가이드: `references/generator_guide.md` 참조

### Evaluator (평가 에이전트)

Generator 완료 후, 역할을 전환하여 독립적·회의적으로 평가한다.

**채점 전에 기계 검사를 먼저 돌린다.** 사람의(모델의) 판단보다 앞에 두는 이유는 제약 2·4·6·7·8 이
점수 매길 대상이 아니라 통과/실패이기 때문이다 — 여기서 걸리면 채점할 것도 없다.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/harness-dev/scripts/validate_feature_list.py \
  docs/harness/{slug}/feature_list.json --stubs <구현 경로>
```

출력 JSON 을 그대로 `sprint_reports/sprint_XX_eval.md` 에 붙인다. 위반이 있으면 **기능성·완성도를
7점 미만으로 두고 스프린트 실패로 판정한다.** 특히 제약 4(스텁)는 Evaluator 가 눈으로 놓치기
쉬운데 `--stubs` 가 파일:줄 단위로 짚어 준다.

**평가 5기준 (각 0~10점):**

| 기준                     | 설명                                                     | 실패 임계값 |
| ------------------------ | -------------------------------------------------------- | ----------- |
| 기능성 (Functionality)   | acceptance_criteria 충족 여부                            | < 7점       |
| 완성도 (Completeness)    | 스텁이나 미구현 없이 완전한가                            | < 7점       |
| 코드 품질 (Code Quality) | 구조, 가독성, 유지보수성                                 | < 7점       |
| 디자인/UX (Design)       | UI가 있는 경우에만 평가                                  | < 7점       |
| 독창성 (Originality)     | 기존 패턴의 단순 복제가 아닌 요구사항에 맞는 창의적 구현 | < 7점       |

**어느 기준이든 7점 미만이면 스프린트 실패.**

**PreCompletion Checklist (PASS 판정 전 필수):**

1. 모든 acceptance_criteria 테스트 통과 여부
2. 기존 기능에 대한 회귀(regression) 없음
3. 엔드투엔드 흐름 검증 완료

**평가 원칙:**

- "회의적 평가자" 톤 유지 — 관대한 점수 금지
- 겉보기에 작동하는 것과 실제로 작동하는 것을 구분
- 가능한 경우 실제 실행하여 검증 (HTML → 브라우저, 코드 → 실행)
- 사소한 문제는 넘어가되, 사용자 경험에 영향을 미치는 문제는 반드시 지적

**실패 시:**

- 구체적이고 실행 가능한 피드백 제공 (문제 위치, 원인, 수정 방향)
- Generator에게 재작업 지시 (최대 2회 재시도)

**2회 재시도 후에도 실패:**

- 사용자에게 상황 보고 후 판단 요청
  > "이 기능에서 반복적으로 실패하고 있습니다. [구체적 이슈]. 어떻게 진행할까요?"

상세 가이드: `references/evaluator_guide.md` 참조

### Sprint Loop 흐름

```
스프린트 N 시작
    │
    ▼
[Generator] progress.md + feature_list.json 읽기 + 목표 재주입 (Ralph Loop)
    │
    ▼
[Generator] 기능 하나씩 구현 + 동작 확인 (Reasoning Sandwich 적용)
    │
    ▼
[Generator] feature_list.json + progress.md 업데이트
    │
    ▼
[Evaluator] PreCompletion Checklist + 5기준 독립 평가
    │
    ├── PASS (모든 기준 ≥ 7점) → 다음 스프린트
    │
    └── FAIL → 피드백 + Generator 재작업
              │
              ├── 재시도 1~2회 → 재평가
              │
              └── 2회 실패 → 사용자에게 에스컬레이션
```

---

## Phase Final: 종합 보고

모든 스프린트 완료 후:

1. **최종 검증 1회** — 종료코드 0 이 아니면 완료로 보고하지 않는다

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/harness-dev/scripts/validate_feature_list.py \
     docs/harness/{slug}/feature_list.json --stubs <구현 경로>
   ```

2. 전체 평가 요약 작성
3. `docs/harness/{slug}/feature_list.json` 최종 상태 제시
4. 산출물 목록 정리
5. 남은 이슈나 개선 제안사항 제시

**AGENTS.md 규율 블록은 제거하지 않는다.** 실행이 아니라 프로젝트에 붙는 항구적 규약이고, 다음
harness 작업에서 그대로 쓰인다. 이 프로젝트에서 harness-dev 를 더 쓰지 않기로 했다면 사용자가
`harness_agents_block.py --remove` 로 직접 지운다.

---

## 8가지 기계적 제약 (절대 규칙)

이 규칙들은 어떤 상황에서도 재정의할 수 없다. 대괄호는 **무엇이 이 규칙을 실제로 지키게 하는지**다.

1. **"한 번에 하나의 기능"** — Generator는 절대 여러 기능을 동시에 작업하지 않음 `[판단]`
2. **"테스트 삭제 금지"** — acceptance_criteria를 수정하거나 삭제하는 것은 허용되지 않음 `[훅+스크립트]`
3. **"자기 평가 불신"** — Generator의 자체 평가는 참고만, Evaluator의 평가가 최종 판단 `[판단]`
4. **"스텁 금지"** — TODO, placeholder, mock 구현으로 기능을 통과시키지 않음 `[스크립트 --stubs]`
5. **"진행 기록 필수"** — 매 스프린트 종료 시 progress.md 업데이트 누락 불가 `[판단]`
6. **"JSON 형식 유지"** — feature_list.json은 항상 JSON 형식 유지, Markdown 변환 금지 `[훅+스크립트]`
7. **"재시도 상한"** — 동일 스프린트 최대 2회 재시도 후 사용자에게 에스컬레이션 `[훅+스크립트]`
8. **"status 기본값은 fail"** — 모든 새 기능의 status는 "fail"로 시작. "pending"은 존재하지 않음. 통과를 증명해야만 "pass"로 전환 `[훅+스크립트]`

`[훅]` 은 `feature_list.json` 쓰기를 가로채는 PreToolUse 훅이다 — 모델이 무엇을 기억하는지와
무관하게 발화하지만, 같은 호출을 다시 하면 통과시킨다(플러그인 훅이 전역 발화해도 안전하려면
차단이 복구 가능해야 한다). 그래서 훅은 지름길을 **불가능하게** 만들지 않고 **의도적인 선택으로**
바꾼다. 불가능하게 만드는 쪽은 스프린트마다 돌리는 검증 스크립트이고, 사람이 그 결과를 본다.

`[판단]` 셋은 코드가 볼 수 없다. 이 셋만 대상 프로젝트 AGENTS.md 의 규율 블록이 담당한다 —
컨텍스트가 압축돼 이 문서가 빠져도 AGENTS.md 는 매 턴 다시 로드되기 때문이다.

왜 이 규칙이 필요한가: 에이전트는 컨텍스트가 쌓이면 "거의 됐으니 넘어가자"는 유혹에 빠지기 쉽다. 기계적 제약은 이 경향을 구조적으로 차단한다. acceptance_criteria 수정을 허용하면 어려운 기능을 "쉽게 통과"시키는 지름길이 되고, 스텁을 허용하면 "겉으로만 완성"된 프로젝트가 된다.

---

## 5-Component Harness Framework

3-에이전트 아키텍처를 지탱하는 환경 설계 원칙. 각 컴포넌트는 LLM의 구조적 실패 모드를 시스템 수준에서 해결한다. 상세: `references/harness_framework.md`

1. **Readable Environment** — slug 폴더 기반 점진적 정보 공개. feature_list.json + progress.md로 30초 내에 프로젝트 상태 재구성
2. **Task State Machine** — 각 기능의 status가 `fail` → `pass` 또는 `fail` → `blocked`로만 전이. "pending"은 존재하지 않음
3. **Verification Loop** — Generator 구현 → Evaluator 독립 검증의 반복. PreCompletion Checklist 강제
4. **Architecture Enforcement** — 프로젝트 구조/컨벤션 준수를 기계적으로 강제. 첫 스프린트부터 규율 적용
5. **Loop Detection** — 동일 파일 5회+ 편집 시 현재 접근 중단, 완전히 다른 방법 시도

---

## 파일 구조

프로젝트별로 `docs/harness/{slug}/` 전용 폴더를 생성하여 격리한다:

```
<project-root>/
├── docs/harness/
│   └── {slug}/                      ← 프로젝트 전용 폴더
│       ├── feature_list.json        ← 기능 목록 (JSON, Planner 생성)
│       ├── .criteria_lock.json      ← acceptance_criteria 지문 (승인 직후 1회 생성)
│       ├── project_spec.md          ← Planner 산출물
│       ├── progress.md              ← 세션 간 인수인계 로그
│       └── sprint_reports/          ← 스프린트별 평가 보고서
│           ├── sprint_01_eval.md
│           └── ...
└── src/                             ← 실제 구현 코드
```

**기존 프로젝트에서 사용하는 경우:** `docs/harness/{slug}/`를 생성하고, 기존 코드 구조 내에서 구현한다. 기존 파일 구조를 존중한다.

**복수 프로젝트 격리:** 서로 다른 프로젝트의 파일은 절대 혼재하지 않는다. 각 slug 폴더가 독립 단위이다.

---

## 출력 언어

- 사용자와의 대화: 사용자 언어에 맞춤 (기본: 한국어)
- feature_list.json, progress.md, sprint_reports: 사용자 언어
- project_spec.md: 한국어 (기술 용어는 영어 병기)
- 코드 및 주석: 영어
- 사용자가 영어로 요청하면 전체 영어로 전환

---

## 기술 스택별 Evaluator 검증 방식

| 프로젝트 유형       | 검증 방법                              |
| ------------------- | -------------------------------------- |
| HTML/CSS/JS 웹앱    | 브라우저 렌더링으로 시각적 검증        |
| React/React Native  | 코드 구조 + 로직 검증 + 빌드/lint 확인 |
| Python 스크립트/API | 실행하여 출력 검증                     |
| 일반 코드           | 정적 분석 + 로직 리뷰 + 테스트 실행    |

가능한 한 실제 실행으로 검증한다. 환경 제약이 있으면 코드 리뷰 기반으로 평가하되, 그 한계를 명시한다.

---

## 참고 자료

- `references/feature_list_template.json` — feature_list.json 템플릿
- `references/generator_guide.md` — Generator 상세 가이드 (Ralph Loop, Reasoning Sandwich, Loop Detection 포함)
- `references/evaluator_guide.md` — Evaluator 상세 가이드 (PreCompletion Checklist, 평가 보고서 템플릿 포함)
- `references/harness_framework.md` — 5-Component Harness Framework 상세 가이드
