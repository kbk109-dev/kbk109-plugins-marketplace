# Changelog

## 1.5.0

`git-branch-workflow` 규칙이 **`main` 에서 바로 분기해 `main` 으로 되돌려 머지**하고 있었다.
에이전트가 릴리스 브랜치를 직접 움직인다는 뜻이고, 사람이 릴리스 시점을 고를 여지가 없었다.
`dev` 를 에이전트가 다루는 최상단으로 두고 `main` 은 사람에게 남긴다.

### 변경 — `project-conventions` 1.2.0 → 1.3.0

- **작업 기점이 `dev` 로 바뀌었다** (규칙 1절). `main` 에 있으면 `dev` 로 이동한 뒤 분기하고,
  `dev` 가 없으면 `git switch -c dev <main>` 으로 **묻지 않고 만든다.** dev 의 존재는 규칙의
  전제이지 사용자에게 확인받을 선택지가 아니다.
- **`main` 머지를 금지했다** (5절). 작업 브랜치는 `dev` 로만 `--no-ff` 머지하고, `main` 체크아웃
  후의 머지·리베이스·푸시·태그를 에이전트가 수행하지 않는다. `dev` → `main` 은 사람이 직접 한다.
- **3절 "이미 다른 브랜치에 있을 때" 를 신설했다.** `main` 도 `dev` 도 아닌 브랜치에서는
  `git log --oneline dev..HEAD` 로 하던 일을 확인한 뒤 **이어서 계속**할지 **`dev` 로 머지하고 새
  브랜치**를 팔지 에이전트가 스스로 정한다. 되묻지 않는 대신 판단 근거를 한 줄로 밝힌다 —
  기준을 문서에 적어 두고도 매번 묻는 것은 결정을 떠넘기는 것이다.
  미커밋 변경의 커밋 승인을 못 받았으면 **"이어서 계속"으로 고정**한다. 브랜치 정리가 커밋 게이트를
  우회하는 뒷문이 되면 안 되기 때문이다.
- **6절 스킬 예외에 `main` 금지의 유일한 구멍을 명시했다** — 사용자가 릴리스 스킬
  (`/release-workflow:main-branch-merge` 등)을 **직접 호출한** 경우. 사람이 그 시점을 고른 것이므로
  5절의 "사람이 직접"에 해당한다. 에이전트가 스스로 그 스킬을 불러 `main` 에 머지하는 것은 금지다.
  이 문장이 없으면 "어떤 경우에도 금지"와 릴리스 자동화가 정면으로 충돌한다.
- 커밋 게이트가 3절 → **4절**로 밀렸다. `--pre-commit-check` 를 설명하는 `SKILL.md` 두 곳과
  eval 4 의 절 번호를 함께 고쳤다.
- `.mdc` 프론트매터 `description` 을 새 동작으로 교체했다 (`install_agent_rules.py` 의
  `RULES[…]["mdc_description"]`). `--sync-mdc` 는 **기존 프론트매터를 보존**하므로 설치된
  프로젝트에서는 이 한 줄이 자동으로 갱신되지 않는다 — 이 저장소 사본은 손으로 맞췄다.

dev 브랜치명은 `dev` 리터럴로 고정했다. `{{DEV_BRANCH}}` 플레이스홀더와 `--dev-branch` 인자를
추가하는 안도 있었지만, `{{MAIN_BRANCH}}` 와 달리 dev 는 **이 규칙이 도입하는 브랜치**여서
탐지 대상이 아니다 — 없으면 만들 뿐이다. `develop` 을 쓰는 프로젝트는 설치 후 `.md` 를 고치고
`--sync-mdc` 로 사본을 맞춘다.

이 저장소 자신의 `.claude/rules/git-branch-workflow.md` 와 `.cursor/rules/*.mdc` 도 같이 갱신했고,
`dev` 브랜치를 만들었다.

## 1.4.0

1.3.0 의 codegraph 검색 규칙이 **서브에이전트에는 닿지 않고 있었다.** 규칙이 메인 세션에 도달하는
경로는 프로젝트 지시로 로드되는 `.claude/rules/codegraph-search.md` 와 codegraph 가 제공하는
`UserPromptSubmit` 훅 둘인데, 서브에이전트는 **사용자 프롬프트로 시작하지 않으므로** 후자가
구조적으로 발화할 수 없고 전자의 상속도 보장되지 않는다. 그래서 메인 세션은 codegraph 를 쓰는데
서브에이전트만 grep 부터 잡았다.

문서로 타이르는 대신 **강제**했다 — "정규식·스크립트로 시행 가능한 제약은 자동화한다"는 이 저장소
원칙 그대로다.

### 추가

- **`project-conventions/hooks/codegraph_subagent_guard.py`** — `PreToolUse` 훅(matcher
  `Agent|Task`). 서브에이전트 디스패치를 가로채 `updatedInput` 으로 프롬프트 끝에 codegraph 검색
  지시를 물리적으로 심는다. 유일하게 반드시 실행되는 지점이 부모 프로세스의 도구 호출이므로
  여기를 잡았고, 결과적으로 **모델의 협조가 필요 없다.** 프롬프트에 이미 `codegraph` 가 있으면
  덧붙이지 않는다 — 멱등성이자 호출자의 명시적 탈출구다.
- **`codegraph-search` 규칙 5절 "서브에이전트에도 적용된다"** — 훅이 없는 환경(Cursor, 플러그인
  미설치)을 위해 손으로 붙일 짧은 인용문을 담았다. 훅이 넣는 블록과 이 인용문은 길이가 다르다.
  훅 쪽은 아무 맥락 없는 서브에이전트가 혼자 이해해야 해서 더 길다 — 사본이 아니므로 바이트
  동일성을 요구하지 않는다.

### 변경

- **`hooks/` 금지가 조건부 허용으로 바뀌었다.** `AGENTS.md` 의 "넣지 않는 것"에서 `hooks/` 와
  `.mcp.json` 이 한 항목으로 묶여 있었는데, 근거는 MCP 재정의 충돌뿐이라 훅까지 같이 막고 있었다.
  분리하고, 플러그인 훅은 **(1) 대상 프로젝트 조건을 스스로 판정해 미충족이면 무출력 (2) 전 구간
  fail-open** 둘을 모두 만족할 때만 허용하도록 다시 썼다. 플러그인 훅은 켜진 모든 프로젝트에서
  발화하므로 이 둘이 곧 "전역 발화해도 안전하다"의 정의다.
- **`validate-marketplace.sh` 가 훅 자산도 검사한다.** 검사 1이 `-path '*.claude-plugin*'` 로만
  JSON 을 훑어 `hooks/hooks.json` 은 파싱 검사조차 받지 않았고, 검사 4의 dangling 스캔도
  `${CLAUDE_PLUGIN_ROOT}/skills/…/scripts/…` 형태만 봤다. 둘 다 넓혔다 — 훅 설정은 깨져도 에러 없이
  등록만 안 되므로, 검사 밖에 두면 훅이 죽은 채 배포된다.

### 구현 중 잡은 것

- **`~/.codegraph` 전역 오탐.** 색인 탐색을 무한정 위로 올리면 홈 디렉토리에서 `codegraph init` 을
  한 번 잘못 실행해 생긴 `~/.codegraph` 하나가 홈 아래 **모든** 프로젝트를 "색인됨"으로 만든다.
  이 개발 환경에 실제로 그런 디렉토리가 있어 첫 구현이 무관한 저장소에서도 주입했다.
  탐색을 **git 저장소 루트와 `$HOME` 에서 멈추도록** 경계를 넣었다. 대가로 바깥 저장소에 색인을 둔
  git 서브저장소는 놓치지만, 그건 조용한 no-op 이고 반대쪽은 전 프로젝트 소음이다.

### 설계상 거부한 것

- **프로젝트 `.claude/settings.json` 에 훅 설치.** `init-agent-rules` 가 훅을 프로젝트마다 심는
  방식도 가능했지만, settings.json 병합 로직과 그 병합을 검사할 항목이 새로 필요하다. 플러그인이
  훅을 들고 다니면 프로젝트에 설치되는 산출물이 하나도 늘지 않는다 — 대신 no-op 판정과 fail-open
  책임이 훅 스스로에게 넘어오고, 그게 위 "구현 중 잡은 것"이 중요해진 이유다.
- **Grep/Glob 호출 자체를 막는 훅.** 규칙 2절이 인정하듯 문자열·설정값 검색은 grep 이 맞다.
  전부 막으면 정당한 검색까지 깨지고, 세션당 첫 호출만 막는 식의 상태 관리는 서브에이전트가
  부모의 session_id 를 공유해 성립하지 않는다.
- **훅 블록과 규칙 본문의 바이트 동일 검사.** 둘은 독자가 다르다(서브에이전트 vs 사람). 사본이
  아닌 것에 사본 검사를 걸면 의도적 차이를 고칠 때마다 검사가 실패한다.

## 1.3.0

`project-conventions` 에 두 번째 규칙 — **코드 검색은 codegraph 로** — 를 넣었다. 규칙이 하나에서
둘이 되면서 스킬의 하드코딩 구조가 드러났다. `RULE_NAME = "git-branch-workflow"` 상수가 설치·검사
스크립트 양쪽에 박혀 있었고 규칙 목록도 루프도 없었다. 규칙 테이블 + 순회 구조로 바꿨다.

### 추가

- **`codegraph-search` 규칙** — 심볼·호출 관계를 찾을 때 grep 대신 codegraph 를 먼저 쓰고,
  **호출할 수 없으면 경고 한 줄을 띄운 뒤 grep·Glob 으로 폴백**한다. 멈추지 않는 이유는 검색이
  대개 더 큰 작업의 중간 단계라서이고, 그렇다고 조용히 넘어가면 검색 품질이 떨어진 걸 사용자가
  모르기 때문이다. 색인 생성(`codegraph init`)은 제안만 하고 승인 없이 실행하지 않는다.
- **`--codegraph-rule {auto,on,off}`** — `auto` 는 프로젝트 루트의 `.codegraph/` 존재로 판정한다.
  색인 없는 프로젝트에 이 규칙을 넣으면 매 검색마다 쓸 수 없는 도구를 시도하고 경고를 띄우므로
  규칙이 소음이 된다.

### 변경

- **규칙 1개 → N개 구조.** `install_agent_rules.py` 와 `check_agent_rules.py` 가 규칙 테이블을
  순회한다. `AGENTS.md` 마커 블록은 규칙마다 한 쌍이고, `--sync-mdc` 는 설치된 모든 규칙을
  미러링한다. 마커 문자열 형식(`<!-- >>> agent-rules: {name} >>> -->`)은 그대로 두었다 —
  기존 설치본의 블록이 그대로 매칭돼야 재실행이 멱등하다.
- **검사 4·5·6 이 규칙별로 반복된다.** 어떤 규칙이 "설치돼 있다"는 판정은 `.md`·`.mdc`·마커 블록
  셋 중 하나라도 있으면 참이고, 그때부터 셋 다 정합해야 한다 — 반쪽 설치를 조용한 통과로 만들지
  않으려는 것이다. 셋 다 없는 선택 규칙은 건너뛴다. 색인이 없어 codegraph 규칙을 안 쓰는 프로젝트는
  정상 상태이지 갈라짐이 아니다.
- 선택되지 않은 규칙은 **건너뛸 뿐 지우지 않는다.** 색인을 잠시 지운 상태에서 재설치했다는 이유로
  쓰던 규칙이 사라지면 안 된다. 규칙 제거는 수동이다.

### 설계상 거부한 것

- **규칙 카탈로그 (재확인).** 1.2.0 에서 거부한 그대로다. 규칙이 둘이 됐어도 사용자가 고르는 메뉴는
  만들지 않았다 — codegraph 규칙이 필요한지는 `.codegraph/` 존재 여부가 이미 답하고 있으므로,
  물어보는 건 사용자에게 같은 정보를 다시 입력시키는 것이다. `--codegraph-rule on|off` 는 그 판정을
  뒤집는 탈출구이지 선택 메뉴가 아니다.

## 1.2.1

`project-conventions` 를 이 저장소 자신에게 적용했다. 첫 사용에서 구멍이 하나 드러났다.

규칙 파일은 플러그인 템플릿에서 렌더되는데, 검사 스크립트가 비교하는 대상은 템플릿이 아니라
`.claude/rules/` 의 `.md` 원본이다. 그래서 프로젝트 고유 규칙을 `.md` 에 추가하면 검사는
통과하지만, 다음 전체 재설치가 그 수정을 템플릿 내용으로 덮어썼다. 규칙을 커스터마이즈한
프로젝트는 재설치를 할 수 없는 셈이었다.

### 추가

- **`--sync-mdc`** — `.cursor/rules/*.mdc` 를 템플릿이 아니라 **현재 `.md` 본문**으로 다시
  미러링한다. `CLAUDE.md`·`AGENTS.md`·`.md` 원본은 건드리지 않는다. 이제 규칙을 고치는 절차가
  "`.md` 를 고치고 `--sync-mdc`" 로 정리되고, 이것이 검사 스크립트의 비교 기준과도 일치한다.
  기존 `.mdc` 의 프론트매터는 보존한다.

### 변경

- **이 저장소가 `AGENTS.md` 를 단일 소스로 쓴다.** `CLAUDE.md` 본문을 `AGENTS.md` 로 옮기고
  (`git mv` 로 rename 히스토리 보존) `CLAUDE.md` 는 `@AGENTS.md` 포인터만 남겼다.
  손으로 미러링하던 `.cursor/rules/git-branch-workflow.mdc` 는 이제 생성물이다.
- `.claude/rules/git-branch-workflow.md` 의 저장소 고유 항목 3곳(브랜치명 예시,
  "기존 관례" 단서, `/release-workflow:main-branch-merge` 예외 조항)은 템플릿에서 일반화되며
  빠졌던 것을 복원하고, 재설치 시 사라진다는 주의를 규칙 안에 적어 두었다.

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
