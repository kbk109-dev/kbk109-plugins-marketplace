---
name: init-agent-rules
description: "프로젝트의 CLAUDE.md 본문을 AGENTS.md 로 이관해 Claude·Cursor 공용 단일 소스로 만들고, CLAUDE.md 는 @AGENTS.md 포인터로 바꾼 뒤 규칙(git 브랜치 워크플로)을 .claude/rules/ 와 .cursor/rules/ 양쪽에 설치하는 스킬. 반드시 이 스킬을 사용해야 하는 경우: 'init-agent-rules', 'AGENTS.md 만들어줘', 'CLAUDE.md 를 AGENTS.md 로 옮겨줘', 'CLAUDE.md 랑 AGENTS.md 같이 관리하고 싶어', '커서랑 클로드 규칙 같이 쓰게 해줘', 'Cursor 랑 Claude 설정 통일해줘', 'AGENTS.md 로 이관', '에이전트 규칙 설치', '프로젝트 규칙 초기 설정', 'git 브랜치 규칙 넣어줘', '브랜치 워크플로 규칙 설치해줘', '커밋 규칙 세팅해줘', '.cursor/rules 만들어줘', 'cursor rules 설정', '프로젝트 초기 설정 해줘', '규칙 문서 세팅', 'set up AGENTS.md', 'migrate CLAUDE.md to AGENTS.md', 'share rules between Claude and Cursor', 'install git branch workflow rule', 'set up project conventions', 'sync CLAUDE.md and AGENTS.md'. CLAUDE.md 가 없는 프로젝트에서는 실행되지 않는다 — 이관 대상이 없으므로 /init 를 먼저 안내한다."
---

# init-agent-rules — CLAUDE.md → AGENTS.md 이관과 규칙 설치

## 이 스킬이 만드는 구조

```
AGENTS.md                              ← 카파시 블록 + 다듬은 본문 + 규칙마다 마커 블록 (SSoT)
CLAUDE.md                              ← 안내문 + @AGENTS.md
.claude/rules/git-branch-workflow.md   ← 규칙 본문
.cursor/rules/git-branch-workflow.mdc  ← 프론트매터 + 동일 본문 (생성물)
```

**왜 AGENTS.md 가 SSoT 인가.** Claude 는 `CLAUDE.md` 를, Cursor 는 `AGENTS.md` 를 읽는다.
같은 내용을 두 파일에 두면 반드시 갈라진다 — 한쪽만 고치게 되고, 갈라져도 에러가 나지 않아
알아채지 못한다. `CLAUDE.md` 가 `AGENTS.md` 를 가리키기만 하면 갈라질 여지 자체가 없어진다.

**왜 규칙은 별도 파일인가.** `.claude/rules/*.md` 는 Claude Code 가 project instructions 로
자동 로드하고, `.cursor/rules/*.mdc` 는 `alwaysApply: true` 로 Cursor 가 항상 주입한다.
각 도구의 네이티브 경로를 쓰는 편이 문서 본문에 규칙을 섞는 것보다 확실하다.

## 설치되는 규칙

| 규칙 | 내용 |
|---|---|
| `git-branch-workflow` | `dev` 에서 분기·네이밍·커밋 승인 게이트·`dev` 로만 `--no-ff` 머지 (main 은 사람이) |

규칙 제거는 `.md`·`.mdc`·`AGENTS.md` 마커 블록을 직접 지우는 **수동 작업**이다 — 스크립트는
어떤 경우에도 설치된 규칙을 지우지 않는다.

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

## Step 0.5. 이관 전 본문 다듬기

Step 0 게이트를 **통과한 뒤에만** 실행한다. 게이트가 실패하면 여기까지 오지 않는다 — 파일을
하나도 건드리지 않고 중단하는 규칙은 그대로다.

`/init` 초안은 이관되는 순간 SSoT 가 된다. 200줄을 넘는 분량, `CLAUDE.md` 역할을 벗어난 절차,
행동 가드레일 부재가 그대로 굳으면 이후 모든 세션이 그것을 전제로 돌아간다. 옮긴 뒤에 고치는
것보다 옮기기 전에 고치는 편이 싸다.

**대상은 이관될 본문 하나뿐이다.** 보통 `CLAUDE.md` 이고, 이미 포인터 구조(`@AGENTS.md` +
`AGENTS.md` 존재)로 재실행하는 경우에는 `AGENTS.md` 본문이다. **포인터 파일에는 카파시 본문을
넣지 않는다.** `.claude/rules/*.md` 와 `.mdc` 는 설치 스크립트의 것이므로 손대지 않는다.

**사용자가 "다듬지 말고 그대로 옮겨줘" 라고 명시하면 이 절을 통째로 건너뛴다.** 사용자 지시가
스킬 절차보다 우선한다. 이때도 설치 보고에는 줄 수가 남는다.

판정 기준·정본 텍스트·표 형식은
[`references/claude_md_rewrite.md`](./references/claude_md_rewrite.md) 에 있다.

### 0.5-1. 카파시 4원칙 검출

Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven Execution (또는 한글
네 제목 — 생각 먼저 / 단순함 우선 / 외과적 수정 / 목표 주도 실행)이 **전용 섹션으로 넷 다**
있으면 skip 한다. 하나라도 없으면 불완전으로 보고 0.5-2 로 간다.

이미 있는 비슷한 문장을 합치거나 지우지 않는다 — 사용자가 쓴 문장을 모델이 "중복" 으로 판정해
지우는 쪽이, 원칙이 두 번 적히는 것보다 나쁘다.

### 0.5-2. 짧은 블록 prepend

reference 2절의 정본 블록을 **그대로** 넣는다. 늘리지 않고, 원문(약 65줄)을 펼치지 않는다.
기존 본문은 교체하지 않고 블록 **아래에 그대로** 둔다.

**넣는 위치는 H1 바로 아래다** (H1 이 없으면 맨 위). 설치 스크립트의 `retitle()` 은 첫 비어 있지
않은 줄 하나만 보고 `# CLAUDE.md` → `# AGENTS.md` 로 바꾼 뒤 멈추므로, H2 블록을 그 위에 얹으면
제목 변환이 조용히 건너뛰어진다. 에러는 나지 않는다.

### 0.5-3. What / How 분류

본문을 문단·불릿 단위로 나눈다. 남기는 것은 **What** — 정확한 명령, 패키지·언어 제약, 검증
가능한 컨벤션, 디렉터리 지도 한 줄, 코드에서 추론할 수 없는 함정. 빼는 후보는 **How** —
다단계 절차, 순서 지시, 튜토리얼, 코드에서 이미 읽히는 장문 아키텍처 해설.

리트머스: **오타 한 줄을 고치는 대화에도 매번 필요한가?** 아니면 그 작업을 할 때만 필요한가.
후자면 How 후보다. 목록과 재작성 예시는 reference 3절에 있다.

**이 단계에서는 파일을 만들지 않는다.** 후보로만 표시한다.

### 0.5-4. 분리 승인 게이트 (필수)

How 후보가 **하나라도** 있으면 설치 스크립트를 호출하지 말고 표를 보여 승인받는다
(표 형식과 목적지 규칙은 reference 4절).

승인 전까지 **`skills/` 와 `.claude/rules/` 에 새 파일을 하나도 만들지 않는다.**
침묵은 거절이 아니다 — 답이 올 때까지 기다린다. 거절·무응답 상태에서 후보를 삭제하지도 않는다.

후보별로 **승인 / 축약만 / 보류** 를 고르게 하고, 승인한 것만 그 때 만든다. 승인 범위 밖 파일은
만들지 않는다.

### 0.5-5. 200줄 예산

측정 대상은 **이관 후 `AGENTS.md` 전체 줄 수** 다. 카파시 블록 + 다듬은 본문 + 규칙 마커 블록을
포함하고, `.claude/rules/*.md` · `.mdc` · 새로 만든 `SKILL.md` 는 제외한다.

200줄은 **목표이지 상한이 아니다.** 넘겨도 잘리지 않으므로 뒷부분을 truncate 하지 않는다 —
잘리는 200줄/25KB 상한은 auto-memory `MEMORY.md` 전용이다.

예상 줄 수를 사용자에게 보여 준다. 200 이상이면 더 자를 What 이나 추가 분리 후보를 제안하고
**다시 승인**받는다. 넘긴 채 스크립트를 돌리지 않는 것이 기본이다. 사용자가 "이대로 이관" 을
명시하면 진행하되 설치 보고에 줄 수와 목표 미달을 적는다.

손으로 세지 말고 Step 2 의 `--dry-run` 출력에 있는 `예상 AGENTS.md 줄 수` 를 쓴다 — 마커 블록까지
반영된 값이다.

### 0.5-6. 이관 전 최종 확인

다듬은 본문의 diff 를 보여 주고 **승인받은 뒤에만** Step 1 로 넘어간다.

Step 0-3 에서 확인한 "깨끗한 작업 트리" 는 *이 스킬이 실행되기 전부터 있던* 미커밋 변경을 뜻한다.
Step 0.5 는 그 뒤에 의도적으로 `CLAUDE.md` 를 더럽히므로 두 지시는 충돌하지 않는다. 다만 그 상태로
설치하면 스크립트가 `git mv` 대신 직접 쓰기로 빠져 **rename 히스토리만 사라진다**(본문 이관은
정상). 히스토리를 남기고 싶으면 Step 0.5 변경을 먼저 커밋하도록 안내한다 —
**스킬은 여전히 커밋하지 않는다.**

## 실행

### Step 1. 커밋 전 검증 명령 결정

`git-branch-workflow` 규칙 4절의 "커밋 전 반드시 실행" 줄에 넣을 명령을 정한다.
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

승인받은 뒤 같은 명령을 `--dry-run` 없이 실행한다.

**모델이 이 파일들을 직접 쓰지 않는다.** `.mdc` 사본은 `.md` 원본과 바이트 단위로 같아야
하는데, 손으로 옮겨 쓰면 공백 하나로도 어긋난다 — 이 플러그인이 막으려는 바로 그 실패다.

주요 인자:

| 인자 | 용도 |
|---|---|
| `--pre-commit-check` | git 규칙 4절에 들어갈 검증 명령. 생략하면 해당 줄 삭제 |
| `--main-branch` | 기본 브랜치명. 생략하면 `origin/HEAD` → `main` → `master` 순으로 탐지 |
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
| `AGENTS.md` | CLAUDE.md 본문 이관 + 규칙 포인터 ({N}줄 · 목표 200 미만 {충족|미달}) |
| `CLAUDE.md` | @AGENTS.md 포인터로 교체 |
| `.claude/rules/git-branch-workflow.md` | 생성 |
| `.cursor/rules/git-branch-workflow.mdc` | 생성 (본문 동일) |

Step 0.5: 카파시 블록 {prepend | 이미 있어 skip | 생략 — 사용자 요청} · How 후보 {N}건 (승인 {N} / 축약 {N} / 보류 {N})
새로 만든 파일: {승인된 skill·rules 경로 | 없음}
기본 브랜치: {탐지된 이름} · 커밋 전 검증: {명령 또는 "없음"}

### 앞으로

- 지시를 추가할 때는 `AGENTS.md` 를 고친다. `CLAUDE.md` 에 쓰면 Cursor 가 못 읽는다.
- 규칙 본문을 고칠 때는 `.claude/rules/` 쪽을 고치고 이 스킬을 다시 실행해 `.mdc` 를 재생성한다.
- `/project-conventions:check-agent-rules` 로 사본이 갈라졌는지 검사한다.
```

커밋은 **하지 않는다.** 변경 요약을 보여주고 사용자의 판단을 받는다.

## 참조 문서

- [`references/claude_md_rewrite.md`](./references/claude_md_rewrite.md) — Step 0.5 의
  정본. 카파시 검출 기준과 짧은 블록 원문, What/How 판정 목록, 분리 승인 표 형식,
  200줄 예산 계산
- [`references/conflict_policy.md`](./references/conflict_policy.md) — 기존 `AGENTS.md` 가
  있을 때의 diff 제시 절차와 선택지별 결과
- [`templates/git-branch-workflow.md`](./templates/git-branch-workflow.md) — 설치되는 규칙 본문.
  `{{MAIN_BRANCH}}` `{{PRE_COMMIT_CHECK}}` 플레이스홀더를 쓴다
