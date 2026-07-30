# Notion MCP 통합 규약

release-impl이 Notion과 주고받는 모든 상호작용의 **공식 참조 문서**. 도구 풀네임, 필터 형식, 역방향 업데이트 경로를 한 곳에 고정하여 세션마다 모델이 축약 이름이나 임의 필터 구조를 재발명하지 않도록 한다.

---

## MCP 도구 풀네임

| SKILL.md에서 사용하는 약칭 | 실제 MCP 도구 풀네임 | 용도 |
|-----------------------------|----------------------|------|
| `notion-search` | `mcp__plugin_Notion_notion__notion-search` | 페이지 이름/키워드 검색 |
| `notion-fetch` | `mcp__plugin_Notion_notion__notion-fetch` | 페이지·데이터베이스·data source 조회 |
| `notion-update-page` | `mcp__plugin_Notion_notion__notion-update-page` | **역방향 상태 업데이트 (Phase 2 Step C)** |
| `notion-update-data-source` | `mcp__plugin_Notion_notion__notion-update-data-source` | DB 스키마 변경 (release-impl은 호출하지 않음; release-plan 전용) |

도구 존재 확인: 세션에 노출된 함수 목록에 `mcp__plugin_Notion_notion__` 접두사가 있으면 연결된 상태. 없으면 `degradation_policy.md`의 Phase 1 Step 0 경로로 진행 (MCP 미설치 감지).

---

## Phase 1 Step 4 — Notion 데이터 조회 (하위 4단계)

SKILL.md Step 4의 추상적 흐름을 실제 MCP 호출 순서로 구체화한다.

### 4-1. 페이지 검색

```
mcp__plugin_Notion_notion__notion-search(query="{입력 페이지 이름}")
```

응답에서 정확히 일치하는 타이틀의 `page.id`를 선택한다. 중복이 있으면 최상위 결과 확인 후 사용자 확인.

### 4-2. child_database 식별

```
mcp__plugin_Notion_notion__notion-fetch(url_or_id="{page.id}")
```

응답의 `children` 배열에서 `type=="child_database"` + `title == "{입력 DB 이름}"` 블록을 찾는다. 완전 일치 실패 시 대소문자 무시 부분 일치 1회 시도, 사용자에게 매칭 DB 이름을 확인받는다. 찾지 못하면 `"{database_name}" 데이터베이스가 없습니다` 메시지 후 종료 (SKILL.md 규정).

### 4-3. data_source_id 추출

```
mcp__plugin_Notion_notion__notion-fetch(url_or_id="{database.id}")
```

응답에서 `data_sources[0].id` 또는 `data_source_id`를 추출 (Notion API 버전에 따라 둘 중 하나). 이 값이 이후 쿼리의 스코프를 지정한다.

### 4-4. 버전별 row 필터

```
mcp__plugin_Notion_notion__notion-fetch(
  url_or_id="{data_source_id}",
  filter={"property": "버전", "rich_text": {"equals": "v{version}"}}
)
```

property 이름(`"버전"`)과 타입(`rich_text`)은 release-plan의 `references/notion_schema.md` 계약을 따른다. 타입이 `select`이면 `{"property":"버전","select":{"equals":"v{version}"}}`로 변경. CLAUDE.md나 실제 DB 스키마에서 확인한 타입을 사용한다.

응답의 각 row에서 다음을 추출:
- `id` — 역방향 업데이트에 필요한 page id
- `properties.작업.title` (또는 해당 title 속성) — feature_list.json의 `tasks[].title`
- `properties.수용 기준` 또는 동등한 속성의 rich_text — `acceptance_criteria` 배열

여기서 조립한 데이터는 `contract_consumer.md`의 매핑표를 따라 `feature_list.json`으로 변환한다.

---

## Phase 2 Step C — 역방향 상태 동기화 (pass 확정 후)

Evaluator가 `verdict=pass`를 반환하면 호출 측은 Notion 쪽 task row의 상태를 `완료`로 전이한다. 이 호출이 빠지면 Notion DB 뷰가 영영 "계획 중"으로 남아 이전 버전 오리엔테이션(Phase 1 Step 2)이 오도된다.

```
mcp__plugin_Notion_notion__notion-update-page(
  page_id="{row.id}",
  properties={
    "상태": {"select": {"name": "완료"}}
  }
)
```

### 상태 속성 매핑

| DB 속성 타입 | 전이 payload |
|---------------|---------------|
| `select` (옵션: 계획/진행/완료/차단) | `{"select": {"name": "완료"}}` |
| `status`       | `{"status": {"name": "Done"}}` |
| `checkbox`     | `{"checkbox": true}` |

release-plan의 `notion_schema.md`에 정의된 속성 타입을 그대로 사용한다. 일관성을 위해 대체 이름(`Done`, `완료`)은 DB 옵션 값 그대로를 써야 한다 — 임의 번역 금지.

### 실패 처리 (secondary output)

`notion-update-page` 호출 실패는 **core execution을 차단하지 않는다**. `references/degradation_policy.md`의 "Notion 쓰기 실패" 조항을 따른다:
- 경고 메시지 stdout 출력
- `PROGRESS.md`의 "발견된 이슈" 섹션에 한 줄 기록
- 로컬 `feature_list.json`의 `status="pass"`는 유지
- 호출 측은 다음 task로 진행

blocked 전이 시에도 동일하게 상태 `차단`으로 업데이트를 시도하고, 실패 시 secondary output으로 처리한다.

---

## Phase 3 완료 보고 — 전체 버전 동기화

모든 task가 pass 상태가 되면, Phase 3 완료 보고 단계에서 **Notion DB 전체 상태를 최종 확인**한다:

```
mcp__plugin_Notion_notion__notion-fetch(
  url_or_id="{data_source_id}",
  filter={"property": "버전", "rich_text": {"equals": "v{version}"}}
)
```

응답의 모든 row가 `상태=완료`인지 확인. 불일치 row가 있으면 경고 출력 + 사용자에게 수동 확인 요청. 자동 재시도하지 않는다 (secondary output).

---

## release-plan과의 계약

release-plan이 생성·관리하는 Notion 스키마는 **단일 출처**다. release-impl은:
- 스키마를 변경하지 않는다 (`notion-update-data-source` 호출 금지)
- 속성 값만 업데이트한다 (`notion-update-page`)
- 새 row를 생성하지 않는다
- row를 삭제하지 않는다

스키마·속성명·옵션값에 불확실이 있으면 release-plan의 `references/notion_schema.md`를 우선 참조하고, 거기에도 없으면 CLAUDE.md나 사용자에게 질의한다. 임의 추론 금지.
