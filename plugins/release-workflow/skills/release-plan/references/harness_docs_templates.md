# Harness 관리 문서 템플릿

Step 7에서 `docs/skills/release-plan/{DB slug}/v{버전}/` 하위에 생성하는 3개 문서의 템플릿이다. `{DB slug}`는 `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/slugify.py` 출력을 사용한다.

폴더가 이미 존재하면 기존 문서를 덮어쓰지 않고 파일명에 날짜를 붙여 생성한다 (예: `release-plan_2026-04-15.md`).

## release-plan.md

```markdown
# Release Plan — v{버전}

> 등록일: {YYYY-MM-DD}
> 대상 Notion 페이지: {페이지 이름}
> 대상 데이터베이스: {DB 이름}
> 입력 버전: {입력 버전}
> 기존 DB 최대 버전: {Step 3 확인 값 또는 '없음'}

## 업데이트 요약

{사용자가 입력한 원본 업데이트 내용}

## 작업 분해

| # | 버전 | 구분 | 작업명 | 선행 관계 | 병렬 진행 가능 | 작업 상세 (요약) |
| - | ---- | ---- | ------ | --------- | -------------- | ---------------- |
| 1 | ...  | ...  | ...    | ...       | ...            | ...              |

## 과거 계획 연계

- 연관 작업 반영 내역: {사용자가 승인한 항목}
- 이월 작업 반영 내역: {사용자가 승인한 항목}
- 후속 작업 추가 내역: {사용자가 승인한 항목}

## 구현 순서

1. 기반 작업 (인프라, 설정, 타입 정의)
2. 핵심 로직 구현
3. UI/UX 구현
4. 테스트/문서화
```

## task_list.json

구조와 검증 규칙은 [`task_list_contract.md`](./task_list_contract.md)를 참조한다.

## progress.md

```markdown
# Progress — v{버전}

> Last Updated: {YYYY-MM-DD HH:mm}
> Total Tasks: N | Pass: 0 | Fail: N | Blocked: 0

## 현재 상태

- 단계: 계획 등록 완료, 구현 대기
- 다음 작업: [Task 1] ({첫 번째 작업명})
- 차단 사항: 없음

## 세션 로그

- [{YYYY-MM-DD}] 릴리즈 계획 등록: {N}개 작업 Notion + 로컬 문서 생성 (DB: {DB 이름}, v{버전})

## 다음 단계

1. [Task 1]부터 선행 관계 순서대로 구현
2. 병렬 진행 가능 항목은 동시 진행 가능
3. 각 작업 완료 후 Evaluator 검증 → task_list.json 상태 업데이트
```
