---
name: check-agent-rules
description: "AGENTS.md 를 단일 소스로 쓰는 프로젝트에서 규칙 문서가 갈라졌는지 검사하는 스킬. .cursor/rules/*.mdc 사본이 .claude/rules/*.md 원본과 여전히 같은지, CLAUDE.md 가 포인터로 남아 있는지, AGENTS.md 마커 블록이 온전한지, (설치돼 있다면) Notion REST 클라이언트·차단 훅·settings.json 등록이 템플릿과 일치하는지를 확인한다. 반드시 이 스킬을 사용해야 하는 경우: 'check-agent-rules', '규칙 갈라졌는지 확인', 'AGENTS.md 검사', 'CLAUDE.md AGENTS.md 동기화 확인', 'cursor rules 랑 claude rules 같은지 확인', '.mdc 랑 .md 다른지 봐줘', '규칙 문서 검증', '에이전트 규칙 점검', 'drift 검사', '규칙 동기화 확인해줘', '커서 규칙 최신인지 봐줘', '규칙 파일 정합성', 'notion_api.py 갈라졌는지 확인', 'Notion 차단 훅 확인', 'check agent rules', 'verify AGENTS.md setup', 'check rule drift', 'are cursor and claude rules in sync', 'validate agent rule files'. 커밋 전 점검이나 다른 도구로 규칙을 고친 뒤 확인할 때도 사용한다."
---

# check-agent-rules — 규칙 문서 갈라짐 검사

## 무엇을 검사하는가

`AGENTS.md` 와 `CLAUDE.md` 는 포인터 구조라 갈라질 수 없다. **갈라지는 건
`.cursor/rules/*.mdc` 사본이다.** 생성물인데 손으로 고쳐도 에러가 안 나고, 그 순간부터 Cursor 와
Claude 가 서로 다른 규칙을 따른다. 검사 5 가 이 스킬의 존재 이유이고, 나머지는 검사 5 가
의미를 갖는 구조를 지킨다.

| # | 검사 | 깨지는 경우 |
|---|---|---|
| 1 | `AGENTS.md` 존재·비어있지 않음 | 설치를 안 했거나 파일을 지움 |
| 2 | `CLAUDE.md` 가 `@AGENTS.md` 를 포함 | 포인터를 지워 Claude 가 지시를 못 읽음 |
| 3 | `CLAUDE.md` 에 자체 본문 없음 | 지시를 CLAUDE.md 에 다시 씀 → Cursor 가 못 봄 |
| 4 | `.claude/rules/<규칙>.md` 존재 | 규칙 본문 유실 |
| 5 | `.cursor/rules/<규칙>.mdc` 본문 == 4번과 바이트 동일 | **사본을 손으로 고침 → 두 도구가 갈라짐** |
| 6 | `AGENTS.md` 에 규칙별 마커 블록 온전 | 블록을 지우거나 반쪽만 남김 |
| 7 | (`notion-api-only` 설치 시만) `.claude/scripts/notion_api.py` 가 플러그인 템플릿과 sha256 동일 | 손으로 고침 → 훅이 안내하는 명령과 실제 스크립트가 갈라짐 |
| 8 | (〃) `.claude/hooks/notion_mcp_gate.py` 가 플러그인 템플릿과 sha256 동일 | 손으로 고침 → 차단 조건이 조용히 바뀜 |
| 9 | (〃) `.claude/settings.json` 의 `PreToolUse` 에 그 훅 등록이 정확히 1개 | 훅이 등록 안 됐거나 중복 등록됨 → 차단이 아예 안 되거나 이중 발화 |

검사 3 은 `##` 섹션 헤딩 유무와 줄 수로 판정한다. 포인터 `CLAUDE.md` 는 헤딩 1개와 짧은
안내문뿐이므로, H2 가 나타났다는 건 본문이 다시 들어왔다는 뜻이다.

**검사 4·5·6 은 규칙마다 반복된다.** 대상은 `git-branch-workflow`(항상 검사) 와
`notion-api-only`(설치돼 있을 때만 검사 — 없는 것 자체는 실패가 아니다, 이 프로젝트가 그
규칙을 선택하지 않은 것뿐이다). 어떤 규칙이 "설치돼 있다"는 판정은 `.md`·`.mdc`·마커 블록
**셋 중 하나라도 있으면** 참이고, 그때부터 셋 다 정합해야 한다 — 반쪽 설치가 조용한 통과가
되지 않게 하려는 것이다. **검사 7·8·9 도 `notion-api-only` 가 그 정의로 설치돼 있을 때만**
수행되며, 비교 대상은 **이 플러그인 자신의 템플릿**이다(검사 5 가 `.mdc` ↔ `.md` 를 보는 것과
같은 성격 — 다른 플러그인과의 비교가 아니다).

## 실행

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/check-agent-rules/scripts/check_agent_rules.py --project-root .
```

| 종료 코드 | 의미 |
|---|---|
| 0 | 전부 통과 (`OK` 출력) |
| 1 | 하나 이상 실패. stderr 에 항목당 한 줄 |
| 2 | 인자·경로 문제 |

`--quiet` 를 붙이면 성공 시 아무것도 출력하지 않는다. pre-commit 훅에 걸 때 쓴다.

## 결과 처리

**exit 0** — 통과했다고 보고하고 끝낸다.

**exit 1** — stderr 의 각 줄을 사용자에게 그대로 보여준 뒤, 항목별로 다음과 같이 안내한다.

| 실패 항목 | 안내 |
|---|---|
| 1, 4, 6 (파일·블록 부재) | `/project-conventions:init-agent-rules` 재실행으로 복구된다 |
| 2 (포인터 없음) | 같음. `CLAUDE.md` 가 재생성된다 |
| 3 (본문 유입) | **먼저 물어본다.** 새로 쓴 내용을 `AGENTS.md` 로 옮길지 확인한 뒤 옮기고, 그 다음 재실행한다. 재실행이 `CLAUDE.md` 를 덮어쓰므로 순서를 지켜야 내용이 안 날아간다 |
| 5 (`.mdc` 갈라짐) | **어느 쪽이 맞는지 사용자에게 확인한다.** 아래 절차 |
| 7, 8 (`notion_api.py`/`notion_mcp_gate.py` 갈라짐) | `/project-conventions:init-agent-rules --notion-rule on` 재실행으로 템플릿에서 다시 설치한다. 이 두 파일은 프로젝트별로 고치는 대상이 아니다(git-branch-workflow 처럼 `--sync-mdc` 로 보존할 프로젝트 고유 수정이 없다) |
| 9 (훅 미등록/중복) | 같은 명령으로 복구. `.claude/settings.json` 을 손으로 고쳤다면 그 편집이 지워지는지 먼저 확인하고 진행한다 |

### 검사 5 실패 — `.mdc` 가 갈라졌을 때

`.mdc` 쪽 수정이 의도된 것일 수도 있다. 먼저 차이를 보여준다 — `RULE` 에 stderr 가 지목한 규칙
이름(`git-branch-workflow` 등)을 넣는다:

```bash
RULE=git-branch-workflow
diff <(sed '1{/^---$/!q;};1,/^---$/d' ".cursor/rules/$RULE.mdc") \
     ".claude/rules/$RULE.md"
```

그리고 묻는다:

> `.mdc` 사본이 원본과 다릅니다. 위가 그 차이입니다.
> - `.mdc` 쪽 수정이 맞다면 → 그 내용을 `.claude/rules/` 원본에 반영한 뒤 재생성합니다
> - 원본이 맞다면 → `.mdc` 를 재생성해 수정분을 버립니다

`.mdc` 는 생성물이므로 **재생성하면 그쪽 수정은 사라진다.** 확인 없이 덮어쓰지 않는다.

## 이 검사를 자동으로 돌리려면

스크립트는 단독 실행되므로 pre-commit 훅에 걸 수 있다. 사용자가 원하면 안내한다:

```bash
echo 'python3 <스크립트 절대경로> --project-root . --quiet' >> .git/hooks/pre-commit
```

플러그인 경로는 설치 환경마다 다르므로, 훅에는 그 환경에서 확인한 절대 경로를 적는다.
`${CLAUDE_PLUGIN_ROOT}` 는 스킬 실행 중에만 정의되므로 훅 안에서는 해석되지 않는다.
