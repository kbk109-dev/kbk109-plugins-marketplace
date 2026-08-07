# project-conventions

Claude 와 Cursor 를 번갈아 쓰는 프로젝트에서, 에이전트 지시 문서를 한 곳으로 모으고 작업 규칙을
양쪽에 설치한다. 스킬 2개.

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

### `init-agent-rules`

`CLAUDE.md` 본문을 `AGENTS.md` 로 옮기고 `CLAUDE.md` 는 `@AGENTS.md` 한 줄로 바꾼다. 이어서 규칙을
`.claude/rules/` 와 `.cursor/rules/` 양쪽에 설치하고, `AGENTS.md` 말미에 규칙마다 그것을 가리키는
마커 블록을 넣는다.

```
/project-conventions:init-agent-rules
```

설치되는 규칙:

| 규칙 | 내용 | 설치 조건 |
|---|---|---|
| `git-branch-workflow` | 브랜치 분리·네이밍, 커밋 승인 게이트, `--no-ff` 머지 | 항상 |
| `codegraph-search` | 코드 검색은 codegraph 우선, 호출 불가 시 경고 후 grep 폴백 | `.codegraph/` 색인이 있을 때만 |

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
