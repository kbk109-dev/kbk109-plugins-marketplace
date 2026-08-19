---
name: new-plugin
description: "이 저장소에서 새 플러그인을 만들거나 기존 플러그인에 스킬을 추가할 때 따르는 절차. marketplace.json 등록 여부와 버전 규칙이 두 경우에 다르므로 A/B 로 나뉜다. 반드시 이 스킬을 사용해야 하는 경우: '새 플러그인 만들어줘', '플러그인 추가', '스킬 추가해줘', '기존 플러그인에 스킬 넣어줘', 'plugin.json 만들어줘', 'marketplace.json 에 등록해줘', '새 스킬 만들기', 'add a new plugin', 'add a skill to an existing plugin', 'register a plugin in the marketplace'."
---

# 새 플러그인·스킬 만들기

이 저장소의 주된 작업이다. 절차를 A/B 로 나누는 이유는 **`marketplace.json` 등록 여부와 버전
규칙이 다르기 때문**이다 — 하나로 묶으면 B 케이스에서 틀린 단계를 따라간다.

제약(불변식·버전 위치·넣지 않는 것)은 `AGENTS.md` 에 있다. 이 문서는 순서만 담는다.

## A. 새 플러그인 만들기

1. **`plugins/<plugin>/.claude-plugin/plugin.json`** — `name` 은 디렉토리명과 동일, `version` 은
   `1.0.0` 시작. 필드 구성은 기존 매니페스트를 따른다
   (`description`/`author`/`homepage`/`repository`/`license`/`keywords`)
2. **`plugins/<plugin>/skills/<skill>/SKILL.md`** — 프론트매터 `name` 은 스킬 디렉토리명과 일치.
   본문 집필은 `harness-devkit:harness-dev` 로 한다. 작성 규칙은 `AGENTS.md` 의
   "SKILL.md 작성 규칙" 참조
3. **`plugins/<plugin>/README.md`** — 그 플러그인의 스킬 목록과 선행 요건. 루트 `README.md` 의
   "선행 요건" 절이 *"플러그인별 README 에 정리해 두었다"* 로 이 파일을 가리킨다
4. **`.claude-plugin/marketplace.json` 의 `plugins[]` 에 항목 추가** — `name`(= plugin.json 의
   `name`) · `source`(`./plugins/<plugin>`) · `version` · `displayName` · `description` ·
   `category` · `keywords` · `homepage`
5. **루트 `README.md`** 의 플러그인 표와 스킬 전체 목록, 두 표 모두에 추가
6. **`bash scripts/validate-marketplace.sh`** — 전 항목 통과
7. **로컬 설치 테스트** (푸시 전에 반드시)
   ```
   /plugin marketplace add <이 저장소 절대경로>
   /plugin install <plugin>@kbk109-plugins-marketplace
   ```
8. **버전** — 플러그인은 `1.0.0`, 마켓플레이스 `metadata.version` 은 minor bump.
   올려야 할 위치 전체는 `AGENTS.md` 의 "버전 관리" 참조
9. **`CHANGELOG.md`** 에 기록

## B. 기존 플러그인에 스킬 추가

1. **`plugins/<plugin>/skills/<skill>/SKILL.md`** — 프론트매터 `name` 은 디렉토리명과 일치
2. **`marketplace.json` 의 `plugins[]` 는 건드리지 않는다** — 등록 단위는 플러그인이지 스킬이 아니다
3. **`plugins/<plugin>/README.md`** 와 **루트 `README.md`** 의 스킬 표에 추가
4. **`validate-marketplace.sh` → 로컬 설치 테스트** (A-6, A-7 과 동일)
5. **버전** — 해당 플러그인을 minor bump 하되 `plugin.json` 의 `version` 과 `marketplace.json` 의
   `plugins[].version` **둘 다** 올린다. 마켓플레이스 `metadata.version` 도 함께 올린다
6. **`CHANGELOG.md`** 에 기록

## 만들면서 지킬 것

- **스킬 자산 디렉토리는 실제로 쓰는 5종만 둔다** — `scripts/` `references/` `agents/` `evals/`
  `templates/`. `agents/` 는 스킬 내부 서브에이전트 전용이며 플러그인 최상위에 두지 않는다
- **`SKILL.md` 안에서 스크립트를 부를 때는 `${CLAUDE_PLUGIN_ROOT}` 기준, 다른 스킬을 부를 때는
  `<plugin>:<skill>`** — `AGENTS.md` 의 두 불변식이 적용되는 지점이 정확히 여기다
- 플러그인에 넣지 **않는** 것(`commands/`, `.mcp.json`, `.skill` 번들, 조건 없는 `hooks/`)은
  `AGENTS.md` 의 "이 저장소에 넣지 않는 것"에 근거와 함께 있다. 빠진 것 같아서 추가하지 말 것
