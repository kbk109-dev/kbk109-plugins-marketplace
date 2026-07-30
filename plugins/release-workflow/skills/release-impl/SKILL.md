---
name: release-impl
description: "Use when a user wants to implement release tasks that release-plan has already registered in a Notion database for a specific semantic version — reads the per-version task list and executes it through a 3-agent Harness (Generator + Evaluator sub-agents, Task State Machine with fail/pass/blocked transitions, evidence-log gated pass, sprint contracts, Notion reverse status sync). Requires three inputs: Notion page name, database name, and version (vX.Y.Z). Triggers on Korean and English phrases including: 'release-impl', '릴리즈 구현', '릴리즈 작업 시작', '릴리즈 구현 시작', '릴리즈 개발', '릴리즈 작업 이어서', 'Release Plan 기반으로 구현', '노션 릴리즈 플랜 작업', 'release implementation', 'release impl', 'implement release', as well as semver-scoped forms like 'v0.9.0 구현', 'v1.2.0 개발 시작', 'v2.0.0 작업 시작' (a 'vX.Y.Z' token must accompany '구현/개발/작업 시작' to trigger — bare '작업 시작' without a semver token does NOT trigger, which reserves this skill for release implementation and avoids over-triggering on generic 'start working' requests)."
---

# release-impl — Harness Engineering 기반 릴리즈 구현

Notion의 Release Plan 데이터베이스에서 특정 버전의 작업 목록을 읽어와, Harness Engineering 5대 구성요소(Readable Environment, Task State Machine, Verification Loop, Architecture Enforcement, Loop Detection)를 적용하여 코드를 구현한다.

---

## 호출 모드 감지 (오케스트레이터 자동화 보호)

`fix-plan-impl` 같은 오케스트레이터가 release-impl을 연쇄 호출할 때, 사용자 확인 게이트가 자동화 흐름을 멈추면 체인 전체가 깨진다. 반대로 대화형 호출에서 게이트를 생략하면 잘못된 버전에 구현이 착수될 수 있다. 두 모드를 신호 기반으로 구분한다.

| 조건 | 모드 | Step 7 사용자 확인 | Phase 1 Step 0 도구 가용성 경고 |
|------|------|-------------------|------------------------------|
| 아래 신호 중 **2개 이상** 동시 성립 | **오케스트레이터 모드** | 생략 (자동 진행) | 동일 (항상 실행) |
| 그 외 | **대화형 모드** | 필수 | 동일 |

오케스트레이터 신호:

1. 호출 프롬프트에 `"버전 고정"` 또는 `"version locked"` 키워드가 포함됨
2. 현재 git 브랜치가 `fix/v{version}` 또는 `release/v{version}` 형식
3. 입력 DB 이름·페이지 이름·버전 **세 값이 모두 프롬프트에 명시적으로 전달**됨 (대화형은 보통 일부만 제공하고 질의로 채움)
4. `docs/skills/release-plan/{slug}/v{version}/task_list.json`이 이미 존재

대화형 모드에서도 Phase 2의 서브에이전트 릴레이·Phase 2 Step D 에스컬레이션은 동일하게 작동한다 — 호출 모드는 "초기화 게이트" 통과 방식에만 영향을 준다. 두 모드 모두 **기계적 제약 11개**는 예외 없이 적용된다.

**오케스트레이터 모드에서 입력 누락은 치명적**: 세 입력 중 하나라도 누락하면 대화형 폴백으로 넘어가지 않고 즉시 오류를 반환한다 (`"오케스트레이터 호출에 필수 입력이 누락됐습니다: {missing}. 호출 측 프롬프트를 수정해주세요."`). 자동 추론을 허용하면 조용한 잘못된 진행 위험이 크다.

---

## 입력값 확인 (게이트)

이 스킬은 **세 가지 필수 입력**이 있다. 하나라도 없으면 진행하지 않는다. release-plan이 사용자 임의 이름(`v2.1 Tasks`, `릴리즈 플랜` 등)으로 DB를 등록할 수 있으므로, DB 이름을 하드코딩하지 않고 반드시 입력으로 받는다.

### 1. 노션 페이지 이름 (필수)

- 릴리즈 계획이 등록된 Notion 페이지 이름
- **미입력 시**: "릴리즈 구현할 노션 페이지 이름을 알려주세요." 메시지를 출력하고 사용자 응답을 대기한다

### 2. 데이터베이스 이름 (필수)

- 페이지 하위의 Release Plan 데이터베이스 이름. `/release-workflow:release-plan`에서 사용한 DB 이름과 **반드시 동일**해야 한다
- 예: `Release Plan`, `v2.1 Tasks`, `릴리즈 플랜`, `PayFlow Tasks`
- **미입력 시**: "릴리즈 구현 대상 데이터베이스 이름을 알려주세요. (release-plan에서 사용한 DB 이름과 동일해야 합니다)" 출력 후 응답 대기

### 3. 버전 (필수)

- `v0.9.0`, `0.9.0`, `v1.2.0` 등의 형식. 정규식 `^v?\d+\.\d+\.\d+$`로 검증 후 내부적으로 `v{major.minor.patch}`로 정규화한다
- **미입력 또는 형식 위반 시**: "구현할 버전을 X.Y.Z 형식으로 알려주세요. (예: v0.9.0)" 출력 후 대기

### 4. 구현 루트 (implementation_root, **선택**)

- 모노레포·멀티 패키지 저장소에서 이번 릴리즈가 만지는 패키지의 `project_root` 기준 상대 경로. 예: `packages/mobile`, `apps/web`.
- 단일 패키지 저장소에서는 입력 생략 (= `null`). Generator·Evaluator가 `project_root` 전체를 사용한다.
- 값이 주어지면 Generator의 탐색·편집과 Evaluator의 회귀 명령(L3) 실행이 그 경로로 한정된다 — 모노레포에서 다른 패키지를 잘못 건드리거나 잘못된 디렉토리에서 테스트를 돌리는 사고를 차단하는 게이트.
- release-plan에서 같은 입력으로 `task_list.json.implementation_root`를 설정해 두었다면 Step 3에서 자동 승계하므로 다시 입력할 필요 없다.

### 5. 입력 수집 전략

미입력 **필수** 필드(1·2·3)가 2개 이상이면 개별 질문을 반복하지 말고 한 번에 묶어 질의한다 — "다음 정보를 함께 알려주세요: 노션 페이지 이름, 데이터베이스 이름, 버전(vX.Y.Z)". 사용자가 부분 응답만 주면 누락 필드만 재질의한다. `implementation_root`는 선택 입력이므로 미입력을 사유로 진행을 막지 않는다.

### 6. 오케스트레이터 호출 시 계약

`fix-plan-impl` 등 오케스트레이터가 호출할 때는 세 입력을 **모두 명시적으로 전달**해야 한다. 누락 시 대화형으로 폴백하지 않고 오케스트레이터 호출 오류로 반환한다 — 자동화 체인에서 사용자 확인 대기로 멈추지 않게 하기 위함이다.

---

## 구조적 실패 방지

이 스킬은 CLAUDE.md의 "LLM 구조적 실패 모드" 4가지를 release-impl 맥락으로 확장하여 총 14가지 실패 패턴에 대해 구조적 가드를 건다. 상세 대응 매핑·상태 전이 규칙은 `references/failure_modes.md` 참조. 핵심 가드만 요약:

- **세션 간 상태 유실** → `PROGRESS.md` + `feature_list.json` + `.loop_state.json` 외부화
- **자기평가 편향** → Generator·Evaluator 서브에이전트 분리 (Task 도구로 각각 기동)
- **조기 완료 선언** → `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/check_evidence_logs.py` — 실행 로그 파일 없이는 pass 불가
- **일회성 탐욕적 완료** → 한 번에 하나의 task + 스프린트 계약 사전 합의
- **AC 변조** → SHA-256 해시 + `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/check_state_transition.py`
- **무한 재시도** → `retry_count ≤ 2` 스키마 제약 + `edit_counter.py`/`error_counter`

---

## Phase 1: 초기화 (Initializer)

### Step 0: 외부 도구 가용성 체크 (세션당 1회)

Phase 1 Step 1 전에 단 한 번 수행한다. 상세 거동은 `references/degradation_policy.md` "Phase 1 Step 0" 섹션 참조.

| 도구 | 확인 방법 | 부재 시 |
|------|----------|---------|
| Notion MCP (`mcp__plugin_Notion_notion__*`) | 노출된 함수 목록에 접두사 존재 여부 | 로컬 `task_list.json`이 있으면 그것으로 진행, 없으면 종료 |
| Context7 MCP (`mcp__plugin_context7_context7__*`) | 동일 | 경고만 출력, 진행. Generator가 서드파티 라이브러리 필요 시 사용자 질의로 전환 |
| 프로젝트 CLAUDE.md | `{project_root}/CLAUDE.md` Read 성공 여부 | Step 1의 폴백(설정 파일 추론 + 사용자 확인)으로 이동 |

결과는 PROGRESS.md 세션 로그 첫 줄에 기록한다.

### Step 1: 프로젝트 컨텍스트 파악

프로젝트의 `CLAUDE.md`를 Read하여 기술 스택·테스트/빌드/린트 명령·네이밍 컨벤션·디렉토리 구조·임포트 패턴·커밋 컨벤션을 파악한다. release-impl은 언어·프레임워크 기본값을 가정하지 않는다 — 잘못된 가정은 조용한 오작동을 낳기 때문이다.

CLAUDE.md가 비어 있거나 항목이 누락되면: 루트 설정 파일(`pyproject.toml`/`go.mod`/`Cargo.toml`/`package.json` 등)로 **보조 추론** → **반드시 사용자 확인**. 자동 기본값으로 진행하지 않는다.

상세 항목별 폴백 규칙과 사용자 질의 템플릿은 `references/initializer_guide.md` "Step 1" 참조.

### Step 2: 이전 버전 컨텍스트 스캔 (결정적 스크립트)

`docs/skills/release-impl/` 하위에 이전 버전 디렉토리가 있으면 현재 버전 구현 **전에** 분석한다 (없으면 Step 3으로). LLM이 직접 디렉토리를 읽지 않고 `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/scan_previous_versions.py`가 4가지(blocked_task, known_issue, architecture_decision, dependency) 후보를 결정적으로 산출한다 — 버전이 누적될수록 비용이 폭증하던 수동 절차를 1회 Bash 호출로 압축.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/scan_previous_versions.py scan \
  docs/skills/release-impl/ --current v{version} --limit 3
```

- `--current v{version}`: 현재 버전을 결과에서 제외 (자기 자신 스캔 방지)
- `--limit K`: 최근 K개 semver만 스캔. 권장 기본 `3`. 더 오래된 버전의 핵심 사항은 직전 버전의 `previous_context_digest.json`(아래)이 흡수해 보존
- 출력: `{schema, scanned_versions, candidates: [{version,type,source,summary,relevance}]}`

LLM은 출력 JSON의 `candidates`에서 **현재 버전 task 영역과 겹치거나 영향을 주는 항목만** 남긴다 (관련성 필터). 무관 항목은 컨텍스트 오염이라 제외한다. 결과는 init 입력의 `previous_context`로 그대로 투입된다 (스키마 동일).

**digest 캐시(옵션)**: 같은 스크립트의 `digest` 모드를 Step 5/6 직후에 호출하면 `docs/skills/release-impl/v{version}/previous_context_digest.json`이 작성된다. 다음 버전이 `consume`으로 이 파일을 먼저 읽어 (source 파일 sha256 검증을 거쳐) drift가 없을 때만 재사용 — drift 감지 시 자동 폴백으로 `scan` 재실행. 첫 도입 버전에서는 효과 없고 두 번째 버전부터 비용이 V→1로 떨어진다.

**이전 버전 기록이 없으면** (첫 릴리즈) 이 Step 생략, `previous_context=[]`. 가짜 과거 기록 생성 금지.

각 task 착수 직전에 Generator가 `previous_context`를 다시 읽는다 (생략 금지). 상세는 `references/initializer_guide.md` "Step 2".

### Step 3: 로컬 기존 데이터 확인 (release-plan 계약 소비)

release-plan이 이미 생성한 `task_list.json`을 재사용한다. 상세 계약·경로 규약·필드 매핑은 `references/contract_consumer.md` 참조.

1. **슬러그 산출** — 입력값 #2(DB 이름)를 release-plan의 슬러그 생성기에 넣는다:
   ```bash
   DB_SLUG=$(python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/slugify.py "{database_name}")
   ```
2. **경로 확정** — `docs/skills/release-plan/${DB_SLUG}/v{version}/task_list.json`
3. **존재 확인**:
   - **존재하는 경우**: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/validate_task_list.py {path}` 실행 → exit 0이면 `contract_consumer.md`의 필드 매핑표를 따라 feature_list.json을 생성한다. Notion 조회 생략.
   - **검증 실패**: stderr를 사용자에게 공유하고 release-plan 재실행을 요청한다. 깨진 task_list로 진행하지 않는다.
   - **존재하지 않는 경우**: Step 4로 진행 (Notion에서 직접 조회)

### Step 4: Notion 데이터 조회

아래 단계의 `{database_name}`은 입력값 #2(데이터베이스 이름)이며, `{version}`은 입력값 #3의 정규화 결과다.

1. `notion-search`로 입력받은 노션 페이지 이름을 검색한다
   - **못 찾은 경우**: "해당 페이지를 찾을 수 없습니다. Notion 페이지 URL을 직접 입력해주세요." 출력 후 대기
2. `notion-fetch`로 해당 페이지의 하위 콘텐츠를 확인하여 `{database_name}` 데이터베이스를 찾는다
   - 완전 일치 우선. 없으면 입력값과 대소문자 구분 없는 부분 일치를 한 번 시도하고, 사용자에게 매칭 DB 이름을 확인받는다
   - **DB 없는 경우**: `"{database_name}" 데이터베이스가 없습니다. 먼저 /release-workflow:release-plan으로 계획을 등록하거나 DB 이름 입력을 확인해주세요.` 출력 후 종료
3. `notion-fetch`로 데이터베이스의 data source를 조회한다
4. `{version}`에 해당하는 작업(Task) 목록을 필터링한다
   - **해당 버전의 작업이 없는 경우**: "버전 {version}에 해당하는 작업이 없습니다." 출력 후 종료

### Step 5 + Step 6: feature_list.json + PROGRESS.md 결정적 생성

**수동 작성 금지**. `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/init_version.py`를 호출하여 결정적으로 생성한다 — 템플릿 드리프트 방지가 이 스크립트의 존재 이유다.

```bash
echo '{
  "version": "v{version}",
  "notion_page": "…",
  "notion_database": "…",
  "source": "release-plan/task_list.json",
  "implementation_root": null,
  "previous_context": [...],
  "tasks": [...]
}' | python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/init_version.py \
  docs/skills/release-impl/v{version} --with-progress
```

스크립트가 자동으로 처리하는 항목: `summary` 카운터 초기화, `acceptance_criteria_hashes` SHA-256 계산, `status="fail"` 강제, `evidence_logs={}` 초기화, `sprint_contracts/`·`logs/` 디렉토리 생성, `created_at` 날짜 기입. `implementation_root`는 입력 게이트 #4 또는 release-plan `task_list.json`에서 승계 — 단일 패키지 저장소는 `null`(생략 가능).

**생성 후 반드시** `python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/validate_feature_list.py {path}` 실행. 실패 시 stderr의 오류를 해결한 뒤 재생성한다.

입력 소스별 필드 매핑 (task_list.json → init 입력)은 `references/contract_consumer.md`. 전체 스키마 계약은 `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/schemas/feature_list.schema.json` (Draft-2020-12). 생성되는 PROGRESS.md 템플릿과 헤더 구조, `previous_context` 포맷 예시는 `references/initializer_guide.md` "Step 5·Step 6" 참조.

### Step 7: 초기 커밋

```
chore: initialize release v{version} task list
```

**사용자 확인 게이트**: 대화형 모드에서는 초기화 결과(feature_list.json 요약, tasks 개수, previous_context 항목 수)를 보여주고 "구현을 시작할까요?"를 사용자에게 묻는다. 오케스트레이터 모드에서는 결과를 stdout에 출력만 하고 Phase 2로 자동 진행한다. 모드 판정은 위 "호출 모드 감지" 섹션의 규칙을 따른다.

---

## Phase 2: 작업 구현 (3-Agent Task Loop)

각 task는 **분리된 두 서브에이전트**의 릴레이로 처리된다 — Generator(구현)와 Evaluator(검증). 두 에이전트는 같은 세션 안에서 페르소나만 바꿔 실행되지 않고, `Task` 도구로 각각 기동된다. 이유: 같은 컨텍스트에서 "내가 짠 코드를 내가 평가"하면 자기평가 편향이 필연적으로 발생하며, 이는 "조기 완료 선언" 실패 모드의 주원인이다.

서브에이전트 시스템 프롬프트:
- Generator: `agents/generator.md`
- Evaluator: `agents/evaluator.md`

### 세션 시작 오리엔테이션 (매 세션 반드시 수행)

새 세션이 시작되거나 이전 task가 끝나 다음 task로 넘어갈 때:

1. **현재 위치 확인**: `pwd`
2. **이전 상태 복원**: `feature_list.json` + `PROGRESS.md` + `git log --oneline -10` 확인
3. **재개 지점 감지**: 최상위 `current_task_id`가 null이 아니면 해당 task가 중단 상태 — 그 task로 강제 진입(새 task 선택 건너뜀). null이면 Step 4로.
4. **다음 task 선택**: `feature_list.json`에서 `status: "fail"`인 task 중 `priority`가 가장 높고 `dependencies`가 모두 pass인 것. 선택 즉시 `current_task_id`를 해당 id로 설정하고 저장.
5. **이전 버전 컨텍스트 재주입**: 선택한 task에 관련된 `previous_context` 항목을 다시 읽는다 — Phase 1에서 한 번 본 걸로 끝내지 않는다
6. **한 번에 하나의 task만.** 선택된 task가 pass 또는 blocked로 종료되기 전에는 다른 task를 시작하지 않는다

### Step A: Generator 기동

`Task` 도구로 Generator 서브에이전트를 기동한다. **state_digest**를 미리 산출해 컨텍스트에 포함시키면 PROGRESS.md/feature_list.json/.loop_state.json 전체를 다시 주입할 필요가 없다 (호출당 토큰을 N에 비례해 절감하는 핵심 최적화):

```bash
DIGEST=$(python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/state_digest.py docs/skills/release-impl/v{version}/ --task-id {TASK-NNN})
```

호출 prompt 템플릿:

```
{agents/generator.md 전체 내용}

---

## 이번 호출의 컨텍스트

- version_dir: docs/skills/release-impl/v{version}/
- task_id: {TASK-NNN}
- feature_list_path: docs/skills/release-impl/v{version}/feature_list.json
- state_digest: {DIGEST JSON inline}
- project_root: {repo root}
- implementation_root: {feature_list.json.implementation_root 또는 null}
- claude_md_path: {repo root}/CLAUDE.md

스프린트 계약을 먼저 작성한 뒤 단일 task를 구현하고, 마지막 메시지에 계약된 JSON으로 복귀하라.
state_digest로 부족한 정보가 있으면 원본 파일을 직접 Read한다.
```

Generator가 `"status": "blocked-*"`로 복귀하면 Evaluator를 호출하지 않고 바로 사용자에게 에스컬레이션한다.

### Step B: Evaluator 기동

Generator가 `"status": "generator-done"`을 반환하면, **별도의 `Task` 호출**로 Evaluator 서브에이전트를 기동한다. 같은 방식으로 state_digest를 미리 산출:

```bash
DIGEST=$(python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/state_digest.py docs/skills/release-impl/v{version}/ --task-id {TASK-NNN})
```

호출 prompt 템플릿:

```
{agents/evaluator.md 전체 내용}

---

## 이번 호출의 컨텍스트

- version_dir: docs/skills/release-impl/v{version}/
- task_id: {TASK-NNN}
- sprint_contract_path: {Generator 출력 JSON의 sprint_contract_path}
- modified_files: {Generator 출력 JSON의 modified_files}
- feature_list_path: docs/skills/release-impl/v{version}/feature_list.json
- state_digest: {DIGEST JSON inline}
- project_root: {repo root}
- implementation_root: {feature_list.json.implementation_root 또는 null}
- claude_md_path: {repo root}/CLAUDE.md

회의적 심사관 톤을 유지하고, 각 criterion에 대해 {version_dir}/logs/{task_id}/{i}.log에
L3/L2/L1 중 하나의 실행 증거를 남긴 뒤 pass/fail을 판정하라.
implementation_root가 비어 있지 않으면 회귀 명령은 그 경로에서 실행한다.
```

Evaluator가 `feature_list.json`과 `evidence_logs`를 직접 업데이트한다. 호출 측은 출력 JSON의 `verdict`를 보고 다음 행동을 결정할 뿐이다.

### Step C: Verdict별 처리

| verdict | 처리 |
|---------|-----|
| `pass` | `sync_progress.py`로 PROGRESS.md 헤더 재생성 → git commit `feat(release/v{version}): {task.title}` → 세션 시작 오리엔테이션으로 복귀 |
| `fail` (retry_count < 2) | Generator를 재기동 (Step A). prompt에 이번 `evaluator_feedback`을 반드시 포함시켜 동일 실수 반복 방지 |
| `blocked` 또는 retry_count==2 | 사용자 에스컬레이션 — 다음 섹션 참조. 자동 재시도하지 않는다 |

### Step D: 에스컬레이션 (blocked)

```
Task {ID} ({title})에서 구현이 반복 실패했습니다.

## 원인
{evaluator_feedback 요약 + 로그 파일 경로}

## 선택지
[1] 재시도 (같은 접근 유지, retry_count 리셋하고 blocked → fail)
[2] 구체 수정 지침을 제공하고 재시도 (prompt에 사용자 지침 추가)
[3] 이 task를 건너뛰고 blocked 상태로 유지
[4] 전체 중단 (세션 종료, 나머지 task도 중단)

번호로 선택해주세요.
```

blocked → fail 복귀 시 `retry_count`는 0으로 리셋하되, `evaluator_feedback`에 `[resolved:{ISO timestamp}] 원래 피드백` 형태로 이력을 보존한다.

### Loop Detection (외부화된 카운터)

- 파일 편집은 Generator가 `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/edit_counter.py edit` 호출로 기록 → 5회 초과 시 Generator가 `"status":"blocked-loop"`로 복귀.
- 에러 반복은 Evaluator가 `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/edit_counter.py error` 호출로 기록 → 3회 누적 시 Evaluator가 `verdict="blocked"`로 즉시 전이.
- 카운터 상태는 `docs/skills/release-impl/v{version}/.loop_state.json`에 외부화되어 있어 **세션이 재시작되어도 유지된다**. 이 파일은 git 추적에서 제외한다 (`.gitignore`).

### 작업 완료 후 처리

Evaluator의 verdict가 `pass`면 호출 측이 수행:

1. **Notion 상태 동기화** (역방향 업데이트) — `mcp__plugin_Notion_notion__notion-update-page`로 해당 task row의 상태 속성을 `완료`로 전이. 상세 payload와 속성 타입별 대응은 `references/notion_integration.md` Phase 2 Step C 참조. 실패는 secondary output으로 처리하여 core 진행을 막지 않는다 (`references/degradation_policy.md`).
2. **Git 커밋**: `feat(release/v{version}): {title}`. 프로젝트 CLAUDE.md에 다른 커밋 컨벤션이 명시되어 있으면 그것을 우선.
3. **깨끗한 상태 확인**: `git status`로 미완성 변경이 없는지 확인.
4. **다음 task로 이동** (세션 시작 오리엔테이션으로 복귀).

blocked 전이 시에도 1번을 동일한 매핑 규칙으로 시도(`차단`)한다. 실패는 secondary output.

세션은 반드시 **깨끗한 상태**로 종료한다 — 미완성 코드, 스텁, 검증되지 않은 변경이 남으면 안 된다.

---

## Phase 3: 완료 보고

모든 task가 `pass`가 되면:

1. **최종 상태 요약** (feature_list.json 기반 테이블 + `Total/Pass/Fail/Blocked` 라인) 출력
2. **PROGRESS.md 최종 완료 기록** (`sync_progress.py`로 헤더 재생성)
3. **git log --oneline**으로 전체 버전 커밋 히스토리 출력
4. **Notion DB 전체 상태 재확인**: 모든 row가 `완료`인지 `notion-fetch`로 크로스체크. 불일치 시 경고 + 사용자에게 수동 확인 요청 (secondary output)
5. **다음 단계 안내**: PR 생성·머지·배포는 이 스킬이 수행하지 않는다. 필요 시 `/release-workflow:main-branch-merge` 스킬로 체인하거나 수동 진행

---

## 기계적 제약 (절대 규칙)

이 제약은 구조적 실패를 방지하기 위한 것이다. 하나도 예외 없이 따른다. 각 항목의 **강제 수단**은 문서가 아닌 스크립트·스키마·훅이다 — 모델이 자각적으로 지키기보다 도구가 거부하도록 설계했다.

1. **"한 번에 하나의 작업"** — feature_list.json에서 하나를 선택하고 완료(pass 또는 blocked)될 때까지 다른 작업을 시작하지 않는다. _강제: 세션 오리엔테이션의 `current_task_id` 필드와 Evaluator의 단일 task 판정._

2. **"acceptance_criteria 삭제/수정 금지"** — 생성 시 기록된 SHA-256 해시(`acceptance_criteria_hashes`)와 항상 일치해야 한다. 달성 불가 시 사용자 에스컬레이션. _강제: `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/check_state_transition.py` + `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/validate_feature_list.py`._

3. **"검증 없이 pass 금지"** — Evaluator 검증 체크리스트를 모두 통과한 후에만 status를 "pass"로 변경한다. _강제: Evaluator 서브에이전트의 로그 파일 제출 요구(P1-1에서 상세화)._

4. **"스텁 금지"** — TODO, FIXME, placeholder, NotImplementedError, `todo!()` 등을 남기지 않는다. _강제: `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/scan_stubs.py` (Evaluator 선결 조건)._

5. **"진행 기록 필수"** — 매 작업 완료 시 PROGRESS.md와 feature_list.json을 반드시 업데이트한다. _강제: `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/sync_progress.py --check` (pre-commit 훅)._

6. **"JSON 형식 유지"** — feature_list.json은 항상 유효한 JSON·스키마여야 한다. _강제: `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/validate_feature_list.py` + `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/schemas/feature_list.schema.json` (pre-commit 훅)._

7. **"재시도 상한"** — 최대 2회 재시도 후 "blocked" + 사용자 에스컬레이션. `retry_count`는 0..2로 제한되고, `status="blocked"`는 `retry_count==2`와 동시에만 성립. _강제: 스키마 조건부 검증._

8. **"git push 절대 자동 실행 금지"** — 모든 push는 사용자가 직접 수행. 커밋만 생성한다.

9. **"증분적 구현만 허용"** — 기존 코드의 전체 리라이트 금지. 누락된 부분만 추가/수정. _강제: 동일 파일 5회 편집 시 차단 (`${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/edit_counter.py`)._

10. **"기존 코드 확인 후 구현"** — 구현 시작 전 반드시 관련 파일을 Read/Grep으로 확인한다.

11. **"이전 버전 컨텍스트 스캔 생략 금지"** — Phase 1 Step 2는 이전 버전 기록이 존재하는 한 생략할 수 없으며, 각 task 착수 직전에 `previous_context`를 다시 조회한다. _강제: `previous_context`는 스키마에서 `required` 배열이며, 빈 배열은 "첫 릴리즈" 명시적 신호로만 허용._

---

## 외부 도구 장애 처리 (요약)

세부 정책은 `references/degradation_policy.md`. 핵심 원칙만 본문에 둔다.

| 경계 | 실패 모드 | 분류 | 처리 |
|------|----------|------|------|
| Notion 조회 (Phase 1 Step 4) | 3회 retry 후 실패 | **core** | 로컬 `task_list.json` fallback → 없으면 종료. 빈 데이터 생성 금지 |
| Notion 쓰기 (Phase 2 Step C 역방향) | 4xx/5xx/예외 | **secondary** | 경고 + PROGRESS.md "발견된 이슈" 기록 + 로컬 pass 유지 + 다음 task 진행 |
| Context7 MCP | 미연결/빈 응답 | **core (제한적)** | 사용자에게 라이브러리 URL 질의. 훈련 데이터 추론 금지 |
| 프로젝트 테스트·빌드 명령 (L3 증거) | command not found / 회귀 | **core** | task fail + evaluator_feedback에 구체 명시. 또는 CLAUDE.md 수정 질의 |
| 편집·에러 카운터 임계 초과 | `.loop_state.json` 누적 | **core** | Generator `blocked-loop` / Evaluator `blocked` 전이 + 4지선다 에스컬레이션 |
| 세션 재개 시 상태 파일 손상 | JSON 파싱 실패 | **core** | 자동 복구 금지 — stderr 공유 후 사용자 수동 수정 대기 |

**원칙**: core 실패는 반드시 표면화하고 사용자에게 에스컬레이션. secondary 실패는 흡수하되 PROGRESS.md에 기록. 조용한 실패 금지.

---

## 상태 전이 규칙 (요약)

```
fail → in_progress  : Generator가 task 집어 구현 시작
fail → pass         : Evaluator 모든 선결 조건·AC·evidence 통과 시
fail → blocked      : retry_count==2에서 Evaluator fail, 또는 edit/error 카운터 임계 초과
blocked → fail      : 사용자 명시적 해제 (retry_count=0 리셋, evaluator_feedback 이력 보존)
pass → *            : 금지 — 통과 후 새 이슈는 새 task로 등록 (check_state_transition.py 차단)
```

---

## 산출물

| 파일 | 생성 시점 | 용도 |
|------|-----------|------|
| `docs/skills/release-impl/v{version}/feature_list.json` | Phase 1 | Task State Machine (스키마: `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/schemas/feature_list.schema.json`) |
| `docs/skills/release-impl/v{version}/PROGRESS.md` | Phase 1 | 세션 간 인수인계 (`${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/sync_progress.py`로 헤더 자동 동기화) |
| `docs/skills/release-impl/v{version}/sprint_contracts/{task_id}.md` | Phase 2 Step A | Generator가 구현 전 작성하는 완료 기준 계약 |
| `docs/skills/release-impl/v{version}/logs/{task_id}/{i}.log` | Phase 2 Step B | Evaluator가 남기는 실행 증거 (L3/L2/L1) |
| `docs/skills/release-impl/v{version}/.loop_state.json` | Phase 2 전체 | 편집·에러 카운터 (git 추적 제외 권장) |
| 구현 코드 (프로젝트 전반) | Phase 2 | 실제 구현 |

---

## 사용하는 도구

| 약칭 | MCP 풀네임 | 용도 |
|-------|-----------|------|
| `notion-search` | `mcp__plugin_Notion_notion__notion-search` | 페이지 탐색 (Phase 1 Step 4) |
| `notion-fetch` | `mcp__plugin_Notion_notion__notion-fetch` | DB·row 조회 (Phase 1 Step 4, Phase 3 최종 확인) |
| `notion-update-page` | `mcp__plugin_Notion_notion__notion-update-page` | **역방향 상태 동기화** (Phase 2 Step C — pass/blocked 후 Notion row 업데이트) |
| `resolve-library-id` | `mcp__plugin_context7_context7__resolve-library-id` | Context7 — 서드파티 ID 해석 (Generator가 필요 시) |
| `query-docs` | `mcp__plugin_context7_context7__query-docs` | Context7 — 최신 API 문서 조회 |
| Task | Claude 표준 | Generator·Evaluator 서브에이전트 기동 |
| Git | 표준 CLI | 커밋만. push 자동 실행 금지 |

상세 호출 규약·필터 JSON·상태 속성 매핑은 `references/notion_integration.md`. 도구 미설치·네트워크 실패 시 거동은 `references/degradation_policy.md`.

---

## 참고 자료

- `agents/generator.md` — Generator 서브에이전트 시스템 프롬프트 (단일 task 구현, 스프린트 계약)
- `agents/evaluator.md` — Evaluator 서브에이전트 시스템 프롬프트 (실행 증거, L3/L2/L1 레벨, retry/blocked)
- `references/initializer_guide.md` — Phase 1 상세 (CLAUDE.md 계약, 이전 버전 스캔, feature_list 스키마, PROGRESS 템플릿)
- `references/failure_modes.md` — 14가지 실패 모드 대응표 + 상태 전이 상세
- `references/contract_consumer.md` — release-plan ↔ release-impl 필드 매핑·경로 규약
- `references/notion_integration.md` — Notion MCP 풀네임·필터 JSON·역방향 업데이트 규약
- `references/degradation_policy.md` — 외부 도구 장애 처리 정책 (core vs secondary)
- `references/generator_guide.md` — Generator용 증분 구현·코딩 컨벤션 보조 가이드
- `references/evaluator_guide.md` — Evaluator용 검증 체크리스트·실패 패턴 보조 가이드
- `scripts/` — validate_feature_list / check_state_transition / check_evidence_logs / check_sprint_contract / scan_stubs / sync_progress / edit_counter / init_version / scan_previous_versions / state_digest / install_hooks
