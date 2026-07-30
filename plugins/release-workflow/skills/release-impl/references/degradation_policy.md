# 외부 도구 장애 처리 정책 (Degradation Policy)

release-impl은 여러 외부 경계(Notion MCP, Context7 MCP, 네트워크, 프로젝트 빌드 도구)에 의존한다. 경계 하나가 실패했다고 스킬 전체를 중단하는 것은 "모 아니면 도"식 극단적 반응이며, 반대로 모든 실패를 조용히 삼키는 것은 "조기 완료 선언"을 숨기는 공범이 된다. 이 문서는 **어떤 실패를 core execution으로 보고, 어떤 실패를 secondary로 분리하는지**를 고정한다.

---

## 원칙

### Core vs Secondary

- **Core execution**: Task State Machine을 한 단계 앞으로 움직이는 연산. feature_list.json·PROGRESS.md·sprint_contracts/·logs/·구현 코드·git commit·acceptance 검증.
- **Secondary output**: 관측·알림·외부 기록. Notion 상태 업데이트·외부 webhook 통지·Slack 알림 등.

Core는 실패 시 **반드시 표면화하여 사용자에게 에스컬레이션**. Secondary는 실패 시 **경고 + PROGRESS.md 이슈 기록**으로 흡수하고 core는 계속 진행.

### Fallback 우선순위

1. 같은 외부 도구를 재시도 (네트워크 일시 장애일 수 있음)
2. 로컬 대체 데이터로 전환 (`task_list.json`, 캐시된 feature_list, 이전 세션 로그)
3. 사용자에게 수동 입력 요청 (최후의 수단)
4. 종료 — 스킬이 추론해선 안 되는 정보가 없으면 빈 값을 만들지 않고 종료

"데이터가 없으면 빈 배열을 만들어서 진행"은 조용한 실패. 항상 실제 신호(파일·응답·사용자 응답) 기반으로 진행한다.

---

## Phase 1 Step 0 — 도구 가용성 체크

Phase 1 Step 1(CLAUDE.md 읽기) 전에 **한 번만** 수행한다. 이후 세션·오리엔테이션에서는 반복하지 않는다.

1. **Notion MCP**: 노출된 함수 목록에 `mcp__plugin_Notion_notion__` 접두사가 있는가. 없으면:
   - 로컬 `docs/skills/release-plan/{slug}/v{version}/task_list.json`이 존재하면 Notion 없이 진행 가능 — 해당 경로로 전환하고 사용자에게 안내 (`"Notion MCP 미연결 — 로컬 task_list.json으로 진행합니다"`).
   - 로컬 파일도 없으면 종료: `"이 스킬은 Notion MCP 플러그인이 필요합니다. 설치 후 재시도하거나, docs/skills/release-plan/{slug}/v{version}/task_list.json을 먼저 준비해주세요."`
2. **Context7 MCP**: 노출된 함수 목록에 `mcp__plugin_context7_context7__` 접두사가 있는가. 없으면 경고만 출력하고 계속 진행 — Generator가 서드파티 라이브러리를 건드릴 때 별도 질의 경로를 쓴다 (아래 "Context7 실패" 참조).
3. **프로젝트 CLAUDE.md**: `{project_root}/CLAUDE.md`가 존재하는가. 없으면 Phase 1 Step 1의 폴백(루트 설정 파일 추론 + 사용자 확인)으로 넘어간다. 이 스킬은 CLAUDE.md 자체를 만들어주지 않는다.

이 체크의 결과는 `PROGRESS.md`의 "세션 로그" 첫 줄에 기록한다 — 이후 세션이 환경을 복원할 때 참조.

---

## Notion 조회 실패 (Phase 1 Step 4)

| 증상 | 대응 |
|------|------|
| `notion-search` 호출이 예외/빈 응답 | 3회 지수 backoff(2s → 4s → 8s) retry |
| 3회 모두 실패, 로컬 `task_list.json` 존재 | `contract_consumer.md` 경로로 전환해 로컬 파일 소비. 사용자에게 전환 사실 안내 |
| 3회 모두 실패, 로컬 파일 부재 | 종료. `"Notion 조회 실패 — 로컬 task_list.json도 없습니다. Notion 연결을 확인하거나 /release-workflow:release-plan을 먼저 실행해주세요."` |
| 페이지는 찾았으나 DB 이름 미존재 | 사용자에게 DB 이름 재확인 요청. 자동 유추 금지 (`"Release Plan"` 가정 금지) |
| DB는 찾았으나 지정 버전의 row가 0건 | `"버전 {version}에 해당하는 작업이 없습니다. /release-workflow:release-plan을 먼저 실행하셨나요?"` 후 종료 |

**하드 원칙**: Notion 응답에서 필드가 비어 있다고 해서 release-impl이 그 빈 자리를 메우지 않는다. 빈 criterion을 "필드 검증 통과"로 대체하거나, 빈 DB를 "첫 릴리즈"로 대체하는 것은 환각 생성이다.

---

## Notion 쓰기 실패 (Phase 2 Step C 역방향 업데이트)

| 증상 | 대응 |
|------|------|
| `notion-update-page` 예외 또는 4xx | 경고 stdout + `PROGRESS.md` "발견된 이슈"에 한 줄 기록 + 로컬 `feature_list.json`은 pass 유지. 다음 task로 진행 |
| 다수 task에서 반복 실패 | 3회 누적 시 사용자에게 "Notion 쓰기가 반복 실패합니다. 연결을 확인하거나 수동 동기화 계획이 필요합니다"라고 알린다. 여전히 core는 차단하지 않는다 |
| 5xx 반복 | 위와 동일. Notion 서비스 장애일 수 있으므로 자동 재시도는 3회 내에서만 |

Notion 쓰기는 **secondary output**이다. core execution(구현 + 로컬 상태 업데이트 + git commit)은 항상 우선한다.

---

## Context7 실패

| 증상 | 대응 |
|------|------|
| MCP 미연결 | Phase 1 Step 0에서 이미 감지. Generator는 서드파티 API가 필요할 때 사용자에게 "Context7 미연결 — 라이브러리 스펙 확정 URL을 알려주세요" 질의 |
| `resolve-library-id` 실패 | 다른 라이브러리 ID 후보를 1회 더 시도 후, 사용자 질의로 전환 |
| `query-docs`는 연결되나 빈 응답 | 사용자에게 "Context7에서 문서를 찾지 못했습니다. 참고 URL을 알려주세요" 질의 |

훈련 데이터에 의존한 API 추론은 금지. 잘못된 API 호출은 Evaluator에서 걸러지지만, "걸리고 나서 수정"하는 비용이 사용자 질의보다 크다.

---

## 프로젝트 빌드·테스트 명령 실패

Evaluator가 L3 증거 수집을 위해 CLAUDE.md 명령을 실행했을 때의 실패는 **core** 범주다 — pass 판정에 직접 영향이 있기 때문이다.

| 증상 | 대응 |
|------|------|
| 명령이 `command not found` | CLAUDE.md 계약 위반. 사용자에게 "CLAUDE.md의 테스트 명령(`{cmd}`)이 실행되지 않습니다. 현재 프로젝트의 실제 명령을 알려주세요" 질의 |
| 명령이 네트워크·의존성 누락으로 실패 | Evaluator가 사실 그대로 기록하고 해당 task fail. Generator가 재구현 시 의존성 설치 포함 여부 판단 |
| 기존에 통과하던 테스트가 새로 깨짐(회귀) | fail + evaluator_feedback에 회귀 경로 명시 (이전 pass task가 새 구현으로 무너짐) |

---

## 세션 복구 (이전 세션이 중단된 경우)

현재 세션이 시작됐는데 `feature_list.json`·`PROGRESS.md`가 이미 존재하면 재개 모드. 이때 다음 안전 검사를 순서대로 수행:

1. `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/validate_feature_list.py` → exit 0? 아니면 stderr을 사용자에게 공유하고 수동 수정 요청. 자동 복구 금지.
2. `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/sync_progress.py --check` → exit 0? 아니면 `sync_progress.py`(rewrite 모드)로 헤더만 재생성.
3. `.loop_state.json`이 존재하면 그대로 둔다 — 편집·에러 카운터는 세션 간 보존되어야 루프 감지가 의미 있다.
4. git working tree에 추적되지 않은 task 영향 파일이 남아 있다면 사용자에게 안내 (`"이전 세션의 미커밋 변경이 남아 있습니다. 검토 후 진행해주세요."`). 자동 stash·discard 금지.

---

## 에스컬레이션 문구 템플릿

다음 상황에서는 항상 사용자 개입을 요청한다:

1. Phase 1 Step 0에서 필수 도구가 누락된 경우 → 종료 (자동 추론 불가)
2. `retry_count==2` 도달 → SKILL.md Phase 2 Step D의 4지선다
3. Notion 쓰기가 3회 연속 실패 → 경고 + PROGRESS.md 기록 + 계속 진행 (사용자는 배치 완료 후 수동 동기화 계획 필요)
4. 세션 재개 시 `validate_feature_list.py` 실패 → 자동 수정 금지, 사용자에게 stderr 공유
5. `.loop_state.json`의 edit_count 임계 초과 → Generator가 `blocked-loop` 복귀, 호출 측이 SKILL.md Phase 2 Step D로 에스컬레이션

**절대 하지 않는 것**: 에스컬레이션 없이 "알아서 처리" 하는 것. 모든 경계 실패는 로그에 남기거나 사용자에게 보고되어야 한다.
