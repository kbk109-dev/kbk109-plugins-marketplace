# 실패 모드 대응표 + 상태 전이 규칙

release-impl이 방어하려는 **구조적 실패 모드**와 그 대응책. CLAUDE.md의 "LLM 구조적 실패 모드" 4가지를 이 스킬 맥락으로 확장한 것이다. SKILL.md 본문에서 요약만 유지하고, 상세 대응 매핑은 이 문서에 격리한다.

---

## 실패 모드 → 대응 매핑

| 실패 모드 | 증상 | release-impl 대응 |
|-----------|------|-------------------|
| 세션 간 상태 유실 | 이전 작업을 모르고 처음부터 시작 | `PROGRESS.md` + `git log` + `.loop_state.json` — 외부화된 상태. 매 세션 오리엔테이션 강제 |
| **버전 간 컨텍스트 유실** | 이전 버전의 blocked·결정·이슈를 모른 채 같은 함정 반복 | Phase 1 Step 2 이전 버전 스캔 + `previous_context` 필드 + 각 task 착수 직전 재조회 강제 |
| 전체를 한번에 구현 | 여러 task 동시 진행, 미완성 코드 | Task State Machine — 한 번에 하나의 task만. Generator 서브에이전트가 단일 task 컨텍스트로만 기동 |
| 자기평가 편향 | Generator가 자기 코드를 "pass"로 판정 | Generator와 Evaluator 서브에이전트 분리 (Task 도구로 각각 기동) |
| 코드 작성 = 완료 선언 | 검증 없이 "pass" 표시 | Evaluator가 `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/check_evidence_logs.py`로 `{version_dir}/logs/{task_id}/{i}.log` 실재·비어있지 않음 검증. 로그 없이는 pass 불가 |
| 같은 접근 반복 | 동일 에러를 계속 수정 시도 | 외부화된 `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/edit_counter.py` — 5회 편집 시 Generator `blocked-loop`, 3회 동일 에러 시 Evaluator `blocked` 전이 |
| 기존 코드 파괴 | 전체 리라이트로 작동하던 코드 파손 | Generator 프롬프트 규칙 + `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/check_state_transition.py`의 `pass→fail` 전이 금지 |
| 스텁 방치 | TODO·NotImplementedError 남겨둔 채 pass | `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/scan_stubs.py`가 Evaluator 선결 조건에서 거부 |
| acceptance_criteria 변조 | 달성 불가한 criterion을 완화하여 통과 | 생성 시 SHA-256 해시 (`acceptance_criteria_hashes`). `check_state_transition.py`가 해시 변경을 무조건 reject |
| 계약 없는 즉흥 구현 | Generator가 "완료의 모양" 없이 코딩 시작 | `${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/check_sprint_contract.py` — 세 섹션(예상 수정 파일/검증 커맨드/실패 가능점) 비어 있으면 Evaluator가 즉시 fail |
| 무한 재시도 | `retry_count` 상한 없음 | 스키마 조건부: `retry_count ≤ 2`. `blocked` 전이는 `retry_count==2`와 동시에만 성립 |
| Notion 상태 고착 | 구현 후 Notion 쪽은 여전히 "계획 중" | Phase 2 Step C pass 처리에서 Notion 역방향 상태 업데이트 강제 (단, 실패 시 secondary) |
| 오케스트레이터 체인 중단 | 자동 호출 중 사용자 확인 게이트 블록 | "호출 모드 감지" 섹션이 task_list/브랜치/프롬프트 신호로 자동 판별 → 오케스트레이터 모드에서 Step 7 게이트 생략 |
| 조용한 실패 | Notion 오프라인·Context7 부재를 감지 못 하고 진행 | Phase 1 Step 0 도구 가용성 체크 + `references/degradation_policy.md`의 core vs secondary 분류 |

---

## 상태 전이 규칙

```
fail → in_progress : Generator가 task를 집어 구현 시작 시
in_progress → fail : Generator가 blocked-* 없이 종료, 또는 Evaluator fail 판정 시
fail → pass        : Evaluator 모든 선결 조건·acceptance_criteria·evidence_logs 통과 시
fail → blocked     : retry_count==2 시점에서 Evaluator fail, 또는 edit_counter/error_counter 임계 초과 시
blocked → fail     : 사용자 명시적 해제 시 (retry_count=0으로 리셋, evaluator_feedback은 '[resolved:ISO] …'로 이력 보존)
pass → *           : 금지 (${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/check_state_transition.py가 reject). 통과 후 새 이슈 발견 시 새 task 등록
```

`in_progress`는 transient 상태 — 세션이 중단된 지점에서 재개할 때 `current_task_id` 필드와 함께 복원 용도로 사용. `summary`에는 `fail` 카테고리로 계산된다 (pass 직전까지는 "아직 증명되지 않음").

---

## 재시도 경로

1. **첫 fail**: Evaluator가 `retry_count=1`, `evaluator_feedback="…"` 기록. Generator 재기동
2. **두 번째 fail**: `retry_count=2`, feedback 갱신. Generator 재기동
3. **세 번째 시도 금지**: `status="blocked"` 전이 + `edit_counter.py error` 호출 결과에 따라 error_count도 반영
4. **4지선다 에스컬레이션** (SKILL.md Phase 2 Step D)

blocked → fail 해제는 사용자 지시로만 발생하며 그때 `retry_count=0`으로 리셋한다. `evaluator_feedback`은 `[resolved:{ISO}] 원래 피드백` 형태로 이력을 보존한다 — 다음 구현이 같은 함정에 다시 빠지지 않도록 맥락을 남긴다.
