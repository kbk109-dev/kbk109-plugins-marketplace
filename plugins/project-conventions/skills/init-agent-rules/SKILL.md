---
name: init-agent-rules
description: "프로젝트의 CLAUDE.md 본문을 AGENTS.md 로 이관해 Claude·Cursor 공용 단일 소스로 만들고, CLAUDE.md 는 @AGENTS.md 포인터로 바꾼 뒤 규칙(git 브랜치 워크플로, 코드 검색 codegraph)을 .claude/rules/ 와 .cursor/rules/ 양쪽에 설치하는 스킬. 반드시 이 스킬을 사용해야 하는 경우: 'init-agent-rules', 'AGENTS.md 만들어줘', 'CLAUDE.md 를 AGENTS.md 로 옮겨줘', 'CLAUDE.md 랑 AGENTS.md 같이 관리하고 싶어', '커서랑 클로드 규칙 같이 쓰게 해줘', 'Cursor 랑 Claude 설정 통일해줘', 'AGENTS.md 로 이관', '에이전트 규칙 설치', '프로젝트 규칙 초기 설정', 'git 브랜치 규칙 넣어줘', '브랜치 워크플로 규칙 설치해줘', '커밋 규칙 세팅해줘', 'codegraph 규칙 넣어줘', '코드 검색 규칙 설치해줘', '검색할 때 codegraph 쓰게 해줘', '.cursor/rules 만들어줘', 'cursor rules 설정', '프로젝트 초기 설정 해줘', '규칙 문서 세팅', 'set up AGENTS.md', 'migrate CLAUDE.md to AGENTS.md', 'share rules between Claude and Cursor', 'install git branch workflow rule', 'install codegraph search rule', 'set up project conventions', 'sync CLAUDE.md and AGENTS.md'. CLAUDE.md 가 없는 프로젝트에서는 실행되지 않는다 — 이관 대상이 없으므로 /init 를 먼저 안내한다."
---

# init-agent-rules — CLAUDE.md → AGENTS.md 이관과 규칙 설치

## 이 스킬이 만드는 구조

```
AGENTS.md                              ← 이전된 본문 + 규칙마다 마커 블록 (SSoT)
CLAUDE.md                              ← 안내문 + @AGENTS.md
.claude/rules/git-branch-workflow.md   ← 규칙 본문
.cursor/rules/git-branch-workflow.mdc  ← 프론트매터 + 동일 본문 (생성물)
.claude/rules/codegraph-search.md      ← 조건부: .codegraph/ 색인이 있을 때만
.cursor/rules/codegraph-search.mdc     ← 위와 같음
```

**왜 AGENTS.md 가 SSoT 인가.** Claude 는 `CLAUDE.md` 를, Cursor 는 `AGENTS.md` 를 읽는다.
같은 내용을 두 파일에 두면 반드시 갈라진다 — 한쪽만 고치게 되고, 갈라져도 에러가 나지 않아
알아채지 못한다. `CLAUDE.md` 가 `AGENTS.md` 를 가리키기만 하면 갈라질 여지 자체가 없어진다.

**왜 규칙은 별도 파일인가.** `.claude/rules/*.md` 는 Claude Code 가 project instructions 로
자동 로드하고, `.cursor/rules/*.mdc` 는 `alwaysApply: true` 로 Cursor 가 항상 주입한다.
각 도구의 네이티브 경로를 쓰는 편이 문서 본문에 규칙을 섞는 것보다 확실하다.

## 설치되는 규칙

| 규칙 | 내용 | 설치 조건 |
|---|---|---|
| `git-branch-workflow` | `dev` 에서 분기·네이밍·커밋 승인 게이트·`dev` 로만 `--no-ff` 머지 (main 은 사람이) | 항상 |
| `codegraph-search` | 코드 검색은 codegraph 우선, 호출 불가 시 경고 후 grep 폴백 | 프로젝트 루트에 `.codegraph/` 가 있을 때만 |

**codegraph 규칙이 조건부인 이유.** 색인이 없는 프로젝트에 이 규칙을 넣으면 에이전트가 매 검색마다
쓸 수 없는 도구를 시도하고 경고를 띄운다 — 규칙이 소음이 된다. 스크립트가 `.codegraph/` 존재로
자동 판정하므로 **모델이 판단하거나 사용자에게 물을 필요가 없다.** 판정을 뒤집으려면
`--codegraph-rule on|off` 를 쓴다.

선택되지 않은 규칙은 **건너뛸 뿐 지우지 않는다.** 색인을 잠시 지운 상태에서 재설치했다고 해서
이미 쓰던 규칙이 사라지면 안 된다. 규칙 제거는 `.md`·`.mdc`·`AGENTS.md` 마커 블록을 직접 지우는
수동 작업이다.

## 입력값 확인 (게이트)

세 가지를 순서대로 확인한다. 하나라도 어긋나면 **파일을 하나도 건드리지 않고** 중단한다.

### Step 0-1. CLAUDE.md 존재

`CLAUDE.md` 가 없거나 비어 있으면 중단하고 이렇게 안내한다:

> 이 프로젝트에 `CLAUDE.md` 가 없습니다. 이 스킬은 기존 `CLAUDE.md` 를 옮기는 것이지
> 없는 내용을 지어내지 않습니다. `/init` 으로 `CLAUDE.md` 를 먼저 만든 뒤 다시 불러 주세요.

프로젝트 지시를 추측으로 채우면 그 추측이 이후 모든 세션의 전제가 된다. 멈추는 게 낫다.

### Step 0-2. AGENTS.md 충돌

`AGENTS.md` 가 이미 있고 그 내용이 포인터 구조가 아니면 **중단하고 사용자에게 묻는다.**
자동 병합하지 않는다 — 규칙 문서는 조용한 유실이 치명적이다.

처리 절차와 선택지별 결과는 [`references/conflict_policy.md`](./references/conflict_policy.md)
를 따른다.

### Step 0-3. 작업 트리 상태

```bash
git status --short
```

깨끗하지 않으면 사용자에게 알리고 진행 여부를 확인한다. 이 스킬은 `CLAUDE.md` 를 재작성하므로
되돌릴 수 있는 상태에서 실행하는 편이 안전하다. git 저장소가 아니면 그대로 진행하되,
`git mv` 대신 일반 복사가 쓰인다는 점을 알린다.

## 실행

### Step 1. 커밋 전 검증 명령 결정

`git-branch-workflow` 규칙 4절의 "커밋 전 반드시 실행" 줄에 넣을 명령을 정한다. 이 값은 git 규칙에만
들어간다 — `codegraph-search` 는 플레이스홀더가 없어 프로젝트마다 같은 본문으로 설치된다.
순서대로 시도한다:

1. `CLAUDE.md` 에 "명령" / "Commands" / "개발" 류 섹션이 있으면 거기서 테스트·린트·빌드
   명령을 찾는다
2. 없으면 `package.json` 의 `scripts.test`, `Makefile` 의 `test` 타깃 등을 확인한다
3. 후보를 찾았으면 사용자에게 확인받는다. 못 찾았으면 **묻고**, 사용자가 없다고 하면 빈 값으로
   둔다 — 빈 값이면 해당 줄이 규칙에서 통째로 빠진다

없는 명령을 규칙에 박아 두면 에이전트가 매 커밋마다 실패하는 명령을 실행한다. 비워 두는 편이 낫다.

### Step 2. 설치

먼저 `--dry-run` 으로 무엇이 바뀌는지 사용자에게 보여준다:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/init-agent-rules/scripts/install_agent_rules.py \
  --project-root . \
  --pre-commit-check "{Step 1 에서 정한 명령}" \
  --dry-run
```

`--dry-run` 출력의 `(main branch: X)` 를 **사용자에게 확인받는다.** 탐지 순서는
`origin/HEAD` → 로컬 `main`/`master` → 로컬 브랜치가 하나뿐이면 그것 → `main` 이다.
원격이 없고 브랜치가 여럿인 저장소에서는 맞힐 방법이 없으므로 `main` 으로 떨어진다. 틀렸으면
`--main-branch` 로 지정한다 — 이 값이 규칙 본문 전체에 박히므로 나중에 고치려면 재설치해야 한다.

`--dry-run` 출력에는 어떤 규칙이 설치되는지도 나온다. `.codegraph/ 없음 — codegraph-search 규칙
건너뜀` 이 보이는데 사용자가 codegraph 를 쓰고 있다면 색인을 만들지(`codegraph init`) 아니면
`--codegraph-rule on` 으로 강제할지 확인한다. **색인 생성을 대신 실행하지 않는다.**

승인받은 뒤 같은 명령을 `--dry-run` 없이 실행한다.

**모델이 이 파일들을 직접 쓰지 않는다.** `.mdc` 사본은 `.md` 원본과 바이트 단위로 같아야
하는데, 손으로 옮겨 쓰면 공백 하나로도 어긋난다 — 이 플러그인이 막으려는 바로 그 실패다.

주요 인자:

| 인자 | 용도 |
|---|---|
| `--pre-commit-check` | git 규칙 4절에 들어갈 검증 명령. 생략하면 해당 줄 삭제 |
| `--main-branch` | 기본 브랜치명. 생략하면 `origin/HEAD` → `main` → `master` 순으로 탐지 |
| `--codegraph-rule` | `auto`(기본, `.codegraph/` 존재로 판정) / `on` / `off` |
| `--on-existing-agents` | `abort`(기본) / `append-claude` / `keep-agents` |
| `--force` | `keep-agents` 가 미커밋 `CLAUDE.md` 를 폐기하는 것을 허용 |
| `--sync-mdc` | `.mdc` 만 현재 `.md` 본문으로 재생성. 아래 참조 |

### 규칙을 프로젝트에 맞게 고칠 때 (`--sync-mdc`)

설치는 규칙을 **템플릿에서** 렌더한다. 따라서 `.claude/rules/<규칙>.md` 를 손으로 고친 뒤 전체
설치를 다시 돌리면 그 수정이 템플릿 내용으로 덮어써진다.

프로젝트 고유 규칙을 추가하려면 이 순서를 지킨다:

1. `.claude/rules/<규칙>.md` 를 고친다 — 이쪽이 규칙의 원본이다
2. 사본을 다시 맞춘다 (설치된 모든 규칙을 한 번에 미러링한다):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/init-agent-rules/scripts/install_agent_rules.py \
  --project-root . --sync-mdc
```

`--sync-mdc` 는 `.mdc` 만 건드린다. `CLAUDE.md` · `AGENTS.md` · `.md` 원본은 그대로 둔다.
검사 스킬이 비교하는 대상도 템플릿이 아니라 이 `.md` 원본이므로, 고친 규칙도 정상 통과한다.

종료 코드 `3` 은 게이트 실패다. **재시도하지 말고** stderr 메시지를 사용자에게 그대로 전달한 뒤
지시를 받는다.

### Step 3. 자기 검증

설치 직후 검사 스크립트를 돌려 구조가 온전한지 확인한다:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/check-agent-rules/scripts/check_agent_rules.py --project-root .
```

exit 0 이 아니면 설치가 실패한 것이다. stderr 를 사용자에게 그대로 보여준다.

## 에러 처리

| 상황 | 대응 |
|---|---|
| exit 3, `CLAUDE.md not found` | `/init` 안내 후 종료. 뼈대를 지어내지 않는다 |
| exit 3, `AGENTS.md already exists` | `references/conflict_policy.md` 절차로 넘어간다 |
| exit 3, `keep-agents ... not committed` | 먼저 커밋하도록 안내. `--force` 는 사용자가 명시적으로 요구할 때만 |
| exit 2 | 인자·경로 문제. `--project-root` 가 프로젝트 루트를 가리키는지 확인 |
| exit 1 | 쓰기 실패. 권한·디스크를 확인하고 사용자에게 보고 |
| Step 3 검사 실패 | 설치가 불완전하다. 되돌리려면 `git checkout -- .` 를 안내 |

## 결과 보고

작업 후 사용자에게 다음 형식으로 보고한다.

```
## 에이전트 규칙 설치 완료

| 파일 | 상태 |
|---|---|
| `AGENTS.md` | CLAUDE.md 본문 이관 + 규칙 포인터 |
| `CLAUDE.md` | @AGENTS.md 포인터로 교체 |
| `.claude/rules/git-branch-workflow.md` | 생성 |
| `.cursor/rules/git-branch-workflow.mdc` | 생성 (본문 동일) |

기본 브랜치: {탐지된 이름} · 커밋 전 검증: {명령 또는 "없음"}
codegraph 규칙: {설치됨 | 건너뜀 — .codegraph/ 색인 없음}

### 앞으로

- 지시를 추가할 때는 `AGENTS.md` 를 고친다. `CLAUDE.md` 에 쓰면 Cursor 가 못 읽는다.
- 규칙 본문을 고칠 때는 `.claude/rules/` 쪽을 고치고 이 스킬을 다시 실행해 `.mdc` 를 재생성한다.
- `/project-conventions:check-agent-rules` 로 사본이 갈라졌는지 검사한다.
```

codegraph 규칙이 설치됐으면 표에 `.claude/rules/codegraph-search.md` 와
`.cursor/rules/codegraph-search.mdc` 행을 추가한다. 건너뛴 경우에는 마지막 줄로 그 이유만 밝히고,
색인을 만들라고 재촉하지 않는다 — 색인 생성은 사용자의 판단이다.

커밋은 **하지 않는다.** 변경 요약을 보여주고 사용자의 판단을 받는다.

## 참조 문서

- [`references/conflict_policy.md`](./references/conflict_policy.md) — 기존 `AGENTS.md` 가
  있을 때의 diff 제시 절차와 선택지별 결과
- [`templates/git-branch-workflow.md`](./templates/git-branch-workflow.md) — 설치되는 규칙 본문.
  `{{MAIN_BRANCH}}` `{{PRE_COMMIT_CHECK}}` 플레이스홀더를 쓴다
- [`templates/codegraph-search.md`](./templates/codegraph-search.md) — 코드 검색 규칙 본문.
  플레이스홀더 없음. `.codegraph/` 색인이 있는 프로젝트에만 설치된다
