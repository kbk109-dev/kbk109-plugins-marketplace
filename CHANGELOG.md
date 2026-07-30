# Changelog

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

- **`test-*` 13개** — `oh-my-connect-cowork-url` 프로젝트 루트의 `agents/N_*.md` 와
  `data/{date}_vN/` 에 직접 의존해 다른 환경에서 동작하지 않는다. 해당 프로젝트에 남긴다.
- **`brand-application`, `decision-council`** — ClaudeCodeSkills 에 없는 외부 유래 스킬.
  출처가 불명확한 상태로 MIT 재배포하지 않는다.
