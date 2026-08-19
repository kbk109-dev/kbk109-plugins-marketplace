# project-conventions

Claude 와 Cursor 를 번갈아 쓰는 프로젝트에서, 에이전트 지시 문서를 한 곳으로 모으고 작업 규칙을
양쪽에 설치한다. 스킬 3개 + 서브에이전트 훅 1개.

## 설치

```
/plugin install project-conventions@kbk109-plugins-marketplace
```

## 왜 필요한가

Claude 는 `CLAUDE.md` 를, Cursor 는 `AGENTS.md` 와 `.cursor/rules/` 를 읽는다. 같은 내용을 두 벌
관리하면 반드시 갈라진다 — 한쪽만 고치고 다른 쪽을 잊기 때문이고, 갈라져도 에러가 나지 않아
알아채지 못한다.

이 플러그인은 **`AGENTS.md` 를 단일 소스(SSoT)로** 만든다. `CLAUDE.md` 는 그것을 가리키기만
하므로 두 파일이 갈라질 여지 자체가 없어진다. 규칙 본문은 `.claude/rules/` 에 두고
`.cursor/rules/` 는 그 사본으로 생성하며, 사본이 갈라졌는지는 검사 스킬이 잡는다.

## 선행 요건

| 요건 | 비고 |
|---|---|
| `python3` | 두 스킬 모두 |
| 프로젝트 `CLAUDE.md` | `init-agent-rules` 의 실행 전제. 없으면 중단한다 |
| git 저장소 | 이관 시 `git mv` 로 히스토리를 보존한다. git 저장소가 아니면 일반 이동으로 대체 |

## 스킬

세 스킬의 역할이 갈린다. **구조를 만드는 것 · 구조가 깨졌는지 보는 것 · 내용이 사실과
어긋났는지 보는 것**은 서로 다른 문제다.

| 스킬 | 보는 것 | 언제 |
|---|---|---|
| `init-agent-rules` | 구조를 **만든다** | 최초 1회 |
| `check-agent-rules` | 구조가 **깨졌는지** — 사본 갈라짐 | 커밋 전·수시 |
| `refresh-agent-rules` | 내용이 **사실과 어긋났는지** | 프로젝트가 바뀐 뒤 |

### `init-agent-rules`

`CLAUDE.md` 본문을 `AGENTS.md` 로 옮기고 `CLAUDE.md` 는 `@AGENTS.md` 한 줄로 바꾼다. 이어서 규칙을
`.claude/rules/` 와 `.cursor/rules/` 양쪽에 설치하고, `AGENTS.md` 말미에 규칙마다 그것을 가리키는
마커 블록을 넣는다.

```
/project-conventions:init-agent-rules
```

**옮기기 전에 본문을 다듬는다.** `/init` 초안은 이관되는 순간 SSoT 가 되므로 결함도 함께 굳는다.
이관 직전에 (1) 카파시 4원칙이 전용 섹션으로 없으면 10~20줄짜리 짧은 블록을 H1 아래에 붙이고,
(2) 다단계 절차(How)를 분리 후보로 뽑아 **승인을 받은 뒤에만** 스킬·`paths` 규칙으로 내보내며,
(3) 이관 후 `AGENTS.md` 줄 수를 200줄 목표와 대조한다. 승인 전에는 파일을 하나도 만들지 않고,
200줄을 넘겨도 설치를 막지 않는다 — 이 파일들은 길어도 잘리지 않으므로 200줄은 목표이지
상한이 아니다. 사용자가 "그대로 옮겨줘" 라고 하면 이 단계는 통째로 건너뛴다.

설치되는 규칙:

| 규칙 | 내용 | 설치 조건 |
|---|---|---|
| `git-branch-workflow` | `dev` 에서 분기·네이밍, 커밋 승인 게이트, `dev` 로만 `--no-ff` 머지 (main 은 사람이) | 항상 |
| `codegraph-search` | 코드 검색은 codegraph 우선, 호출 불가 시 경고 후 grep 폴백. **서브에이전트에도 적용** | `.codegraph/` 색인이 있을 때만 |

codegraph 규칙이 조건부인 이유는 색인 없는 프로젝트에서 이 규칙이 소음이 되기 때문이다 — 매 검색마다
쓸 수 없는 도구를 시도하고 경고를 띄운다. 판정은 `.codegraph/` 존재 여부로 자동이며,
`--codegraph-rule on|off` 로 뒤집을 수 있다. 선택되지 않은 규칙은 건너뛸 뿐 **지우지 않는다.**

설치 후 상태:

```
AGENTS.md                              ← 이전된 본문 + 규칙마다 마커 블록 (SSoT)
CLAUDE.md                              ← 안내문 + @AGENTS.md
.claude/rules/git-branch-workflow.md   ← 규칙 본문
.cursor/rules/git-branch-workflow.mdc  ← 프론트매터 + 동일 본문 (생성물)
.claude/rules/codegraph-search.md      ← 조건부
.cursor/rules/codegraph-search.mdc     ← 조건부
```

**`CLAUDE.md` 가 없으면 중단한다.** 뼈대를 지어내지 않는다 — 프로젝트 지시를 추측으로 채우는
것보다 멈추는 게 낫고, 초안 작성은 `/init` 의 몫이다.

**`AGENTS.md` 가 이미 있으면 중단한다.** 두 파일의 차이를 보여주고 어떻게 할지 물은 뒤 진행한다.
자동 병합하지 않는다 — 규칙 문서는 조용한 유실이 치명적이다.

재실행해도 안전하다. 마커 블록 구간만 교체하고 `.mdc` 를 다시 생성한다.

**규칙을 프로젝트에 맞게 고쳤다면** `.claude/rules/` 쪽 원본을 고친 뒤 `--sync-mdc` 로 사본만
다시 맞춘다. 전체 재설치는 규칙을 템플릿에서 다시 렌더하므로 그 수정을 덮어쓴다.

### `check-agent-rules`

설치된 구조가 갈라졌는지 검사한다. 검사 항목 6가지:

| # | 검사 |
|---|---|
| 1 | `AGENTS.md` 존재·비어있지 않음 |
| 2 | `CLAUDE.md` 가 `@AGENTS.md` 를 가리킴 |
| 3 | `CLAUDE.md` 에 본문이 다시 유입되지 않음 |
| 4 | `.claude/rules/<규칙>.md` 존재 |
| 5 | `.cursor/rules/<규칙>.mdc` 본문이 4번과 **바이트 동일** |
| 6 | `AGENTS.md` 의 규칙별 마커 블록이 온전함 |

4·5·6 은 규칙마다 반복한다. `.md`·`.mdc`·마커 블록 셋 중 하나라도 있으면 그 규칙은 설치된 것으로
보고 나머지 둘도 요구한다 — 반쪽 설치를 잡기 위해서다. 셋 다 없는 선택 규칙은 건너뛴다.

```
/project-conventions:check-agent-rules
```

5번이 이 플러그인의 존재 이유다. `.mdc` 는 생성물이라 손으로 고치면 조용히 갈라지고, 그 뒤로
Cursor 와 Claude 는 서로 다른 규칙을 따르게 된다.

스크립트는 단독 호출할 수 있으므로 pre-commit 훅에 걸어도 된다 — 실패 시 exit 1 이다.

### `refresh-agent-rules`

시간이 지나 `AGENTS.md` 가 실제 코드베이스와 어긋났는지 다시 분석해 갱신한다. 프로젝트를
스캔해 명령·패키지 매니저·툴체인·디렉터리 구조 같은 **사실**을 모으고, 마지막 갱신 이후의
git 변경분으로 어디부터 볼지 정한 뒤 `AGENTS.md` 의 주장과 대조한다.

```
/project-conventions:refresh-agent-rules
```

**바꿀 게 없으면 파일을 열지도 않는다.** 무엇을 확인했는지만 보고하고 끝낸다 — 갱신 스킬이
매번 무언가를 고쳐야 한다는 압박으로 멀쩡한 문서를 흔드는 것이 가장 흔한 실패다.

고치는 대상은 **`AGENTS.md` 본문 하나뿐이다.** 마커 블록 구간(`init` 소관), `CLAUDE.md`(포인터),
`.claude/rules/*.md`, `.mdc` 는 건드리지 않는다.

**삭제만 항목별로 승인받는다.** 추가·수정은 diff 하나로 일괄 승인해도, 사람이 손으로 쓴 설계
근거를 모델이 "낡았다"고 지우는 것은 되돌리기 어려운 손실이다. 삭제 후보에는 사라진 경로나
바뀐 스크립트명 등 **어느 사실에서 나온 판정인지**를 반드시 붙인다.

마지막 갱신 시점은 `.claude/agent-rules.state.json` 에 남고 **커밋 대상**이다. 팀원이 각자 다른
기준점을 들면 같은 변경을 몇 번이고 다시 제안하게 된다.

카파시 4원칙 블록·What/How 분리·200줄 예산은 `init-agent-rules` 와 **같은 규칙**을 쓴다.
정본은 `init-agent-rules/references/claude_md_rewrite.md` 하나다 — 규칙 정본이 둘이면 반드시
갈라지고, 그게 이 플러그인이 막으려는 실패다.

## codegraph 규칙을 서브에이전트까지 강제하는 훅

`hooks/codegraph_subagent_guard.py` (`PreToolUse`, matcher `Agent|Task`)

**왜 필요한가.** codegraph 규칙이 메인 세션에 닿는 경로는 두 가지 — 프로젝트 지시로 로드되는
`.claude/rules/codegraph-search.md`, 그리고 codegraph 가 제공하는 `UserPromptSubmit` 훅이다.
둘 다 서브에이전트에는 닿지 않는다. 서브에이전트는 **사용자 프롬프트로 시작하지 않으므로**
`UserPromptSubmit` 이 구조적으로 발화할 수 없고, 프로젝트 지시 상속도 보장되지 않는다.
그 결과 메인 세션은 codegraph 를 쓰는데 서브에이전트만 grep 부터 잡는다.

이 훅은 유일하게 반드시 실행되는 지점 — 부모 프로세스의 `Agent`/`Task` 도구 호출 — 을 잡아
`updatedInput` 으로 서브에이전트 프롬프트에 규칙을 물리적으로 심는다. **모델의 협조가 필요 없다.**

동작 조건 (하나라도 어긋나면 아무것도 출력하지 않고 통과):

| 조건 | 통과(no-op) 하는 경우 |
|---|---|
| 도구 | `Agent`·`Task` 가 아님 |
| 색인 | git 저장소 루트까지 올라가도 `.codegraph/` 없음 |
| 프롬프트 | 문자열이 아니거나 비어 있음 |
| 멱등 | 프롬프트에 이미 `codegraph` 가 들어 있음 (호출자의 명시적 탈출구이기도 하다) |

**전 구간 fail-open.** 플러그인 훅은 켜진 모든 프로젝트에서 발화하므로, 서브에이전트 디스패치를
막을 수 있는 가드는 가드가 없는 것보다 나쁘다. 예외는 통째로 삼키고 언제나 exit 0 한다.

상향 탐색은 **git 저장소 루트와 `$HOME` 에서 멈춘다.** `codegraph init` 을 홈에서 한 번 잘못
실행해 생긴 `~/.codegraph` 하나가 홈 아래 모든 프로젝트를 "색인됨"으로 만들어, 무관한 프로젝트의
모든 서브에이전트에 주입되는 전역 오탐이 되기 때문이다.

훅이 없는 환경(Cursor 등)은 규칙 문서 5절이 대신 덮는다 — 서브에이전트 프롬프트에 손으로 붙일
짧은 인용문이 거기 있다.
