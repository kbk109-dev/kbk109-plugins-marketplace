# kbk109 plugins marketplace

[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Marketplace](https://img.shields.io/badge/marketplace-1.12.0-blue)](./docs/release/v1.12.0.md)
[![Plugins](https://img.shields.io/badge/plugins-6-informational)](./plugins)

직접 제작한 Claude Code 커스텀 플러그인 모음. Harness Engineering 원칙으로 집필한 스킬 18개를
도메인별 6개 플러그인으로 묶어 배포한다.

> **Harness Engineering** — 에이전트 = 모델 + 하네스. 모델이 성능의 상한선이라면, 하네스는
> 그 상한선에 얼마나 근접하는지를 결정한다. 여기 실린 스킬들은 LLM의 5가지 구조적 실패 모드
> (세션 간 상태 소실 · 일회성 탐욕적 완료 · 조기 완료 선언 · 자기평가 편향 · 훈련 컷오프 밖
> 할루시네이션)를 상태 외부화, Task State Machine, 독립 검증 루프, grounding 게이트로 막는
> 구조를 공유한다.
> 배경 문서: [`docs/harness-engineering/`](./docs/harness-engineering/)

## 설치

```
/plugin marketplace add kbk109-dev/kbk109-plugins-marketplace
/plugin install expo-app-kit@kbk109-plugins-marketplace
```

플러그인은 필요한 것만 골라 설치한다. 플러그인 간 의존은 없다.

## 업데이트

마켓플레이스와 설치한 플러그인을 최신으로 맞출 때:

```
/plugin marketplace update kbk109-plugins-marketplace
```

반영이 안 되면 `/reload-plugins` 를 실행하거나 Claude Code 세션을 다시 시작한다.

## 릴리스

현재 마켓플레이스 버전은 **1.12.0**이다. 변경 내역은 [CHANGELOG](./CHANGELOG.md),
이번 태그 노트는 [docs/release/v1.12.0.md](./docs/release/v1.12.0.md) 를 본다.

## 플러그인

| 플러그인 | 스킬 | 용도 |
|---|---|---|
| [`expo-app-kit`](./plugins/expo-app-kit) | 4 | Expo/RN 앱의 AdMob 광고 계획·구현, EAS Update(OTA) 핫픽스 |
| [`firebase-observability`](./plugins/firebase-observability) | 4 | Firebase Analytics(GA4)·Crashlytics 도입 계획·구현 |
| [`release-workflow`](./plugins/release-workflow) | 4 | Notion 기반 릴리즈 계획·구현·패치·main 머지 |
| [`harness-devkit`](./plugins/harness-devkit) | 2 | 스킬 집필 도구, dev 서버 로그 감시 |
| [`product-planning`](./plugins/product-planning) | 1 | 노션 문서·회의록 → PRD 10개 섹션 정규화 |
| [`project-conventions`](./plugins/project-conventions) | 3 | AGENTS.md 단일 소스화, Claude·Cursor 규칙(git 워크플로·codegraph 검색) 동기화. 이관 전 본문을 200줄 목표로 다듬는다. codegraph 검색은 훅 2개로 강제 — 심볼 검색을 차단해 codegraph 로 보내고(Bash 의 grep·rg 포함), 서브에이전트 프롬프트에도 규칙을 심는다 |

## 스킬 전체 목록

플러그인 스킬은 `/<플러그인>:<스킬>` 로 호출한다. 대부분은 트리거 문구만으로 자동 호출된다.
`references` 는 스킬이 **필요할 때만 읽는** 딸림 자료다. 본문을 500줄 이하로 유지하기 위해
특정 단계에서만 쓰는 템플릿·상세 가이드를 밖으로 뺀 것이다 (점진적 정보 공개).

### expo-app-kit
| 스킬 | 트리거 예 | references |
|---|---|---|
| `admob-plan` | "광고 배치 계획", "어디에 광고 넣을지", "admob 설계" | `plan_document_template.md` |
| `admob-impl` | "ADMOB-PLAN 기반으로 구현해줘", "배너 광고 코드 넣어줘" | — |
| `admob-impl-harness` | "하네스로 광고 구현", "AdMob harness" | `evaluator_guide.md` 외 2 |
| `ota-hotfix` | "OTA 반영 안 됨", "fingerprint 불일치", "eas update 했는데 적용 안 돼" | — |

### firebase-observability
| 스킬 | 트리거 예 | references |
|---|---|---|
| `firebase-analytics-plan` | "GA4 이벤트 설계", "이벤트 트래킹 계획" | `ga4-events.md` |
| `firebase-analytics-impl` | "GA_PLAN 기반으로 구현해줘", "screen_view 트래킹 구현해줘" | `evaluator_guide.md` 외 2 |
| `firebase-crashlytics-plan` | "크래시 리포팅 계획 세워줘", "Error Boundary 어디에 넣어야 해?" | — |
| `firebase-crashlytics-impl` | "CRASHLYTICS_PLAN 기반으로 구현해줘", "글로벌 에러 핸들러 설정해줘" | `report_template.md` 외 3 |

### release-workflow
| 스킬 | 트리거 예 | references |
|---|---|---|
| `release-plan` | "릴리즈 계획", "작업 분해해서 노션에 등록" | `harness_docs_templates.md` 외 3 |
| `release-impl` | "v1.2.0 구현", "릴리즈 작업 시작" | `contract_consumer.md` 외 6 |
| `fix-plan-impl` | "버그 수정 릴리즈", "패치 릴리즈", "핫픽스 계획+구현" | `notion_version_rules.md` |
| `main-branch-merge` | "main 머지", "릴리스 노트", "태그 찍어줘" | `readme-best-practices.md` 외 1 |

### harness-devkit
| 스킬 | 트리거 예 | references |
|---|---|---|
| `harness-dev` | 스킬 설계·집필 (Harness 프레임워크 적용) | `feature_list_template.json` 외 3 |
| `dev-monitor` | `/harness-devkit:dev-monitor <port>` — 서버 기동 + 로그 감시 | — |

### product-planning
| 스킬 | 트리거 예 | references |
|---|---|---|
| `create-prd` | "PRD 만들어줘", "기획서를 PRD로 정리해줘", "수용기준 뽑아줘" | `prd_template.md` 외 2 |

### project-conventions
| 스킬 | 트리거 예 | references |
|---|---|---|
| `init-agent-rules` | "CLAUDE.md 를 AGENTS.md 로 옮겨줘", "커서랑 클로드 규칙 같이 쓰게 해줘", "codegraph 규칙 넣어줘" | `claude_md_rewrite.md` 외 1 |
| `check-agent-rules` | "규칙 갈라졌는지 확인", "cursor rules 랑 claude rules 같은지 봐줘" | — |
| `refresh-agent-rules` | "AGENTS.md 업데이트", "AGENTS.md 가 지금 코드랑 맞는지 봐줘", "프로젝트 바뀌었으니 문서 반영해줘" | `refresh_policy.md` |

> 사용 가이드: [docs/guide/project-conventions.md](./docs/guide/project-conventions.md) — 왜 쓰는지, 쓰면 저장소가 어떻게 바뀌는지

## 선행 요건

스킬마다 다르다. 플러그인별 README 에 정리해 두었다.

| 요건 | 필요한 플러그인 |
|---|---|
| [context7 MCP](https://github.com/upstash/context7) | expo-app-kit, firebase-observability, release-workflow, harness-devkit |
| Notion MCP | release-workflow, product-planning |
| WebSearch | release-workflow, harness-devkit |
| `python3` | release-workflow, product-planning, project-conventions |
| EAS CLI (`eas`) | expo-app-kit (ota-hotfix) |
| 프로젝트 `CLAUDE.md` | project-conventions (init-agent-rules), harness-devkit (dev-monitor) |

## 개발

```bash
bash scripts/validate-marketplace.sh   # 매니페스트·경로·네임스페이스 정합성 검사
```

새 플러그인·스킬을 만드는 절차는 [`.claude/skills/new-plugin`](./.claude/skills/new-plugin/SKILL.md)
스킬에 있다 — 이 저장소에서 작업할 때 자동으로 불린다. 지켜야 할 제약(두 불변식·버전 위치·
넣지 않는 것)은 [AGENTS.md](./AGENTS.md) 에 있다.

스킬을 수정할 때 지켜야 할 두 규칙:

1. **스크립트 경로는 `${CLAUDE_PLUGIN_ROOT}` 기준으로 쓴다.**
   `${CLAUDE_PLUGIN_ROOT}/skills/<스킬>/scripts/x.py` — 상대 경로는 사용자 프로젝트의 cwd 에서
   깨진다.
2. **다른 스킬을 호출할 때는 네임스페이스를 붙인다.**
   `/release-workflow:release-plan` — 플러그인 스킬은 bare 이름으로 호출되지 않는다.

두 규칙은 `validate-marketplace.sh` 가 검사한다.

## 계보

이 저장소의 스킬은 [`kbk109-dev/ClaudeCodeSkills`](https://github.com/kbk109-dev/ClaudeCodeSkills)
v1.9.1 에서 분리해 플러그인으로 재구성한 것이다. 이후 유지보수는 이 저장소에서 한다.

## 라이선스

MIT — [LICENSE](./LICENSE)
