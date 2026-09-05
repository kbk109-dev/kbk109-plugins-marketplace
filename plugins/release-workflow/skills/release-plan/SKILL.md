---
name: release-plan
description: "Use when a user wants to plan, register, or break down a release into tasks on a Notion database — takes a Notion page name, database name, target semantic version (X.Y.Z), and update description, then produces version-scoped task records with [Task N] labels, dependencies, and parallel-work metadata, and verifies every technology token (model IDs, library names, package versions) appearing in task details against Context7 MCP and WebSearch via a separate fact-checker subagent — blocks Notion registration on any unverified token through the verify_tech_tokens.py gate. Triggers on Korean and English phrases including: '릴리즈 계획', '릴리즈 플랜', '업데이트 계획 등록', '버전 계획', '릴리즈 작업 등록', 'release-plan', '릴리즈 작업 분해', '버전 계획 세워줘', '릴리즈 계획 등록해줘', '업데이트 항목 정리해줘', 'Notion에 릴리즈 등록', '릴리즈 DB에 작업 추가', '다음 버전 계획', '작업 분해해서 노션에 등록', 'release plan', 'plan release tasks', 'register release items', 'break down update into tasks'."
compatibility: 'mcp: context7'
---

# Release Plan — Harness Engineering 기반 릴리즈 작업 등록

입력받은 업데이트 내용을 Harness Engineering 방법론으로 분석·분해하여, Notion 페이지 하위의 지정된 데이터베이스(예: "Release Plan")에 구조화된 작업 항목으로 등록한다. 대상 DB 이름과 대상 버전은 스킬 실행 시 입력받는다.

---

## 입력값 확인 (게이트)

이 스킬은 네 가지 필수 입력이 있다. 하나라도 없거나 형식이 맞지 않으면 즉시 종료한다. 가드는 LLM의 "일회성 탐욕적 완료" 성향을 막기 위함이다 — 누락 입력을 추측으로 메우지 않는다.

### 1. 노션 페이지 이름 (필수)

- **미입력 시**: `"릴리즈 계획을 등록할 노션 페이지 이름을 알려주세요."` 출력 후 **즉시 종료**.

### 2. 데이터베이스 이름 (필수)

- 페이지 하위에서 사용할 대상 데이터베이스의 이름. 예: `Release Plan`, `v2.1 Tasks`, `릴리즈 플랜`.
- **미입력 시**: `"릴리즈 계획을 등록할 데이터베이스 이름을 알려주세요."` 출력 후 **즉시 종료**.

### 3. 대상 버전 (필수)

- `X.Y.Z` 형식의 시맨틱 버전. 예: `1.0.0`, `2.1.0`.
- 정규식 `^\d+\.\d+\.\d+$`로 검증.
- **미입력 또는 형식 위반 시**: `"등록할 버전을 X.Y.Z 형식으로 알려주세요. (예: 1.0.0)"` 출력 후 **즉시 종료**.
- 입력된 버전은 이 배치의 모든 작업이 공유한다. 단, 성격이 명확히 다른 작업(예: feature + hotfix 혼재)은 미리보기에서 "별도 버전으로 분리 제안"을 사용자에게 확인받은 뒤에만 분리한다.

### 4. 업데이트 내용 (필수)

- 사용자가 자연어로 설명하는 업데이트/변경 계획.
- **미입력 시**: `"등록할 업데이트 내용을 알려주세요."` 출력 후 사용자 응답 대기.

### 5. 구현 루트 (implementation_root, **선택**)

- 모노레포·멀티 패키지 저장소에서 이번 릴리즈가 만지는 패키지의 저장소 루트 기준 상대 경로. 예: `packages/mobile`, `apps/web`.
- 단일 패키지 저장소에서는 입력 생략 (= `null`).
- 값을 받으면 Step 4-8에서 `task_list.json.implementation_root`에 그대로 기록되고, release-impl이 같은 입력을 다시 받지 않아도 자동 승계한다 — 모노레포에서 release-plan ↔ release-impl 사이 스코프 누락을 방지하는 게이트.
- 미입력은 `null`로 기록되며 단일 패키지 저장소 의미. 누락 자체로 진행을 막지 않는다.

### 6. 입력 수집 전략

미입력 **필수** 필드(1·2·3·4)가 2개 이상이면 개별 질문을 반복하지 말고 한 번에 묶어 질의한다(예: `"다음 정보를 함께 알려주세요: 노션 페이지 이름, 데이터베이스 이름, 버전(X.Y.Z), 업데이트 내용"`). 사용자가 부분 응답만 주면 누락 필드만 재질의한다. `implementation_root`는 선택 입력이므로 미입력을 사유로 진행을 막지 않는다.

---

## Notion 접근 방식

이 스킬은 **어떤 도구로 Notion 에 접근할지 모른다** — 그건 프로젝트 설정이다. 아래 Step 에서
"Notion 페이지를 찾는다"·"DB 를 만든다"처럼 서술한 부분은 매번 이 절차를 뜻한다.

1. 이 프로젝트에 `.claude/rules/notion-api-only.md` 가 있는지 확인한다.
2. 있으면 그 규칙이 지시하는 방법(`.claude/scripts/notion_api.py`)을 그대로 따른다 — **이
   스킬은 MCP 도구 이름을 지시하지 않는다.**
3. 없으면 사용자에게 Notion 연동 방식을 확인한다. 이 스킬은 Notion 을 유일한 상태 저장소로
   쓰므로 로컬 전용 대체 경로가 없다 — 연동이 없다는 응답이면 등록 전에 중단하고
   `"Notion 연동이 설정돼 있지 않습니다. /project-conventions:init-agent-rules --notion-rule on 을
   먼저 실행하거나, 사용자가 직접 Notion 에 접근할 방법을 알려주세요."` 를 안내한다.

## 호출 모드 (오케스트레이터 감지)

이 스킬은 사용자가 직접 호출하는 경우와 `fix-plan-impl` 같은 오케스트레이터가 호출하는 경우를 구분해야 한다. 분리 제안을 잘못 발동하면 오케스트레이션 체인이 깨진다.

| 조건 | 모드 | 버전 분리 제안 |
| --- | --- | --- |
| 호출 프롬프트에 `"이번 릴리즈를 {버전}으로 고정해주세요"` 또는 동의 문구(`"버전 고정"`, `"버전 분리 금지"`, `"version locked"`) 포함 | **오케스트레이터 모드** | 비활성화. 모든 작업이 입력 버전을 공유한다 |
| 그 외 | **대화형 모드** | 기본적으로 입력 버전 고정. 성격이 명확히 다른 작업이 혼재할 때만 미리보기에 "별도 버전 분리 제안"을 표시하고 **사용자의 명시적 승인**이 있을 때만 분리 적용 |

두 모드 모두 **기본값은 입력 버전 고정**이다. "마음대로 분리"는 어느 모드에서도 허용되지 않는다. 오케스트레이터 모드에서는 분리 제안 표시 자체를 생략해 자동화 흐름이 사용자 확인 대기로 멈추지 않게 한다.

---

## 루프 감지와 접근 전환

LLM은 실패 시 동일한 접근을 약간만 바꾸어 반복하는 경향이 있다. 사용자가 미리보기 결과에 대한 수정 요청을 계속 보내는 상황을 탐지해 무한 루프를 차단한다.

- `progress.md`의 **세션 로그**에 `수정 반복 카운트`를 누적 기록한다(예: `[2026-04-15 14:03] 사용자 수정 요청 (반복 2회): "...분해가 너무 잘다"`).
- **카운트 3회 이상** 도달 시, 동일 분해 접근을 재시도하지 않고 **전략 전환을 제안**한다. 전환 옵션 예:
  - 분해 입도를 한 단계 키우거나 줄이기(묶기/나누기)
  - 분해 기준을 `기술 계층` → `기능 도메인` 또는 그 반대로 교체
  - 업데이트 요구사항 자체를 사용자가 2~3개 하위 요구사항으로 재작성하도록 요청
- 같은 요청을 단어만 바꿔 다시 시도하는 것은 **반복으로 간주**한다. "조금 더 잘 분해해줘"는 이전 접근을 유지한 재시도이므로 카운트가 증가한다.

이 규칙은 "자기평가 편향과 무한 루프" 실패 모드에 대한 하드 가드이며, Step 4-7 self-critic으로 잡히지 않은 수렴 실패를 사람의 개입으로 돌려보내는 탈출구다.

---

## 실행 플로우

아래 Step 1~8을 순서대로 실행한다.

### Step 1: Notion 페이지 탐색

입력받은 노션 페이지 이름을 찾는다(위 "Notion 접근 방식" 절차).

- **찾은 경우**: 페이지 ID를 기록하고 Step 2로 진행
- **못 찾은 경우**: `"해당 이름의 노션 페이지를 찾을 수 없습니다: {페이지 이름}"` 출력 후 종료

### Step 2: 지정된 데이터베이스 확인

해당 페이지 하위에서 입력된 **{DB 이름}**과 동일한 제목의 데이터베이스 존재 여부를 판단한다.

- **있는 경우**: 기존 DB를 사용. Step 3으로 진행.
- **없는 경우**: Step 2-1에서 새로 생성.

#### Step 2-1: 데이터베이스 생성

[`references/notion_schema.md`](./references/notion_schema.md)에 정의된 스키마(컬럼·속성 타입·
RICH_TEXT 포맷 계약)로 **입력된 {DB 이름}** 제목의 데이터베이스를 만든다. 스키마 자체는 이
스킬 소유다 — "무엇을 저장하는가"는 여기서 정하고, "어떻게 만드는가"만 위임한다.

#### Step 2-2: 데이터베이스 뷰 설정

DB 생성 직후 `references/notion_schema.md`의 "뷰 설정" 섹션에 따라 **버전별**(table, GROUP BY
버전)과 **진행 현황**(board, GROUP BY 완료) 두 개의 뷰를 만든다. 위임 대상이 뷰 생성을
지원하지 않으면(예: 구 버전 스크립트) 이 단계는 secondary 로 취급한다 — 실패해도 Step 3 으로
계속 진행하고, 최종 보고에 "뷰 수동 생성 필요"를 남긴다.

### Step 3: 과거 계획 컨텍스트 수집

신규 요구사항만 단독으로 받지 않고, 과거 계획을 읽어 연속성·추가 제안의 재료를 만든다. LLM의 "세션 간 상태 소실"을 보완하기 위한 단계다.

**수집 대상:**

1. **Notion DB 전체 레코드**: 대상 DB의 모든 레코드를 조회해 버전별로 그룹핑. 각 버전의 작업 목록·완료 상태·구분 분포를 집계.
2. **로컬 관리 문서**: `docs/skills/release-plan/{DB slug}/v*/release-plan.md`, `task_list.json`, `progress.md` 파일을 시간순으로 로드. **직전 최대 3개 버전**만 읽는다(컨텍스트 과부하 방지). `{DB slug}`는 반드시 `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/slugify.py "{DB 이름}"`의 출력값을 사용한다(모델이 slug를 임의로 만들면 경로가 호출마다 달라진다).
3. **현재 버전 내 기존 Task**: 입력된 대상 버전과 동일한 버전이 DB에 이미 존재하면, **해당 버전의 최대 Task 번호**와 기존 작업 제목·선행 관계·상태를 수집 (Step 4-4의 번호 이어 붙이기에 사용).

**산출물 (내부 변수로 유지, Step 4에 투입):**

- `previous_versions_summary`: 최근 버전의 목표/결과/미해결 항목 요약
- `open_tasks`: 과거 버전에서 `계획`/`진행` 상태로 남아 있는 작업 (이월 후보)
- `related_themes`: 과거 계획에서 반복 등장한 모듈·도메인 키워드
- `version_continuity`: 입력 버전이 기존 DB 최대 버전과 일관된지 검증 (불일치 시 미리보기에서 경고)
- `max_task_number_in_target_version`: 입력된 대상 버전 내 이미 등록된 최대 Task 번호 (없으면 0)

### Step 4: Harness Engineering 기반 작업 분해

#### 4-0. 연관성 및 추가 계획 탐지

Step 3 산출물과 신규 요구사항을 대조하여 아래를 식별한다. 자동 등록하지 않고, Step 5 미리보기의 `## 추가 제안` 섹션에 제시한 뒤 사용자 승인 후에만 작업 목록에 편입한다.

1. **연관 작업**: 신규 요구사항이 과거 작업과 구조적으로 연결된 경우 → 해당 과거 작업을 "선행 관계"로 자동 연결 제안
2. **이월 작업**: 과거 버전에서 미완료로 남은 작업 중 이번 버전에서 다룰 가능성이 높은 후보
3. **누락된 후속 작업**: 과거 계획의 논리적 다음 단계인데 신규 요구사항에 빠진 작업 (예: 이전에 "로그인 구현"만 있고 "로그아웃"이 없음)

#### 4-1. 작업 분해 원칙

**단일 책임**: 하나의 작업 항목 = 하나의 독립적이고 검증 가능한 작업 단위.

**논리적 분해 기준** — 다음 중 하나 이상에 해당하면 별도 작업으로 분리:

- 서로 다른 기술 계층 (백엔드/프론트엔드/인프라)
- 서로 다른 기능 도메인
- 독립적으로 테스트/검증 가능한 단위
- 서로 다른 구분(feature/system/hotfix/performance/docs/refactor/infra)

**과도한 분해 지양**: 원자적 작업은 억지로 나누지 않는다.

**점진적 구현 순서** — 의존성을 고려하여 정렬한다. 동일 `구분` 내에서 선행 관계의 기본 가설은 다음 사슬이다(반증이 없으면 이 순서로 배치):

1. **데이터/스키마** — DB 마이그레이션, 타입/모델 정의, 환경 설정
2. **로직/서비스** — 비즈니스 규칙, API 핸들러, 상태 관리
3. **UI/UX** — 화면·컴포넌트·상호작용
4. **테스트/문서** — 자동화 테스트, 릴리즈 노트, 사용 가이드

하위 단계는 상위 단계의 산출물에 기본적으로 의존한다. 반대 방향 의존(예: UI가 데이터 스키마를 강제) 이 필요한 경우에만 사슬을 뒤집고 그 이유를 "작업 상세"에 적는다.

#### 4-2. 구분(Category) 판단

MULTI_SELECT이므로 한 작업에 여러 구분을 동시에 지정할 수 있다(예: `hotfix` + `infra`).

- `feature`: 새로운 기능 추가 — 사용자 가시성 있는 신규 동작
- `system`: 광범위한 시스템 변경·설정·의존성 업데이트(아래 세분화와 겹치면 더 구체적인 쪽 우선)
- `hotfix`: 버그 수정, 긴급 패치
- `performance`: 성능 최적화 — 기존 동작은 유지하되 속도/자원 개선
- `refactor`: 동작 변화 없는 코드 재구성 — 외부 관찰 가능한 출력이 동일해야 한다
- `docs`: 문서·릴리즈 노트·주석·가이드만 변경
- `infra`: 빌드·CI/CD·환경·배포 파이프라인 변경

구분 선택 가이드:

- **동작이 바뀌면 `refactor`가 아니다** — 동작 변경이 있으면 `feature`/`hotfix`/`performance` 중 하나를 쓴다.
- **문서 전용 변경은 `docs`** — 코드·설정 변경이 같이 있다면 `docs`만 붙이지 않고 실제 코드 변경의 구분을 함께 쓴다.
- **CI/CD·Dockerfile·EAS 설정은 `infra`** — 앱 런타임 코드 변경이 섞이면 해당 코드의 구분과 `infra`를 함께 지정한다.

#### 4-3. 버전 부여 (자동 추론 제거)

모든 작업은 **입력된 대상 버전**을 공유한다. 자동 추론하지 않는다. 다만 성격이 명확히 다른 작업(예: feature + hotfix 혼재)에 대해 별도 버전 분리가 더 적절하다고 판단되면, 미리보기에서 "입력 버전과 다른 버전으로 분리 제안"을 명시하고 사용자 확인 후에만 분리한다.

#### 4-4. "작업" (Title) 작성 — [Task N] 말머리 규칙

**형식**: `[Task N] {작업명}`

- N은 **버전별로 독립된 1부터의 연속 정수**
- 동일 등록 배치에 여러 버전이 섞이면 각 버전마다 1부터 새로 부여
- 입력된 대상 버전에 DB 기존 레코드가 있으면 `max_task_number_in_target_version + 1`부터 이어서 부여
- 작업명 자체는 동사로 시작하는 액션 지향 표현 (예: 구현/추가/개선/수정/리팩토링)

예시:
- `[Task 1] 이메일 로그인 구현`
- `[Task 2] 로그인 화면 UI 구현`

#### 4-5. "작업 상세" 작성

```
[구현 내용]
- 구체적인 구현 사항 1
- 구체적인 구현 사항 2

[수용 기준]
- 검증 가능한 완료 조건 1
- 검증 가능한 완료 조건 2
```

수용 기준은 모호한 표현("잘 동작해야 한다") 금지. "로그인 버튼 클릭 시 JWT 토큰이 발급되어 SecureStore에 저장된다"처럼 구체적 조건으로 작성.

#### 4-6. 의존성/병렬성 판단 (선행 관계 / 병렬 진행 가능)

- **선행 관계**: 4-1의 구현 순서(데이터/스키마 → 로직/서비스 → UI → 테스트/문서)를 바탕으로, 시작 전 반드시 완료되어야 하는 타 Task의 말머리를 쉼표로 나열. 없으면 `-`.
- **병렬 진행 가능**: 서로 다른 기술 계층 또는 독립 도메인에 속하는 Task들을 쉼표로 나열. 없으면 `-`.
  - **이 단계에서는 "계층·도메인이 다른가"만 판정한다**. 실제 파일/리소스 충돌(같은 파일을 수정하는지, 같은 마이그레이션 번호를 점유하는지 등)은 release-plan이 코드 레벨을 모르므로 추정하지 않는다. 충돌 여부의 **최종 확정은 `release-impl`의 Evaluator가 구현 단계에서 수행**한다. 여기서는 "병렬 진행 가능 후보"라는 의미로 기록한다.
- **상호 배타**: 동일 대상 Task에 대해 두 컬럼에 동시에 기재하지 않는다.

#### 4-7. 분해 후 self-critic (3문 체크리스트)

Step 5 미리보기 생성 전, 분해 결과를 자기 점검한다. 자기평가 편향을 보완하기 위한 최소 절차이며, **하나라도 `NO`면 Step 4-1로 돌아가 재분해한다**.

1. **독립 검증 가능성**: 각 Task가 다른 Task와 독립적으로 "완료/미완료" 판정이 가능한가? (수용 기준이 한 Task 내부에서 완결되는가?)
2. **[Task N] 연속성**: 동일 버전 내에서 Task 번호가 `1..N` 또는 `max+1..max+k`로 건너뜀 없이 연속하는가?
3. **라벨 참조 정합성**: `선행 관계` / `병렬 진행 가능`에 쓰인 `[Task N]` 라벨이 이번 배치 또는 기존 DB에 모두 존재하는가? 두 컬럼에 동시에 등장하거나 자기 자신을 가리키는 라벨은 없는가?

세 항목 모두 `YES`일 때만 Step 4-8로 진행한다.

#### 4-8. task_list.json 작성 (검증 대상 영속화)

검증을 시작하려면 분해 결과가 디스크에 있어야 한다. `docs/skills/release-plan/{DB slug}/v{버전}/task_list.json`을 [`references/task_list_contract.md`](./references/task_list_contract.md) 스키마로 작성한다. 입력값 #5 `implementation_root`는 그대로 최상위 필드로 기록(미입력 시 `null`) — release-impl이 자동 승계한다. `fact_check` 객체는 비워두지 않고 **임시 placeholder**(`{"verdict": "fail", "tokens_path": "tokens.json", "verified_count": 0, "unverified_tokens": [], "evidence_logs": {}, "checked_at": null}`)로 둔다 — Fact-checker가 Step 4-10에서 덮어쓴다. `summary.fail`은 `tasks.length`로 초기화한다.

사용자가 Step 5 미리보기에서 abort하면 이 폴더(`task_list.json` + `tokens.json` + `logs/fact_check/`)를 삭제하여 부분 산출물을 남기지 않는다.

#### 4-9. 외부 기술 토큰 추출 (extract_tech_tokens.py)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/extract_tech_tokens.py \
  docs/skills/release-plan/{DB slug}/v{버전}/task_list.json \
  docs/skills/release-plan/{DB slug}/v{버전}/tokens.json
```

스크립트가 모델 ID·npm 패키지·Python 핀을 정규식으로 추출한다. exit 0이지만 `tokens` 배열이 비어 있을 수 있다 — UI-only 변경 등에서는 정상이며, Step 4-10에서 Fact-checker가 즉시 verdict=pass로 통과시킨다.

#### 4-10. Fact-checker 서브에이전트 호출 (별개 Task)

[`agents/fact-checker.md`](./agents/fact-checker.md)를 시스템 프롬프트로 주입한 **별개 Task 도구 호출**로 기동한다. 같은 컨텍스트에서 순차 실행 금지 — 분해 주체와 검증 주체를 분리하는 것이 자기평가 편향과 "훈련 컷오프 밖 세계에 대한 자신감 있는 할루시네이션" 방어의 핵심이다.

호출 컨텍스트(JSON)는 `task_list_path`, `tokens_path`, `version_dir`, `project_root`, `claude_md_path`. Fact-checker가 Context7 → WebSearch 폴백으로 각 토큰을 검증하고, evidence 로그를 `{version_dir}/logs/fact_check/{token-slug}.log`에 작성한 뒤 `task_list.json`의 `fact_check` 객체를 직접 갱신한다.

Fact-checker가 `verdict: fail`을 반환하면 `unverified_tokens`을 사용자에게 보여주고 Step 4-1(재분해)로 복귀한다. Context7과 WebSearch가 둘 다 응답 실패라고 보고하면 사용자에게 명시 승인을 요청한 뒤에만 `verdict: unverified-user-approved`로 진행한다 — 자동 통과 금지.

#### 4-11. 검증 게이트 (verify_tech_tokens.py)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/verify_tech_tokens.py \
  docs/skills/release-plan/{DB slug}/v{버전}/task_list.json
```

비-영(非零) exit code 시 Step 5로 진행하지 않는다. 게이트는 `verdict ∈ {pass, unverified-user-approved}`, `evidence_logs` 모든 경로의 실재·비공백을 확인한다. 이 게이트는 Fact-checker의 자기보고가 아닌 디스크의 증거 파일을 본다 — "확인했음"만 적고 로그를 남기지 않은 경우를 잡는다.

세 단계(4-9/4-10/4-11)를 통과한 후에만 Step 5로 진행한다.

### Step 5: 미리보기 제시

#### 5-0. SemVer sanity check

미리보기 출력 직전에 입력된 버전과 분해된 작업의 `구분` 분포가 SemVer 관행에 부합하는지 점검한다. 이 체크는 **경고만 표시하고 차단하지는 않는다** — 릴리즈 매니지먼트는 사용자의 판단이다.

| 상황 | 경고 문구 (미리보기 `## SemVer 점검` 섹션에 표기) |
| --- | --- |
| `hotfix` / `performance`만 있는데 minor 또는 major 증가 (예: 2.0.0 → 2.1.0) | "해당 작업군은 보통 patch 릴리즈로 처리됩니다. 버전 `X.Y.Z+1` 사용을 고려해 보세요." |
| `feature`가 포함되는데 patch 증가 (예: 2.1.0 → 2.1.1) | "`feature` 작업이 포함되어 있습니다. 일반적으로 minor 릴리즈가 적절합니다." |
| breaking change가 의심되는 키워드(`호환성 깨짐`, `breaking`, `schema v2`, `API 제거` 등)가 포함 | "breaking change 가능성이 있습니다. major 릴리즈 여부를 확인해 주세요." |
| 위 경고가 하나도 해당 없음 | 섹션 생략 가능 |

오케스트레이터 모드에서도 경고는 표시하되, 사용자 확인 없이 버전을 바꾸지 않는다.

```
## 릴리즈 작업 미리보기 (v{입력 버전})

| # | 버전 | 구분 | 작업명 | 선행 관계 | 병렬 진행 가능 | 작업 상세 (요약) |
|---|------|------|--------|-----------|----------------|------------------|
| 1 | 2.1.0 | feature | [Task 1] 이메일 로그인 구현 | - | [Task 2] | JWT 기반 인증 + SecureStore 저장 |
| 2 | 2.1.0 | feature | [Task 2] 로그인 화면 UI 구현 | [Task 1] | - | 이메일/비밀번호 입력 폼 + 유효성 검증 |
| ... | ... | ... | ... | ... | ... | ... |

> 총 N개 작업 | 등록일: {YYYY-MM-DD}
> 대상 페이지: {페이지 이름}
> 대상 데이터베이스: {DB 이름}
> ✅ 외부 사실 검증: {verified_count}개 토큰 통과 (evidence: docs/skills/release-plan/{slug}/v{버전}/logs/fact_check/) — verdict: {pass | unverified-user-approved}

## 추가 제안 (과거 계획 분석 기반)

- [연관] [Task 2] 로그인 화면 UI는 v2.0.0의 [Task 4] 공용 Form 컴포넌트와 연관 → 선행 관계 연결 권장
- [이월] v2.0.0 [Task 7] "비밀번호 재설정 플로우"가 `계획` 상태 → 본 버전 포함 여부 확인 필요
- [후속] 과거 "이메일 로그인"의 논리적 후속인 "로그아웃" 작업 누락 → 추가 등록 여부 확인 필요

위 미리보기 + 추가 제안을 어떻게 반영할까요? (전부 포함 / 일부 선택 / 무시)
```

추가 제안이 없으면 `## 추가 제안` 섹션은 `(해당 없음)`으로 표기하되 섹션 자체는 유지한다.

**사용자 확인을 반드시 받은 후에만 Step 6으로 진행한다.**

### Step 6: Notion 데이터베이스에 등록

#### 6-1. 중복 검사 (멱등성 가드)

Notion 레코드 생성을 위임하기 전에 Step 3에서 조회한 DB 레코드를 이용해 **이번 배치에 등록할 각 `(버전, 작업명)` 조합이 이미 존재하는지** 확인한다. 검사는 작업명 전체가 아니라 `[Task N]` 말머리를 제외한 뒷부분을 대소문자 무시·공백 정규화 후 비교한다(예: `이메일 로그인 구현` vs `이메일 로그인  구현`).

- **중복이 없는 경우**: 6-2로 진행.
- **중복이 있는 경우**: 사용자에게 `skip` / `upsert` / `abort` 중 하나를 선택받는다. 기본 동작은 `abort`이며, 선택 없이는 Notion 에 레코드를 생성하지 않는다.
  - `skip`: 중복된 작업만 제외하고 나머지만 등록한다.
  - `upsert`: 중복된 레코드의 작업 상세/선행/병렬 컬럼을 새 값으로 업데이트한다(단, `완료` 상태가 `완료`·`진행`인 레코드는 건드리지 않는다).
  - `abort`: 이번 실행을 즉시 종료한다. 부분 등록을 남기지 않는다.

추측으로 덮어쓰지 않는다 — 이 가드는 "일회성 탐욕적 완료"와 "세션 간 상태 소실"이 결합되어 DB에 중복 레코드를 누적시키는 회귀를 막기 위한 장치다.

#### 6-2. 레코드 생성

각 작업을 개별 레코드로 Notion 에 만든다(위 "Notion 접근 방식" 절차).

**각 레코드 속성:**

- **작업**: `[Task N] {작업명}`
- **완료**: `계획`
- **버전**: 입력된 대상 버전 (또는 사용자가 승인한 분리 버전)
- **구분**: 판단된 카테고리
- **작업 상세**: [구현 내용] + [수용 기준] 전문
- **선행 관계**: `[Task X], [Task Y]` 또는 `-`
- **병렬 진행 가능**: `[Task X], [Task Y]` 또는 `-`
- **등록일**: 당일
- **완료일**: 비워둠

> ❗ **완료 선언 금지 지점**: Step 6까지 끝났더라도 "등록 완료"를 보고하지 않는다. Step 7의 관리 문서 생성과 Step 7-3 말미의 `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/validate_task_list.py` 통과까지 마친 뒤, **Step 8에서만** 최종 결과를 보고한다. LLM이 "Notion 등록 성공 = 작업 완료"로 조기에 선언하는 실패 모드를 차단하기 위한 게이트다.

### Step 7: Harness Engineering 관리 문서 생성

#### 7-1. 버전 폴더 생성

`docs/skills/release-plan/{DB slug}/v{버전}/` 디렉토리를 생성한다.

- `{DB slug}`: 반드시 `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/slugify.py "{DB 이름}"` 실행 결과를 사용한다. 예: `Release Plan` → `release-plan`, `v2.1 Tasks` → `v2-1-tasks`. Step 3에서 사용한 slug와 동일해야 한다.
- 버전은 Step 6에서 등록한 작업들의 **최대 버전**을 사용
- 폴더가 이미 존재하면 기존 문서를 덮어쓰지 않고 파일명에 날짜를 붙여 생성 (예: `release-plan_2026-04-15.md`)

#### 7-2. release-plan.md (릴리즈 계획 명세)

템플릿은 [`references/harness_docs_templates.md`](./references/harness_docs_templates.md)의 `release-plan.md` 섹션을 사용한다. 업데이트 요약·작업 분해 테이블·과거 계획 연계·구현 순서 4개 섹션을 필수로 채운다.

#### 7-3. task_list.json 최종 검증 (validate + verify 재실행)

`task_list.json` 자체는 Step 4-8에서 작성되고 Step 4-10에서 Fact-checker가 `fact_check` 객체를 채웠다. 여기서는 Notion 등록 후 최종 일관성을 한 번 더 확인한다:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/validate_task_list.py docs/skills/release-plan/{DB slug}/v{버전}/task_list.json
python3 ${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/verify_tech_tokens.py  docs/skills/release-plan/{DB slug}/v{버전}/task_list.json
```

두 스크립트 모두 exit 0이어야 Step 8로 진행한다. validator는 번호 연속성·[Task N] 라벨 참조 정합성·acceptance_criteria 비공백·선행/병렬 상호 배타·summary 집계 일치·`fact_check` 형식을 검사하고, verify는 `fact_check.evidence_logs`의 모든 경로가 디스크에 실재·비공백으로 남아 있는지를 재확인한다 (등록 사이에 삭제되지 않았는지).

**acceptance_criteria는 생성 후 삭제·수정 금지**. 달성 불가 시 새 Task로 등록하거나 사용자에게 에스컬레이션. 모든 작업은 `"fail"` 상태로 시작한다 — "아직 완료를 증명하지 못한 상태"라는 인지 프레임으로 조기 완료 선언을 방지한다.

#### 7-4. progress.md

템플릿은 `references/harness_docs_templates.md`의 `progress.md` 섹션을 사용한다. 현재 상태·세션 로그·다음 단계를 포함한다.

### Step 8: 등록 완료 보고

```
## 릴리즈 작업 등록 완료

- 등록 작업 수: N개
- 대상 페이지: {페이지 이름}
- 대상 데이터베이스: {DB 이름}
- 버전: v{버전}
- Task 번호 범위: [Task {시작}] ~ [Task {끝}]
- 등록일: {YYYY-MM-DD}
- 관리 문서: docs/skills/release-plan/{DB slug}/v{버전}/

모든 작업이 "{DB 이름}" 데이터베이스에 등록되었습니다.
Harness Engineering 관리 문서가 생성되었습니다:
  - release-plan.md (릴리즈 계획 명세)
  - task_list.json (Task State Machine)
  - progress.md (진행 상황 추적)
```

---

## 핵심 제약 조건

1. **4가지 필수 입력 게이트**: 페이지 이름·DB 이름·버전(X.Y.Z)·업데이트 내용 중 하나라도 누락·형식 위반 시 즉시 종료. 추측으로 메우지 않는다.
2. **DB 이름은 입력값**: "Release Plan"을 하드코딩하지 않는다. 모든 DB 관련 처리는 입력된 이름을 사용.
3. **버전은 입력값**: Step 4에서 자동 추론하지 않는다. 입력된 `X.Y.Z`를 기본으로 사용. 버전 분리는 미리보기에서 사용자 확인 후에만 가능.
4. **작업 제목 형식 고정**: 모든 제목은 `[Task N] {작업명}`. N은 **버전별 독립 번호**이며, 기존 DB에 해당 버전 레코드가 있으면 최대 번호 + 1부터 이어서 부여.
5. **선행/병렬 컬럼 상호 배타**: 동일 Task에 대해 선행 관계와 병렬 진행 가능에 동시에 기재하지 않는다.
6. **작업 분해는 필수 분석 과정**: 단순 업데이트도 분해 가능성 검토 후 단일 작업으로 등록 가능.
7. **기존 데이터 절대 보존**: 기존 DB를 삭제/재생성하지 않는다. 레코드만 추가.
8. **과거 계획 컨텍스트 수집 필수**: Step 3에서 Notion 레코드 + 로컬 관리 문서(직전 3개 버전)를 읽고, Step 4-0에서 연관/이월/누락 후속 제안을 수행.
9. **등록 전 미리보기 필수**: 사용자 확인 없이 Notion에 직접 등록 금지. 미리보기에는 `## 추가 제안` 섹션을 항상 포함(없으면 `해당 없음`).
10. **모든 출력은 한국어**: 작업명·작업 상세·안내 메시지 모두 한국어.
11. **완료 기본값은 `계획`**: task_list.json 상태는 `"fail"` (증명될 때까지 미완료 원칙).
12. **관리 문서 필수 생성**: `docs/skills/release-plan/{DB slug}/v{버전}/` 폴더에 3개 문서(release-plan.md, task_list.json, progress.md) 동시 생성.
13. **기존 버전 폴더 보존**: 이전 버전 폴더의 문서를 수정·삭제하지 않는다.
14. **acceptance_criteria 불변**: 생성 후 삭제·수정 금지.
15. **slug는 스크립트로만 결정**: 로컬 경로에 쓰는 `{DB slug}`는 반드시 `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/slugify.py`의 출력. 모델이 kebab-case를 직접 만들지 않는다.
16. **중복 검사 필수**: Step 6-1에서 `(버전, 작업명)` 중복을 확인하고, 중복 존재 시 사용자가 `skip`/`upsert`/`abort`를 명시적으로 선택하기 전까지 Notion 에 레코드를 생성하지 않는다(기본 `abort`).
17. **조기 완료 선언 금지**: Step 6까지 끝나도 "완료"를 보고하지 않는다. Step 7 문서 생성 + `validate_task_list.py` 통과 후 Step 8에서만 최종 보고.
18. **외부 기술 토큰 검증 필수**: Step 4-9에서 추출된 모든 토큰은 Step 4-10 Fact-checker(별개 Task 호출)가 Context7 → WebSearch로 검증한다. Step 4-11 `verify_tech_tokens.py` 게이트가 비-영(非零)이면 Step 5 미리보기로 진행하지 않는다. 외부 도구가 모두 응답 실패한 경우에만 사용자 명시 승인 후 `fact_check.verdict = "unverified-user-approved"`로 진행하며 `progress.md`에 사유를 기록한다. Fact-checker는 자기 기억으로 토큰을 통과시키지 않는다 — evidence 로그 파일이 유일한 근거다.

---

## 사용하는 외부 검증 도구 (Step 4-10)

Fact-checker 서브에이전트가 호출한다. 분해 주체(Generator)는 직접 호출하지 않는다 — 자기평가 편향 차단을 위한 권한 분리.

| 도구                                                | 용도                                                                                 |
| --------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `mcp__plugin_context7_context7__resolve-library-id` | 모델 ID·npm 패키지·Python 패키지의 실존성을 1차 조회                                  |
| `WebSearch`                                         | Context7 미매치 시 공식 도메인(google.dev / huggingface.co / npmjs.com 등)에서 2차 확인 |

---

## 참조 문서

- [`references/notion_schema.md`](./references/notion_schema.md) — DB 컬럼·DDL·뷰 설정·RICH_TEXT 포맷 계약 (컬럼 이름·옵션의 정본)
- [`references/notion_db_schema.json`](./references/notion_db_schema.json) — 위 스키마를 REST `properties` 객체로 표현한 파일(DB 생성 위임 시 사용)
- [`references/task_list_contract.md`](./references/task_list_contract.md) — task_list.json 스키마·상태 전이·검증 지시
- [`references/harness_docs_templates.md`](./references/harness_docs_templates.md) — release-plan.md·progress.md 템플릿
- [`references/golden_example.md`](./references/golden_example.md) — 종단간 실행 예제 (Stage Sudoku v2.2.0)
- `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/slugify.py` — DB 이름 → 경로 slug 결정적 변환
- `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/validate_task_list.py` — task_list.json 정합성 검증 (구조 + `fact_check` 형식)
- `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/extract_tech_tokens.py` — task_list.json에서 모델 ID·npm 패키지 토큰 정규식 추출 (Step 4-9)
- `${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/verify_tech_tokens.py` — `fact_check` evidence 파일 실재·비공백 차단 게이트 (Step 4-11)
- [`agents/fact-checker.md`](./agents/fact-checker.md) — 별개 Task로 기동되는 외부 사실 검증 서브에이전트 (Step 4-10)
