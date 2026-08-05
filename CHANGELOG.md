# Changelog

## 1.2.0

Claude 와 Cursor 를 번갈아 쓸 때 같은 규칙을 두 벌 관리하게 되는 문제를 플러그인으로 옮겼다.
이 저장소 자신이 그 문제의 표본이었다 — `.claude/rules/git-branch-workflow.md` 와
`.cursor/rules/git-branch-workflow.mdc` 를 손으로 미러링하고 있었고, 갈라져도 에러가 나지 않아
검출할 방법이 없었다. 프로젝트를 새로 열 때마다 이 세트를 다시 만드는 것도 반복 작업이었다.

해법은 **`AGENTS.md` 를 단일 소스로 삼는 것**이다. `CLAUDE.md` 가 `AGENTS.md` 를 가리키기만
하면 두 파일이 갈라질 여지 자체가 없어진다. 갈라질 수 있는 건 생성물인 `.mdc` 사본 하나로
좁혀지고, 그 하나는 바이트 비교로 확실히 잡을 수 있다 — 검출 불가능한 문제를 검출 가능한
문제로 바꾸는 교환이다.

### 추가

- **`project-conventions`** (2 스킬) — `init-agent-rules`, `check-agent-rules`.
  `init-agent-rules` 는 `CLAUDE.md` 본문을 `AGENTS.md` 로 이관하고(`git mv` 로 rename 히스토리
  보존), `CLAUDE.md` 를 `@AGENTS.md` 포인터로 재작성한 뒤, git 브랜치 워크플로 규칙을
  `.claude/rules/` 와 `.cursor/rules/` 양쪽에 동일 본문으로 설치한다.
  `check-agent-rules` 는 그 구조가 유지되는지 6개 항목으로 검사한다.
- `scripts/install_agent_rules.py` — 이관·렌더·마커 블록 삽입을 결정적으로 수행한다.
  모델이 파일을 직접 쓰지 않는 이유는 `.mdc` 사본이 `.md` 원본과 **바이트 단위로** 같아야
  하기 때문이다. 손으로 옮겨 쓰면 공백 하나로 어긋나는데, 그게 이 플러그인이 막으려는 실패다.
  재실행 시 마커 블록 구간만 교체하므로 멱등하다.
- `scripts/check_agent_rules.py` — 6개 검사. 핵심은 5번(`.mdc` 본문 == `.md` 본문)이고,
  나머지는 5번이 의미를 갖는 구조를 지킨다. exit 1 이므로 pre-commit 훅에 걸 수 있다.

### 설계상 거부한 것

- **자동 병합.** `AGENTS.md` 가 이미 있으면 중단하고 사용자에게 선택을 넘긴다. 어느 쪽이
  최신인지는 파일 내용만으로 판정할 수 없고, 잘못 합친 규칙은 없는 규칙보다 나쁘다.
- **`CLAUDE.md` 뼈대 생성.** `CLAUDE.md` 가 없으면 실행을 거부하고 `/init` 을 안내한다.
  프로젝트 지시를 추측으로 채우면 그 추측이 이후 모든 세션의 전제가 된다.
- **규칙 카탈로그.** 지금 필요한 건 git 워크플로 하나다. 선택지가 1개인 메뉴를 만들지 않는다.

### 변경

- `README.md` 플러그인 표에 `product-planning` 을 추가했다. 1.1.0 에서 누락됐던 것으로,
  `validate-marketplace.sh` 가 README 를 보지 않아 검출되지 않았다.

## 1.1.0

제품 기획 계열 플러그인을 추가했다. 노션 페이지
[Mastering PRDs in Product Management](https://app.notion.com/p/3ac09f96fe5281979f9dca1cba4a589a)
(원문: Medium / khutumadesewa) 이 정의하는 10개 섹션·6단계 작성법·4가지 흔한 실수를 계약으로 삼는다.

### 추가

- **`product-planning`** (1 스킬) — `create-prd`.
  노션 문서·회의록을 PRD 10개 섹션으로 정규화하고, 모든 기능 요구사항에 Given-When-Then
  수용기준을 도출한다. 원문 Step 6("PRD는 혼자 작성하는 것이 아니다")을
  **디자인·엔지니어링·QA 리뷰어 서브에이전트 3개 병렬 기동**으로 구현했다 — 생성자와 검증자를
  분리해야 자기평가 편향이 걸리지 않으므로, 원문의 요구와 저장소 규약이 같은 장치로 수렴한다.
- `scripts/prd_slug.py` — 기능명 → 결정적 경로 slug.
  `release-plan` 의 `slugify.py` 는 비-ASCII 를 전부 버려 순수 한글 입력이 `untitled` 이 된다.
  PRD 기능명은 한글이 기본이라 그대로 쓰면 모든 PRD가 `docs/plan/PRD-untitled.md` 하나로
  충돌한다(`결제 API 연동` 과 `인증 API 개편` 처럼 부분 ASCII 도 둘 다 `api` 로 붕괴).
  알파뉴메릭이 유실된 경우에만 원본 이름의 결정적 해시를 덧붙여 구분한다. 두 스크립트는
  용도가 달라 통합하지 않는다.
- `scripts/validate_prd.py` — 10개 섹션 실재, 유저스토리 형식, 모든 `FR-n` 의 수용기준 참조,
  Given-When-Then 키워드, `[제안]` 수치의 근거 실재, 스텁 표현 부재를 검사하는 차단 게이트.

### 변경

- **`scripts/validate-marketplace.sh` 가 플러그인 목록을 `marketplace.json` 에서 읽는다.**
  검사 4·5 가 플러그인 이름 4개를 하드코딩하고 있어, 신규 플러그인은 네임스페이스 검사와
  스크립트 경로 검사를 *실패하지 않고 아예 건너뛰었다* — 미수행이 통과처럼 보였다.
- **검사 4 의 dangling 참조 검출을 수정했다.** 이전 구현은 "찾은 참조"만 출력한 뒤 그것의 존재를
  다시 확인해 항상 통과했다. 어느 플러그인에도 없는 스크립트 참조가 검출되지 않았다.
  스킬 디렉토리 패턴도 `[a-z-]+` → `[a-z0-9-]+` 로 넓혔다.

## 1.0.0

첫 릴리즈. [`kbk109-dev/ClaudeCodeSkills`](https://github.com/kbk109-dev/ClaudeCodeSkills)
v1.9.1 의 스킬 14개를 플러그인 마켓플레이스로 재구성했다. 이후 유지보수는 이 저장소에서 한다.

### 추가

- **`expo-app-kit`** (4 스킬) — `admob-plan`, `admob-impl`, `admob-impl-harness`, `ota-hotfix`
- **`firebase-observability`** (4 스킬) — `firebase-analytics-plan|impl`,
  `firebase-crashlytics-plan|impl`
- **`release-workflow`** (4 스킬) — `release-plan`, `release-impl`, `fix-plan-impl`,
  `main-branch-merge`
- **`harness-devkit`** (2 스킬) — `harness-dev`, `dev-monitor`
- `scripts/validate-marketplace.sh` — 매니페스트·스크립트 경로·네임스페이스 정합성 검사
- `docs/harness-engineering/` — 배경 문서 2편

### 변경 (이관에 따른 것)

- **스크립트 경로를 `${CLAUDE_PLUGIN_ROOT}` 기준으로 하드닝** (91건).
  이전에는 `scripts/x.py`, `skills/release-impl/scripts/x.py`, `{skill_root}/scripts/x.py`
  세 형태가 섞여 있었고 셋 다 cwd 에 의존해 사용자 프로젝트에서 경로가 깨졌다.
  이제 전부 `${CLAUDE_PLUGIN_ROOT}/skills/<스킬>/scripts/x.py` 다.
- **스킬 간 호출을 네임스페이스화** (89건). 플러그인 스킬은 bare 이름으로 호출되지 않으므로
  `/release-plan` → `/release-workflow:release-plan`,
  `/dev-monitor` → `/harness-devkit:dev-monitor` 형태로 바꿨다.
  파일 경로 안의 같은 문자열(`docs/skills/release-impl/` 등 134건)은 보존했다.
- `admob-impl-harness.skill` 번들 제거. 같은 스킬의 오래된 zip 사본이었고(내부 SKILL.md 10578B
  vs 실제 10862B), 플러그인은 loose 파일을 로드하므로 중복이면서 원본과 어긋나 있었다.

### 제외한 것

- **`test-*` 16개** — `oh-my-connect-cowork-url` 프로젝트 루트의 `agents/N_*.md` 와
  `data/{date}_vN/` 에 직접 의존해 다른 환경에서 동작하지 않는다. 해당 프로젝트에 남긴다.
- **`brand-application`, `decision-council`** — ClaudeCodeSkills 에 없는 외부 유래 스킬.
  출처가 불명확한 상태로 MIT 재배포하지 않는다.
