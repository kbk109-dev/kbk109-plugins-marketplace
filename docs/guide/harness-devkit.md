# harness-devkit 사용 가이드

> **대상** — 에이전트에게 큰 구현을 맡겼다가 "다 됐습니다"라는 말을 믿었다 낭패를 본 개발자
> **범위** — 스킬 2개(`harness-dev`, `dev-monitor`), 에이전트 9개, 훅 1개, 스크립트 4개
> **읽는 순서** — 1절이 *왜 두 스킬이 한 플러그인인지*, 2~4절이 `harness-dev`,
> 5~6절이 `dev-monitor`, 7~9절이 *언제 쓰고 언제 피하나*

## 선행 요건과 설치

| 요건 | 쓰는 곳 | 없으면 |
|---|---|---|
| 프로젝트 `CLAUDE.md` | `dev-monitor` | **즉시 중단**한다. 서버 명령을 추측하지 않는다 |
| context7 MCP | `dev-monitor` | 오류 분석이 근거 없는 추측으로 떨어진다 |
| WebSearch | `dev-monitor` | 외부 이벤트(CVE·장애·차단 정책)를 못 짚는다 |
| `lsof` · `pkill` | `dev-monitor` | 포트 정리와 Monitor 종료가 안 된다 (macOS·Linux 기본 포함) |

`harness-dev` 는 필수 선행 요건이 없다. 다만 QA 는 PLAN 의 **Run & Verify** 에 적힌 기동·test·E2E
명령을 evaluator 가 실제로 실행해야 성립한다 — 그 명령이 없는 계획은 승인 단계로 넘어가지 못한다.
인터뷰는 `/mattpocock-skills:grill-with-docs` 가 있으면 그것을 쓰고, 없으면 같은 방식을 직접 한다.

```
/plugin marketplace add https://github.com/kbk109-dev/kbk109-plugins-marketplace
/plugin install harness-devkit@kbk109-plugins-marketplace
```

---

## 1. 무슨 문제를 푸는가

두 스킬은 하는 일이 전혀 다르다. 하나는 앱을 짓고 하나는 서버 로그를 본다.
**그런데 둘 다 같은 실패를 막는다 — 에이전트가 자기가 어디까지 했는지 잃어버리는 것.**

```mermaid
flowchart TB
  L["LLM 은 세션 간 기억이 없다"]
  L --> A["긴 구현<br/>→ 앞 단계를 잊는다<br/>→ '거의 됐으니 넘어가자'"]
  L --> B["서버 감시<br/>→ 이전 세션의 Monitor 를 못 본다<br/>→ 서버를 또 띄운다"]
  A --> HD["harness-dev<br/>feature_list.json · progress.md"]
  B --> DM["dev-monitor<br/>port-N.state.json"]
  HD --> S["상태를 파일로 외부화한다"]
  DM --> S
```

증상은 다르지만 처방이 같아서 한 플러그인이다.

**두 실패의 결정적 공통점은 조용하다는 것이다.** 단계를 건너뛰어도 에러가 안 나고,
서버가 두 벌 떠도 포트는 하나만 잡히니 겉보기엔 정상이다. 이 플러그인이 하는 일은
**조용한 실패를 시끄러운 실패로 바꾸는 것**이다.

> 배경 이론은 [`docs/harness-engineering/`](../harness-engineering/) 에 있다.
> 이 가이드는 그 이론이 두 스킬에서 어떤 모습으로 나타나는지만 다룬다.

---

## 2. harness-dev — 단계마다 새 서브에이전트

아이디어 하나를 **PRD → PLAN → 에픽별 feature_list → TC → 개발 → QA** 로 끌고 간다.
메인 세션은 사용자와 대화하고 호출 순서를 지휘할 뿐이고, 각 단계의 일은 새 서브에이전트가 한다.

```mermaid
flowchart TD
  I["인터뷰<br/>grill-with-docs → BRIEF.md"] --> PRD["prd-writer ↔ prd-critic<br/>(최대 2라운드)"]
  PRD --> A1{"사용자 승인"}
  A1 --> PL["planner ↔ plan-critic<br/>Run & Verify 필수"]
  PL --> A2{"사용자 승인"}
  A2 --> FP["feature-planner<br/>에픽별 feature_list"]
  FP --> A3{"사용자 승인 (잠금)"}
  A3 --> TC["tc-writer ↔ tc-critic<br/>→ TC 잠금"]
  TC --> G["generator<br/>기능 1개 구현"]
  G --> E["evaluator<br/>확정 TC 를 실앱에서 실행"]
  E -->|"FAIL (2회까지)"| G
  E -->|"3번째 FAIL"| ESC["blocked → 사용자"]
  E -->|"PASS"| NEXT{"남은 기능"}
  NEXT -->|있음| G
  NEXT -->|없음| CL["에픽 종료<br/>/simplify → 회귀 평가 → 승인 → 커밋"]
  CL -->|"다음 에픽"| TC
```

핵심은 화살표가 아니라 **누가 판정하느냐**다.

| 나누는 것 | 왜 |
|---|---|
| Writer ≠ Critic | 쓴 쪽이 검토하면 후하다. critic 은 PRD·PLAN 은 **회의적으로**, TC 는 **보수적으로**(누락이 의심되면 REVISE) 본다 |
| TC 는 구현 **전**에 | 코드를 보고 쓴 TC 는 구현이 하는 일을 기대 결과로 적어 느슨해진다. 확정되면 잠기고, 바뀌면 에스컬레이션한다 |
| **Generator ≠ Evaluator** | **구현한 쪽이 채점하면 반드시 후하다.** 1.x 는 같은 컨텍스트에서 역할만 바꿨다 — 2.0 은 별개 서브에이전트다 |
| 기능 하나 = 작업 단위 | 여러 개를 동시에 잡으면 "대충 다 된 것 같다"가 성립해 버린다 |

generator 의 자체 평가는 **참고만** 한다. `pass` 는 evaluator 만 기록한다.

### 진입할 때마다 일어나는 일 — 상태 판정

새 세션은 앞선 대화를 모른다. 그래서 진입 스킬의 첫 동작은 항상 `harness_state.py status` 다.
파일 상태(PRD frontmatter, 리뷰 파일, 잠금 파일, feature_list)에서 **코드가** 현재 단계를 판정한다 —
모델이 판정하면 재진입할 때마다 달라진다. 한 번의 진입에서 서브에이전트를 한 단계만 부르고,
사용자 승인 단계에서 멈추며, 에픽 하나가 끝나면 새 세션을 권한다.

### `status: "fail"` 이 기본값이다

새 기능은 전부 `"fail"` 로 태어나고 `"pending"` 은 **존재하지 않는다.**

```
"pending" 이 있으면  →  "아직 안 한 것"과 "해봤는데 안 되는 것"이 섞인다
                      →  마지막에 pending 을 훑으며 "이건 됐지" 하고 넘긴다
"fail" 만 있으면     →  통과를 증명하지 못한 모든 것은 실패다
```

2.0 은 한 걸음 더 간다. `pass` 는 evaluator 만 쓸 수 있고, `logs/<FID>/*.log`(실제 실행 로그)와
`eval/<FID>.md` 의 `VERDICT: PASS` 가 없으면 성립하지 않는다.

---

## 3. 실행하면 무슨 일이 일어나나

### 멈춰 서서 물어보는 지점

| # | 멈추는 지점 | 무엇을 묻나 | 언제 |
|---|---|---|---|
| 1 | 인터뷰 | 설계 트리를 라운드로 돌며 결정 사항 | **항상** |
| 2 | PRD · PLAN 승인 | critic 의견과 남은 blocking 을 보고 확정 | **항상** |
| 3 | 에픽 승인 | feature_list 를 확정(잠금) | **항상** |
| 4 | blocked · TC 2라운드 후 REVISE · TC 잠금 위반 | 고쳐서 재시도 / blocked 인정 / 중단 | 사고 시 |
| 5 | 에픽 종료 | 변경 요약과 `eval/EPIC.md` 를 보고 커밋 승인 | **항상** |

3번 전까지는 코드가 하나도 안 생긴다. TC 는 사람 게이트가 아니라 critic 의 PASS 가 확정한다.
**자동 커밋은 없다.** 에픽 종료 때 `/simplify` 로 변경분을 정리하고, 정리가 고친 코드를 evaluator 가
회귀 모드로 다시 평가한 뒤에야 승인을 묻는다. push 는 하지 않는다.

**기능 3개 이하는 이 스킬을 쓰지 않는다** — 버그 하나 고치는 데 PRD 와 TC 를 돌리는 건 순수한 낭비다.

### 11가지 기계적 제약 — 무엇을 막는지

각각이 **특정한 지름길**을 막는다. 지름길 쪽을 읽어야 왜 필요한지 보인다.

| 제약 | 이게 없으면 생기는 지름길 |
|---|---|
| 1 한 번에 하나의 기능 | 여러 개를 열어 놓고 "전체적으로 거의 됨"으로 뭉갠다 |
| **2 테스트 삭제 금지** | **어려운 `acceptance_criteria` 를 쉽게 고쳐서 통과시킨다** |
| 3 자기 평가 불신 | 구현한 쪽이 자기 작업에 후한 점수를 준다 |
| 4 스텁 금지 | `TODO` 와 `mock` 으로 "겉으로만 완성"된 프로젝트가 나온다 |
| 5 진행 기록 필수 | 다음 세션이 처음부터 다시 헤맨다 |
| 6 JSON 형식 유지 | Markdown 으로 바꾸면 상태가 산문이 되어 기계 판독이 깨진다 |
| 7 재시도 상한 2회 | 같은 실패를 무한히 반복하며 토큰만 태운다 |
| 8 `status` 기본값 `fail` | 증명 없이 통과하는 경로가 생긴다 |
| 9 pass 는 evaluator 만 | generator 가 자기 기능을 pass 로 바꾼다 |
| 10 전이는 `fail→pass/blocked`, `blocked→fail` | 통과한 기능을 되돌리거나 blocked 에서 곧장 pass 로 간다 |
| 11 pass 는 증거 로그 필수 | 실행하지 않고 "확인했다" 고 쓴다 |

2번이 가장 위험하다. **합격 기준을 고칠 수 있으면 나머지가 전부 무의미해진다.** TC 잠금이 같은 이유로
있다.

---

## 4. 산출물 — `docs/harness/{slug}/`

slug 는 `harness_state.py slug` 가 정한다 (이미 있으면 `-2`).

```
<내-프로젝트>/docs/harness/todo-manager/
├── BRIEF.md · PRD.md · PLAN.md · PROGRESS.md
├── reviews/{prd,plan}-critic-r{N}.md        ← critic 의견과 VERDICT
└── epics/01-core/
    ├── feature_list.json · .criteria_lock.json    ← 에픽 승인 표지
    ├── TC.md · .tc_lock.json                      ← TC 확정 표지
    ├── reviews/tc-critic-r{N}.md
    ├── sprint_contracts/F001.md                   ← generator 의 구현 전 선언
    ├── logs/F001/1.log                            ← evaluator 가 실행한 실제 출력
    ├── eval/F001.md · eval/EPIC.md                ← 판정 근거
    └── CLOSED.md                                  ← 에픽 종료 표지
```

**승인 표지는 전부 파일이다** — PRD·PLAN 은 frontmatter `status: approved`, 에픽은 잠금 파일.
그래서 어느 세션에서든 `PROGRESS.md` 와 이 파일들만 보면 다음 할 일이 같게 판정된다.

### `docs/harness/` 는 여러 스킬이 나눠 쓰는 이름공간이다

실제 프로젝트를 열어 보면 이렇게 섞여 있다. **`docs/harness/` 아래 있다고 전부 `harness-dev` 가
만든 것이 아니다.**

```
docs/harness/
├── todo-manager/                  ← harness-dev  ({slug}/ 아래로 격리)
└── firebase/
    ├── analytics/                 ← firebase-analytics-impl
    │   ├── ga-feature-list.json
    │   └── ga-progress.txt
    └── crashlytics/               ← firebase-crashlytics-impl
        ├── CRASHLYTICS_FEATURES.json
        └── CRASHLYTICS_PROGRESS.txt
```

firebase 쪽 파일명은 `feature_list.json` 으로 끝나지 않아 훅의 대상이 아니다. 1.x 의
`{slug}/feature_list.json`(+ `progress.md`) 평면 레이아웃은 `legacy` stage 로 계속 재개된다.

---

## 5. dev-monitor — 왜 상태를 파일로 빼는가

서버를 띄우고 로그를 감시한다. 어려운 부분은 감시가 아니라 **"이미 띄웠는지"를 아는 것**이다.

```mermaid
flowchart TD
  CALL["/harness-devkit:dev-monitor 8000"] --> ST{"port-8000.state.json"}
  ST -->|없음| FRESH["신규 기동<br/>Phase 1~5"]
  ST -->|있음| PS{"ps -p 로 생존 확인"}
  PS -->|"서버 살아있음<br/>Monitor 살아있음"| REUSE["재연결<br/>Phase 1~5 전부 건너뜀"]
  PS -->|"서버 살아있음<br/>Monitor 죽음"| REMON["고아 tail 정리 후<br/>Monitor 만 재등록"]
  PS -->|"둘 다 죽음"| CLEAN["stale 삭제 → 신규 기동"]
```

`TaskList` 를 보면 안 된다. **`TaskList` 는 현재 세션만 비추는 휘발성 메모리**라서, 이전 세션이
띄운 서버가 "없는 것"으로 보인다. 그 상태로 진행하면 서버가 두 벌 뜬다. 상태 파일이 Ground Truth 다.

### 서버와 Monitor 는 수명이 다르다 (1.1.0)

이 스킬에서 가장 헷갈리는 지점이고, 1.1.0 에서 고쳐진 부분이다.

| | 정체 | 세션이 끝나면 |
|---|---|---|
| `server_pid` | `nohup` 으로 띄운 진짜 PID | **살아남는다** |
| `monitor_pid` | Monitor 래퍼 셸의 진짜 PID | **죽는다** |
| `monitor_task_id` | `Monitor` 도구의 task ID (문자열) | 무효가 된다 |

그래서 새 세션에서 **"서버는 살아 있는데 Monitor 는 죽어 있다"는 정상**이다. 사고가 아니다.
서버만 재사용하고 Monitor 는 다시 등록하는 것이 옳은 처리다.

`monitor_pid` 를 확보하는 방법이 조금 특이하다. `Monitor` 도구는 PID 가 아니라 task ID 를
돌려주므로 그 값으로는 `ps -p` 도 `kill` 도 안 된다. 그래서 명령 첫 줄에 `echo $$` 를 넣어
래퍼 셸의 진짜 PID 를 파일로 남긴다.

```bash
echo $$ > ~/.claude/dev-monitor/port-8000.monitor.pid
tail -f /tmp/dev_server_8000.log | grep --line-buffered -E "..."
```

> **1.1.0 이전 상태 파일은 자동으로 stale 처리된다.** 예전 버전은 `monitor_pid` 자리에 task ID
> 문자열(`"b1cgaqjgm"`)을 넣었다. 값이 숫자가 아니면 구스키마로 보고 생존 판정과 `kill` 을
> 건너뛴다. 그냥 다시 실행하면 되고, 손으로 지울 필요는 없다.

---

## 6. dev-monitor 실행 흐름과 하드 게이트 2개

| Phase | 하는 일 |
|---|---|
| 0 | 포트 검증. `stop`·`stop-all`·`status` 는 여기서 선분기 |
| 0.5 | **상태 파일 확인** — 재진입 감지 |
| 1 | `CLAUDE.md` 에서 서버 명령 추출 |
| 2 | 포트 정리 (`lsof` → 서버 프로세스만 kill) |
| 3 | `docker compose ps` (compose 파일 있을 때만) |
| 4 | `nohup` 백그라운드 기동 + health 확인 + **상태 파일 기록** |
| 5 | Monitor 등록 (`echo $$` → pidfile → 상태 파일 갱신) |
| 6 | 이상 감지 시 `[날짜 시간]` + 원인 + 해결 방향 표 |
| 7 | heartbeat / `status` 보고 |
| 8 | 종료 — `TaskStop` → `pkill -P` → `kill` → 고아 청소 |

### 게이트 2개는 물어보지 않고 **중단**한다

| 게이트 | 조건 | 왜 묻지 않고 멈추나 |
|---|---|---|
| Phase 0 | 포트 미입력 | 기본 포트를 가정하면 엉뚱한 포트의 남의 프로세스를 kill 한다 |
| Phase 1 | `CLAUDE.md` 없음 / 명령 못 찾음 | **틀린 명령으로 서버를 띄우는 것보다 멈추는 게 낫다** |

두 번째가 이 스킬의 성격을 정한다. 서버 명령의 단일 소스는 `CLAUDE.md` 이고, 모델이 스스로
`npm run dev` 를 추론해 실행하는 경로는 **없다.** 탐색 순서는 `./CLAUDE.md` →
`./.claude/CLAUDE.md` → `./docs/CLAUDE.md` → `~/.claude/CLAUDE.md` 이고, 후보가 2개 이상이면
고르라고 묻는다.

### 종료할 때 순서가 중요하다

```
TaskStop(task_id)   ← 같은 세션이면 이걸로 끝
   ↓ 실패하거나 다른 세션이면
pkill -P <monitor_pid>   ← 자식(tail·grep) 먼저
kill <monitor_pid>       ← 그다음 래퍼
pkill -f "tail -f <log>" ← 남은 고아 청소
```

**순서를 바꾸면 안 된다.** 래퍼를 먼저 죽이면 `tail` 이 PID 1 로 재부모화되어 살아남는다.
그 상태로 재등록하면 같은 로그를 붙든 `tail` 이 하나씩 쌓인다.

`stop` 은 **이 스킬이 띄운 것만** 정리한다. 상태 파일에 적힌 PID 만 신뢰하고, 포트를 물고 있는
외부 프로세스는 건드리지 않는다. Chrome 같은 클라이언트도 죽이지 않는다 — CLOSE_WAIT 소켓은
서버가 죽으면 알아서 풀린다.

---

## 7. 언제 무엇을 쓰나

이 저장소에는 같은 Generator/Evaluator 패턴을 쓰는 스킬이 **다섯 개**다. 가장 헷갈리는 지점이라
따로 정리한다.

| 하려는 일 | 쓸 스킬 | 상태 저장소 | 계획 문서 |
|---|---|---|---|
| Expo/RN 앱 AdMob 광고 구현 | `expo-app-kit:admob-impl-harness` | `docs/plan/ADMOB_PROGRESS.md` | `ADMOB-PLAN.md` **필수** |
| GA4 이벤트 트래킹 구현 | `firebase-observability:firebase-analytics-impl` | `docs/harness/firebase/analytics/` | `GA_PLAN.md` **필수** |
| Crashlytics 도입 | `firebase-observability:firebase-crashlytics-impl` | `docs/harness/firebase/crashlytics/` | `CRASHLYTICS_PLAN.md` **필수** |
| 릴리스 단위 기능 구현 | `release-workflow:release-impl` | Notion + `docs/skills/release-plan/` | Notion DB **필수** |
| **위 어디에도 안 맞는 새 앱·기능 5개+** | **`harness-devkit:harness-dev`** | `docs/harness/{slug}/` | **없어도 된다** |

판단은 두 줄이면 끝난다.

1. **도메인 전용 스킬이 있으면 그것을 쓴다.** 그쪽이 해당 도메인의 함정(광고 정책, GA4 예약
   이벤트명, Crashlytics 초기화 순서)을 알고 있다. `harness-dev` 는 모른다.
2. **`harness-dev` 는 폴백이다.** 전용 스킬 넷은 전부 계획 문서를 **선행 조건으로 요구하고
   없으면 거부**한다. `harness-dev` 만 인터뷰부터 PRD·PLAN 까지 자기 안에 갖고 있어서 맨손으로 시작한다.

---

## 8. 자주 막히는 곳 · 언제 쓰지 말아야 하나

### `dev-monitor`

| 증상 | 원인 | 처리 |
|---|---|---|
| "CLAUDE.md에서 서버 실행 명령을 찾을 수 없습니다" | 하드 게이트. 우회 경로는 없다 | `CLAUDE.md` 에 `## Dev Server` 섹션과 bash 코드블록을 넣는다 |
| 후보 명령 N개 발견하고 멈춤 | `CLAUDE.md` 에 실행 명령이 여러 개 | 번호로 고른다. 자주 겪으면 `## Dev Server` 섹션을 하나만 남긴다 |
| 포트 불일치 경고 | `--port 8000` 인데 인자는 `3000` | A(명령 치환)/B(인자 변경)/C(중단) 중 선택 |
| 서버가 안 죽고 포트가 안 비어 있다 | 상태 파일 밖에서 띄운 서버 | `stop` 은 상태 파일의 PID 만 건드린다. 외부 프로세스는 직접 정리 |
| `tail` 이 여러 개 쌓였다 | 1.1.0 이전 버전에서 남은 고아 | `pkill -f "tail -f /tmp/dev_server_<port>.log"` |
| Monitor 가 매번 새로 등록된다 | 새 세션이라 정상 | 사고가 아니다. 5절 참고 |

### `harness-dev`

| 증상 | 원인 | 처리 |
|---|---|---|
| 부르지도 않았는데 발동한다 | `disable-model-invocation` 이 없어 트리거 문구로 자동 호출된다 | "복잡한 앱 만들어줘" 류를 피하거나, 적합성 판단에서 일반 개발로 전환하라고 말한다 |
| PRD·PLAN·에픽 승인에서 멈춰 있다 | 설계상 필수 확인 지점 | 승인 전에는 코드가 안 생긴다. 계획을 고칠 마지막 기회다 |
| PLAN 이 승인 단계로 안 넘어간다 | Run & Verify 의 `start`/`test`/`e2e` 중 비었거나 `TBD` | 실제로 실행되는 명령을 적는다. E2E 도구가 없으면 도입을 첫 에픽에 넣는다 |
| 합격 기준을 좀 낮추고 싶다 | `acceptance_criteria` 수정은 금지, TC 는 잠금 | 기준을 바꾸려면 사용자와 상의해 에픽 승인 단계부터 다시 한다 |
| generator 가 pass 를 쓰려다 막혔다 | 제약 9 — 훅이 한 번 막는다 | 정상이다. 판정은 evaluator 가 한다. 같은 호출을 다시 하면 통과하므로 검증 스크립트가 최종으로 잡는다 |
| 새 세션에서 어디까지 했는지 모르겠다 | — | 스킬을 다시 부르면 `harness_state.py status` 가 stage 를 알려 준다 |

### 쓰지 말아야 할 때

- **기능 3개 이하** — PRD·TC·채점 오버헤드가 작업보다 크다. 적합성 판단에서 일반 개발로 전환하지만,
  애초에 부르지 않는 게 낫다
- **단순 버그 수정 · 단일 파일 리팩터 · 질문 · 문서 작성** — `harness-dev` 대상이 아니다
- **도메인 전용 스킬이 있는 작업** — 7절 표를 먼저 본다
- **`CLAUDE.md` 가 없는 프로젝트에서 `dev-monitor`** — 중단된다. 먼저 `/init` 을 돌린다

### 알아 둘 한계 — 절반은 여전히 판단이다

11가지 기계적 제약 중 **여덟은 실제로 코드가 검사한다.**

| 제약 | 검사 주체 |
|---|---|
| 2 acceptance_criteria 불변 · 6 JSON 유지 · 7 재시도 상한 · 8 status enum | PreToolUse 훅 + `validate_feature_list.py` |
| 10 전이 | 훅(디스크의 이전 파일과 비교) + `validate_feature_list.py --prev` |
| 9 pass 기록 주체 | 훅만 — 호출한 `agent_type` 은 훅만 안다 |
| 11 증거 | 훅(모양) + `validate_feature_list.py`(로그 실재·`VERDICT: PASS`) |
| 4 스텁 금지 | `validate_feature_list.py --stubs` |
| TC 모양·추적성·잠금, PLAN 의 Run & Verify | `validate_harness_doc.py` |
| 1 한 번에 하나씩 · 3 자기평가 불신 · 5 진행 기록 필수 | **판단 — 코드가 볼 수 없다** |

훅은 `feature_list.json` 쓰기를 가로채므로 모델이 무엇을 기억하는지와 무관하게 발화한다. 다만
플러그인 훅이 전역 발화해도 안전하려면 차단이 복구 가능해야 하므로, **같은 호출을 다시 하면
통과한다.** 그래서 훅은 지름길을 불가능하게 만들지 않고 *의도적인 선택으로* 바꾼다.

불가능하게 만드는 쪽은 매 기능 끝에 evaluator 가 돌리는 검증 스크립트이고, 그건 사람이 결과를 본다.
판단 영역 셋은 대상 프로젝트의 AGENTS.md 규율 블록이 컨텍스트 압축을 견디게 해 줄 뿐, 강제하지는
못한다. **`eval/` 의 판정 근거와 `logs/` 의 실제 출력을 사람이 들여다보는 일은 여전히 필요하다.**

---

## 9. 더 읽을 곳

- [`plugins/harness-devkit/README.md`](../../plugins/harness-devkit/README.md) — 설치와 명령 요약
- [`docs/harness-engineering/`](../harness-engineering/) — 배경 이론 2편
- `skills/harness-dev/references/harness_framework.md` — 5-Component Harness Framework
- `skills/harness-dev/references/generator_guide.md` — Ralph Loop · Reasoning Sandwich · Loop Detection
- `skills/harness-dev/references/evaluator_guide.md` — 판정 원칙 · 증거의 기준 · PreCompletion Checklist
- [`plugins/harness-devkit/docs/adr/0001-…`](../../plugins/harness-devkit/docs/adr/0001-per-stage-subagents-thin-orchestrator.md) — 단계별 서브에이전트로 간 이유
- [`docs/guide/project-conventions.md`](./project-conventions.md) — 훅으로 규율을 **강제**하는 쪽 사례
