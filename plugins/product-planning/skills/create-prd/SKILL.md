---
name: create-prd
description: "Use when a user wants to turn a Notion page, meeting note, or requirements memo into a PRD (Product Requirements Document) — normalizes the source document into the ten canonical PRD sections (Document Information, Overview, User Stories, Functional and Non-Functional Requirements, User Flow, Acceptance Criteria, Dependencies, Risks and Assumptions, Success Metrics), derives Given-When-Then acceptance criteria for every functional requirement, marks any success metric it had to draft itself as [제안] with a stated rationale, then launches design, engineering, and QA reviewer subagents in parallel to cross-review the draft before writing docs/plan/PRD-{slug}.md and publishing a Notion page under a user-specified parent. Triggers on Korean and English phrases including: 'PRD 만들어줘', 'PRD 작성', 'PRD 써줘', '제품 요구사항 문서', '요구사항 문서 만들어줘', '요구사항 정리해줘', '기획서 PRD로 정리해줘', '회의록을 PRD로', '회의록 정리해서 PRD', '노션 문서로 PRD 만들어줘', '이 문서 PRD로 바꿔줘', '유저스토리 정리해줘', '유저 스토리 뽑아줘', '수용기준 만들어줘', '인수 기준 정리', 'Given-When-Then', '기능 요구사항 정리', '비기능 요구사항', '성공 지표 정의', 'PRD 업데이트', 'PRD 검토해줘', 'create-prd', 'write a PRD', 'create a PRD', 'product requirements document', 'turn this doc into a PRD', 'turn this into requirements', 'draft requirements doc', 'acceptance criteria', 'user stories', 'success metrics'."
compatibility: 'mcp: notion'
---

# Create PRD — 문서를 PRD 10개 섹션으로 정규화

노션 문서·회의록·요구사항 메모를 입력으로 받아, PRD 10개 핵심 섹션을 갖춘 문서를 만든다.
로컬 `docs/plan/PRD-{slug}.md` 가 SSoT 이고, 사용자가 지정한 Notion 부모 페이지 하위에 사본을 발행한다.

이 스킬이 따르는 계약은 세 겹이다. 임의로 줄이지 않는다.

| 계약 | 내용 |
| --- | --- |
| **10개 섹션** | 문서 정보 / 개요 / 유저스토리 / 기능 요구사항 / 비기능 요구사항 / 유저 플로우 / 수용기준 / 의존성 / 위험·가정 / 성공 지표 |
| **6단계 작성법** | ① 문제 이해 ② 목표 정의 ③ 유저스토리 ④ 기능·비기능 요구사항 ⑤ 수용기준 ⑥ 협업·검토 |
| **4가지 흔한 실수** | 혼자 쓰기 / 기술 전문용어 과다 / 수용기준·지표 생략 / 기능과 목표 혼동 |

전체를 지배하는 원칙 하나 — **PRD는 의도를 설명하는 문서이고, 기술 명세서가 아니다.**
"어떻게 만들지"는 엔지니어의 몫이다. 명세로 취급하면 구현 여지를 없앤다.
Step 5·8 의 장치는 대부분 이 원칙이 무너지는 것을 막기 위해 존재한다.

모든 산출물과 안내 메시지는 **한국어**로 쓴다.

---

## 입력값 확인 (게이트)

필수 입력 2개다. 하나라도 없으면 묶어서 한 번 질의하고, 응답에 없으면 **즉시 종료**한다.
누락 입력을 추측으로 메우지 않는다 — 원본 문서를 잘못 짚으면 PRD 전체가 엉뚱한 근거 위에 선다.

### 1. 원본 문서 (필수)

PRD로 정규화할 노션 페이지 이름 또는 로컬 파일 경로.

- **미입력 시**: `"어떤 문서를 PRD로 만들지 알려주세요. (노션 페이지 이름 또는 파일 경로)"` 출력 후 종료.
- 이름으로 검색해 결과가 여러 건이면 후보를 제시하고 사용자가 고르게 한다. 임의로 첫 번째를
  고르지 않는다.

### 2. Notion 부모 페이지 (필수)

완성된 PRD를 발행할 부모 페이지 이름.

- **미입력 시**: `"PRD를 발행할 노션 부모 페이지 이름을 알려주세요."` 출력 후 종료.

### 3. 입력 수집 전략

둘 다 없으면 개별 질문을 반복하지 말고 한 번에 묶는다:
`"다음 두 가지를 알려주세요: ① PRD로 만들 원본 문서 ② PRD를 발행할 노션 부모 페이지 이름"`
부분 응답만 오면 누락된 것만 재질의한다.

---

## 실행 플로우

Step 0~11 을 순서대로 실행한다. 각 Step 옆의 "원문 대응" 은 근거이며, 이 절차들은 원문이 명시적으로
요구한 것이다 — "불필요한 단계"로 보고 걷어내지 말 것.

### Step 0: 원본 문서 로드

`notion-search` 로 입력받은 문서를 찾고 `notion-fetch` 로 전문을 읽는다. 로컬 경로면 직접 읽는다.

- **못 찾은 경우**: `"해당 이름의 문서를 찾을 수 없습니다: {이름}"` 출력 후 종료.
- 전문을 `source_excerpt` 로 보관한다. Step 8 리뷰어에게 전달되어 **"원본에 있던 내용"과
  "도출한 내용"을 구분하는 정답지**가 된다. 이 대조가 없으면 날조를 판별할 수 없다.

### Step 1: slug 결정과 기존 PRD 확인

기능명을 원본 문서에서 확정한 뒤 slug 를 스크립트로 결정한다.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/create-prd/scripts/prd_slug.py --explain "{기능명}"
```

**모델이 kebab-case 를 직접 만들지 않는다.** slug 가 호출마다 달라지면 다음 세션이 기존 PRD를
찾지 못하고 두 번째 문서를 만든다.

- `lossy: false` → 출력 `slug` 를 그대로 사용.
- `lossy: true` (한국어 기능명 등) → 해시 slug 는 사람이 읽기 어렵다. **한 번만** 사용자에게 확인한다:
  `"기능명이 한국어라 자동 slug 가 {slug} 가 됩니다. 파일명에 쓸 짧은 영문 slug 를 알려주세요. (예: traveler-login)"`
  응답값을 frontmatter `slug:` 에 기록하면 이후 세션은 문서에서 읽으므로 재질의하지 않는다.

**`docs/plan/PRD-{slug}.md` 가 이미 있으면 덮어쓰지 않는다.** 사용자에게 선택받는다:

| 선택 | 동작 |
| --- | --- |
| `update` | 기존 문서를 읽어 이어서 개정한다. `version` 을 올리고 `revision_count` 를 유지한다 |
| `new` | 다른 slug 를 받아 새 문서를 만든다 |
| `abort` | **기본값.** 즉시 종료. 부분 산출물을 남기지 않는다 |

`update` 는 원문 베스트 프랙티스 *"정기적으로 검토하기 — 제품이 진화하듯 PRD도 함께 진화해야
한다"* 에 해당하는 경로다. 기존 문서의 확정된 수치와 `[제안]` 표기는 보존한다 — 팀이 이미
확정한 것을 초안으로 되돌리면 합의가 리셋된다.

### Step 2: 문제 이해  · 원문 Step 1

`"왜"에서 시작한다.` 원본 문서에서 아래를 추출한다.

- 어떤 사용자 페인포인트를 푸는가
- 누가 영향받는가
- 근거가 되는 데이터·피드백은 무엇인가

**원본 문서에서 확인되는 것만 적는다.** 배경을 발명하면 PRD 전체가 그 위에 세워진다.
원본에 근거가 없으면 섹션 9 위험·가정에 `ASM-n` 으로 기록한다 — 검증되지 않은 전제라고 밝히는 것이
없는 근거를 만드는 것보다 정확하다.

### Step 3: 목표 정의  · 원문 Step 2 + 흔한 실수 ④

문제를 측정 가능한 목표로 옮긴다. **기능을 목표 자리에 쓰지 않는다.**

```
✗ 목표 — 이메일 로그인 기능을 제공한다.        (기능이다)
✓ 목표 — 여행자가 스스로 예약 이력을 조회·관리할 수 있는 상태에 도달한다.
```

자체 점검 — 목표 문장에서 기능 이름을 지웠을 때 문장이 무너지면 그건 기능이다.

### Step 4: 유저스토리  · 원문 Step 3

`- **US-n**: As a {사용자}, I want {행동} so that {이유}.`

형식은 `validate_prd.py` 가 검사한다. 형식보다 중요한 것은 목적이다 — 유저스토리는 팀에게
**누구를 위해 만드는지**를 상기시킨다. 시스템 동작을 사용자 문장으로 위장하면 형식은 맞아도 실패다.

```
✗ As a 사용자, I want 로그인 API를 호출하고 싶다 so that 인증 토큰을 받는다.
```

`so that` 은 행동의 재서술이 아니라 **이유**여야 한다.

### Step 5: 기능·비기능 요구사항  · 원문 Step 4

두 표로 분리한다. 분리 자체가 원문의 요구다.

- **기능(FR-n)**: 제품이 **무엇을** 해야 하는가 — actions·data·logic
- **비기능(NFR-n)**: 제품이 **어떻게** 동작해야 하는가 — security·speed·scalability

모든 `FR-n` 은 `US-n` 을 참조한다. 참조할 스토리가 없는 요구사항은 목표와 연결되지 않은 기능이다 —
원문 베스트 프랙티스 *"기능이 아니라 가치에 집중하기: 모든 요구사항은 사용자 또는 비즈니스 목표와
연결되어야 한다"* 위반이므로 Step 4 로 돌아가 스토리를 확인한다.

**구현 방법을 쓰지 않는다.** 금지·대체 대응은
[`references/prd_template.md`](./references/prd_template.md) 의 "쓰지 말아야 할 것" 표를 따른다.
테이블 스키마·라이브러리 선정·파일 경로가 들어가면 PRD가 기술 명세로 변한 것이다.

### Step 6: 수용기준  · 원문 Step 5 + 흔한 실수 ③

`- **AC-n** (FR-m): Given {전제}, When {행동}, Then {기대 결과}.`

- **모든 `FR-n` 에 최소 1건.** 게이트가 강제한다.
- `Given`·`When`·`Then` 키워드는 영어로 유지한다 — 원문이 지정한 형식이고 grep 이 가능해야 한다.
- `Then` 은 **관측 가능한 결과**여야 한다. "잘 동작한다"는 수용기준이 아니다.
- 위반 시나리오가 본질인 요구사항(고유성·권한·한도)에는 위반 케이스 AC 를 함께 쓴다. 성공
  경로만 있으면 그 제약은 검증되지 않는다.

### Step 7: 초안 영속화

[`references/prd_template.md`](./references/prd_template.md) 형식으로
`docs/plan/PRD-{slug}.md` 를 쓴다. `status: draft`, `revision_count: 0`.

디스크에 있어야 리뷰어가 **직접 읽을 수 있다.** 컨텍스트로 넘긴 요약을 검토하면 요약 단계에서 이미
걸러진 문제를 볼 수 없고, 검토가 무의미해진다.

#### 성공 지표와 `[제안]` 표기

원본 문서에 지표가 없으면 업계 관행으로 초안을 제안한다. 단 **예외 없이 아래를 지킨다.**

| 상황 | 표기 |
| --- | --- |
| 원본 문서에 있는 수치 | 표기 없음. `근거` 에 출처를 적는다 |
| 모델이 만든 초안 | `[제안]` 접두 + `근거` 에 **왜 그 수치인지** |

`[제안]` 은 `근거` 컬럼이 있는 표 안에만 쓴다 — 산문에 쓰면 근거를 검증할 수 없다.
`근거` 에 "업계 표준", "일반적" 처럼 출처 없는 권위 주장을 적으면 Step 8 QA 리뷰어가 반려한다.
무엇을 근거로 삼았는지(원본의 어느 서술, 어떤 플로우 특성)를 구체적으로 쓴다.

이 구분이 흐려지면 사용자는 무엇이 합의된 수치이고 무엇이 초안인지 알 수 없다.

### Step 8: 리뷰어 3개 병렬 기동  · 원문 Step 6

원문: *"PRD는 혼자 작성하는 것이 아닙니다. 초안을 디자인·엔지니어링·QA 팀과 일찍 공유하세요."*

세 에이전트 문서를 각각 시스템 프롬프트로 주입한 **별개 Task 도구 호출 3개를 한 메시지에서 동시
실행**한다.

| 에이전트 | 담당 |
| --- | --- |
| [`agents/design-reviewer.md`](./agents/design-reviewer.md) | 목표↔스토리 정렬, 유저스토리, 유저 플로우 |
| [`agents/engineering-reviewer.md`](./agents/engineering-reviewer.md) | 요구사항 실현 가능성, 의존성, 위험, 기술 명세 흘러내림·용어 |
| [`agents/qa-reviewer.md`](./agents/qa-reviewer.md) | 수용기준 테스트 가능성, 성공 지표, `[제안]` 근거 |

**순차 실행 금지.** 뒤의 리뷰어가 앞의 지적을 보면 그 프레임에 갇혀 상관된 맹점이 생긴다.
서로의 결과를 모르는 상태가 이 설계의 값어치다.

**같은 컨텍스트에서 실행 금지.** PRD를 쓴 주체가 자기 PRD를 검토하면 통과시킨다. 원문의 "혼자 쓰지
말라"와 저장소 규약의 "생성자와 검증자를 분리하라"는 같은 요구다.

호출 컨텍스트는 `prd_path`, `source_excerpt`, `evidence_log`, `revision_count`.
공통 입출력 계약은 [`references/reviewer_contract.md`](./references/reviewer_contract.md).

각 리뷰어는 `docs/plan/logs/review/{role}.log` 에 근거를 남기고
`{"role", "verdict", "findings", "evidence_log"}` 를 반환한다. `verdict` 기본값은 `revise` 다 —
통과를 증명해야 pass 이며, 이것이 조기 완료 선언을 막는다.

`severity: blocking` 이 하나라도 있으면 해당 Step(2~7)으로 돌아가 수정하고, `revision_count` 를
올린 뒤 **리뷰어 3개를 다시 기동**한다. `advisory` 는 Step 10 미리보기에 표시하고 사용자가 판단한다.

### Step 9: 게이트

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/create-prd/scripts/validate_prd.py docs/plan/PRD-{slug}.md
```

비-영(非零) exit 이면 Step 10 으로 진행하지 않는다. 스크립트는 10개 섹션 실재·본문 비공백,
유저스토리 형식, 모든 FR 의 AC 참조, Given-When-Then 키워드, `[제안]` 의 근거 실재, 스텁 표현
부재를 검사한다.

이어서 **리뷰어 evidence 로그 3개가 실제로 존재하고 비어 있지 않은지** 확인한다.

```bash
for r in design engineering qa; do
  test -s "docs/plan/logs/review/$r.log" || echo "evidence 로그 누락: $r"
done
```

게이트가 리뷰어의 자기보고가 아닌 디스크의 파일을 보는 이유 — "검토했음"만 반환하고 로그를 남기지
않은 경우를 잡기 위함이다.

두 검사를 통과한 후에만 Step 10 으로 진행한다.

### Step 10: 미리보기와 사용자 승인

```
## PRD 미리보기 — {기능명}

- 로컬: docs/plan/PRD-{slug}.md
- 발행 예정: {부모 페이지} > PRD — {기능명}
- 구성: 섹션 10/10 · US {n} · FR {n} · NFR {n} · AC {n}
- 검토: design {verdict} / engineering {verdict} / qa {verdict} (수정 {revision_count}회차)

## 팀 확정이 필요한 [제안] 수치 ({n}건)

| ID | 지표 | 초안 목표 | 근거 |
|----|------|-----------|------|
| M-2 | 가입 이탈률 | [제안] 30% 이하 | ... |

## 리뷰어 advisory ({n}건)

- [engineering] E-1: DEP-1 메일 채널 발송 한도가 가입 급증 시 병목 가능

이대로 Notion 에 발행할까요? (발행 / 수정 요청 / 취소)
```

`[제안]` 이 0건이면 해당 섹션은 `(없음)` 으로 표기하되 섹션 자체는 유지한다 — 사용자가 "초안
수치가 없다"는 사실을 확인할 수 있어야 한다.

**사용자 승인 없이 Notion 에 쓰지 않는다.**

### Step 11: Notion 발행과 완료 보고

`notion-search` 로 부모 페이지를 찾고, `notion-create-pages` 로 `PRD — {기능명}` 페이지를 그 하위에
만든다. 발행 후 로컬 문서의 frontmatter 를 갱신한다: `notion_page` 에 URL, `status: reviewed`,
`updated` 를 당일로.

> ❗ **완료 선언 금지 지점**: Notion 등록이 끝나도 그 자체를 "완료"로 보고하지 않는다.
> frontmatter 갱신까지 마친 뒤에만 아래 보고를 출력한다. "발행 성공 = 작업 완료"로 조기 선언하는
> 실패 모드를 막는 게이트다.

```
## PRD 작성 완료

- 기능명: {기능명}
- 로컬: docs/plan/PRD-{slug}.md
- Notion: {부모 페이지} > PRD — {기능명}
- 구성: 섹션 10/10 · US {n} · FR {n} · NFR {n} · AC {n}
- 검토: design/engineering/qa 3개 모두 pass (수정 {revision_count}회차)
- 리뷰 로그: docs/plan/logs/review/{design,engineering,qa}.log

⚠ [제안] {n}건 — 팀 확정 필요
  - M-2 가입 이탈률 30% 이하
  - M-3 예약 문의 20% 감소
  위 수치는 모델이 업계 관행으로 제안한 초안이다. 합의된 목표가 아니다.
```

`[제안]` 을 완료 보고에 다시 올리는 이유 — 문서 안에만 표기하면 사용자가 그 부분을 읽지 않고 PRD
전체를 합의된 것으로 취급할 수 있다. 0건이면 이 블록을 생략한다.

---

## 루프 감지와 전략 전환

LLM은 실패 시 동일한 접근을 약간만 바꾸어 반복한다. 리뷰어가 계속 `revise` 를 반환하거나 사용자
수정 요청이 반복되는 상황을 탐지해 무한 루프를 차단한다.

`revision_count` 를 frontmatter 에 누적 기록한다. **3회 도달 시 같은 접근을 재시도하지 않고**
전략 전환을 제안한다:

- 범위를 좁혀 기능 1개짜리 PRD로 다시 쓴다
- 원본 문서가 얇아 도출이 계속 빗나가는 경우 → 원본 보강을 요청한다
- 계속 걸리는 항목을 섹션 9 위험·가정으로 이관하고 이번 버전에서는 미해결로 남긴다

"조금 더 잘 써줘" 같은 요청은 이전 접근을 유지한 재시도이므로 카운트가 증가한다.
이것은 자기평가 편향과 무한 루프에 대한 하드 가드이며, 수렴 실패를 사람의 개입으로 돌려보내는 탈출구다.

---

## 핵심 제약 조건

1. **필수 입력 2개 게이트**: 원본 문서·Notion 부모 페이지 중 하나라도 누락 시 묶어 질의 후 종료. 추측으로 메우지 않는다.
2. **10개 섹션 전부 필수**: 하나도 생략하지 않는다. 내용이 없으면 비워두지 말고 위험·가정으로 이관한다.
3. **slug 는 스크립트로만 결정**: `${CLAUDE_PLUGIN_ROOT}/skills/create-prd/scripts/prd_slug.py` 출력을 쓴다. 모델이 kebab-case 를 만들지 않는다.
4. **기존 PRD 덮어쓰기 금지**: `update`/`new`/`abort` 를 사용자가 명시적으로 고르기 전까지 쓰지 않는다(기본 `abort`).
5. **모든 FR 은 AC 를 가진다**: 원문 흔한 실수 ③. 게이트가 강제한다.
6. **모든 FR 은 US 를 참조한다**: 목표와 연결되지 않은 기능을 넣지 않는다.
7. **Given-When-Then 키워드는 영어 유지**: 원문 지정 형식이며 grep 가능해야 한다.
8. **구현 방법 서술 금지**: PRD는 기술 명세서가 아니다. 스키마·라이브러리·파일 경로·아키텍처 결정을 쓰지 않는다.
9. **`[제안]` 표기 필수**: 원본에 없는 수치는 예외 없이 `[제안]` + 근거. 근거 컬럼이 있는 표 안에만 쓴다.
10. **리뷰어 3개 병렬·별개 컨텍스트**: 순차 실행 금지, 같은 컨텍스트 실행 금지. 원문 Step 6 이자 자기평가 편향 차단 장치다.
11. **리뷰어는 PRD를 수정하지 않는다**: findings 만 반환한다. 수정 주체와 검토 주체를 분리한다.
12. **verdict 기본값은 `revise`**: 통과를 증명해야 pass.
13. **evidence 로그 없이 통과 없음**: Step 9 가 로그 3개의 실재·비공백을 확인한다.
14. **발행 전 미리보기 필수**: 사용자 승인 없이 Notion 에 쓰지 않는다.
15. **조기 완료 선언 금지**: Notion 발행 후 frontmatter 갱신까지 마친 뒤에만 완료 보고.
16. **`[제안]` 은 완료 보고에 재노출**: 문서 안 표기만으로는 사용자가 놓친다.
17. **모든 출력은 한국어**: 문서 본문·안내 메시지 모두. `Given`/`When`/`Then` 과 `As a`/`I want`/`so that` 골격만 영어를 유지한다.
18. **짧고 명확하게**: 원문 베스트 프랙티스 ①. 분량으로 완성도를 대체하지 않는다. 각 섹션은 읽는 사람이 판단할 수 있는 최소량을 목표로 한다.

---

## 사용하는 Notion MCP 도구

| 도구 | 용도 |
| --- | --- |
| `notion-search` | 원본 문서 검색(Step 0), 부모 페이지 검색(Step 11) |
| `notion-fetch` | 원본 문서 전문 로드 (Step 0) |
| `notion-create-pages` | 부모 페이지 하위에 PRD 페이지 발행 (Step 11) |

`engineering-reviewer` 는 기술 토큰 실존성 확인에 `context7` MCP → `WebSearch` 폴백을 쓴다.
생성 주체는 이 도구를 직접 호출하지 않는다 — 자기평가 편향 차단을 위한 권한 분리다.

## 참조 문서

- [`references/prd_template.md`](./references/prd_template.md) — 10개 섹션 템플릿·형식 계약·`[제안]` 규칙·쓰지 말아야 할 것
- [`references/reviewer_contract.md`](./references/reviewer_contract.md) — 리뷰어 3개 공통 입출력 계약·담당 경계
- [`references/golden_example.md`](./references/golden_example.md) — 원문의 Journey-Forge 여행자 로그인 종단간 예제 (게이트 통과 확인됨)
- [`agents/design-reviewer.md`](./agents/design-reviewer.md) · [`agents/engineering-reviewer.md`](./agents/engineering-reviewer.md) · [`agents/qa-reviewer.md`](./agents/qa-reviewer.md) — Step 8 병렬 기동 서브에이전트
- `${CLAUDE_PLUGIN_ROOT}/skills/create-prd/scripts/prd_slug.py` — 기능명 → 결정적 경로 slug (한국어 대응)
- `${CLAUDE_PLUGIN_ROOT}/skills/create-prd/scripts/validate_prd.py` — 10개 섹션·GWT·FR↔AC·`[제안]` 근거 차단 게이트
