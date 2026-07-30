# Generator 보조 가이드

이 문서는 `agents/generator.md` 시스템 프롬프트의 **보조 자료**다. agents 파일은 호출 계약·게이트·실패 형식만 두고, 절차 상세는 여기에 둔다. Generator는 필요할 때만 Read한다 (점진적 정보 공개).

## 절차 상세

### 1. 스프린트 계약 작성 (구현 **전**)

`sprint_contracts/{task_id}.md`를 다음 형식으로 생성:

```markdown
# Sprint Contract — {task_id}

## 예상 수정 파일
- src/…/foo.ts (함수 bar 추가)
- src/…/__tests__/foo.test.ts (신규)

## 예상 검증 커맨드
- npx tsc --noEmit
- npm test -- --runTestsByPath src/__tests__/foo.test.ts

## 예상 실패 가능점
- foo.ts의 bar가 null 입력을 어떻게 다룰지 명세 모호 — Evaluator가 이 케이스를 지적하면 재구현 필요
```

계약은 **expectation-first**다. 구현 전에 "완료의 모양"을 고정해야 Evaluator가 일관된 기준으로 판정할 수 있다. 계약 파일이 없으면 Evaluator는 자동 fail.

### 2. 컨텍스트 재주입 (5초 이내)

- `state_digest`로 현재 상태(요약·summary·current_task_id·loop counters)를 즉시 파악
- `feature_list.json`의 해당 task 블록 전체 Read (acceptance_criteria, dependencies, 기존 evidence_logs)
- `previous_context` 전체를 다시 읽고, 같은 파일·모듈·기능 영역 영향 항목 요약
- PROGRESS.md "이전 버전 컨텍스트" + "발견된 이슈" 재확인
- 관련 항목이 없으면 즉시 통과. 생략 금지.

### 3. 기존 코드 탐색

구현 **전** 관련 파일을 Read/Grep으로 탐색. 중복 생성·덮어쓰기 방지:

- task의 `acceptance_criteria`에 등장하는 파일 경로가 이미 있는가 → Read
- 동일 기능이 다른 이름으로 이미 구현돼 있지 않은가 → Grep
- `architecture_decision` previous_context가 지정한 디렉토리/패턴이 있는가 → 그대로 따른다
- `implementation_root`가 비어 있지 않으면 그 하위 경로로 탐색 범위 한정

### 4. 증분적 구현

- 전체 리라이트 금지. 기존 코드에 누락된 부분만 추가·수정.
- 언어별 컨벤션은 CLAUDE.md와 기존 코드 패턴에 전적으로 의존. 스킬은 기본값을 강요하지 않는다.
- 서드파티 라이브러리 API 사용 시 Context7 MCP가 연결돼 있으면 반드시 `mcp__plugin_context7_context7__resolve-library-id` → `mcp__plugin_context7_context7__query-docs` 순서로 최신 문서 조회.
- 파일 수정 직후마다 편집 카운터 호출. exit 1이면 즉시 `"status": "blocked-loop"` 복귀.

### 5. 스텁 검사 (Evaluator 인계 전)

`${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/scan_stubs.py`를 Generator가 먼저 실행. 스텁이 남아 있으면 Evaluator가 반드시 fail 처리하므로 여기서 걸러서 왕복을 줄인다.

### 6. Evaluator 인계

`feature_list.json`의 해당 task는 건드리지 않는다 — status 전이는 Evaluator 권한. 출력 JSON을 마지막 메시지로 반환.

---


## 증분적 구현 원칙

기존 코드를 **전체 리라이트하지 않는다**. 대신:

1. **기존 코드 탐색**: Grep/Read로 관련 파일 현재 상태 확인
2. **변경 범위 최소화**: 필요한 부분만 추가/수정
3. **기존 패턴 따르기**: 프로젝트의 기존 스타일·디렉토리·네이밍 규칙을 그대로 따른다
4. **임포트/모듈 경로**: CLAUDE.md에 명시된 패턴 우선. 언어별 예시 — JS/TS path alias `@/`, Python `from src.module import …`, Go 패키지 경로, Rust `crate::module::…`. CLAUDE.md에 없으면 기존 코드 패턴 추종

## Context7 MCP 활용 (서드파티 API)

1. `mcp__plugin_context7_context7__resolve-library-id` 로 라이브러리 ID 해석
2. `mcp__plugin_context7_context7__query-docs` 로 최신 API 조회
3. 훈련 데이터와 충돌하면 Context7을 우선
4. Context7 미연결 시: 웹검색 시도 → 그래도 불확실하면 "Context7 미연결 — 라이브러리 스펙 확정 URL을 알려주세요"로 사용자 질의

## Reasoning Sandwich

추론 예산 배분:

- **계획 단계 (최대 추론)**: 스프린트 계약 작성 시. 어떤 파일을 어떻게 수정할지, 어떤 실패가 예상되는지 상세 기록
- **구현 단계 (중간 추론)**: 계약에 따라 코드 작성
- **Evaluator 인계 전 검증 (추가 추론)**: scan_stubs 실행 + 스스로 criteria 대비 셀프체크. 자기평가는 금지이지만, 명백한 오류를 미리 걸러서 Evaluator 왕복을 줄이는 정도의 점검은 허용

## 코딩 컨벤션 체크리스트

모든 기준의 원천은 **CLAUDE.md** 또는 **기존 코드 패턴**이다. 스킬은 언어별 기본값을 강요하지 않는다:

- [ ] **네이밍**: CLAUDE.md 규정 (예: Python `snake_case` + `PascalCase` / Go `mixedCaps` + 노출 규칙 / JS·TS `camelCase` + `PascalCase` / Rust `snake_case` + `PascalCase`)
- [ ] **임포트 경로**: CLAUDE.md 또는 기존 코드 패턴
- [ ] **타입 안전성**: 프로젝트 타입 검사 도구가 오류 없음
- [ ] **상태·데이터 관리**: 해당되는 경우 CLAUDE.md 패턴 따름
- [ ] **에러 핸들링**: CLAUDE.md 또는 기존 코드 관례 (예외 vs Result 타입 vs error 반환값)
- [ ] **테스트 위치·네이밍**: 기존 `__tests__/` 혹은 `_test.go` 등 프로젝트 관행

## 세션 종료 절차 (Evaluator pass 후 호출 측이 수행)

1. **Git 커밋**:
   - pass: `feat(release/v{version}): {title}`
   - blocked: `wip(release/v{version}): {title} — blocked`
   - 프로젝트 CLAUDE.md에 다른 컨벤션이 있으면 그것 우선
2. **feature_list.json**: Evaluator가 이미 업데이트함 — 호출 측은 재검증만
3. **PROGRESS.md**: `sync_progress.py`로 헤더 재생성 후 세션 로그 한 줄 추가
4. **깨끗한 상태**: 미완성 코드/디버그 로그/임시 파일이 남지 않았는지 확인

세션이 중단되더라도 다음 세션이 PROGRESS.md + git log + feature_list.json + `.loop_state.json`으로 상태를 완전 복원할 수 있어야 한다.
