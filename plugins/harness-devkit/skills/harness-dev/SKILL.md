---
name: harness-dev
description: "Drives a product from idea to QA — PRD, PLAN, per-epic feature_list.json, TC, build, evaluate — through fresh per-stage subagents, saving state under docs/harness/<slug>/ so any new session resumes. Needs no prior plan file (fallback when no domain skill fits). Trigger: '복잡한 앱 만들어줘', '스프린트로 나눠서 개발해줘', '계획-구현-평가 루프', 'PRD 부터 QA 까지'. Not for a single bug fix, one-file refactor, or Q&A."
---

# Harness-Dev: PRD 에서 QA 까지 — 단계별 서브에이전트 하네스

"더 똑똑한 모델이 아니라, 모델을 둘러싼 더 똑똑한 환경"

이 스킬의 메인 세션은 **얇은 오케스트레이터**다. 단계마다 새 서브에이전트가 일하고(컨텍스트 리셋),
세션 사이의 연속성은 전부 `docs/harness/<slug>/` 의 파일이 맡는다. 메인이 직접 하는 일은 셋뿐이다 —
사용자와의 대화(인터뷰·승인·에스컬레이션), 서브에이전트 호출 순서 지휘, 상태 파일 갱신.

방지하는 실패: 한 번에 다 하기 · 컨텍스트 불안 · 조기 성공 선언 · 자기평가 편향 · 목표 표류.
설계 근거는 `docs/adr/0001-per-stage-subagents-thin-orchestrator.md`, 용어는 `CONTEXT.md`.

## 0. 적합성

기능이 5개 이상이거나 여러 모듈이 얽힌 제품 빌드에 쓴다. 단순 버그 수정·단일 파일 리팩토링·
질의응답·기능 3개 이하는 일반 개발로 처리한다.

## 1. 매 진입의 첫 동작 — 상태 판정

새 시작이든 재개든 **먼저** 이것을 실행한다. 판정은 코드가 한다 — 모델이 판정하면 재진입할 때마다
달라진다. 이 출력을 읽기 전에는 아무것도 구현하지 않는다.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/harness-dev/scripts/harness_state.py status docs/harness
```

출력 `{slug, stage, epic, epic_dir, feature, round, reason}` 의 `stage` 로 아래 표를 따른다.
`stage: choose` 면 `candidates` 중 어느 것을 이어 갈지 사용자에게 묻고 `--slug` 를 붙여 다시 실행한다.
새 제품이면 slug 는 `harness_state.py slug "<제품 이름>" docs/harness` 로 정한다 (직접 만들면 호출마다 달라진다).

| stage | 하는 일 |
|---|---|
| `interview` | §3 인터뷰 → `BRIEF.md` |
| `prd-draft` / `prd-revise` | `prd-writer` 호출 |
| `prd-critic` | `prd-critic` 호출 |
| `prd-approval` | §4 문서 승인 |
| `plan-draft` / `plan-revise` | `planner` 호출 |
| `plan-critic` | `plan-critic` 호출 |
| `plan-approval` | §4 문서 승인 (`validate_harness_doc.py plan` 통과 필수) |
| `feature-plan` | `feature-planner` 호출 |
| `epic-approval` | §5 에픽 승인 |
| `tc-draft` / `tc-revise` | `tc-writer` 호출 |
| `tc-critic` | `tc-critic` 호출 |
| `tc-lock` | §6 TC 확정 |
| `dev` | §7 개발·QA 릴레이 (기능 1개) |
| `escalate` | §8 사용자 판단 |
| `epic-close` | `references/epic_close.md` 의 절차 |
| `final` | §9 종합 보고 |

한 번의 진입에서 서브에이전트를 한 단계만 부르고 `harness_state.py` 를 다시 실행해 다음 stage 로
간다. 사용자 승인 stage 에 닿으면 멈춘다. 에픽 하나가 끝나면 **새 세션을 권하고** 멈춘다 — 메인
컨텍스트가 에픽을 넘어 쌓이는 것을 끊기 위해서다.

## 2. 서브에이전트 호출

서브에이전트는 `harness-devkit:<이름>` 으로 Agent 도구로 부른다. 에이전트 문서는 플러그인 루트
`agents/` 에 있다. **프롬프트에 절대 경로를 직접 넣는다** — 서브에이전트는 이 대화를 모른다.

| 키 | 값 |
|---|---|
| `product_dir` | `<프로젝트>/docs/harness/<slug>` 절대 경로 |
| `epic_dir` | `<product_dir>/epics/<NN-slug>` (에픽 단계에서) |
| `refs_dir` | 이 스킬의 `references/` 절대 경로 |
| `project_root` | 프로젝트 루트 |
| `round` · `feature_id` · `mode` | 해당 단계가 필요로 할 때 |

서브에이전트의 마지막 메시지는 한 줄 JSON `{"status","artifact","summary"}` 하나다. 상세는 그 파일에
있으니 메인은 JSON 만 읽는다 (메인 컨텍스트 보호). 호출이 끝날 때마다 `PROGRESS.md` 에 한 줄 덧붙인다:
`- <일시> <stage> → <status> (<artifact>)`.

| 에이전트 | 단계 | 산출 |
|---|---|---|
| `prd-writer` · `prd-critic` | PRD | `PRD.md` · `reviews/prd-critic-r{N}.md` |
| `planner` · `plan-critic` | PLAN | `PLAN.md` · `reviews/plan-critic-r{N}.md` |
| `feature-planner` | 에픽 분해 | `epics/<NN>/feature_list.json` |
| `tc-writer` · `tc-critic` | TC | `epics/<NN>/TC.md` · `reviews/tc-critic-r{N}.md` |
| `generator` | 구현 | 코드 · `sprint_contracts/<FID>.md` |
| `evaluator` | QA | `logs/<FID>/` · `eval/<FID>.md` · status 기록 |

서브에이전트는 사용자와 대화할 수 없고 다른 서브에이전트를 부를 수 없다. 그래서 대화는 메인이,
generator→evaluator 릴레이도 메인이 지휘한다.

## 3. 인터뷰 (`interview`)

`/mattpocock-skills:grill-with-docs` 가 사용 가능하면 그것을 호출한다. 설계 트리를 라운드로 돌며
공유 이해에 닿을 때까지 묻고, 용어와 ADR 은 그 스킬이 프로젝트의 `CONTEXT.md`·`docs/adr/` 에 쓴다.
없는 환경이면 같은 방식을 직접 한다 — 질문마다 추천안을 붙이고, 사실(코드·파일·도구)은 사용자에게
묻지 않고 직접 조사하고, AskUserQuestion 으로 결정을 받는다.

끝나면 결정 사항을 `docs/harness/<slug>/BRIEF.md` 로 정리한다 (문제·사용자·범위·비목표·제약·
성공 기준·열린 질문). 이 파일이 새 세션의 `prd-writer` 가 읽는 **유일한** 요구사항 출처다 —
대화에만 있는 결정은 세션이 끊기면 사라진다.

## 4. 문서 승인 (PRD · PLAN)

critic 루프는 최대 2라운드다 (writer → critic → revise → critic). 2라운드 뒤에도 REVISE 면
`unresolved_blocking: true` 로 온다 — 남은 blocking 을 사용자에게 **그대로** 보여 주고 판단을 받는다.

1. 문서 경로와 critic 의 최근 리뷰 요약(blocking·non-blocking)을 사용자에게 보여 준다.
2. PLAN 이면 먼저 `validate_harness_doc.py plan <PLAN.md>` 를 돌려 exit 0 을 확인한다 (Run & Verify
   누락이면 승인을 묻지 않고 `planner` 로 되돌린다). PRD 면 `validate_harness_doc.py prd <PRD.md>`.
3. 승인되면 **메인이** 문서 frontmatter 를 `status: approved` 로 바꾼다. 수정 요청이면 요청을 반영해
   `*-revise` 로 돌린다 (사용자 수정은 critic 라운드 수에 세지 않는다 — `reviews/` 에 새 파일이 없으면
   상태 판정이 그대로 `*-approval` 이므로, 수정 후 다시 `prd-writer`/`planner` 를 직접 부른다).

## 5. 에픽 승인 (`epic-approval`)

`feature_list.json` 과 에픽 요약을 보여 주고 승인을 받는다. 승인 **뒤에** 실행한다 — 승인 전에
잠그면 사용자의 수정이 제약 위반으로 잡힌다.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/harness-dev/scripts/validate_feature_list.py \
  <epic_dir>/feature_list.json --update-lock
python3 ${CLAUDE_PLUGIN_ROOT}/skills/harness-dev/scripts/harness_agents_block.py \
  --install --project-root .
```

`--update-lock` 은 `acceptance_criteria` 잠금을 쓰는 **유일한** 경로다. AGENTS.md 규율 블록은
항구적 규약이라 에픽이 끝나도 제거하지 않는다.

## 6. TC 확정 (`tc-lock`)

TC 는 사람 승인이 아니라 `tc-critic` 의 PASS 가 확정한다. 메인은 모양과 추적성을 검사하고 잠근다:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/harness-dev/scripts/validate_harness_doc.py tc \
  <epic_dir>/TC.md --feature-list <epic_dir>/feature_list.json
python3 ${CLAUDE_PLUGIN_ROOT}/skills/harness-dev/scripts/validate_harness_doc.py tc-lock <epic_dir>/TC.md
```

검사가 실패하면 잠그지 않고 `tc-writer` 로 되돌린다. 잠긴 뒤 TC.md 가 바뀌면 stage 가 `escalate` 가
된다 — 기준을 완화해 통과시키는 지름길을 막는 장치다. 바꿔야 하면 사용자와 상의해 `.tc_lock.json`
을 지우고 `tc-critic` 재검토를 거친다.

## 7. 개발·QA 릴레이 (`dev`)

`feature` 하나마다 아래를 돈다. 이 한 번의 진입에서 기능 하나만 처리한다.

1. `generator` 호출 (`epic_dir`, `feature_id`, 재시도면 직전 `eval/<FID>.md`) → `generator-done`
2. `evaluator` 호출 (`epic_dir`, `feature_id`) → `pass` | `fail` | `blocked`
3. `fail` 이면 1 로 돌아간다 (`attempts` 가 2 가 될 때까지). evaluator 가 3번째 FAIL 에서 `blocked`
   로 기록하면 §8 로 간다. `generator` 가 `error` 를 반환해도 같다.
4. `pass` 면 `PROGRESS.md` 를 갱신하고 `harness_state.py status` 를 다시 실행한다.

메인은 `feature_list.json` 의 `status` 를 직접 쓰지 않는다. `pass` 를 기록할 수 있는 것은 evaluator
뿐이고, 그 증거는 `logs/<FID>/*.log` 와 `eval/<FID>.md` 의 `VERDICT: PASS` 다.

## 8. 에스컬레이션 (`escalate`)

`reason` 을 그대로 사용자에게 보고하고 판단을 받는다: 재시도 한도를 넘은 blocked 기능, 의존이
풀리지 않는 기능, tc-critic 이 2라운드 뒤에도 REVISE, TC 잠금 위반. 선택지를 준다 — 요구사항·TC 를
고쳐 다시 시도(`blocked → fail`) / blocked 인정하고 계속(`blocked_ack.md` 작성) / 중단.

## 9. 종합 보고 (`final`)

모든 에픽의 `CLOSED.md` 와 `eval/EPIC.md` 를 읽어 보고한다: PRD 요구사항별 충족 여부, 남은 이슈,
blocked 인정 사항, 다음 제안. 보고에 근거가 없는 항목(로그·리포트 없음)은 "미검증" 으로 쓴다.

## 10. 레거시 레이아웃 (`docs/harness/<slug>/feature_list.json` 이 최상위에 있는 1.x 작업)

stage 가 `epic-approval` / `dev` / `epic-close` / `final` 로 오며 `epic` 은 `legacy` 다. `epic_dir` 는
slug 디렉토리 자체다. TC.md 가 없으므로 evaluator 는 `acceptance_criteria` 를 직접 검증한다.
`progress.md`(소문자)를 상태 기록으로 쓴다. 새 작업은 항상 2.0 레이아웃으로 시작한다.

## 11. 기계적 제약 (재정의 불가)

대괄호는 **무엇이 이 규칙을 실제로 지키게 하는지**다.

1. **한 번에 하나의 기능** — generator 는 기능 하나만 `[판단]`
2. **acceptance_criteria 수정·삭제 금지** `[훅+스크립트]`
3. **자기 평가 불신** — 판정은 evaluator 의 것 `[판단]`
4. **스텁 금지** — TODO·placeholder 로 통과시키지 않음 `[스크립트 --stubs]`
5. **진행 기록 필수** — `PROGRESS.md` 갱신 `[판단]`
6. **JSON 유지** `[훅+스크립트]`
7. **재시도 상한 2회** 뒤 에스컬레이션 `[훅+스크립트]`
8. **status 기본값 fail**, 허용값은 `fail`/`pass`/`blocked` `[훅+스크립트]`
9. **pass 는 evaluator 만 기록한다** (v2 파일) `[훅]` — 스크립트는 작성자를 알 수 없어 보지 못한다
10. **status 전이는 `fail→pass`, `fail→blocked`, `blocked→fail` 뿐** `[훅+스크립트 --prev]`
11. **pass 는 증거 로그 없이 성립하지 않는다** — `evidence` 의 `logs/<FID>/*.log` 가 실재·비어 있지
    않고 `eval/<FID>.md` 에 `VERDICT: PASS` (v2 파일) `[훅(모양)+스크립트(실재)]`

훅은 같은 호출을 다시 하면 통과시킨다 (플러그인 훅이 전역 발화해도 안전하려면 차단이 복구 가능해야
한다). 그래서 훅은 지름길을 **불가능하게** 만들지 않고 **의도된 선택**으로 바꾼다. 불가능하게 만드는
쪽은 매 기능 끝에 evaluator 가 돌리는 검증 스크립트다. `[판단]` 셋(1·3·5)만 대상 프로젝트 AGENTS.md 의
규율 블록이 담당한다 — 컨텍스트가 압축돼 이 문서가 빠져도 AGENTS.md 는 매 턴 다시 로드된다.

## 12. 파일 구조

```
docs/harness/<slug>/
├── BRIEF.md · PRD.md · PLAN.md · PROGRESS.md        (PRD·PLAN 은 frontmatter status)
├── reviews/{prd,plan}-critic-r{N}.md
└── epics/<NN-slug>/
    ├── feature_list.json · .criteria_lock.json      (에픽 승인 표지)
    ├── TC.md · .tc_lock.json · reviews/tc-critic-r{N}.md   (TC 확정 표지)
    ├── sprint_contracts/<FID>.md · logs/<FID>/<n>.log · eval/<FID>.md · eval/EPIC.md
    ├── blocked_ack.md                               (blocked 인정 시)
    └── CLOSED.md                                    (에픽 종료 표지)
```

기존 프로젝트에서 쓰면 기존 코드 구조를 존중한다. 서로 다른 제품은 slug 폴더로 격리한다.

## 13. 출력 언어

사용자와의 대화·상태 문서는 사용자 언어(기본 한국어), 코드·주석은 영어, 사용자가 영어로 요청하면 전체
영어.

## 참고 자료 (`references/`)

- `prd_template.md` · `plan_template.md` · `tc_template.md` — 산출 문서 템플릿
- `sprint_contract_template.md` · `eval_report_template.md` — 기능 단위 문서 템플릿
- `epic_close.md` — 에픽 종료 절차 (`/simplify` → 회귀 평가 → 승인 → 커밋)
- `feature_list_template.json` — v2 스키마
- `generator_guide.md` · `evaluator_guide.md` — 에이전트 상세 가이드
- `harness_framework.md` — 5-Component Harness Framework 와 상태 머신
