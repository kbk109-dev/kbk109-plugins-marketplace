# release-plan ↔ release-impl 계약 수용

이 문서는 release-impl이 release-plan의 산출물(`task_list.json`)을 소비할 때 따르는 계약을 정의한다. 경로·스키마·필드 매핑 규칙을 한 곳에 고정하여, 두 스킬이 다른 기대치로 어긋나 "로컬 파일이 있는데도 Notion 조회로 빠지는" 조용한 실패를 방지한다.

원천 계약: `skills/release-plan/references/task_list_contract.md`.
검증 스크립트: `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/validate_task_list.py`, `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/slugify.py`.

---

## 경로 규약

```
docs/skills/release-plan/{slug(database_name)}/v{version}/task_list.json
```

- `{slug(database_name)}`: release-plan의 `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/slugify.py`가 산출하는 kebab-case 슬러그. release-impl은 반드시 같은 스크립트를 호출하여 슬러그를 얻는다. 직접 문자열 가공 금지 — 같은 DB 이름이 두 스킬에서 다른 경로로 귀결되면 계약 파손.
- `v{version}`: 입력 버전을 `v{major.minor.patch}`로 정규화한 값. `0.9.0`/`v0.9.0`/`V0.9.0` 모두 `v0.9.0`으로 통일.

호출 예:

```bash
DB_SLUG=$(python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/slugify.py "{database_name}")
TASK_LIST="docs/skills/release-plan/${DB_SLUG}/v{version}/task_list.json"
```

---

## 선행 검증

`task_list.json`을 읽기 전 반드시 release-plan의 검증 스크립트를 통과시킨다. 실패 시 release-plan 재실행을 유도한다.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/validate_task_list.py "${TASK_LIST}"
```

exit code가 0이 아니면 stderr를 사용자에게 보여주고 release-plan 재실행을 요청한다. release-impl은 깨진 task_list로 진행하지 않는다.

---

## 필드 매핑표

| task_list.json (release-plan) | feature_list.json (release-impl) | 변환 규칙 |
|-------------------------------|----------------------------------|-----------|
| `tasks[].task_number` (int) | `tasks[].id` (string) | `f"TASK-{task_number:03d}"` — zero-padded 3자리 |
| `tasks[].name` (string, `[Task N] 제목`) | `tasks[].title` | 그대로 복사. `[Task N]` 접두사 **보존** — PROGRESS.md 가독성과 역추적에 필요 |
| `tasks[].acceptance_criteria` (list[str]) | `tasks[].acceptance_criteria` | 불변 복사. 생성 시 `sha256` 해시를 최상위 `acceptance_criteria_hashes`에 기록하여 이후 수정·삭제를 감지 |
| `tasks[].implementation_details` (list[str]) | `tasks[].description` (string) | 줄바꿈으로 join |
| `tasks[].depends_on_labels` (list[`[Task N]`]) | `tasks[].dependencies` (list[string]) | 각 `[Task N]` → 대응 `TASK-NNN` id로 변환 |
| `tasks[].parallel_with_labels` | (미사용) | release-impl은 순차 실행만 수행하므로 매핑하지 않는다. 향후 병렬 구현 지원 시 추가 |
| `tasks[].version` | (참조만) | 버전 일치 확인에만 사용. feature_list.json 자체가 단일 버전 스코프 |
| `tasks[].status` | `tasks[].status` | 항상 `"fail"`로 강제 — release-plan에서 다른 값이 와도 덮어쓴다 |
| `tasks[].retry_count` | `tasks[].retry_count` | 항상 `0`으로 초기화 |
| `tasks[].completed_at` | `tasks[].completed_at` | 항상 `null`로 초기화 |
| `tasks[].category` | (참조만) | 분류 정보는 PROGRESS.md 본문 서술에만 활용 |
| `notion_page` | `notion_page` | 그대로 복사 |
| `notion_database` | `notion_database` | 그대로 복사 (입력값 #2와 일치해야 함. 불일치 시 오류) |
| `implementation_root` (옵션) | `implementation_root` | 그대로 복사. 누락 또는 `null`은 단일 패키지 저장소 의미 — 모든 도구가 `project_root` 전체를 사용 |

release-impl 고유 필드 (매핑 원천 없음): `previous_context`, `summary`, `source`, `created_at`.

---

## 불변성 보장

- `acceptance_criteria`는 release-plan이 생성한 이후 **수정·삭제 금지** (release-plan task_list_contract §6 재인용). release-impl은 생성 시 각 task criterion 배열의 SHA-256 해시를 `feature_list.json`의 `acceptance_criteria_hashes[task_id]`에 기록한다. `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/check_state_transition.py`가 매 커밋에서 이 해시의 변경을 차단한다.
- `tasks[].id`는 생성 후 변경 불가. task 재배치가 필요하면 `dependencies`에서만 순서를 조정한다.

---

## 오류 처리

| 상황 | 처리 |
|------|------|
| task_list.json 부재 | SKILL.md Step 4 경로로 진행 — Notion에서 직접 조회 |
| JSON 파싱 실패 | 사용자에게 원본 오류 공유, release-plan 재실행 권장 |
| `validate_task_list.py` 실패 | stderr 출력 공유, release-plan 재실행 권장 |
| `notion_database` 값이 입력 DB 이름과 다름 | "task_list.json의 DB 이름({written})이 입력값({input})과 다릅니다. 올바른 DB 이름을 확인해주세요." 출력 후 종료 |
| `tasks` 배열이 빈 리스트 | "이 버전에 등록된 작업이 없습니다. release-plan으로 작업을 먼저 등록해주세요." 출력 후 종료 |

---

## 파일 생성 전 의무 체크리스트

feature_list.json을 쓰기 전 release-impl은 다음을 모두 통과해야 한다:

1. `slugify.py`로 계산한 경로에 task_list.json이 실재하는가
2. `validate_task_list.py`가 exit 0인가
3. `notion_database` 값이 입력 DB 이름과 일치하는가
4. 매핑표대로 변환한 결과가 `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/validate_feature_list.py`를 통과하는가

이 중 하나라도 실패하면 **feature_list.json을 생성하지 않는다**. 잘못된 계약 상태에서 파일을 만들면 이후 세션이 그 파일을 신뢰하고 구현을 진행해 구조적 오류가 눌러붙는다.
