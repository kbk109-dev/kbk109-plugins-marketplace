# task_list.json 계약

이 문서는 release-plan이 생성하고 release-impl·fix-plan-impl이 소비하는 `task_list.json`의 스키마 계약이다. 필드 추가·제거 시 이 문서와 `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/validate_task_list.py`를 함께 갱신한다.

## 경로

```
docs/skills/release-plan/{DB slug}/v{버전}/task_list.json
```

`{DB slug}`는 반드시 `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/slugify.py` 출력값을 사용한다.

## 스키마

```json
{
  "version": "v{버전}",
  "created_at": "YYYY-MM-DD",
  "notion_page": "{페이지 이름}",
  "notion_database": "{DB 이름}",
  "input_version": "{입력 버전}",
  "base_version": "{기존 DB 최대 버전 또는 null}",
  "implementation_root": null,
  "summary": {
    "total": 0,
    "pass": 0,
    "fail": 0,
    "blocked": 0
  },
  "fact_check": {
    "verdict": "pass",
    "tokens_path": "tokens.json",
    "verified_count": 0,
    "unverified_tokens": [],
    "evidence_logs": {},
    "checked_at": "YYYY-MM-DDTHH:MM:SS"
  },
  "tasks": [
    {
      "id": "TASK-001",
      "task_number": 1,
      "name": "[Task 1] 이메일 로그인 구현",
      "version": "2.1.0",
      "category": "feature",
      "status": "fail",
      "acceptance_criteria": [
        "검증 가능한 완료 조건 1",
        "검증 가능한 완료 조건 2"
      ],
      "implementation_details": [
        "구체적인 구현 사항 1",
        "구체적인 구현 사항 2"
      ],
      "depends_on_labels": [],
      "parallel_with_labels": ["[Task 2]"],
      "retry_count": 0,
      "completed_at": null
    }
  ]
}
```

## 필드 의미

- `task_number`: 버전별 1부터의 연속 정수. 동일 `version`을 공유하는 task 간에 중복·건너뛰기 금지.
- `name`: 정규식 `^\[Task <task_number>\] .+`를 만족해야 한다.
- `status`: `fail` | `pass` | `blocked`. 생성 시 반드시 `fail`.
- `acceptance_criteria`: 비어있지 않은 문자열 배열. **생성 후 삭제·수정 금지**. 달성 불가 시 사용자에게 에스컬레이션.
- `depends_on_labels` / `parallel_with_labels`: `[Task N]` 라벨 배열. 동일 라벨이 두 배열에 동시에 등장하면 안 된다. 자기 자신 참조 금지. 존재하지 않는 Task 참조 금지.
- `implementation_root` (선택): 모노레포에서 이번 릴리즈가 만지는 패키지의 `project_root` 기준 상대 경로. 단일 패키지 저장소에서는 `null`(생략 가능). release-impl이 Generator 탐색·Evaluator 명령 실행 범위를 이 경로로 좁힌다. 5번째 옵션 입력으로 받으며, 누락 시 `null`로 저장하여 backward compatibility를 유지한다.

## 외부 사실 검증 (fact_check)

`task_list.json` 작성 직후 `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/extract_tech_tokens.py`가 `tokens.json`을 만들고, `agents/fact-checker.md` 서브에이전트가 외부 도구(Context7 → WebSearch 폴백)로 각 토큰의 실존성을 확인한 뒤 이 객체를 채운다. 동일 폴더의 `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/verify_tech_tokens.py`가 게이트로 동작하여 `verdict ∈ {pass, unverified-user-approved}`이고 `evidence_logs`의 모든 경로가 실재·비공백일 때만 통과시킨다.

- `verdict`:
  - `pass`: 모든 토큰이 외부 도구로 검증됨. `unverified_tokens`는 반드시 비어 있어야 한다.
  - `unverified-user-approved`: Context7와 WebSearch 모두 응답 실패한 환경에서 호출 측이 사용자 명시 승인을 받은 경우에만 부여. Fact-checker가 직접 부여 금지.
- `tokens_path`: `extract_tech_tokens.py` 출력 경로 (`task_list.json` 위치 기준 상대 경로 권장).
- `evidence_logs`: `{token: log_path}` 매핑. 각 로그 파일은 호출한 도구·정확한 쿼리·응답 원문·판정 한 줄을 포함한다. 빈 로그는 게이트가 fail 처리한다.
- `unverified_tokens[]`: 미검증 토큰 객체. 각 항목은 `{value, kind, reason, occurrences_first}` 형식.
- `checked_at`: ISO 8601 timestamp.

`tokens.json`의 `tokens` 배열이 비어 있는 경우(예: UI-only 변경) `verdict: pass`, `evidence_logs: {}`로 즉시 통과 가능하다.

## 상태 전이 규칙

- `fail → pass`: Evaluator 검증 통과 시
- `fail → blocked`: 2회 재시도 실패 시 (사용자 개입 필요)
- `blocked → fail`: 사용자가 차단 해제 시
- `pass → fail`: **금지** — 통과 후 새 이슈 발견 시 새 작업으로 등록

## 검증

작성 직후 반드시 실행:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/validate_task_list.py docs/skills/release-plan/{slug}/v{버전}/task_list.json
```

exit code가 0이 아니면 Step 8로 진행하지 않는다. stderr에 출력되는 오류 목록을 기반으로 수정 후 재검증한다.

## 소비자 계약

- **release-impl**: `tasks[].acceptance_criteria`와 `depends_on_labels` 순서로 구현한다.
- **fix-plan-impl**: 오케스트레이터로서 `summary`를 집계해 완료 여부를 판단한다.

소비자는 `acceptance_criteria`를 수정하지 않는다. 추가 기준이 필요하면 새 Task로 등록한다.
