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
| `codegraph-search` | 코드 검색은 codegraph 우선, 호출 불가 시 경고 후 grep 폴백. **훅 2개가 검색 도구 호출과 서브에이전트 양쪽에서 강제** | `.codegraph/` 색인이 있을 때만 |

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

## codegraph 를 강제하는 훅 2개

규칙 문서만으로는 codegraph 가 쓰이지 않는다. 문서는 모델이 따를 수도, 안 따를 수도 있는 부탁이다.
훅 둘이 그 부탁을 각각 다른 지점에서 사실로 바꾼다.

| 훅 | 매처 | 하는 일 |
|---|---|---|
| `hooks/codegraph_subagent_guard.py` | `Agent\|Task` | 서브에이전트 프롬프트에 규칙을 **삽입** |
| `hooks/codegraph_search_gate.py` | `Grep\|Glob\|Bash` | 심볼처럼 생긴 검색을 **차단**하고 codegraph 로 보냄 |

둘 다 `.codegraph/` 색인 판정을 공유한다 (`hooks/_codegraph_index.py`). 그 경계 탐색이 이 플러그인에서
실제로 버그가 났던 부분이라 사본을 두지 않는다 — 아래 "상향 탐색" 문단이 그 사고의 기록이다.

### 1. 서브에이전트 프롬프트에 규칙을 심는 훅

`hooks/codegraph_subagent_guard.py` (`PreToolUse`, matcher `Agent|Task`)

**왜 필요한가.** codegraph 규칙이 메인 세션에 닿는 경로는 두 가지 — 프로젝트 지시로 로드되는
`.claude/rules/codegraph-search.md`, 그리고 codegraph 가 제공하는 `UserPromptSubmit` 훅이다.
둘 다 서브에이전트에는 닿지 않는다. 서브에이전트는 **사용자 프롬프트로 시작하지 않으므로**
`UserPromptSubmit` 이 구조적으로 발화할 수 없고, 프로젝트 지시 상속도 보장되지 않는다.
그 결과 메인 세션은 codegraph 를 쓰는데 서브에이전트만 grep 부터 잡는다.

이 훅은 유일하게 반드시 실행되는 지점 — 부모 프로세스의 `Agent`/`Task` 도구 호출 — 을 잡아
`updatedInput` 으로 서브에이전트 프롬프트에 규칙을 물리적으로 심는다.

동작 조건 (하나라도 어긋나면 아무것도 출력하지 않고 통과):

| 조건 | 통과(no-op) 하는 경우 |
|---|---|
| 도구 | `Agent`·`Task` 가 아님 |
| 색인 | git 저장소 루트까지 올라가도 `.codegraph/` 없음 |
| 프롬프트 | 문자열이 아니거나 비어 있음 |
| 멱등 | 프롬프트에 이미 `codegraph` 가 들어 있음 (호출자의 명시적 탈출구이기도 하다) |

### 2. 심볼 검색을 codegraph 로 통과시키는 훅

`hooks/codegraph_search_gate.py` (`PreToolUse`, matcher `Grep|Glob|Bash`)

**왜 1번만으로 부족한가.** 1번이 심는 것은 *지시문*이다. 서브에이전트는 그것을 메인 세션이 규칙
파일을 무시하는 것과 똑같이 무시할 수 있다. 심는 쪽을 아무리 다듬어도 "부탁"이라는 성질은 그대로다.
이 훅은 부탁을 그만두고 검색 도구 호출 자체를 잡는다 — 심볼처럼 생긴 패턴이면 `deny` 하고,
이유문으로 codegraph 호출 방법을 돌려준다. **모델의 협조가 필요 없다.**

동작 조건 (하나라도 어긋나면 아무것도 출력하지 않고 통과):

| 조건 | 통과(no-op) 하는 경우 |
|---|---|
| 도구 | `hooks.json` matcher 가 이 훅으로 보내지 않음 (아래) |
| 색인 | git 저장소 루트까지 올라가도 `.codegraph/` 없음 |
| 패턴 | 심볼처럼 생기지 않음 (아래) · Bash 라면 명령에서 검색 패턴을 뽑아내지 못함 |
| 식별자 | `agent_id`·`session_id` 둘 다 없음 — 무엇을 차단했는지 기억할 수 없으면 차단하지 않는다 |
| 탈출구 | 같은 `(도구, 패턴)` 을 이미 차단한 적 있음 |
| 기록 | 상태 파일 기록 실패 |

**판정은 "패턴 안에 이름처럼 생긴 토큰이 있는가"다.** camelCase 경계나 밑줄을 가진 3자 이상 토큰이
하나라도 있으면 코드 검색으로 본다. 패턴 **전체**가 식별자일 필요는 없다 — `export const appUser`,
`function collectPropertyNames`, `enrollRunner\|issueRunnerToken` 전부 걸린다.

**이 규칙은 실측으로 정했다.** 색인이 있는 실제 프로젝트의 검색 패턴 74종을 코드검색 23 / 비코드검색
51 로 분류하고 후보 규칙을 돌렸다.

| 규칙 | 코드검색 23건 중 | 비코드검색 51건 중 오탐 |
|---|---|---|
| 패턴 전체가 식별자 | 12 | 0 |
| + 심볼 alternation | 17 | 0 |
| **+ 패턴 내 토큰 (채택)** | **23** | **11** |

앞의 두 규칙은 코드 검색의 절반 가까이를 통과시킨다. `export const appUser` 처럼 구조와 이름이 섞인
패턴, 그리고 모델이 심볼 여러 개를 한 번에 찾을 때 쓰는 alternation 을 놓치기 때문이다. **"코드 검색은
codegraph 로"가 목적인 이상 절반을 통과시키는 규칙은 목적을 달성하지 못한다.**

오탐 11건은 `CREATE TABLE app_user`·`DATABASE_URL\|skip` 처럼 이름 토큰이 섞인 DB·설정 검색이다.
**받아들인 대가다** — 각 1회 재시도로 끝나고, 규칙 문서 2절에 그 경계를 명시했다. 반대로 단일 소문자
단어까지 넓히는 안은 함께 재봤는데 오탐만 8건(`auth`·`origin`·`outcome`) 늘고 새로 잡는 것이 없어
버렸다.

**Bash 의 `grep` 도 본다.** `Grep`·`Glob` 도구만 막으면 구멍이 그대로다 — 하네스는 어떤 모드에서
모델에게 *"검색은 Bash 의 `grep` 으로 하라"* 고 지시하고, 그런 세션에서 Bash grep 은 우회가 아니라
**기본 경로**다. 대상은 `grep`·`egrep`·`fgrep`·`rg`·`ag`·`ack`·`git grep` 이며, 명령에서 패턴을 뽑아내
`Grep` 과 **완전히 같은 휴리스틱**에 넣는다. `find` 는 뺐다 — 파일명 검색은 규칙 문서가 Glob 에
맡긴 영역이다.

셸 파싱은 전 구간 "확신 없으면 통과"다. 세그먼트의 **첫 토큰만** 바이너리로 인정하고(`echo "run grep
later"` 가 검색으로 읽히지 않는 이유), `|` 뒤 세그먼트는 건너뛰며(`ps aux | grep node` 는 stdout
필터다), heredoc(`<<`)이 있으면 통째로 통과시킨다 — 본문의 단어를 `shlex` 가 명령과 구분하지 못하기
때문이다. 명령 치환 `$(grep …)` 과 `xargs grep` 은 **의도적으로 놓친다.**

**비용을 알고 지불한다.** Bash 를 매처에 넣으면 이 훅이 **켜진 모든 프로젝트의 모든 Bash 호출마다**
프로세스로 뜬다(호출당 python 기동 수십 ms). v1.9.0 은 바로 이 비용 때문에 Bash 를 채택하지
않았는데, 그 판단은 Bash grep 이 부차적 경로라는 전제 위에 있었고 **그 전제가 틀렸다.** 대신 Bash
분기는 가장 싼 검사(명령에 검색 바이너리 이름이 있는가)로 먼저 빠져나가도록 짰다.

**완화 없이 매번 차단한다.** "세션당 1회"·"N회마다" 같은 완화는 심볼 검색의 일부만 codegraph 로
보낸다. 목적이 "소스 검색은 codegraph 로"인 이상 통과분이 남으면 목적 자체를 놓친다.

**그런데도 전역 배포가 안전한 이유는 차단이 복구 가능하기 때문이다.** 같은 `(도구, 패턴)` 은 에이전트당
한 번만 차단되므로, 동일한 호출을 그대로 다시 하면 **반드시** 통과한다. codegraph 가 답하지 못하는
심볼을 grep 으로 확인하는 길이 늘 열려 있고, 훅이 오판했을 때의 최대 대가는 **도구 호출 한 번
재시도**다. 차단하는 훅을 플러그인으로 전역 배포할 수 있는 조건이 이것 하나다.

상태는 `{tmpdir}/codegraph-search-gate/{에이전트 해시}.json` 에 둔다. **OS 가 이 디렉터리를 주기적으로
비운다**(macOS 는 `/var/folders/.../T/`). 그래서 정리가 차단과 재시도 **사이**에 끼면 같은 검색이 한 번
더 막힌다 — 그다음은 통과하므로 루프는 아니지만, "재호출은 반드시 통과한다"가 그 경계에서는 "한 번 더
막힐 수 있다"가 된다. 같은 이유로 **`denied` 배열은 누적 감사 기록이 아니다** — 마지막 정리 이후의 것만
담으므로 총 차단 건수를 세는 데 쓸 수 없다. **키가 `session_id` 가 아니라
`agent_id` 인 것이 핵심이다** — 서브에이전트는 부모와 `session_id` 를 공유하지만 고유한 `agent_id` 를
받으므로, 이 키로만 "에이전트당 한 번"이 실제로 에이전트당 한 번이 된다. `agent_id` 가 없는 메인
세션은 `session_id` 로 떨어진다. 기록은 차단 **직전에** 하고, 기록이 실패하면 차단하지 않는다 —
기록 없이 차단하면 재호출도 차단돼 이 훅이 절대 만들면 안 되는 루프가 된다.

**도구 이름은 `hooks.json` 에만 있다.** 훅 코드에는 이름 목록이 없다 — `Bash` 한 곳만 예외인데,
셸 명령은 파싱해야 패턴이 나오기 때문이다. 그 밖에는 `tool_input` 에 `pattern` 문자열이 있으면 검색으로
본다. 이름을 두 곳에 두면 **둘 다 맞아야 동작하는데 어긋나도 아무 신호가 없다** — matcher 가 새 이름을
잡아도 훅이 조용히 통과시킨다. 그래서 하나로 줄였고, 덕분에 이 훅이 모르는 검색 도구라도 matcher 가
보내주기만 하면 그대로 잡힌다.

### 훅이 안 뛰는 것 같을 때

이 훅들의 실패는 **에러 없이 조용하다.** 조건 하나만 어긋나도 아무것도 출력하지 않고 통과하는 것이
설계이고, 그건 matcher 의 도구 이름이 틀렸을 때도 똑같이 보인다. 그래서 추측 대신 순서대로 측정한다.

**1. 차단된 적이 있는가 — 상태 파일**

```bash
D=$(python3 -c "import tempfile,os;print(os.path.join(tempfile.gettempdir(),'codegraph-search-gate'))")
ls "$D" 2>/dev/null && cat "$D"/*.json
```

`{"denied": ["Bash handleSubmit", …]}` 가 보이면 그 경로는 살아 있는 것이다. 도구 이름이 접두어로
붙으므로 **어느 경로가 잡혔는지까지** 여기서 읽힌다.

> zsh 에서 `cat "$D"/*.json` 은 매칭되는 파일이 없으면 `no matches found` 로 **명령 전체를 중단**시킨다.
> `2>/dev/null` 로는 안 막힌다 — 실패가 셸의 글롭 확장 단계에서 일어나기 때문이다. 위처럼 `ls` 로
> 존재를 먼저 확인하거나 `setopt local_options null_glob` 을 앞에 둔다.

**2. 그 도구가 쓰이기는 하는가 — 세션 기록 집계**

하네스가 이미 transcript 에 도구 이름을 남겨 뒀다. **소급해서 읽히고, 설정을 건드리지 않고,
검색을 다시 시킬 필요도 없다.** 그래서 이게 첫 번째 실측 수단이다.

```bash
python3 - "$PWD" <<'PY'
import collections, glob, json, os, sys
d = os.path.join(os.path.expanduser("~/.claude/projects"), os.path.abspath(sys.argv[1]).replace("/", "-"))
n, k = collections.Counter(), collections.defaultdict(set)
for p in glob.glob(os.path.join(d, "*.jsonl")):
    for line in open(p, encoding="utf-8", errors="replace"):
        if '"tool_use"' not in line: continue
        try: rec = json.loads(line)
        except ValueError: continue
        for b in (rec.get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                n[b["name"]] += 1
                if isinstance(b.get("input"), dict): k[b["name"]].update(b["input"])
for name, c in n.most_common():
    print("%-40s %5d  %s" % (name, c, ",".join(sorted(k[name])[:6])))
PY
```

도구 이름과 `tool_input` 키가 함께 나오므로 matcher 와 대조할 것이 한 번에 다 나온다.

> **검색 도구가 목록에 아예 없는 경우가 있다.** 그러면 matcher 가 깨진 게 아니라 **확인할 대상이
> 없는 것이다.** bypass permissions 모드는 모델에게 *"가능한 한 Bash 로 하라 — 검색은 `grep`,
> `find` 로"* 라고 지시하므로, 그런 환경에서는 `Grep`·`Glob` 이 한 번도 호출되지 않고 검색이 전부
> Bash 로 간다. 실측 사례 — 어떤 프로젝트의 도구 호출 1906건 중 `Grep`·`Glob` 은 **0건**이었고
> Bash 가 68%였다. 상태 파일에 `Grep …` 항목이 없다는 것은 그 자체로 고장의 근거가 아니다.

**3. 도구 이름 실측 — 살아 있는 세션에서**

2번으로 갈리지 않을 때만 쓴다(예: 이번 세션의 호출을 실시간으로 보고 싶을 때).
`TMPDIR` 이 세션마다 다를 수 있으므로 로그는 홈에 고정한다.

```bash
cat > ~/cg-probe.py <<'PY'
import json, os, sys
try:
    d = json.load(sys.stdin)
    ti = d.get("tool_input")
    keys = ",".join(sorted(ti)) if isinstance(ti, dict) else "-"
    with open(os.path.expanduser("~/cg-toolnames.log"), "a") as f:
        f.write("%s :: %s\n" % (d.get("tool_name", "?"), keys))
except Exception:
    pass
PY
```

프로젝트의 `.claude/settings.local.json` 에 아래를 넣고(기존 파일이 있으면 `hooks` 만 합친다) 검색을
몇 번 시킨 뒤 `sort -u ~/cg-toolnames.log` 를 본다. 설정은 재시작 없이 반영된다.

```json
{"hooks":{"PreToolUse":[{"matcher":".*","hooks":[{"type":"command",
 "command":"python3 -B /절대/경로/cg-probe.py","timeout":5}]}]}}
```

경로는 **절대경로**로 쓴다 — 훅이 도는 셸의 `~` 확장을 믿지 않는다. 찍힌 이름이 정본이고,
`hooks.json` 의 matcher 와 다르면 그게 원인이다. 확인이 끝나면 probe 를 반드시 지운다(모든 도구
호출마다 기록한다).

**4. 훅이 뛰었는데 죽었는가 — stderr**

`claude --debug` 로 실행하면 훅의 stderr 가 보인다. import 실패·타임아웃이 여기서 드러난다.

### 두 훅에 공통인 것

**전 구간 fail-open.** 플러그인 훅은 켜진 모든 프로젝트에서 발화하므로, 서브에이전트 디스패치를
막을 수 있는 가드는 가드가 없는 것보다 나쁘다. 예외는 통째로 삼키고 언제나 exit 0 한다.
게이트가 유일하게 하는 차단도 위의 복구 가능성으로 유계에 묶여 있다.

상향 탐색은 **git 저장소 루트와 `$HOME` 에서 멈춘다.** `codegraph init` 을 홈에서 한 번 잘못
실행해 생긴 `~/.codegraph` 하나가 홈 아래 모든 프로젝트를 "색인됨"으로 만들어, 무관한 프로젝트의
모든 세션에서 발화하는 전역 오탐이 되기 때문이다.

훅이 없는 환경(Cursor 등)은 규칙 문서 5절이 대신 덮는다 — 서브에이전트 프롬프트에 손으로 붙일
짧은 인용문이 거기 있다.
