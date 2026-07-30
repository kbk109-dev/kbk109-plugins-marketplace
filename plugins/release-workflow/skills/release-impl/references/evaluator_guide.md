# Evaluator 보조 가이드

이 문서는 `agents/evaluator.md` 시스템 프롬프트의 **보조 자료**다. agents 파일은 호출 계약·게이트·실패 형식만 두고, 검증 절차 상세는 여기에 둔다. Evaluator는 필요할 때만 Read한다 (점진적 정보 공개).

## 검증 절차 상세

### Step 1: 선결 조건 (하나라도 실패 시 즉시 fail)

1. **스프린트 계약 유효성**: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/check_sprint_contract.py {version_dir} {task_id}` → exit 0. 1이면 stderr 메시지를 feedback에 그대로 포함해 fail. 계약 파일이 없거나 세 섹션(예상 수정 파일/예상 검증 커맨드/예상 실패 가능점) 중 하나라도 비어 있으면 거부.
2. **스텁 부재**: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/scan_stubs.py {modified_files...}` → exit 0. 1이면:
   > `"{hits를 파일:라인별로 나열}. 스텁 코드를 제거해야 pass 가능."`
3. **acceptance_criteria 해시 일치**: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/validate_feature_list.py {feature_list_path}` → exit 0이어야 한다. 해시 불일치는 Generator가 criteria를 수정했다는 신호 — 즉시 fail + 명시적 지적.
4. **소비 프로젝트 working tree가 Generator 보고와 일치**: `git diff --stat`(필요 시 `--relative={implementation_root}`)으로 modified_files와 교차 확인. 보고되지 않은 전역 변경은 지적 필요.

### Step 2: Criterion별 실행 증거 수집

각 acceptance_criteria[i]에 대해 가장 강한 증거 레벨 채택. `implementation_root`가 비어 있지 않으면 명령은 그 디렉토리에서 실행 (`cd {project_root}/{implementation_root} && ...`).

| 레벨 | 증거 | 언제 사용 |
|------|------|----------|
| L3 — 실행 로그 | CLAUDE.md 명령(`npm test`, `npx tsc` 등)을 실제 실행하여 stdout+stderr를 `{version_dir}/logs/{task_id}/{i}.log`에 기록 | criterion이 "테스트 통과", "타입 에러 없음" 등 실행 가능 |
| L2 — 파일 Read | 대상 파일을 Read하여 함수/패턴 존재 확인, 스니펫을 로그 파일에 기록 | criterion이 "함수 X가 파일 Y에 존재" 등 구조적 주장 |
| L1 — Grep | 여러 파일에 걸친 패턴 존재 확인. Grep 결과를 로그 파일에 기록 | criterion이 "import가 제거되었음" 등 교차 파일 주장 |

**L0(자기 서술·기억 의존) 금지**. "확인했음"만 적고 로그 파일이 없으면 자동 fail. 로그 파일이 비어 있거나 에러 exit이면 해당 criterion fail.

로그 파일 경로 고정: `{version_dir}/logs/{task_id}/{i}.log`. 디렉토리는 `mkdir -p`로 생성.

### Step 3: 회귀 확인

- CLAUDE.md 테스트 명령을 한 번 실행 (Step 2에서 실행했다면 로그 재사용).
- pass였던 task의 코드가 새 구현으로 깨지지 않았는가? Generator가 건드린 파일이 pre-existing import/export를 훼손하지 않았는지 확인.
- 회귀 발견 시 해당 task fail + evaluator_feedback에 회귀 경로 명시.

### Step 4: 아키텍처 준수

- 파일 배치·네이밍·임포트 경로가 CLAUDE.md 규정과 일치하는가.
- `previous_context[].type == "architecture_decision"` 항목의 경로·패턴 위반 여부.
- 위반 시 fail + 어떤 decision과 충돌하는지 명시.

### Step 5: 결과 기록

**pass인 경우**:
- `feature_list.json`의 해당 task: `status="pass"`, `evaluator_feedback=null`, `completed_at={ISO timestamp}`, `evidence_logs={…}`.
- 전체 `summary.pass`+=1, `summary.fail`-=1 재계산.
- 최상위 `current_task_id=null`로 비운다.
- **마지막 pass 게이트**: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/check_evidence_logs.py {version_dir} {task_id}` → exit 0. 게이트 fail이면 pass 판정 취소 → fail verdict.
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/sync_progress.py {version_dir}`로 PROGRESS.md 헤더 재생성.
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/validate_feature_list.py {feature_list_path}`로 전체 재검증 (exit 0 필수).
- `evidence_logs` 맵을 출력 JSON에 포함.

**fail인 경우**:
- `feature_list.json`의 해당 task: `retry_count+=1`, `evaluator_feedback="{구체적 지적}"`.
- 이전 `evaluator_feedback` 값이 있으면 `evaluator_feedback_history`(array, optional)에 그대로 append.
- `retry_count >= 2`이면 `status="blocked"` 전이. 최상위 `current_task_id`는 비우지 **않는다** — 사용자 에스컬레이션 대기. blocked → fail 해제 시 `current_task_id=null` 리셋.
- summary 재계산은 하지 않는다 (여전히 fail 카테고리 유지).
- Evaluator는 재구현을 직접 수행하지 않는다. 호출 측이 Generator를 재기동.

---


## 증거 레벨 상세

Evaluator는 각 acceptance_criteria[i]에 대해 증거를 수집하여 `{version_dir}/logs/{task_id}/{i}.log`에 저장한다. 아래 레벨 중 가장 강한 증거를 채택한다:

### L3 — 실행 로그

criterion이 "테스트 통과", "타입 에러 없음", "빌드 성공" 같이 **결정적 명령**으로 검증 가능한 경우.

| criterion 유형 | 실행 명령 (CLAUDE.md에서) | 로그 내용 |
|----------------|---------------------------|----------|
| 테스트 통과    | `npm test` / `pytest` / `go test ./...` / `cargo test` | stdout + stderr 전체 + exit code |
| 타입 에러 없음 | `npx tsc --noEmit` / `mypy src/` / `pyright` / `go vet ./...` / `cargo check` | 동일 |
| 빌드 성공      | `npm run build` / `go build` / `cargo build` / `mvn compile` | 동일 |
| 린트 통과      | `eslint` / `ruff check` / `golangci-lint` | 동일 |

명령 표준 stdout/stderr을 `{i}.log` 파일로 리다이렉트. 파일 끝에 `# exit=0` 또는 `# exit={N}` 한 줄 첨부.

### L2 — 파일 Read 증거

criterion이 "함수 X가 파일 Y에 존재", "특정 컴포넌트에 prop P 추가" 같이 **구조적 주장**인 경우. Read 결과의 해당 스니펫(앞뒤 5줄 포함)을 로그 파일에 기록하고, 끝에 `# assertion: matched` 주석 추가.

### L1 — Grep 증거

criterion이 "기존 import가 모두 제거됨", "어떤 패턴이 교차 파일에서 일관성 있게 적용됨" 같이 **다중 파일 주장**인 경우. Grep 결과 전체(파일:라인:내용)를 로그 파일에 기록.

### L0 금지

"검토했음", "확인 완료" 같은 자기 서술로 pass를 주지 않는다. 로그 파일이 없거나 비어 있으면 자동 fail.

---

## 흔한 실패 패턴과 대응

| 패턴 | 증상 | 대응 |
|------|------|------|
| Import 누락 | 새 심볼을 참조했지만 import 없음 | 타입 검사 L3 로그에서 포착. feedback: `"src/x.ts:N — foo() 사용 시 import 누락. 파일 상단에 import { foo } from '@/lib/bar' 추가"` |
| 타입 불일치 | interface 정의와 실제 사용 다름 | 타입 검사 L3 로그 + 양쪽 파일 Read 교차 | 
| 테스트 미작성 | 코드만 있고 테스트 없음 | acceptance_criteria에 "테스트 통과"가 있으면 L3 로그에 테스트 발견 0건이면 fail |
| 기존 코드 덮어쓰기 | 이미 존재하던 함수가 변경 | `git diff HEAD^ -- {file}`로 pre-existing 코드 변경 감지. 의도된 변경이 아니면 fail |
| 잘못된 경로 | CLAUDE.md 디렉토리 규정과 불일치 | architecture_decision previous_context 비교 |
| Edge case 미처리 | 빈 입력/null/특수문자 | acceptance_criteria에 명시된 경우 직접 입력해 테스트 실행 |
| 스텁 | TODO / NotImplemented 잔존 | `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/scan_stubs.py`가 선결 조건에서 포착 |

---

## 피드백 품질 기준

`evaluator_feedback`은 Generator가 **추가 조사 없이** 재구현에 착수할 수 있어야 한다:

- 파일 + 라인 번호
- 무엇이 잘못됐는가 (관찰 가능한 사실)
- 어떻게 고칠지 (구체 제안)

**나쁜 예**: `"코드 품질이 부족합니다"`, `"검증 실패"`, `"타입 에러"`.
**좋은 예**: `"src/lib/payment.ts:45 — processPayment가 AbortError를 일반 Error로 래핑. acceptance_criteria[1]은 '네트워크 에러를 분류하여 반환'을 요구. PaymentAbortError 새 클래스로 래핑 필요 (기존 PaymentError 패턴 참조)"`.

---

## Secondary Output 실패 처리

Notion 상태 업데이트, 외부 알림 등 **secondary output**의 실패는 core execution을 차단하지 않는다:

- Notion `notion-update-page` 실패 → 경고 출력 + `PROGRESS.md` "발견된 이슈"에 한 줄 기록 + 로컬 `feature_list.json`은 pass 유지
- 외부 API 실패 → 로컬 상태는 계속 진행

이 정책은 release-impl 전용 설계 원칙으로 **역방향 Notion 동기화가 실패해도 구현 자체는 멈추지 않게** 한다. 자세한 처리 규약은 (Sprint 3에서 추가될) `references/degradation_policy.md` 참조.

---

## 재시도와 blocked 전이

1. 첫 fail: `retry_count=1`, feedback 기록, Generator 재기동
2. 두 번째 fail: `retry_count=2`, feedback 기록, 재기동
3. 세 번째 fail 시도 **금지**: 대신 `status="blocked"` 전이 + 사용자 4지선다 에스컬레이션 (SKILL.md Phase 2 Step D 참조)

blocked → fail 해제는 사용자 지시로만 발생하며, 그때 `retry_count`는 0으로 리셋한다. 단 `evaluator_feedback`은 `[resolved:{ISO}] 원래 피드백` 형식으로 이력을 보존한다.
