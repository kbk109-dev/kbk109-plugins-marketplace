# Notion 연동 — 토큰 기반 REST API 전용

이 프로젝트는 Notion 을 MCP 도구가 아니라 `.claude/scripts/notion_api.py` 로만 다룬다.
`.claude/hooks/notion_mcp_gate.py` 가 Notion MCP 도구 호출(`mcp__*notion*` 형태 전부)을
막으므로, 아래 표를 따르지 않으면 그 호출은 실패한다.

## 1. 왜 MCP 를 쓰지 않는가

MCP 서버 접두사는 환경마다 다르다(`mcp__claude_ai_Notion__`, `mcp__plugin_Notion_notion__`,
`mcp__notionApi__`, …). 같은 스킬이 사람마다 다른 도구를 부르고, 응답 스키마도 서버 구현에
좌우된다. `notion_api.py` 는 결정적이다 — 같은 입력에 같은 출력, 같은 종료 코드. 스킬은
종료 코드로만 성공·실패를 판단해야 한다(산문 해석 금지).

## 2. 서브커맨드 — 구 MCP 도구 대응표

| 하려는 일 | 명령 |
|---|---|
| 토큰 설정 확인 | `notion_api.py doctor` (`--dry-run` 은 네트워크 없이 토큰 출처만 확인) |
| 제목으로 검색 | `notion_api.py search --query "<검색어>"` |
| 페이지 + 하위 DB 한 번에 찾기 | `notion_api.py resolve --page "<이름 또는 ID>" [--database "<이름>"]` |
| 페이지 속성 조회 | `notion_api.py page-get <page_id>` |
| 페이지 본문 → 마크다운 | `notion_api.py page-markdown <page_id> [--max-depth N]` |
| 새 페이지(레코드) 생성 | `notion_api.py page-create --parent-page-id\|--parent-data-source-id <id> [--title …] [--set 키=타입:값]… [--markdown-file …]` |
| 페이지(레코드) 속성 갱신 | `notion_api.py page-update <page_id> [--set 키=타입:값]…` |
| 페이지 본문에 내용 추가 | `notion_api.py blocks-append <block_id> --markdown-file <path>` |
| 데이터베이스 메타 조회 | `notion_api.py db-get <database_id>` |
| 데이터베이스 생성 | `notion_api.py db-create --parent-page-id <id> --title "…" --schema-file <path>` |
| 데이터소스(필터 대상) 조회 | `notion_api.py ds-get <data_source_id>` |
| 조건으로 레코드 조회 | `notion_api.py ds-query <data_source_id> --filter-json '{...}' [--all]` |
| 뷰(표/보드 등) 생성 | `notion_api.py view-create --database-id … --data-source-id … --name "…" --type table\|board\|…` |
| 마크다운 → 블록 변환만(검증용, 네트워크 없음) | `notion_api.py md2blocks --markdown-file <path>` |

`--set` 은 `키=타입:값` 형식이며 반복 가능하다. 지원 타입:
`title rich_text select multi_select status checkbox date number url`.
예: `--set '완료=select:완료' --set '버전=select:2.2.0'`.

**`notion_api.py` 에 데이터소스 스키마를 바꾸는 서브커맨드는 없다.** 스키마 변경이
필요하면 Notion UI 에서 직접 하거나 `db-create` 로 새 데이터베이스를 만든다 — 도구
부재가 곧 "스키마는 함부로 안 건드린다"는 정책이다.

## 3. 실패 시 대처

종료 코드로 원인을 구분한다(`stderr` 에 `{"error": {...}}` JSON 도 함께 나온다).

| 종료 코드 | 원인 | 조치 |
|---|---|---|
| 3 | 토큰 없음 또는 401/403 | `doctor` 로 토큰 출처 확인. 403 이면 해당 페이지에 integration 이 공유돼 있는지 확인(Notion 페이지 ⋯ → 연결 → integration 추가) |
| 4 | 400 validation_error | 대개 속성 이름·타입 불일치. `ds-get <id>` 로 실제 스키마를 먼저 확인 |
| 5 | 404 또는 `resolve` 실패 | ID 오타이거나 공유되지 않아 안 보이는 경우(Notion 은 둘을 구분해 주지 않는다) |
| 6 | 429/5xx/네트워크 | 스크립트가 이미 재시도했다(쓰기 요청의 5xx 는 중복 방지를 위해 재시도하지 않는다). 잠시 후 다시 실행 |

방금 만든 페이지·데이터소스가 `search` 에 안 보일 수 있다 — Notion 검색은 즉시 반영을
보장하지 않는다(eventually consistent).

## 4. 이 규칙을 끄려면

이 프로젝트에서만 일시적으로 MCP 를 허용하려면 `NOTION_MCP_GATE=off` 환경변수로 실행한다.
