# AGENTS.md

이 문서는 Claude Code 와 Cursor 가 이 저장소에서 작업할 때 따르는 지시다.

## Behavioral Guidelines (Karpathy)

세션마다 지키는 행동 가드레일. 프로젝트 규칙보다 위에 둔다.
신중함 편향 — 사소한 작업은 판단으로 건너뛴다.

1. **Think Before Coding (생각 먼저)** — 가정하지 않는다. 해석이 여럿이면 제시하고, 불분명하면 멈춰 묻는다.
2. **Simplicity First (단순함 우선)** — 문제를 푸는 최소 코드만. 요청 안 한 기능·추상화·유연성을 넣지 않는다.
3. **Surgical Changes (외과적 수정)** — 요청에 추적되는 줄만 고친다. 인접 코드·포맷을 "개선"하지 않는다.
4. **Goal-Driven Execution (목표 주도 실행)** — 검증 가능한 성공 기준을 정하고, 통과할 때까지 루프한다.

원문: https://github.com/forrestchang/andrej-karpathy-skills

## 커뮤니케이션

사용자와는 **한글로** 소통한다. 커밋 메시지·코드 주석·기술 고유명사는 기존 관례를 따르되,
설명·질문·요약·확인 요청은 한국어로 한다.

## 이 저장소의 성격

**Claude Code 커스텀 플러그인을 제작·배포하는 저장소다.** 남의 스킬을 담아 두는 곳이 아니다 —
스킬과 훅을 직접 집필해 플러그인으로 묶고, 그것을 배포하는 마켓플레이스이기도 하다.
이 구분이 아래 "두 가지 불변식"을 낳는다.

**스킬의 SSoT 는 여기다.** `~/.claude/skills/` 에서 고쳐 여기로 복사하지 말 것 — 사본이 갈라진다.
([`kbk109-dev/ClaudeCodeSkills`](https://github.com/kbk109-dev/ClaudeCodeSkills) v1.9.1 계승, 그쪽은 은퇴 예정)

빌드·컴파일 단계가 없다. 산출물은 마크다운 지시 문서와 파이썬/셸 검증 스크립트다.
플러그인·스킬을 새로 만드는 절차는 `.claude/skills/new-plugin/SKILL.md` 에 있다 — 만들 때만
필요한 순서라서 분리했다.

## 명령

```bash
# 정합성 검사 — 커밋 전 항상 실행. 아래 두 불변식을 이게 검사한다.
bash scripts/validate-marketplace.sh

# 로컬 설치 테스트 (푸시 전에 먼저 확인) — Claude Code 안에서:
#   /plugin marketplace add /Users/kdk109/Desktop/project/kbk109-plugins-marketplace
#   /plugin install <plugin>@kbk109-plugins-marketplace

# 스크립트 단위 확인 — 테스트 러너가 없으므로 직접 호출한다
python3 plugins/release-workflow/skills/release-plan/scripts/slugify.py "v2.1 Tasks"   # → v2-1-tasks
echo '["v1.9.0","v1.9.1"]' | python3 plugins/release-workflow/skills/fix-plan-impl/scripts/compute_next_patch.py
bash -n plugins/release-workflow/skills/release-impl/scripts/install_hooks.sh          # 셸 문법

# harness-devkit 훅 — feature_list.json 이 아닌 쓰기는 무출력이 정상. 출력이 나오면 경로 판정이 깨진 것.
HG=plugins/harness-devkit/hooks/harness_feature_list_gate.py
echo '{"cwd":"/tmp","tool_name":"Write","agent_id":"A","tool_input":{"file_path":"/tmp/a.ts","content":"x"}}' \
  | python3 -B $HG                                                                  # 무출력

# 픽스처가 필요하다. status "pending" 은 이 상태 머신에 없는 값이라 1번째는 deny, 같은 위반 2번째는 무출력(탈출구).
mkdir -p /tmp/hd-fixture/docs/harness/demo
P='{"cwd":"/tmp/hd-fixture","tool_name":"Write","agent_id":"A","tool_input":{"file_path":"/tmp/hd-fixture/docs/harness/demo/feature_list.json","content":"{\"features\":[{\"id\":\"F1\",\"acceptance_criteria\":[],\"status\":\"pending\"}]}"}}'
echo "$P" | python3 -B $HG   # → permissionDecision: deny
echo "$P" | python3 -B $HG   # → 무출력

# 검증 스크립트 — 훅과 같은 규칙 모듈을 쓰므로 판정이 일치해야 한다. 위반이 있으면 exit 1.
python3 -B plugins/harness-devkit/skills/harness-dev/scripts/validate_feature_list.py \
  /tmp/hd-fixture/docs/harness/demo/feature_list.json; echo "exit=$?"

# notion-api-only 훅 — 프로젝트 로컬 설치이므로 탈출구가 없다(harness 훅과 대조).
# 발화 조건은 "이 프로젝트에서 토큰을 구할 수 있는가" 하나뿐이다.
NG=plugins/project-conventions/skills/init-agent-rules/templates/notion_mcp_gate.py
env -u NOTION_TOKEN python3 -B $NG <<< \
  '{"cwd":"/tmp","tool_name":"mcp__claude_ai_Notion__notion-fetch","tool_input":{}}'   # 무출력(토큰 없음)
NOTION_TOKEN=dummy python3 -B $NG <<< \
  '{"cwd":"/tmp","tool_name":"mcp__claude_ai_Notion__notion-fetch","tool_input":{}}'   # deny — 재시도해도 계속 막힘
```

`evals/evals.json` 은 CLI 러너가 없다. `skill-creator:skill-creator` 플러그인이 소비하며,
케이스마다 서브에이전트 2개(`with_skill` / `without_skill`)를 동시 실행해 비교하는 방식이다.

## 구조와 두 가지 불변식

```
.claude-plugin/marketplace.json     플러그인 목록 (source: ./plugins/<name>)
plugins/<plugin>/
├── .claude-plugin/plugin.json      플러그인 매니페스트
└── skills/<skill>/SKILL.md         + scripts/ references/ agents/ evals/
```

매니페스트가 2단이다. **marketplace.json 과 plugin.json 의 `name` 이 반드시 일치**해야 하고
`source` 경로가 실제로 존재해야 한다. 아래 두 불변식은 위반해도 조용히 깨지기만 하고 에러가
안 나므로 `validate-marketplace.sh` 가 검사한다.

### 1. 스크립트 경로는 `${CLAUDE_PLUGIN_ROOT}` 기준

```
${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/slugify.py     # 옳음
scripts/slugify.py · skills/release-plan/scripts/slugify.py      # 깨짐
```

상대 경로는 cwd 에 의존하고, 스킬이 도는 cwd 는 저장소 루트가 아니라 **사용자의 프로젝트**다.

예외 — **프로젝트에 설치되는** 스크립트(플러그인이 번들한 것이 아니라
`project-conventions:init-agent-rules` 가 대상 프로젝트에 복사해 넣는 것, 예:
`.claude/scripts/notion_api.py`)는 이 규칙의 대상이 아니다. 그 파일은 애초에 프로젝트
루트 기준 고정 경로에 있으므로, 스킬이 `.claude/scripts/notion_api.py` 처럼 프로젝트
상대 경로로 참조하는 것이 옳다 — `${CLAUDE_PLUGIN_ROOT}` 를 붙이면 오히려 틀린 경로가 된다.

### 2. 스킬 간 호출은 `<plugin>:<skill>` 네임스페이스

```
/release-workflow:release-plan     # 옳음
/release-plan                      # 해석되지 않음
```

플러그인이 제공하는 스킬은 bare 이름으로 호출되지 않는다. 같은 문자열이 **파일 경로 안에도**
나타나므로(`docs/skills/release-impl/`) 일괄 치환 시 경로를 건드리면 안 된다. 호출 형태는
줄 시작·공백·백틱·괄호·따옴표 뒤에 오는 것만이다.

### 일괄 편집 시 한글 경계 함정

이 저장소 문서는 한국어다. 파이썬 `re` 의 `\b` 는 유니코드 인식이라 `/release-plan으로` 에서
`n`↔`으` 를 단어 내부로 봐 **매칭에 실패**한다 (grep 의 C 로케일 `\b` 는 매칭돼 집계가 어긋난다).
스킬명 뒤 경계는 `\b` 대신 `(?![A-Za-z0-9_-])` 로 쓴다.

## 스킬 아키텍처 — plan/impl 짝

스킬 18개 중 다수가 **계획 스킬 + 구현 스킬** 짝으로 동작한다. 계획 스킬이 문서를 쓰고,
구현 스킬이 그 문서를 상태 저장소로 읽는다. 계획 문서 없이 구현 스킬을 부르면 거부한다.

| 계획 | 산출 문서 | 구현 |
|---|---|---|
| `admob-plan` | `docs/plan/ADMOB-PLAN.md` | `admob-impl`, `admob-impl-harness` |
| `firebase-analytics-plan` | `docs/plan/GA_PLAN.md` | `firebase-analytics-impl` |
| `firebase-crashlytics-plan` | `docs/plan/CRASHLYTICS_PLAN.md` | `firebase-crashlytics-impl` |
| `release-plan` | Notion DB + `docs/skills/release-plan/{DB slug}/v{ver}/` | `release-impl` |

`release-workflow` 는 Notion 을 상태 저장소로(선택) 쓰고, 로컬 경로의 `{DB slug}` 를 반드시
`slugify.py` 출력으로 정한다 — 모델이 kebab-case 를 직접 만들면 경로가 호출마다 달라진다.
Notion 접근 방법은 플러그인이 모른다 — 프로젝트에 `notion-api-only` 규칙이 있으면 위임하고,
없으면 로컬 파일·사용자 입력으로 대체한다(자세한 내용은 `release-workflow/README.md`).

## Harness Engineering — 스킬 수정 시 지켜야 할 근거

전체 문서: [`docs/harness-engineering/`](./docs/harness-engineering/) ·
3-에이전트 하네스의 참조 구현: `harness-devkit:harness-dev`

**에이전트 = 모델 + 하네스.** 이 저장소 스킬들의 구조는 전부 LLM 의 5가지 구조적 실패 모드를
막기 위한 것이다. 아래 장치를 "불필요한 복잡성"으로 보고 걷어내지 말 것 — 각각이 특정 실패 모드에
대응한다.

| 실패 모드 | 스킬에 들어 있는 대응 장치 |
|---|---|
| 세션 간 상태 소실 | 상태 외부화 (`feature_list.json`, `PROGRESS.md`, Notion, `.state.json`) |
| 일회성 탐욕적 완료 | 스프린트 단위 실행, **한 번에 하나의 기능만** |
| 조기 완료 선언 | `status: "fail"` 기본값 + 증거 로그 없이는 pass 불가 게이트 |
| 자기평가 편향·무한 루프 | Generator/Evaluator 서브에이전트 분리, 동일 접근 3회 시 전략 전환 강제 |
| 훈련 컷오프 밖 할루시네이션 | 외부 출처(context7 MCP / WebSearch) 차단형 grounding 게이트 |

마지막 항목이 특히 중요하다. 모델 ID·패키지명·API 를 자기 기억으로 통과시키지 않는다.
**검증을 생성과 같은 컨텍스트에서 하면 자기평가 편향이 발동**하므로 별개 서브에이전트로 분리하고
evidence 로그만 증거로 인정한다 (`release-plan/agents/fact-checker.md` + `verify_tech_tokens.py`).

### SKILL.md 작성 규칙

- 프론트매터 `name` 은 kebab-case 이며 **디렉토리명과 일치**해야 한다 (검증 대상)
- `description` 은 "언제 트리거될지"의 계약서다. 워크플로 요약을 쓰지 말 것 — Claude 가 요약만 읽고
  본문을 건너뛴다. 구체적 트리거(에러 메시지·증상·도구명)와 동의어를 넣어 언더트리거를 막는다
- 본문 500줄 이하를 목표로 하고, 넘치면 `references/` 로 분리한다 (점진적 정보 공개).
  현재 초과하는 스킬은 없다(최대 `dev-monitor` 500줄). 가장 먼저 덜어낼 것은
  **산출 문서 템플릿**이다 — 특정 Phase 에서만 필요한데 분량이 크다
- 규칙을 나열할 때 **WHY 를 함께 쓴다.** Claude 는 충분히 똑똑하므로 모르는 맥락만 추가한다
- 정규식·스크립트로 시행 가능한 제약은 스킬 문서에 쓰지 말고 자동화한다 (아키텍처 강제)

## 이 저장소에 넣지 않는 것

되돌리는 판단이 이미 내려진 항목이다. "빠진 것 같아서" 추가하지 말 것.

- **프로젝트 전용 스킬** — `test-*` 16개는 `oh-my-connect-cowork-url` 프로젝트 루트의
  `agents/N_*.md` 와 `data/{date}_vN/` 에 직접 의존해 다른 환경에서 동작하지 않는다.
  해당 프로젝트의 `.claude/skills/` 에 둔다.
- **출처 불명 외부 스킬** — `brand-application`, `decision-council` 은 직접 집필한 것이 아니어서
  MIT 재배포 대상이 아니다.
- **`.skill` 번들** — 플러그인은 loose 파일을 로드하므로 zip 사본은 중복이고 원본과 어긋난다.
  `.gitignore` 에 등록돼 있다.
- **`.mcp.json`** — 스킬이 쓰는 MCP(context7 등)는 사용자 환경에 이미 연결돼 있다.
  플러그인이 재정의하면 충돌한다. Notion 은 예외다 — 이 저장소는 Notion MCP 를 플러그인이
  전제하는 것 자체를 지양하고, 토큰 기반 REST(`notion-api-only` 규칙)로 유도한다.
- **조건 없는 `hooks/`** — 플러그인 훅은 켜진 **모든 프로젝트**에서 발화한다. 기본은 넣지 않되,
  ① 조건 미충족이면 아무것도 출력하지 않고 ② 전 구간 fail-open 이며 ③ 도구를 차단한다면
  **복구 가능**한 훅만 허용한다. ③ 은 "같은 호출을 그대로 다시 하면 반드시 통과한다"는 뜻이다 —
  그래야 훅이 오판했을 때 최대 대가가 **도구 호출 한 번 재시도**로 유계이고, 그 유계성이 곧
  "전역 발화해도 안전하다"의 정의다. 사례는 `harness-devkit/hooks/` 의 훅 1개
  (설계 근거는 그 플러그인 README).
  **예외** — 이 ③ 은 플러그인이 번들해 **모든 프로젝트**에 뜨는 훅을 전제로 한다.
  `project-conventions:init-agent-rules` 가 사용자의 명시적 옵트인에 따라 **그 프로젝트에만**
  설치하는 `notion_mcp_gate.py` 는 전역 발화가 아니므로 이 요구사항의 적용 대상이 아니다 —
  탈출구 없이 영구 차단해도 된다(단, 토큰을 구할 수 있을 때만 발화 — 대체 경로 없이 막지
  않는다는 ①②는 그대로 지킨다).
- **`commands/`** — 18개 전부 스킬이고 스킬은 이미 `/plugin:skill` 로 호출된다. 래퍼는 중복이다.

## 버전 관리

변경 내역은 `CHANGELOG.md` 에 기록한다 (README 가 아니다).

버전은 **세 곳**에 있다.

| 위치 | 의미 |
|---|---|
| `plugins/<plugin>/.claude-plugin/plugin.json` 의 `version` | 그 플러그인의 버전 |
| `.claude-plugin/marketplace.json` 의 `plugins[].version` | 같은 플러그인의 버전 (사본) |
| `.claude-plugin/marketplace.json` 의 `metadata.version` | 마켓플레이스 자체의 버전 |

플러그인을 고치면 앞의 두 곳을 **함께** 올리고, 마켓플레이스 버전도 올린다.
**문서만 고치는 변경은 버전을 올리지 않는다** (`README.md`·`AGENTS.md` 등). 선례: `cdbba02`
**`validate-marketplace.sh` 검사 2 는 `name` 만 비교하고 `version` 은 비교하지 않는다** — 두 곳이
어긋나도 검사는 통과하므로 손으로 맞춰야 한다.

## 문서 구조

**이 파일이 에이전트 지시의 단일 소스다.** `CLAUDE.md` 는 `@AGENTS.md` 로 이 파일을 가져올
뿐이니 지시는 여기에 쓴다 — `CLAUDE.md` 에 쓰면 Cursor 가 못 읽어 두 도구가 갈라진다.
`project-conventions` 플러그인이 설치한 구조이며(이 저장소가 첫 사용처), 사본 정합성은
`/project-conventions:check-agent-rules` 로 검사한다.

<!-- >>> agent-rules: git-branch-workflow >>> -->
## Git 브랜치 워크플로

브랜치·커밋·머지 절차는 `.claude/rules/git-branch-workflow.md` 를 따른다.
Cursor 는 `.cursor/rules/git-branch-workflow.mdc` 로 같은 내용을 받는다.

이 블록은 `/project-conventions:init-agent-rules` 가 관리한다. 직접 고치지 말 것 —
재실행하면 덮어쓴다. 규칙 본문을 바꾸려면 `.claude/rules/git-branch-workflow.md` 를 고치고
`/project-conventions:check-agent-rules` 로 사본과의 일치를 확인한다.
<!-- <<< agent-rules: git-branch-workflow <<< -->
