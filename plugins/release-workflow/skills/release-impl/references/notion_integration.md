# Notion 통합 규약

release-impl이 Notion에 기대하는 것의 **공식 참조 문서**다. 어떤 도구로 Notion 을 호출할지는
이 스킬의 관심사가 아니다 — 그건 프로젝트가 `.claude/rules/notion-api-only.md` (있다면) 로
정한다. 이 문서가 고정하는 것은 **어떤 조회 조건과 어떤 속성 이름·타입을 기대하는가**다.
release-plan의 `references/notion_schema.md` 가 이 스키마의 정본이며, 여기 적힌 속성
이름·타입은 그 문서와 항상 일치해야 한다(어긋나면 `notion_schema.md` 를 우선한다).

---

## Phase 1 Step 4 — Notion 데이터 조회

SKILL.md Step 4의 추상적 흐름이 실제로 필요로 하는 조회 3가지다.

### 4-1. 페이지 찾기

입력받은 페이지 이름으로 정확히 일치하는 페이지를 찾는다. 중복이 있으면 최상위 결과 확인 후
사용자 확인.

### 4-2. child database 식별

페이지 하위에서 `title == "{입력 DB 이름}"` 인 데이터베이스를 찾는다. 완전 일치 실패 시
대소문자 무시 부분 일치 1회 시도, 사용자에게 매칭 DB 이름을 확인받는다. 찾지 못하면
`"{database_name}" 데이터베이스가 없습니다` 메시지 후 종료 (SKILL.md 규정).

### 4-3. 버전별 row 필터

**property 이름은 `"버전"`, 타입은 `select`, 값은 `X.Y.Z` 형식**(release-plan
`notion_schema.md` 계약 — `v` 접두 없음). release-impl 내부에서 쓰는 `{version}`(예:
`v2.2.0`)은 경로용 표기이므로, Notion 조회에는 **`v` 를 뗀 값**(`2.2.0`)을 쓴다.

응답의 각 row에서 다음을 추출:
- row id — 역방향 업데이트에 필요
- `작업` 속성(title) — feature_list.json의 `tasks[].title`
- `작업 상세` 속성(rich_text)에서 [수용 기준] 절 — `acceptance_criteria` 배열

여기서 조립한 데이터는 `contract_consumer.md`의 매핑표를 따라 `feature_list.json`으로 변환한다.

---

## Phase 2 Step C — 역방향 상태 동기화 (pass 확정 후)

Evaluator가 `verdict=pass`를 반환하면 호출 측은 Notion 쪽 task row의 상태를 `완료`로
전이한다. 이 갱신이 빠지면 Notion DB 뷰가 영영 "계획 중"으로 남아 이전 버전 오리엔테이션
(Phase 1 Step 2)이 오도된다.

**property 이름은 `"완료"`**(release-plan `notion_schema.md` 계약 — `"상태"` 가 아니다),
값은 `select` 타입 `완료`. blocked 전이 시에는 값 `보류`(release-plan 계약의 옵션 이름 —
`"차단"` 이 아니다)로 같은 업데이트를 시도한다.

### 상태 속성 매핑

release-plan이 만든 DB 는 항상 `select` 타입이지만(§ 위), 사용자가 스키마를 직접 고친
프로젝트를 대비해 대안 타입도 남긴다 — 실제 DB 의 속성 타입을 `ds-get` 등으로 먼저 확인한다.

| DB 속성 타입 | 완료 전이 값 | 보류 전이 값 |
|---------------|---------------|---------------|
| `select` (기본, 옵션: 계획/진행/완료/보류) | `완료` | `보류` |
| `status` | `Done` | `On Hold` |
| `checkbox` | `true` | (checkbox 는 보류 표현 불가 — secondary 로 스킵) |

임의 번역 금지 — DB 옵션 값 그대로를 써야 한다.

### 실패 처리 (secondary output)

Notion 갱신 실패는 **core execution을 차단하지 않는다**. `references/degradation_policy.md`의
"Notion 쓰기 실패" 조항을 따른다:
- 경고 메시지 stdout 출력
- `PROGRESS.md`의 "발견된 이슈" 섹션에 한 줄 기록
- 로컬 `feature_list.json`의 `status="pass"`는 유지
- 호출 측은 다음 task로 진행

blocked 전이 시에도 동일하게 상태 `보류`로 업데이트를 시도하고, 실패 시 secondary output으로
처리한다.

---

## Phase 3 완료 보고 — 전체 버전 동기화

모든 task가 pass 상태가 되면, Phase 3 완료 보고 단계에서 **Notion DB 전체 상태를 최종
확인**한다 — 4-3 과 동일한 필터(`버전` select, `v` 없는 값)로 대상 버전의 모든 row 를 다시
조회한다.

응답의 모든 row가 `완료=완료`인지 확인. 불일치 row가 있으면 경고 출력 + 사용자에게 수동
확인 요청. 자동 재시도하지 않는다 (secondary output).

---

## release-plan과의 계약

release-plan이 생성·관리하는 Notion 스키마는 **단일 출처**다. release-impl은:
- 스키마를 변경하지 않는다 — 위임 대상(`notion_api.py`)에 스키마 변경 서브커맨드가 없는 것도
  이 정책을 강제하기 위한 설계다
- 속성 값만 업데이트한다
- 새 row를 생성하지 않는다
- row를 삭제하지 않는다

스키마·속성명·옵션값에 불확실이 있으면 release-plan의 `references/notion_schema.md`를 우선
참조하고, 거기에도 없으면 CLAUDE.md나 사용자에게 질의한다. 임의 추론 금지.
