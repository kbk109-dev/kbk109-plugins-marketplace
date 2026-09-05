---
name: fix-plan-impl
description: "버그 수정(fix) 릴리즈의 계획 수립부터 구현까지 한 번에 자동 진행하는 오케스트레이터 스킬. Notion Release Plan DB에서 최신 shipped 버전을 조회해 maintenance(patch) 버전을 +1 증가시킨 새 버전으로 `fix/v{버전}` 전용 브랜치를 만든 뒤 `/release-workflow:release-plan`과 `/release-workflow:release-impl`을 순차 호출한다. 반드시 이 스킬을 사용해야 하는 경우: 'fix-plan-impl', '버그 수정 릴리즈', 'fix 릴리즈', '패치 릴리즈', 'maintenance 릴리즈', 'patch 버전 올려서 구현', '핫픽스 계획+구현', '버그픽스 계획부터 구현까지', '버그 고치고 릴리즈', '버그 고친 거 릴리즈', '패치 버전으로 구현해줘', 'fix 배포', '빠른 패치 배포', 'fix release plan and impl', 'patch release plan+impl', 'small bug fix release', '버그 수정 릴리즈 시작', 'fix 릴리즈 자동화'. 단, 단순 릴리즈 계획(/release-workflow:release-plan)만 또는 단순 릴리즈 구현(/release-workflow:release-impl)만 요청하는 경우에는 트리거하지 않는다 — 이 스킬은 계획과 구현을 한 번에 묶어서 처리할 때만 사용한다. 한국어·영어 모두 트리거."
---

# fix-plan-impl — Fix 릴리즈 계획+구현 오케스트레이터

버그 수정(fix) 릴리즈를 하나의 플로우로 처리한다. Notion Release Plan 데이터베이스에서 최신 버전을 읽어 maintenance(patch) 버전만 +1 증가시킨 새 버전으로 **`fix/v{버전}` 전용 브랜치를 생성하고, 그 브랜치 위에서 `/release-workflow:release-plan` → `/release-workflow:release-impl`을 순차 실행**한다.

이 스킬은 "계획"과 "구현"을 모두 갖춘 두 스킬을 연결하는 얇은 조율 층(orchestrator)이다. 실제 계획 수립·작업 분해·구현·검증은 각 하위 스킬이 담당하며, 이 스킬은 버전 계산·브랜치 격리·순차 호출·사후 검증만 책임진다.

---

## 왜 이 스킬이 필요한가

버그 수정 릴리즈는 매번 아래 패턴을 반복한다:

1. Notion에서 "이전 릴리즈 버전이 뭐였지?" 확인
2. 새 patch 버전 번호 결정 (예: `1.4.2` → `1.4.3`)
3. dev에서 해당 버전 작업용 브랜치 분기
4. `/release-workflow:release-plan`으로 버그 수정 계획 등록
5. `/release-workflow:release-impl`로 순차 구현

매 단계를 사람이 수동으로 이어 붙이면 실수(버전 skip, 잘못된 DB 참조, 브랜치 격리 누락, 계획만 하고 구현 잊음)가 발생한다. 이 스킬은 버전 계산·브랜치 생성·확인 게이트를 자동화하고, 두 하위 스킬을 한 컨텍스트에서 순차 실행하여 "계획만 등록하고 끝난" 상태와 "dev에 직접 커밋해버린" 상태를 구조적으로 차단한다.

---

## 입력값 확인 (게이트)

이 스킬은 하나의 필수 입력이 있다.

### 노션 페이지 이름 (필수)

- 릴리즈 계획이 등록될 Notion 페이지 이름
- **미입력 시**: "버그 수정 릴리즈를 등록할 노션 페이지 이름을 알려주세요." 출력 후 응답 대기

### 업데이트 내용 (선택)

- 사용자가 자연어로 설명하는 버그 수정 내용. Phase 4의 `/release-workflow:release-plan` 호출 시 그대로 전달된다
- **미입력 시**: "수정할 버그 내용을 알려주세요." 출력 후 응답 대기. 입력 전에는 Phase 0~1까지만 수행할 수 있다 — 확인 게이트(Phase 2)에서 함께 묻는 것도 허용된다

---

## Phase 0: 시작 브랜치 게이트

**반드시 `dev` 브랜치에서 시작해야 한다.** 스킬이 생성할 작업 브랜치는 dev에서 분기되며, 잘못된 브랜치에서 분기하면 이후 main 머지 시 엉뚱한 커밋이 섞인다.

```bash
git branch --show-current
```

- 출력이 `dev`가 아닌 경우 → 아래 메시지를 출력하고 **즉시 스킬을 종료**한다. 다른 어떤 작업도 수행하지 않는다.

  > `` `dev` 브랜치에서만 실행할 수 있습니다. `git checkout dev`로 전환 후 다시 시도해주세요. ``

- 출력이 `dev`인 경우 → stale dev 감지로 진행

### stale dev 감지 (경고 전용)

오래된 dev에서 분기하면 타 팀이 먼저 머지한 핫픽스가 누락될 수 있다. 경고만 출력하며, 자동 pull은 하지 않는다(사용자 상태 임의 변경 금지 원칙).

```bash
git fetch origin dev --quiet 2>/dev/null || true
BEHIND=$(git rev-list --count HEAD..origin/dev 2>/dev/null || echo 0)
```

- `BEHIND > 0`이면 아래 메시지를 출력하고 사용자 확인을 받는다:

  > `` 현재 dev가 `origin/dev`보다 {BEHIND} 커밋 뒤에 있습니다. 먼저 `git pull`로 최신화하는 것을 권장합니다. 이대로 계속 진행할까요? ``

- `BEHIND == 0`이거나 `origin/dev`가 없는 경우 → Phase 0.5로 진행

이 시점에서는 `git stash`나 `git checkout`, `git pull`을 **자동으로 수행하지 않는다**. 사용자의 작업 상태를 임의로 건드리면 예측 불가능한 손실이 발생한다. Phase 3에서 안전한 방식으로 작업 브랜치를 생성한다.

---

## Phase 0.5: 세션 재개 확인

LLM은 세션 간 영구 메모리가 없다. Phase 4와 Phase 5 사이에서 컨텍스트가 날아가면 "계획은 등록됐지만 구현이 안 된" 상태가 영구 고착될 수 있다. 이를 방지하기 위해 **각 Phase 진입 시 상태 파일을 기록하고, 스킬 시작 시 기존 상태를 복원한다**.

### 상태 파일 경로

```
docs/skills/fix-plan-impl/v{new_version}/state.json
```

(Phase 0.5 시점에는 `new_version`을 아직 모르므로, 임의 버전 디렉토리 전체를 조회한다.)

### 재개 로직

```bash
ls -1 docs/skills/fix-plan-impl/v*/state.json 2>/dev/null
```

- 파일이 **없으면** → 새 실행. Phase 1로 진행.
- 파일이 **있으면** 가장 최근 것을 Read로 읽고 `phase`, `new_version`, `branch`, `confirmed_at`, `plan_verified_at`, `impl_started_at` 필드를 확인한다. 아래 메시지를 출력하고 사용자에게 선택을 받는다:

  > 이전 실행의 중단된 상태를 발견했습니다.
  > - 버전: v{new_version}
  > - 마지막 Phase: {phase}
  > - 브랜치: {branch}
  >
  > 이어서 진행할까요, 새로 시작할까요? ("이어서" / "새로 시작")

- "이어서" → 해당 Phase부터 재개 (예: `plan_verified_at`이 있으면 Phase 5부터).
- "새로 시작" → 기존 state.json을 `state.json.bak.{timestamp}`로 이동한 뒤 Phase 1부터 실행.

### 상태 기록 지점

| 시점 | 기록 필드 |
| --- | --- |
| Phase 2 확인 통과 직후 | `phase=2`, `new_version`, `branch`, `confirmed_at` |
| Phase 3 브랜치 생성 직후 | `phase=3` |
| Phase 4 `/release-workflow:release-plan` 완료 + verify_plan.sh PASS | `phase=4`, `plan_verified_at` |
| Phase 5 `/release-workflow:release-impl` 진입 | `phase=5`, `impl_started_at` |
| Phase 6 완료 | `phase=6`, `completed_at` |

---

## Phase 1: Notion 정보 수집 및 버전 계산

### Step 1: CLAUDE.md 읽기

프로젝트 루트의 `CLAUDE.md`를 Read로 읽어 Notion 연동 정보(특히 Release Plan 데이터베이스가 존재하는 페이지 이름이나 ID)를 찾는다. 정보가 비어 있거나 부족하면 사용자가 이미 제공한 "노션 페이지 이름"을 우선 사용한다. 이 스킬은 Notion 설정을 직접 가정하지 않는다 — CLAUDE.md와 사용자 입력이 유일한 권위 있는 출처다.

### Step 2: Notion 페이지 및 데이터베이스 탐색

이 스킬은 **어떤 도구로 Notion 에 접근할지 모른다** — 그건 프로젝트 설정이다. 이 프로젝트에
`.claude/rules/notion-api-only.md` 가 있으면 그 규칙(`.claude/scripts/notion_api.py`)을
그대로 따르고, 없으면 사용자에게 Notion 연동 방식을 확인한다. 아래 "탐색한다"·"조회한다"는
전부 이 절차를 뜻하며, 이 문서에서 MCP 도구 이름은 지시하지 않는다.

1. 입력받은 페이지 이름(또는 CLAUDE.md에서 찾은 이름)을 찾는다
2. **찾지 못한 경우**: "해당 이름의 노션 페이지를 찾을 수 없습니다: `{페이지 이름}`" 출력 후 종료
3. 페이지 하위에서 **"Release Plan"** 또는 유사한 이름의 데이터베이스를 찾는다. 완전 일치가 없으면 "Release", "릴리즈", "Plan" 등 부분 일치를 시도한다
4. **데이터베이스를 찾지 못한 경우**: "`{페이지 이름}` 아래에서 Release Plan 데이터베이스를 찾지 못했습니다. 먼저 `/release-workflow:release-plan`으로 최초 데이터베이스를 생성해야 합니다." 출력 후 종료

### Step 3: 최신 버전 조회 + Step 4: 새 버전 결정 (스크립트 위임)

버전 파싱·정렬·+1 계산은 LLM이 직접 수행하지 않고 **결정적 스크립트**에 위임한다 (CLAUDE.md "아키텍처 강제" 원칙). 상세 규칙은 `references/notion_version_rules.md` 참조.

절차:

1. Release Plan DB의 전체 레코드 조회.
2. "버전" 컬럼 값을 모두 수집하여 JSON 배열로 구성. **상태 컬럼(`Status`/`상태`/`배포`)이 존재하면 released/done/shipped/배포완료 상태만** 채택 (shipped vs in-progress 구분).
3. `compute_next_patch.py`에 stdin으로 전달:

   ```bash
   echo '<versions-json-array>' | python3 ${CLAUDE_PLUGIN_ROOT}/skills/fix-plan-impl/scripts/compute_next_patch.py
   ```

4. 출력 JSON에서 `latest_version`, `new_version`, `warnings`, `ignored`를 획득.
   - `warnings`에 pre-release 무시 / 파싱 실패 항목이 있으면 사용자에게 고지.
   - 종료코드 2 (유효 버전 없음) → 사용자 확인 요청: "Release Plan DB에 유효한 X.Y.Z 레코드가 없습니다. `/release-workflow:release-plan`으로 초기 버전부터 등록하시겠습니까?"

major/minor는 스크립트가 절대 변경하지 않는다. patch 자리만 +1 — 이 스킬의 존재 이유.

예시:

| latest_version | new_version |
| -------------- | ----------- |
| `1.4.2`        | `1.4.3`     |
| `2.0.0`        | `2.0.1`     |
| `0.9.7`        | `0.9.8`     |

### Step 5: 작업 브랜치 이름 결정

이 스킬이 생성할 작업 브랜치 이름은 **`fix/v{new_version}`** 으로 고정한다.

- 접두어 `fix/`는 이 스킬이 버그 수정(fix) 릴리즈 전용임을 명시한다. GitFlow 계열 컨벤션과도 호환된다
- 버전 부분은 Step 4에서 계산한 `new_version`을 그대로 사용하되, `v` 접두가 붙은 형태(`v1.4.3`)로 통일한다 — `/release-workflow:release-impl`이 기본으로 기대하는 버전 표기와 일치시켜 혼선을 줄인다

**예시:**

| new_version | 작업 브랜치 이름 |
| ----------- | ---------------- |
| `1.4.3`     | `fix/v1.4.3`     |
| `2.0.1`     | `fix/v2.0.1`     |
| `0.9.8`     | `fix/v0.9.8`     |

---

## Phase 2: 사전 확인 게이트 (필수)

**어떤 변경(Notion 등록, 파일 생성, 브랜치 생성, 하위 스킬 호출)도 이 게이트를 통과하기 전에는 수행하지 않는다.** 자동 계산된 버전이 사용자의 의도와 다를 수 있고(예: 사용자가 이미 다른 채널에서 `1.4.3`을 공개했을 수도), 잘못된 DB에 등록되거나 잘못된 이름의 브랜치가 생성되면 되돌리기 어렵다.

아래 형식으로 사용자에게 확인을 요청한다. **미커밋 변경이 있으면 이관 예정 파일 목록을 반드시 포함**한다 — Phase 3의 `git checkout -b`가 이들을 새 브랜치로 묵시적으로 가져가기 때문에, 사용자가 "포함 안 함" 의사가 있다면 여기서 멈춰야 한다.

```bash
git status --porcelain
```

```
## 데이터베이스 확인 요청

- 대상 페이지: {노션 페이지 이름}
- 대상 데이터베이스: {찾은 DB 이름}
- 최신 등록 버전: {latest_version}
- 새로 생성할 버전 (patch +1): {new_version}
- 생성할 작업 브랜치: fix/v{new_version}
- 현재 git 브랜치: dev ✓
- 이관 예정 미커밋 파일: N개   ← 0개면 "없음"으로 표기
  - {파일1}
  - {파일2}
  ...

(버전 경고가 있으면 여기 추가: pre-release 태그 무시 N개 등)

이 정보로 작업 브랜치를 만들고 `/release-workflow:release-plan` → `/release-workflow:release-impl`을 순차 실행할까요?
미커밋 파일 중 이관하지 않을 파일이 있다면 먼저 dev에서 정리(stash/commit)해주세요.
진행하려면 "확인" 또는 "yes", 중단하려면 "아니오"라고 답해주세요.
```

**사용자의 명시적 확인이 없으면 Phase 3으로 진행하지 않는다.** "확인", "yes", "진행", "ok" 등 명확한 긍정 응답만 통과로 간주한다. "아니오", "no", "취소" 등 부정 응답은 **브랜치·파일·Notion 변경을 일절 수행하지 않고 즉시 종료**한다. 애매한 응답("음…", "글쎄")은 재확인 요청으로 처리한다.

업데이트 내용(버그 수정 설명)이 아직 입력되지 않았다면, 확인과 함께 요청한다: "추가로, 수정할 버그 내용을 간단히 알려주세요."

---

## Phase 3: 작업 브랜치 생성 (작업물 이관 포함)

사용자 확인을 받으면, 이후 모든 계획·구현 작업이 수행될 전용 브랜치를 dev에서 분기한다. 커밋되지 않은 변경이 dev에 남아 있더라도 안전하게 새 브랜치로 이관된다.

### Step 0: Notion 중복 버전 재조회 (race 방지)

Phase 1 조회 이후 Phase 2 확인까지 사이 시간이 흐르는 동안, 동료가 먼저 같은 버전을 등록했을 수 있다. 브랜치 생성 직전에 **1회 재조회**한다.

1. Release Plan DB 레코드 재조회.
2. `new_version`과 동일한 버전 레코드가 새로 발견되면 아래 메시지 출력 후 사용자 확인 요청:

   > 동일 버전(`v{new_version}`) 레코드가 방금 등록된 것으로 보입니다. 다음 patch로 진행할까요, 기존 것을 이어받을까요? ("다음 patch" / "기존 이어받기" / "중단")

3. 동일 버전이 없으면 Step 1로 진행.

### Step 1: 브랜치 중복 확인 (로컬 + 원격)

```bash
git rev-parse --verify fix/v{new_version} 2>/dev/null        # 로컬
git ls-remote --heads origin fix/v{new_version} 2>/dev/null  # 원격
```

- **로컬에 이미 존재**: 동일 버전의 fix 브랜치가 이전에 만들어진 상태. 이 스킬은 **자동으로 덮어쓰거나 강제 생성하지 않는다**. 아래 메시지를 출력하고 종료한다.

  > `fix/v{new_version}` 브랜치가 이미 존재합니다. 이전 작업을 이어서 진행하려면 `git checkout fix/v{new_version}` 후 `/release-workflow:release-impl v{new_version}`을 직접 호출해주세요. 새로 시작하려면 해당 브랜치를 먼저 정리해주세요.

- **원격에만 존재 (로컬에는 없음)**: 동료가 먼저 만든 브랜치일 가능성. 자동 fetch·checkout하지 않고 사용자에게 안내:

  > 원격에 `origin/fix/v{new_version}` 브랜치가 이미 존재합니다. 동료가 같은 버전 작업을 시작했을 수 있습니다. 먼저 확인 후 `git fetch && git checkout fix/v{new_version}`로 이어가거나, 다른 patch 버전으로 재시작해주세요.

- **어디에도 없는 경우**: Step 2로 진행

### Step 2: 작업물 이관 방식 결정

`git status --porcelain`로 dev의 현재 상태를 확인한다.

**핵심 원리 — `git checkout -b`의 working tree 이관 동작:**
`git checkout -b fix/v{new_version}`은 커밋되지 않은 working tree/index 변경을 **새 브랜치로 그대로 따라가게 한다**. 변경은 아직 어떤 커밋에도 속하지 않기 때문에 브랜치 분기 시점과 무관하게 이동한다. 따라서 별도의 stash/pop 과정 없이도 "dev에 있던 수정 파일을 새 브랜치로 이동"이 자연스럽게 이루어진다.

단, 드물게 아래 조건에서는 이관이 실패할 수 있다:
- 이미 다른 이름으로 존재하는 untracked 파일이 새 브랜치에 포함되어 있어 덮어쓸 위험이 있는 경우

이런 경우에만 Step 3의 폴백(stash 기반)을 사용한다.

### Step 3: 브랜치 생성 및 전환

**기본 경로 (대부분의 경우 이 경로를 사용):**

```bash
git checkout -b fix/v{new_version}
```

성공하면 Phase 4로 진행한다. `git status`로 이관된 변경이 새 브랜치에 그대로 남아 있는지 한 번 더 확인한 뒤, 사용자에게 아래 형식으로 알린다:

```
✓ 작업 브랜치 생성 완료: fix/v{new_version}
  - dev에서 분기
  - 이관된 수정 파일: N개 ({파일1}, {파일2}, ...)  ← 있는 경우만 표시
```

**폴백 경로 (checkout 실패 시):**

기본 경로가 "would be overwritten" 등의 에러로 실패하면:

```bash
git stash push -u -m "fix-plan-impl: temp stash for fix/v{new_version}"
git checkout -b fix/v{new_version}
git stash pop
```

- `stash pop`에서 충돌이 발생하면 **즉시 중단**하고 사용자에게 수동 해결을 요청한다. 이 스킬은 자동 머지·자동 해결을 시도하지 않는다
- stash 과정을 사용한 경우, 사용자에게 "stash를 경유하여 작업물을 이관했습니다"라고 명확히 알린다

### Step 4: 이관 후 무결성 확인

```bash
git branch --show-current   # fix/v{new_version}인지 확인
git status                  # 이관된 파일 목록 확인
```

현재 브랜치가 `fix/v{new_version}`이 아니면 즉시 중단하고 사용자에게 상태를 공유한다.

---

## Phase 4: /release-workflow:release-plan 호출

작업 브랜치가 준비되면 `/release-workflow:release-plan` 스킬을 호출한다. 이 스킬은 계획 수립·작업 분해·Notion 등록·Harness Engineering 관리 문서 생성까지 담당한다. 모든 새 커밋과 파일은 `fix/v{new_version}` 브랜치 위에 쌓인다.

호출 시 전달할 정보:

- **노션 페이지 이름**: Phase 1 Step 2에서 확정한 이름
- **업데이트 내용**: 사용자가 입력한 버그 수정 설명. `/release-workflow:release-plan`이 작업 분해와 버전 추론에 사용한다
- **힌트 — 권장 버전**: Phase 1 Step 4에서 계산한 `new_version`. `/release-workflow:release-plan`의 버전 추론 로직이 이를 존중하도록 "이번 릴리즈의 버전을 `{new_version}`으로 고정해 주세요. 모든 작업은 maintenance(patch) 성격이어야 합니다."를 함께 전달한다

### `/release-workflow:release-plan` 완료 확인 (증거 기반 검증)

하위 스킬이 종료되면 **스크립트와 Notion 재조회를 병행**하여 증거로 검증한다. LLM이 산문 체크리스트를 주관적으로 판정하지 않는다 (CLAUDE.md "증거 기반 검증" 원칙).

1. **파일·브랜치 검증 스크립트**:

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/fix-plan-impl/scripts/verify_plan.sh {new_version}
   ```

   스크립트는 `task_list.json` 존재, 작업 수 > 0, 현재 브랜치 == `fix/v{new_version}`을 자동 판정하고 종료코드 0(PASS) / 1(FAIL)로 반환한다.

2. **Notion 레코드 재조회**: Release Plan DB를 다시 읽어 `{new_version}` 버전 레코드가 실제로 존재하는지 확인한다. (이 스킬이 도는 프로젝트마다 Notion 연동 방식이 다를 수 있어 스크립트가 그 방식을 하드코딩할 수 없다 — 그래서 이 단계는 LLM이 위임 절차를 통해 담당한다.)

### 재시도 상한 (루프 감지)

위 검증이 실패하면 사용자에게 결과를 공유한 뒤 재시도 의사를 묻는다. **동일 재시도는 최대 1회**까지만 허용한다. 2회째 실패 시 자동으로 중단하고 사용자에게 수동 진단을 요청한다 — 같은 접근의 반복은 CLAUDE.md 실패모드 #4(자기평가 편향/무한 루프)에 해당한다.

**계획 단계가 실패한 채로 구현 단계로 진입하면 구현할 대상이 없거나 잘못된 버전에서 구현이 시작된다.** 검증 통과 후에만 `state.json`의 `plan_verified_at`을 기록하고 Phase 5로 넘어간다.

---

## Phase 5: /release-workflow:release-impl 호출

`/release-workflow:release-plan`이 정상 완료된 경우에만 `/release-workflow:release-impl`을 호출한다. 구현 커밋 역시 `fix/v{new_version}` 브랜치에 쌓인다.

호출 시 전달할 정보 (세 값 모두 **명시적으로 전달**한다 — release-impl 입력 게이트가 세 개이고 누락 시 자동 실패한다):

- **노션 페이지 이름**: Phase 4와 동일한 페이지 이름
- **데이터베이스 이름**: Phase 1 Step 2에서 찾은 Release Plan DB 이름 (release-plan 호출 시 전달한 동일 값)
- **버전**: Phase 1 Step 4에서 계산한 `new_version` (예: `v1.4.3`)

`/release-workflow:release-impl`은 자체적으로 Harness Engineering 방법론(Task State Machine, Verification Loop, Loop Detection 등)을 적용하여 각 task를 순차 구현한다. 이 스킬은 그 과정을 관찰만 하며, 하위 스킬의 내부 플로우에 개입하지 않는다.

### 구현 중 실패 처리

`/release-workflow:release-impl`이 사용자 개입 요청(blocked task 에스컬레이션, 반복 루프 감지 등)을 보내면, 이 스킬은 **중단하고 사용자에게 제어권을 넘긴다**. 오케스트레이터가 임의로 "다시 시도해보자"며 루프를 돌지 않는다 — `/release-workflow:release-impl`에 이미 재시도 상한과 루프 감지가 내장되어 있기 때문이다. 이 경우 사용자는 `fix/v{new_version}` 브랜치에 남아 있으므로 수동으로 작업을 이어가거나 브랜치를 정리할 수 있다.

---

## Phase 6: 완료 보고

두 하위 스킬이 모두 정상 완료되면 아래 형식으로 결과를 요약한다:

```
## Fix 릴리즈 계획+구현 완료

| 항목              | 값                                      |
| ----------------- | --------------------------------------- |
| 이전 버전         | {latest_version}                        |
| 새 버전           | {new_version}                           |
| 작업 브랜치       | fix/v{new_version}                      |
| 대상 페이지       | {노션 페이지 이름}                      |
| 등록된 작업 수    | N개                                     |
| 구현 완료 작업    | N개 (pass)                              |

### 생성된 산출물
- Notion: Release Plan DB에 v{new_version} 작업 등록됨
- 로컬: docs/skills/release-plan/v{new_version}/
- 로컬: docs/skills/release-impl/v{new_version}/
- Git: fix/v{new_version} 브랜치에 계획+구현 커밋 완료

### 다음 단계
1. 구현 커밋 확인:
   ```bash
   git log fix/v{new_version} --oneline
   ```
2. 원격 push (권장 — 컨텍스트 손실 시 복구 가능):
   ```bash
   git push -u origin fix/v{new_version}
   ```
3. dev로 머지:
   ```bash
   git checkout dev && git merge --no-ff fix/v{new_version}
   ```
4. 이후 `/release-workflow:main-branch-merge` 또는 수동 PR로 main 반영
5. 배포 파이프라인 실행
```

push는 이 스킬이 자동 실행하지 않는다(기계적 제약 #11). 위 명령은 복사·실행용 가이드다.

만약 일부 task가 `blocked` 상태로 남았다면, 요약 테이블에 "blocked 작업: N개"를 명시하고 해당 task 목록을 출력한다. 사용자 개입이 필요한 상태임을 명확히 알린다. 이 경우에도 브랜치는 `fix/v{new_version}`에 그대로 남아 있으므로, 사용자가 수동으로 이어서 작업할 수 있다.

---

## 기계적 제약 (절대 규칙)

1. **dev 브랜치 외 시작 금지** — Phase 0 게이트를 통과하지 못하면 어떤 파일·커밋·Notion 변경도 수행하지 않는다
2. **Patch 자리만 증가** — major/minor 버전은 이 스킬에서 변경하지 않는다. 필요하면 `/release-workflow:release-plan`을 직접 사용해야 한다
3. **사전 확인 필수** — Phase 2 게이트를 통과하기 전에는 브랜치 생성이나 `/release-workflow:release-plan` 호출을 하지 않는다
4. **작업 브랜치 필수** — 계획·구현 작업은 반드시 `fix/v{new_version}` 브랜치 위에서 수행한다. dev에 직접 커밋하지 않는다
5. **브랜치 이름 고정 규칙** — 접두어 `fix/`, 버전 부분 `v{major.minor.patch}`. 이 규칙에서 벗어나지 않는다
6. **기존 브랜치 덮어쓰기 금지** — 동일 이름의 브랜치가 이미 존재하면 자동으로 삭제·재생성하지 않는다. 사용자에게 선택권을 넘긴다
7. **순차 실행** — `/release-workflow:release-plan`이 정상 완료된 후에만 `/release-workflow:release-impl`을 시작한다. 두 스킬을 병렬 또는 역순으로 호출하지 않는다
8. **계획 실패 시 구현 금지** — Phase 4 검증 실패 시 Phase 5로 진입하지 않는다
9. **하위 스킬 내부에 개입하지 않음** — `/release-workflow:release-plan`과 `/release-workflow:release-impl`이 자체적으로 처리하는 작업 분해·검증 루프·재시도 로직에 이 오케스트레이터가 임의로 끼어들지 않는다
10. **한국어 출력** — 모든 사용자 안내 메시지는 한국어로 작성
11. **git push 금지** — 이 스킬은 push를 자동 실행하지 않는다. 커밋만 생성되고 push는 사용자가 직접 수행
12. **stash는 폴백 경로에서만** — 기본 경로는 `git checkout -b`만 사용한다. stash는 checkout 실패 시에만 사용하고, stash pop 충돌 시 즉시 사용자 개입을 요청한다
13. **Phase 4 재시도 상한** — 동일 접근의 검증 재시도는 최대 1회. 2회째 실패 시 자동 중단하고 사용자 개입 요청 (CLAUDE.md 실패모드 #4 — 무한 루프 방지)
14. **증거 기반 검증** — Phase 4 완료 판정은 `verify_plan.sh`의 종료코드와 Notion 재조회 결과를 증거로 사용한다. 산문 체크리스트 자주관 판정으로 통과 처리하지 않는다
15. **상태 파일 기록** — 각 Phase 진입 시 `docs/skills/fix-plan-impl/v{new_version}/state.json`을 업데이트한다. 세션 재개 시 이 파일이 유일한 권위 있는 출처다

---

## 사용하는 도구

| 도구                              | 용도                                                     |
| --------------------------------- | -------------------------------------------------------- |
| `Bash: git branch --show-current`       | Phase 0 시작 브랜치 확인, Phase 3 이관 후 검증           |
| `Bash: git fetch origin dev`            | Phase 0 stale dev 감지 (경고 전용)                        |
| `Bash: git rev-list --count HEAD..origin/dev` | Phase 0 behind count 계산                         |
| `Bash: git status / status --porcelain` | Phase 2 이관 파일 목록, Phase 3 working tree 검증        |
| `Bash: git rev-parse --verify`          | Phase 3 Step 1 로컬 브랜치 중복 확인                     |
| `Bash: git ls-remote --heads`           | Phase 3 Step 1 원격 브랜치 중복 확인                     |
| `Bash: git checkout -b`                 | Phase 3 작업 브랜치 생성 및 working tree 이관            |
| `Bash: git stash`                       | Phase 3 폴백 경로 (기본 checkout 실패 시에만)            |
| `${CLAUDE_PLUGIN_ROOT}/skills/fix-plan-impl/scripts/compute_next_patch.py`         | Phase 1 semver 파싱·정렬·patch+1 계산                    |
| `${CLAUDE_PLUGIN_ROOT}/skills/fix-plan-impl/scripts/verify_plan.sh`                | Phase 4 파일·브랜치 증거 기반 검증                       |
| `Read`                                  | CLAUDE.md, state.json, references 읽기                   |
| `Write`                                 | state.json 갱신                                          |
| Notion 접근 (위임)                       | 페이지/DB 탐색·레코드 조회 (Phase 1, Phase 3 Step 0 재조회, Phase 4). 어떤 도구를 쓰는지는 프로젝트 설정을 따른다 — Step 2 참조 |
| `/release-workflow:release-plan` 스킬                    | 릴리즈 계획 수립 및 Notion 등록                          |
| `/release-workflow:release-impl` 스킬                    | 계획된 작업의 순차 구현                                  |

---

## 관련 스킬

- `release-plan` — 단순 릴리즈 계획만 필요한 경우
- `release-impl` — 이미 등록된 계획의 구현만 필요한 경우
- `ota-hotfix` — 빌드된 앱에 JS 변경만 OTA로 전달해야 하는 긴급 상황 (코드 구현이 아닌 배포 계층 핫픽스)
- `main-branch-merge` — 구현 완료 후 dev→main 릴리즈 문서화 및 머지
