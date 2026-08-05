# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 커뮤니케이션

사용자와는 **한글로** 소통한다. 커밋 메시지·코드 주석·기술 고유명사는 기존 관례를 따르되,
설명·질문·요약·확인 요청은 한국어로 한다.

## 이 저장소의 성격

Claude Code **플러그인 마켓플레이스**다. 스킬을 담는 저장소가 아니라, 스킬을 플러그인으로 묶어
**배포**하는 저장소다. 이 구분이 중요한 이유는 아래 "두 가지 불변식" 때문이다.

[`kbk109-dev/ClaudeCodeSkills`](https://github.com/kbk109-dev/ClaudeCodeSkills) v1.9.1 을 계승했다.
그 저장소는 은퇴 예정이며, 스킬의 SSoT 는 이제 여기다. 스킬을 `~/.claude/skills/` 에서 고치고
여기로 복사하는 식으로 작업하지 말 것 — 사본이 갈라진다.

빌드·컴파일 단계가 없다. 산출물은 마크다운 지시 문서와 파이썬/셸 검증 스크립트다.

## 명령

```bash
# 정합성 검사 — 커밋 전 항상 실행. 아래 두 불변식을 이게 검사한다.
bash scripts/validate-marketplace.sh

# 로컬 설치 테스트 (푸시 전에 이걸로 먼저 확인)
#   Claude Code 안에서:
#   /plugin marketplace add /Users/kdk109/Desktop/project/kbk109-plugins-marketplace
#   /plugin install <plugin>@kbk109-plugins-marketplace

# 스크립트 단위 확인 — 테스트 러너가 없으므로 직접 호출한다
python3 plugins/release-workflow/skills/release-plan/scripts/slugify.py "v2.1 Tasks"   # → v2-1-tasks
echo '["v1.9.0","v1.9.1"]' | python3 plugins/release-workflow/skills/fix-plan-impl/scripts/compute_next_patch.py
bash -n plugins/release-workflow/skills/release-impl/scripts/install_hooks.sh          # 셸 문법
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

매니페스트가 2단이다. 플러그인을 추가·개명할 때 **marketplace.json 과 plugin.json 의 `name` 이
반드시 일치**해야 하고, `source` 경로가 실제로 존재해야 한다.

스킬이 플러그인 안으로 들어오면서 두 가지가 평소와 달라진다. 둘 다 위반해도 조용히 깨지기만 하고
에러가 안 나므로 `validate-marketplace.sh` 가 검사한다.

### 1. 스크립트 경로는 `${CLAUDE_PLUGIN_ROOT}` 기준

```
${CLAUDE_PLUGIN_ROOT}/skills/release-plan/scripts/slugify.py     # 옳음
scripts/slugify.py                                               # 깨짐
skills/release-plan/scripts/slugify.py                           # 깨짐
```

상대 경로는 cwd 에 의존하는데, 스킬이 실행되는 cwd 는 **사용자의 프로젝트**다. 저장소 루트가 아니다.
이관 시 91건을 이 형태로 고쳤다.

### 2. 스킬 간 호출은 `<plugin>:<skill>` 네임스페이스

```
/release-workflow:release-plan     # 옳음
/release-plan                      # 해석되지 않음
```

플러그인이 제공하는 스킬은 bare 이름으로 호출되지 않는다. 이관 시 89건을 고쳤다.
같은 문자열이 **파일 경로 안에도** 나타나므로(`docs/skills/release-impl/` 등 134건) 일괄 치환 시
경로를 건드리면 안 된다. 호출 형태는 줄 시작·공백·백틱·괄호·따옴표 뒤에 오는 것만이다.

### 일괄 편집 시 한글 경계 함정

이 저장소 문서는 한국어다. 파이썬 `re` 의 `\b` 는 유니코드 인식이라
`/release-plan으로` 에서 `n`↔`으` 사이를 단어 내부로 판정해 **매칭에 실패**한다.
(grep 의 C 로케일 `\b` 는 매칭된다 — 그래서 두 도구의 집계가 어긋난다.)
스킬명 뒤 경계는 `\b` 대신 `(?![A-Za-z0-9_-])` 로 쓴다.

## 스킬 아키텍처 — plan/impl 짝

스킬 14개 중 다수가 **계획 스킬 + 구현 스킬** 짝으로 동작한다. 계획 스킬이 문서를 쓰고,
구현 스킬이 그 문서를 상태 저장소로 읽는다. 계획 문서 없이 구현 스킬을 부르면 거부한다.

| 계획 | 산출 문서 | 구현 |
|---|---|---|
| `admob-plan` | `docs/plan/ADMOB-PLAN.md` | `admob-impl`, `admob-impl-harness` |
| `firebase-analytics-plan` | `docs/plan/GA_PLAN.md` ⚠️ | `firebase-analytics-impl` |
| `firebase-crashlytics-plan` | `docs/plan/CRASHLYTICS_PLAN.md` | `firebase-crashlytics-impl` |
| `release-plan` | Notion DB + `docs/skills/release-plan/{DB slug}/v{ver}/` | `release-impl` |

⚠️ **알려진 불일치** — GA 계획 문서 파일명이 스킬 문서 안에서 `GA_PLAN.md`(4건)와
`GA_Plan.md`(4건)로 갈려 있다. 이관 전부터 있던 문제로 아직 통일하지 않았다.
대소문자 구분 파일시스템에서는 계획→구현 연결이 끊긴다. 이쪽을 건드릴 일이 있으면 함께 정리할 것.

`release-workflow` 는 여기서 한 단계 더 나아가 Notion 을 상태 저장소로 쓰고, 로컬 경로의
`{DB slug}` 를 반드시 `slugify.py` 출력으로 결정한다 — 모델이 kebab-case 를 직접 만들면
경로가 호출마다 달라져 세션 간 상태 연결이 끊긴다.

## Harness Engineering — 스킬 수정 시 지켜야 할 근거

전체 문서: [`docs/harness-engineering/`](./docs/harness-engineering/) ·
스킬 집필 도구: `harness-devkit:harness-dev`

**에이전트 = 모델 + 하네스.** 모델이 성능의 상한선이면, 하네스는 그 상한선에 얼마나 근접하는지를
결정한다. 이 저장소 스킬들의 구조는 전부 LLM 의 5가지 구조적 실패 모드를 막기 위한 것이다.
스킬을 고칠 때 아래 장치를 "불필요한 복잡성"으로 보고 걷어내지 말 것 — 각각이 특정 실패 모드에 대응한다.

| 실패 모드 | 스킬에 들어 있는 대응 장치 |
|---|---|
| 세션 간 상태 소실 | 상태 외부화 (`feature_list.json`, `PROGRESS.md`, Notion, `.state.json`) |
| 일회성 탐욕적 완료 | 스프린트 단위 실행, **한 번에 하나의 기능만** |
| 조기 완료 선언 | `status: "fail"` 기본값 + 증거 로그 없이는 pass 불가 게이트 |
| 자기평가 편향·무한 루프 | Generator/Evaluator 서브에이전트 분리, 동일 접근 3회 시 전략 전환 강제 |
| 훈련 컷오프 밖 할루시네이션 | 외부 출처(context7 MCP / WebSearch) 차단형 grounding 게이트 |

마지막 항목이 특히 이 저장소에서 중요하다. 모델 ID·패키지명·API 같은 외부 고유명사는 자기 기억으로
통과시키지 않는다. `release-plan` 의 `agents/fact-checker.md` + `verify_tech_tokens.py` 가
그 패턴의 구현체다 — **검증을 생성과 같은 컨텍스트에서 하면 자기평가 편향이 발동**하므로 별개
서브에이전트로 분리하고, evidence 로그 파일만을 증거로 인정한다.

### SKILL.md 작성 규칙

- 프론트매터 `name` 은 kebab-case 이며 **디렉토리명과 일치**해야 한다 (검증 대상)
- `description` 은 "언제 트리거될지"의 계약서다. 워크플로 요약을 쓰지 말 것 — Claude 가 요약만 읽고
  본문을 건너뛴다. 구체적 트리거(에러 메시지·증상·도구명)와 동의어를 넣어 언더트리거를 막는다
- 본문 500줄 이하를 목표로 하고, 넘치면 `references/` 로 분리한다 (점진적 정보 공개).
  현재 `firebase-crashlytics-impl`(549줄), `admob-plan`(535줄)이 초과 상태다 — 이 둘을 수정할 때는
  줄을 더 늘리지 말고 분리를 먼저 고려할 것
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
- **`hooks/`, `.mcp.json`** — 스킬이 쓰는 MCP(Notion, context7)는 사용자 환경에 이미 연결돼 있다.
  플러그인이 재정의하면 충돌한다.
- **`commands/`** — 14개 전부 스킬이고 스킬은 이미 `/plugin:skill` 로 호출된다. 래퍼는 중복이다.

## 버전 관리

변경 내역은 `CHANGELOG.md` 에 기록한다 (README 가 아니다). 플러그인을 고치면 해당
`plugin.json` 의 `version` 과 `marketplace.json` 의 같은 플러그인 `version` 을 함께 올린다 —
두 곳에 있으므로 한쪽만 올리면 어긋난다.

## 문서 구조

**이 파일이 에이전트 지시의 단일 소스다.** `CLAUDE.md` 는 `@AGENTS.md` 로 이 파일을 가져오기만
하므로, 지시를 추가·수정할 때는 여기에 쓴다. `CLAUDE.md` 에 쓰면 Cursor 가 읽지 못해 두 도구의
지시가 갈라진다.

이 구조는 `project-conventions` 플러그인이 설치한 것이다 — 이 저장소가 그 플러그인의 첫
사용처다. 규칙 파일과 사본의 정합성은 `/project-conventions:check-agent-rules` 로 검사한다.

<!-- >>> agent-rules: git-branch-workflow >>> -->
## Git 브랜치 워크플로

브랜치·커밋·머지 절차는 `.claude/rules/git-branch-workflow.md` 를 따른다.
Cursor 는 `.cursor/rules/git-branch-workflow.mdc` 로 같은 내용을 받는다.

이 블록은 `/project-conventions:init-agent-rules` 가 관리한다. 직접 고치지 말 것 —
재실행하면 덮어쓴다. 규칙 본문을 바꾸려면 `.claude/rules/git-branch-workflow.md` 를 고치고
`/project-conventions:check-agent-rules` 로 사본과의 일치를 확인한다.
<!-- <<< agent-rules: git-branch-workflow <<< -->
