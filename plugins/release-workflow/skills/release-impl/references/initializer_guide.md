# Initializer 상세 가이드 (Phase 1)

SKILL.md Phase 1의 Step 1·Step 2·Step 5·Step 6에서 사용하는 상세 계약·템플릿·스키마. SKILL.md 본문은 흐름만 유지하고, 표·템플릿은 이 문서에 격리되어 있다 (점진적 정보 공개).

---

## Step 1 — CLAUDE.md 계약

release-impl은 언어·프레임워크를 가정하지 않는다. 모든 기술 스택 정보는 프로젝트의 `CLAUDE.md`에서 읽는다. 이유: JS 기본값을 Python/Go/Rust에 밀어 넣으면 조용히 오작동한다.

| 항목 | CLAUDE.md 예시 | 없을 때 폴백 |
|------|----------------|-------------|
| 기술 스택 | `언어: Python 3.11 / 프레임워크: FastAPI` | 루트 파일(`pyproject.toml`/`go.mod`/`Cargo.toml`/`package.json` 등)로 추론 후 **사용자 확인** |
| 테스트 명령 | `pytest tests/ -v` | 사용자에게 직접 질의 (`"프로젝트 테스트 명령을 알려주세요 (예: pytest, go test ./..., cargo test, npm test)"`) |
| 빌드/타입 검사 명령 | `mypy src/` / `npx tsc --noEmit` | 사용자에게 직접 질의 |
| 린트 명령 | `ruff check src/` | 선택적 — 생략 가능 |
| 네이밍 컨벤션 | `snake_case 변수/함수, PascalCase 클래스` | 기존 코드 패턴에서 추론 |
| 임포트/모듈 경로 패턴 | `from src.module import …` 또는 path alias `@/` | 기존 코드 패턴에서 추론 |
| 디렉토리 구조 | `소스: src/, 테스트: tests/` | 기존 코드 배치에서 추론 |
| 커밋 컨벤션 | `feat/fix/chore/... with scope` | 없으면 `feat(release/v{version}): …` 폴백 |

자동 추론이 모호하면 사용자 질의로 폴백한다. 임의 기본값을 써서 진행하지 않는다.

---

## Step 2 — 이전 버전 컨텍스트 스캔 (결정적 스크립트)

`docs/skills/release-impl/` 하위에 이전 버전 디렉토리가 있으면 현재 버전 구현 **전에** 분석한다. 이전 구현의 미해결 이슈·결정·패턴을 모른 채 진행하면 같은 함정을 반복하거나 기존 컨벤션과 충돌한다.

LLM이 디렉토리를 직접 Read하지 않고 `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/scan_previous_versions.py`가 결정적으로 후보를 산출한다 — 버전이 누적될수록 비용이 폭증하던 수동 절차를 1회 Bash 호출로 압축한다.

### 스캔 절차

1. **스크립트 실행** — 최근 K개 semver만 스캔(권장 `--limit 3`). `--current`로 자기 자신은 제외:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/scan_previous_versions.py scan \
     docs/skills/release-impl/ --current v{version} --limit 3
   ```

2. **자동 추출되는 네 항목** (`candidates[]`):

   | type | 출처 | 현재 버전에 주는 영향 |
   |------|------|---------------------|
   | `blocked_task` | `feature_list.json`의 `status=="blocked"` task + `evaluator_feedback` | 이월/대체 여부 판단 |
   | `known_issue` | `PROGRESS.md` "## 발견된 이슈" bullet 항목 | 같은 영역을 건드릴 때 주의할 함정 |
   | `architecture_decision` | `PROGRESS.md` "## 아키텍처 결정" bullet 항목 | 이미 세워진 디렉토리·경로·패턴. 중복·상충 방지 |
   | `dependency` | `PROGRESS.md` "## 의존성 변경" bullet 항목(있을 때) | 추가·제거된 라이브러리·초기화 코드 위치 |

3. **관련성 판정 (LLM)**: 스크립트 출력의 `candidates`를 받아 현재 버전 task 영역과 겹치거나 영향을 주는 항목만 남긴다. 무관한 과거 작업은 컨텍스트 오염을 유발하므로 제외. 이 단계가 LLM이 직접 수행하는 유일한 부분.

4. **결과 저장**: Step 5(`feature_list.json.previous_context`)와 Step 6(`PROGRESS.md` "이전 버전 컨텍스트" 섹션)에 기록. 각 task 구현 직전에 Generator가 다시 읽는다.

### digest 캐시 (옵션)

Step 5/6 직후 같은 스크립트의 `digest` 모드를 호출하면 `docs/skills/release-impl/v{version}/previous_context_digest.json`이 생성된다. 다음 버전이 `consume`으로 이 파일을 먼저 읽고 source 파일 sha256 검증을 통과하면 재사용 — drift 감지 시 자동 폴백으로 `scan` 재실행. 두 번째 버전부터 비용이 V→1로 떨어진다.

```bash
# 작성 (현재 버전 작업 종료 시점)
python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/scan_previous_versions.py digest \
  docs/skills/release-impl/ --current v{version} --limit 3

# 소비 (다음 버전 Phase 1 Step 2 진입 시)
python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/scan_previous_versions.py consume \
  docs/skills/release-impl/v{prev_version}/previous_context_digest.json
```

소비 결과 `status: drift`이면 그대로 무시하고 정규 `scan`을 다시 실행한다.

**이전 버전 기록이 없을 때** (첫 릴리즈): 이 Step 생략, `previous_context=[]`. 가짜 과거 기록을 만들지 않는다.

---

## Step 5 — feature_list.json 생성

경로: `docs/skills/release-impl/v{version}/feature_list.json`.

**결정적 템플릿은 `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/init_version.py`가 생성한다.** 수동 작성 금지 — 템플릿 드리프트의 주원인. 호출 예:

```bash
echo '{
  "version": "v0.9.0",
  "notion_page": "PayFlow Release Notes",
  "notion_database": "Release Plan",
  "source": "release-plan/task_list.json",
  "previous_context": [...],
  "tasks": [...]
}' | python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/init_version.py \
  docs/skills/release-impl/v0.9.0 --with-progress
```

스크립트는 다음을 자동으로 한다:
- `summary` 카운터 초기화 (모두 `fail` → `total=N, pass=0, fail=N, blocked=0`)
- `acceptance_criteria_hashes` SHA-256 계산 및 저장
- `tasks[]`에 `status="fail"`, `retry_count=0`, `evaluator_feedback=null`, `completed_at=null`, `evidence_logs={}` 강제 초기화
- `sprint_contracts/`, `logs/` 디렉토리 생성
- `created_at` 날짜 자동 기입

### 소스별 입력

| 소스 | 입력 규칙 |
|------|----------|
| **release-plan/task_list.json** (기본) | `references/contract_consumer.md`의 필드 매핑표 그대로 적용 |
| **notion-direct** (task_list 부재 시) | Notion `notion-fetch` 응답에서 `name → title`, `수용 기준 → acceptance_criteria`, `[구현 내용] → description` 매핑 |

**생성 후 반드시**:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/validate_feature_list.py {path}
```

exit 0이 아니면 stderr 오류를 해결한 뒤 재생성한다.

### 스키마 전체

선언적 계약은 `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/schemas/feature_list.schema.json` (Draft-2020-12). 핵심 필드:

- `version`: `^v\d+\.\d+\.\d+$`
- `summary`: `{total, pass, fail, blocked}` 모두 integer ≥ 0
- `acceptance_criteria_hashes`: `{TASK-NNN: sha256(64hex)}` 전 task 커버
- `previous_context[].type`: `blocked_task | known_issue | architecture_decision | dependency`
- `tasks[].status`: `fail | pass | blocked | in_progress`
- `tasks[].retry_count`: 0..2
- `tasks[].evidence_logs`: `{criterion_idx: "logs/{task_id}/{i}.log"}` (pass 시 필수)
- 조건부: `status=="pass" ⇒ completed_at:string`, `status=="blocked" ⇒ retry_count==2`, `retry_count>0 ⇒ evaluator_feedback:string`

---

## Step 6 — PROGRESS.md 생성

`init_version.py --with-progress`가 아래 템플릿으로 자동 생성한다. 수동 편집은 세션 로그 추가·"발견된 이슈" 업데이트에만 국한한다.

```markdown
# Progress — release-impl v{version}

> Last Updated: {YYYY-MM-DD HH:MM}
> Total Tasks: N | Pass: 0 | Fail: N | Blocked: 0

## 현재 상태

- 단계: 초기화 완료, 구현 대기
- 다음 작업: {첫 번째 task.title}
- 차단 사항: 없음

## 이전 버전 컨텍스트

> Step 2 스캔 결과 중 현재 버전에 영향을 주는 항목만 기록. 무관한 과거 작업은 넣지 않는다.

- **[v0.8.0 · blocked_task]** TASK-005 결제 웹훅 재시도 큐 — Stripe 서명 로테이션으로 blocked. 현재 TASK-002와 영역 겹침, 착수 전 evaluator_feedback 재확인
- **[v0.8.0 · known_issue]** 결제 폴링에서 setTimeout이 iOS 백그라운드에서 멈춤 — BackgroundTimer로 교체 필요
- **[v0.7.0 · architecture_decision]** 결제 핸들러는 src/lib/payment.ts에 집약 — 새 핸들러 추가 시 이 파일 유지

(이전 버전 기록이 없으면: "해당 없음 — 첫 릴리즈")

## 세션 로그

- [YYYY-MM-DD] Step 0: Notion MCP·Context7·CLAUDE.md 모두 가용
- [YYYY-MM-DD] 초기화: Notion에서 N개 작업 로드, feature_list.json 생성, 이전 버전 M개 스캔 완료

## 발견된 이슈

(없음)

## 다음 단계

1. {첫 번째 task.id}부터 순차 구현 시작
```

헤더의 "Total Tasks / Pass / Fail / Blocked" 라인은 매 task 완료 후 `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/sync_progress.py`로 자동 재생성한다. pre-commit 훅이 `sync_progress.py --check`로 드리프트를 차단한다.
