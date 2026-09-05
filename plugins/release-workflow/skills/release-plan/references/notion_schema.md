# Notion Database Schema Reference

이 문서는 release-plan 스킬이 사용하는 Notion 데이터베이스의 구조를 정의한다. SKILL.md Step 2에서 DB 존재 여부를 확인하고 없으면 이 스키마로 생성한다.

## 컬럼 정의

| 컬럼             | 타입         | 설명                                                                                                  |
| ---------------- | ------------ | ----------------------------------------------------------------------------------------------------- |
| 작업             | TITLE        | `[Task N] {작업명}` 형식. N은 버전별 독립 번호                                                        |
| 완료             | SELECT       | `계획`(gray), `진행`(blue), `완료`(green), `보류`(red). 기본값 `계획`                                 |
| 버전             | SELECT       | `X.Y.Z` 형식. GROUP BY 지원을 위해 SELECT 사용. 새 버전 등록 시 옵션 자동 추가                        |
| 구분             | MULTI_SELECT | `feature`, `system`, `hotfix`, `performance`, `docs`, `refactor`, `infra` 중 선택 (복수 선택 가능)     |
| 작업 상세        | RICH_TEXT    | 구현 내용 + 수용 기준(acceptance criteria)                                                            |
| 선행 관계        | RICH_TEXT    | 이 작업 시작 전 완료되어야 하는 선행 Task의 말머리 나열 (예: `[Task 1], [Task 3]`). 없으면 `-`        |
| 병렬 진행 가능   | RICH_TEXT    | 이 작업과 동시에 진행 가능한 Task의 말머리 나열 (예: `[Task 2], [Task 4]`). 없으면 `-`                |
| 등록일           | DATE         | 레코드 생성일                                                                                         |
| 완료일           | DATE         | 완료 시 기록. 생성 시 비워둠                                                                          |

## SQL DDL

```sql
CREATE TABLE (
  "작업" TITLE,
  "완료" SELECT('계획':gray, '진행':blue, '완료':green, '보류':red),
  "버전" SELECT('2.1.0':blue, '2.2.0':green),
  "구분" MULTI_SELECT('feature':blue, 'system':gray, 'hotfix':red, 'performance':green, 'docs':default, 'refactor':purple, 'infra':brown),
  "작업 상세" RICH_TEXT,
  "선행 관계" RICH_TEXT,
  "병렬 진행 가능" RICH_TEXT,
  "등록일" DATE,
  "완료일" DATE
)
```

## 설계 판단: RICH_TEXT vs RELATION

선행 관계·병렬 진행 가능을 RELATION이 아닌 RICH_TEXT로 둔 이유는 두 가지다.

1. 여러 레코드를 한 배치로 만드는 시점에는 각 레코드의 ID가 아직 존재하지 않아 self-relation을 거는 것이 어렵다.
2. `[Task N]` 말머리 자체가 읽을 때 충분한 식별력을 제공한다 — 사람도, 후속 스킬(release-impl)도 번호만으로 Task를 지목할 수 있다.

## RICH_TEXT 포맷 계약

선행 관계와 병렬 진행 가능 컬럼은 아래 정규식 중 하나를 만족해야 한다.

```
^-$
^\[Task \d+\](, \[Task \d+\])*$
```

즉, 빈 값은 `-`로 표기하고, 여러 Task를 나열할 때는 `, ` 구분자를 사용한다(공백 1칸 포함). 이 포맷은 `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/validate_task_list.py`가 `depends_on_labels` / `parallel_with_labels` 배열과 함께 검증한다.

## 뷰 설정

DB 생성 직후 두 개의 뷰를 만든다.

| 뷰 이름   | 타입  | 설정                                     | 용도                         |
| --------- | ----- | ---------------------------------------- | ---------------------------- |
| 버전별    | table | `GROUP BY "버전"; SORT BY "등록일" DESC` | 버전별 작업 그룹핑 (기본 뷰) |
| 진행 현황 | board | `GROUP BY "완료"`                        | 칸반 스타일 진행 추적        |

## REST 스키마 (`notion_db_schema.json`)

Notion REST API 로 DB 를 생성할 때는 위 SQL DDL 대신 `references/notion_db_schema.json` 의
`properties` 객체를 쓴다. **컬럼 이름·옵션은 이 문서가 정본이다** — REST 스키마 파일이 이
표와 어긋나면 이 표를 기준으로 REST 스키마 파일을 고친다.
