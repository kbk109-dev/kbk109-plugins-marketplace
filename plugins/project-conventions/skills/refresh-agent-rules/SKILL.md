---
name: refresh-agent-rules
description: "이미 AGENTS.md 를 단일 소스로 쓰는 프로젝트에서, 시간이 지나 문서가 실제 코드베이스와 어긋났는지 다시 분석해 갱신하는 스킬. 프로젝트를 스캔해 명령·패키지 매니저·디렉터리 구조 같은 사실을 모으고 AGENTS.md 의 주장과 대조한 뒤, 바꿀 것이 있을 때만 승인을 받아 고친다. 바꿀 것이 없으면 파일을 건드리지 않는다. 반드시 이 스킬을 사용해야 하는 경우: 'refresh-agent-rules', 'AGENTS.md 업데이트', 'AGENTS.md 갱신해줘', 'AGENTS.md 최신화', 'AGENTS.md 현행화', 'AGENTS.md 낡았어', 'AGENTS.md 가 지금 코드랑 맞는지 봐줘', '프로젝트 바뀌었으니 에이전트 문서 반영해줘', '에이전트 지시 최신인지 확인하고 고쳐줘', '프로젝트 규칙 다시 분석해줘', '테스트 명령 바뀌었는데 문서도 고쳐줘', '디렉터리 구조 바뀐 거 문서에 반영', 'AGENTS.md 오래됐어', 'update AGENTS.md', 'refresh agent rules', 'AGENTS.md is out of date', 'sync AGENTS.md with the codebase', 're-analyze the project and update AGENTS.md', 'is AGENTS.md still accurate'. 아직 이관하지 않은 프로젝트에서는 실행되지 않는다 — 고칠 AGENTS.md 가 없으므로 init-agent-rules 를 먼저 안내한다."
---

# refresh-agent-rules — AGENTS.md 를 프로젝트 현황에 맞게 갱신

## 이 스킬의 자리

`init-agent-rules` 는 한 번 동작하고 끝난다. 그 뒤로 프로젝트는 계속 변한다 — 테스트 명령이
바뀌고, 디렉터리가 옮겨지고, 패키지 매니저가 갈리고, 문서가 가리키는 경로가 사라진다.
**`AGENTS.md` 는 그대로 남아 조용히 틀린 지시가 된다.** 틀린 지시는 없는 지시보다 나쁘다.

| 스킬 | 보는 것 |
|---|---|
| `init-agent-rules` | 구조를 **만든다** (1회) |
| `check-agent-rules` | 구조가 **깨졌는지** — 포인터·마커·`.mdc` 바이트 동일 |
| **이 스킬** | 내용이 **사실과 어긋났는지** |

`check-agent-rules` 로는 이걸 못 잡는다. 그 스킬은 `.mdc` 가 `.md` 와 같은지를 볼 뿐,
`.md` 에 적힌 `npm test` 가 아직 존재하는 명령인지는 보지 않는다.

**이 스킬은 이관하지 않는다.** 포인터 구조가 아니면 중단하고 `init` 을 안내한다.

## 고치는 것과 고치지 않는 것

`AGENTS.md` **본문 한 곳**만 고친다. 마커 블록 구간·`CLAUDE.md`·`.claude/rules/*.md`·`.mdc` 는
건드리지 않는다. 경계와 그 이유는
[`references/refresh_policy.md`](./references/refresh_policy.md) 1절에 있다.

## Step 0. 전제 게이트

하나라도 어긋나면 **파일을 하나도 건드리지 않고** 중단한다.

### 0-1. 구조가 온전한가

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/check-agent-rules/scripts/check_agent_rules.py --project-root .
```

exit 1 이면 **구조부터 고쳐야 한다.** stderr 를 사용자에게 보여주고
`/project-conventions:check-agent-rules` 의 항목별 대응으로 넘긴다. 틀어진 구조 위에 내용을
얹으면 어느 쪽이 원인인지 분간할 수 없게 된다.

### 0-2. 이관된 프로젝트인가

Step 1 의 스캔이 이것도 판정한다. exit 3 이면 포인터 구조가 아니므로 이렇게 안내하고 멈춘다:

> 이 프로젝트는 아직 `AGENTS.md` 단일 소스 구조가 아닙니다. 이 스킬은 기존 `AGENTS.md` 를
> 갱신하는 것이지 이관하지 않습니다. `/project-conventions:init-agent-rules` 를 먼저 실행해 주세요.

### 0-3. 작업 트리 상태

```bash
git status --short
```

깨끗하지 않으면 알리고 진행 여부를 확인한다. 이 스킬은 `AGENTS.md` 를 고치므로 되돌릴 수 있는
상태가 안전하다. 스캔 결과의 `git.dirty` 로도 같은 값을 볼 수 있다.

## Step 1. 사실 수집

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/refresh-agent-rules/scripts/scan_project_facts.py \
  --project-root .
```

**읽기 전용이다.** JSON 한 덩어리를 stdout 에 낸다.

| 키 | 쓰임 |
|---|---|
| `structure` | 포인터 구조 판정. `ok:false` 면 스크립트가 exit 3 으로 이미 멈춘다 |
| `state` | 상태 파일. `exists:false` 면 첫 실행이므로 기준점 없이 전체 대조 |
| `git` | `head` · `dirty` · `baseline_valid` · `changed_files` · `deleted_files` · **`renamed_files`** · `commits_since` |
| `facts` | `command_sources` · `package_managers` · `toolchain_files` · `typescript_strict` · `ci_workflows` · `tree` · `codegraph_index` |
| `agents_md` | `lines` · `budget` · `over_by` · **`marker_ranges`** |

`command_sources` 는 항목마다 출처를 달고 온다 — `package.json scripts`, `Makefile`,
`scripts/ directory` 등. **어느 파일을 믿어야 하는지가 근거가 되므로** 출처 없이 인용하지 않는다.

**직접 세거나 grep 하지 않는다.** 손으로 세면 매 실행마다 다른 값이 나오고, 특히 줄 수는
아직 쓰지 않은 파일을 세는 셈이라 항상 틀린다.

## Step 2. 대조

`AGENTS.md` 본문의 각 주장을 `facts` 와 맞춰 **유지 / 수정 / 추가 / 삭제 후보** 로 나눈다.
판정 기준과 근거로 댈 수 있는 키는 [`references/refresh_policy.md`](./references/refresh_policy.md)
3절에 있다.

두 가지만 여기서 못 박는다.

- **`marker_ranges` 가 가리키는 줄은 대조에서 뺀다.** `init-agent-rules` 가 관리하는 구역이고
  재실행하면 덮어써 편집이 사라진다. 범위를 스크립트가 주므로 눈으로 셀 필요가 없다.
- **사실 항목과 사람이 쓴 산문을 가른다.** 명령·경로·버전은 대조 대상이지만, 설계 근거·정책·
  함정 설명은 `facts` 로 반증되지 않는 한 손대지 않는다. 근거를 못 대는 항목은 판정 대상이 아니다.

`git.changed_files` · `git.deleted_files` · `git.renamed_files` 가 가리키는 영역을 먼저 본다.
**`renamed_files` 의 `from` 은 삭제가 아니라 경로 갱신 신호다** — 파일이 옮겨졌을 뿐인데
문서 줄을 지우면 지시가 사라진다.
`baseline_valid` 가 거짓이면 (기준점이 rebase 로 사라졌거나 shallow clone) **빈 diff 를
"변경 없음" 으로 읽지 말고** 전체 대조로 되돌아간다.

## Step 3. 변경할 게 없으면 아무것도 하지 않는다

수정·추가·삭제 후보가 **모두 0건이면 `AGENTS.md` 를 열지 않는다.** 승인도 묻지 않는다.
보고 형식은 `references/refresh_policy.md` 5절.

무엇을 확인했는지는 함께 밝힌다 — "고칠 게 없다" 를 근거 없이 말하면 확인을 안 한 것과
구분되지 않는다. 그 뒤 Step 5 의 상태 기록만 수행한다.

## Step 4. 승인 — 두 단계로 나눈다

### 4-1. 추가·수정 (일괄)

다듬은 본문의 diff 를 보여 주고 한 번에 승인받는다.

### 4-2. 삭제 (항목별)

**삭제만 따로 게이트를 둔다.** 모델이 사람이 쓴 설계 근거를 "낡았다"고 지우는 것이 이 스킬
최대의 손실이고, 긴 diff 안의 삭제 한 줄은 놓치기 쉽다.

후보마다 원문 발췌(최대 6줄)와 **사라졌다고 보는 근거**를 표로 제시한다. 근거에는
`facts`/`git` 의 어느 키를 봤는지 지목한다 — "더 이상 안 쓰는 것 같다" 는 근거가 아니다.
표 형식은 `references/refresh_policy.md` 4절.

- 확신이 낮으면 삭제 대신 **수정**을 제안한다
- **승인 못 받은 항목은 원문 그대로 남긴다.** 침묵은 대기, 거절은 유지다

### 4-3. 200줄 예산

`agents_md.over_by > 0` 이면 `init-agent-rules` 와 **같은 규칙**으로 How 절차 분리 후보를 뽑아
승인받는다. 승인 전까지 `skills/` · `.claude/rules/` 에 파일을 하나도 만들지 않는다.

카파시 4원칙이 전용 섹션으로 넷 다 없으면 같은 짧은 블록을 H1 아래에 prepend 한다.

**검출 기준·정본 블록·배치 규칙·What/How 목록·예산 계산은 정본이 하나다** —
[`../init-agent-rules/references/claude_md_rewrite.md`](../init-agent-rules/references/claude_md_rewrite.md).
여기 복제하지 않는다. 정본이 둘이면 반드시 갈라지고, 갈라져도 에러가 안 난다.

200줄은 목표이지 상한이 아니다. 삭제가 거절돼 초과인 채로 남아도 실패가 아니다.

## Step 5. 적용과 기록

1. **승인된 것만** `AGENTS.md` 에 반영한다
2. 기준점을 현재 HEAD 로 옮긴다 — 이 명령만이 파일을 쓴다:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/refresh-agent-rules/scripts/scan_project_facts.py \
  --project-root . --record --result {updated|no-change}
```

**변경이 없었어도 기록한다.** 기준점을 안 옮기면 다음 실행이 같은 diff 를 다시 훑고 같은
결론을 다시 낸다.

3. 자기 검증 — 구조가 여전히 온전한지 확인한다:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/check-agent-rules/scripts/check_agent_rules.py --project-root .
```

exit 0 이 아니면 편집이 구조를 깨뜨린 것이다. stderr 를 그대로 보여주고 `git checkout -- AGENTS.md`
로 되돌리는 방법을 안내한다.

4. **커밋하지 않는다.** 변경 요약만 보고한다. 상태 파일이 새로 생겼으면 **커밋 대상**이라고
   알린다 — 팀원이 각자 다른 기준점을 들면 같은 변경을 몇 번이고 다시 제안하게 된다.

## 에러 처리

| 상황 | 대응 |
|---|---|
| 스캔 exit 3 | 포인터 구조가 아니다. `/project-conventions:init-agent-rules` 안내 후 종료 |
| 스캔 exit 2 | 인자·경로 문제. `--project-root` 가 프로젝트 루트인지 확인 |
| Step 0-1 check exit 1 | 구조가 깨졌다. 내용 갱신 전에 그쪽부터 고친다 |
| `baseline_valid: false` | 기준점 유실. 전체 대조로 되돌아간다. 실패가 아니다 |
| `command_sources` 가 비어 있음 | 매니페스트도 `scripts/` 도 없는 프로젝트. 명령 항목은 대조하지 말고 사용자에게 묻는다 |
| Step 5 check 실패 | 편집이 구조를 깨뜨렸다. 되돌리기 안내 |

## 결과 보고

```
## AGENTS.md 갱신 {완료 | 변경 없음}

확인 범위: 기준점 {commit 7자리} 이후 커밋 {N}개 · 변경 파일 {M}건 · 삭제 {K}건
{기준점이 없거나 유실됐으면: "기준점 없음 — 전체 대조"}

| 판정 | 건수 |
|---|---|
| 수정 | {N} |
| 추가 | {N} |
| 삭제 (승인 {N} / 거절 {N}) | {N} |

AGENTS.md: {이전}줄 → {이후}줄 (목표 200 미만 — {충족 | N줄 초과})
상태 파일: `.claude/agent-rules.state.json` {기록 | 신규 생성 — 커밋 대상}
```

변경이 0건이면 표를 생략하고 확인 범위와 줄 수만 적는다.

## 참조 문서

- [`references/refresh_policy.md`](./references/refresh_policy.md) — 판정 규칙 정본.
  고치는 경계, 사실/산문 구분, 네 갈래 판정, 삭제 승인 표, no-op 조건, 상태 파일
- [`../init-agent-rules/references/claude_md_rewrite.md`](../init-agent-rules/references/claude_md_rewrite.md)
  — 카파시 블록·What/How·200줄 예산의 **유일한** 정본. Step 4-3 이 이걸 따른다
