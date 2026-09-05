# 종단간 Golden Example — release-plan

하나의 가상 시나리오를 따라가며 입력 → 미리보기 → Notion 등록 → 관리 문서까지 전체 플로우를 예시한다. 세부 옵션은 모두 실제 기본값이며, 필드 하나하나가 나중에 release-impl이 소비하는 계약이라는 점을 보여주기 위한 참조용이다.

## 시나리오

프로젝트: **Stage Sudoku** (Expo RN 앱).

사용자 요청:

> Stage Sudoku 페이지의 '릴리즈 플랜' DB에 v2.2.0으로 릴리즈 계획 등록해줘. 이메일 로그인 이후에 로그인 유지(토큰 갱신) 기능 추가.

## Step 1~3 산출

- **페이지 ID**: "Stage Sudoku" 페이지 확인(이 프로젝트에 설치된 Notion 연동 방식으로 위임)
- **DB 이름**: `릴리즈 플랜` (존재함)
- **DB slug**: `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/slugify.py "릴리즈 플랜"` → `untitled` (한글만 → ASCII 변환 결과 빈 문자열이라 fallback)
  - ⚠️ 한글 전용 DB 이름은 slug가 `untitled`로 수렴할 수 있으므로 팀 단위로 영문 별칭을 쓰는 편이 안전하다. 본 예제는 fallback 동작 자체를 보이기 위해 그대로 진행한다.
- **과거 계획**:
  - v2.1.0: `[Task 3] 이메일 로그인 구현` (상태: 완료)
  - v2.1.0: `[Task 7] 비밀번호 재설정 플로우` (상태: 계획 — 이월 후보)
- `max_task_number_in_target_version` (v2.2.0): 0 (기존 레코드 없음)

## Step 4 분해

3개 작업으로 분해.

| # | 버전 | 구분 | 작업명 | 선행 관계 | 병렬 진행 가능 |
| - | --- | --- | --- | --- | --- |
| 1 | 2.2.0 | feature | [Task 1] Refresh Token API 핸들러 구현 | - | [Task 2] |
| 2 | 2.2.0 | feature | [Task 2] SecureStore에 refreshToken 저장/복원 로직 | - | [Task 1] |
| 3 | 2.2.0 | feature | [Task 3] 로그인 유지 플로우 통합 (앱 시작 시 자동 갱신) | [Task 1], [Task 2] | - |

### self-critic (4-7)

1. 독립 검증 가능? YES — 각 Task는 별도 수용 기준으로 완료 판정 가능.
2. [Task N] 연속성? YES — 1..3 연속.
3. 라벨 참조 정합성? YES — 선행/병렬에 등장하는 [Task 1], [Task 2], [Task 3] 모두 본 배치에 존재.

## Step 5 미리보기 출력

```
## 릴리즈 작업 미리보기 (v2.2.0)

| # | 버전 | 구분 | 작업명 | 선행 관계 | 병렬 진행 가능 | 작업 상세 (요약) |
|---|------|------|--------|-----------|----------------|------------------|
| 1 | 2.2.0 | feature | [Task 1] Refresh Token API 핸들러 구현 | - | [Task 2] | POST /auth/refresh — accessToken 갱신, 재발급 |
| 2 | 2.2.0 | feature | [Task 2] SecureStore refreshToken 저장/복원 | - | [Task 1] | 앱 시작 시 복원, 로그아웃 시 삭제 |
| 3 | 2.2.0 | feature | [Task 3] 로그인 유지 플로우 통합 | [Task 1], [Task 2] | - | 앱 시작 → 토큰 확인 → 필요 시 refresh → 실패 시 로그인 화면 |

> 총 3개 작업 | 등록일: 2026-04-15
> 대상 페이지: Stage Sudoku
> 대상 데이터베이스: 릴리즈 플랜

## SemVer 점검

(해당 경고 없음 — feature + minor 증가로 관행 일치)

## 추가 제안 (과거 계획 분석 기반)

- [연관] v2.1.0 [Task 3] "이메일 로그인 구현" → 본 [Task 1] Refresh Token API의 **선행 관계로 연결 권장**
- [이월] v2.1.0 [Task 7] "비밀번호 재설정 플로우"가 `계획` 상태 → 본 버전 포함 여부 확인 필요
- [후속] 과거 "이메일 로그인"의 논리적 후속인 "로그아웃(토큰 폐기)" 작업 누락 → 추가 등록 여부 확인 필요

위 미리보기 + 추가 제안을 어떻게 반영할까요? (전부 포함 / 일부 선택 / 무시)
```

## Step 6 등록 (사용자가 "전부 포함" 승인)

1. 6-1 중복 검사: 기존 DB의 v2.2.0 레코드 없음, 중복 0건 → 진행.
2. 6-2: Notion 에 3개 레코드 생성(위임).
3. "이월 [Task 7]"은 v2.1.0 DB에 그대로 남기고, 연관 선행 관계만 [Task 1]에 반영한다. 이월은 **별도 버전을 건드리지 않는다**.

## Step 7 관리 문서

경로: `docs/skills/release-plan/untitled/v2.2.0/`

### release-plan.md (발췌)

```markdown
# Release Plan — v2.2.0

> 등록일: 2026-04-15
> 대상 Notion 페이지: Stage Sudoku
> 대상 데이터베이스: 릴리즈 플랜
> 입력 버전: 2.2.0
> 기존 DB 최대 버전: 2.1.0

## 업데이트 요약
이메일 로그인 이후에 로그인 유지(토큰 갱신) 기능 추가.

## 과거 계획 연계
- 연관 작업 반영: v2.1.0 [Task 3] 이메일 로그인 → v2.2.0 [Task 1] 선행 관계 연결
- 이월 작업 반영: 없음 (사용자가 이번 배치에 포함하지 않기로 결정)
- 후속 작업 추가: 없음 (로그아웃은 다음 버전에서 다루기로 결정)
```

### task_list.json (발췌)

```json
{
  "version": "v2.2.0",
  "created_at": "2026-04-15",
  "notion_page": "Stage Sudoku",
  "notion_database": "릴리즈 플랜",
  "input_version": "2.2.0",
  "base_version": "2.1.0",
  "summary": {"total": 3, "pass": 0, "fail": 3, "blocked": 0},
  "tasks": [
    {
      "id": "TASK-001",
      "task_number": 1,
      "name": "[Task 1] Refresh Token API 핸들러 구현",
      "version": "2.2.0",
      "category": "feature",
      "status": "fail",
      "acceptance_criteria": [
        "POST /auth/refresh 요청에 유효한 refreshToken을 보내면 200 OK와 새 accessToken을 반환한다.",
        "만료·변조된 refreshToken에는 401을 반환한다.",
        "재발급 시 refreshToken도 회전(rotate)되어 이전 값은 무효화된다."
      ],
      "implementation_details": [
        "Expo Router API route 또는 서버 엔드포인트",
        "JWT 서명 재사용, exp 검증"
      ],
      "depends_on_labels": [],
      "parallel_with_labels": ["[Task 2]"],
      "retry_count": 0,
      "completed_at": null
    }
    /* [Task 2], [Task 3] 생략 */
  ]
}
```

### validate_task_list.py 실행

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/validate_task_list.py docs/skills/release-plan/untitled/v2.2.0/task_list.json
# -> OK
```

## Step 8 보고 (발췌)

```
## 릴리즈 작업 등록 완료

- 등록 작업 수: 3개
- 대상 페이지: Stage Sudoku
- 대상 데이터베이스: 릴리즈 플랜
- 버전: v2.2.0
- Task 번호 범위: [Task 1] ~ [Task 3]
- 등록일: 2026-04-15
- 관리 문서: docs/skills/release-plan/untitled/v2.2.0/
```

## 이 예제에서 얻을 교훈

1. **slug fallback**: 한글 전용 DB 이름은 `untitled`가 된다. 경로 충돌이 우려되면 영문 별칭을 DB 이름에 포함시키는 게 안전하다.
2. **이월 제안 ≠ 자동 이동**: 이월 작업은 과거 버전에 그대로 두고, 연결만 선행 관계로 표현한다.
3. **acceptance_criteria가 구체적이어야** release-impl이 수용 기준을 기계적으로 평가할 수 있다.
4. **validator 통과 없이는 Step 8 보고로 넘어가지 않는다** — 이 게이트가 조기 완료 선언을 차단한다.
