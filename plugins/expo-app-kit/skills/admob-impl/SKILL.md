---
name: admob-impl
description: Implements AdMob ads in React Native Expo projects based on an ADMOB-PLAN.md planning document. Reads the plan, looks up the latest `react-native-google-mobile-ads` API via Context7 MCP, then generates/modifies actual source files — ad utility module, Banner/Interstitial/Rewarded/AppOpen ad components, screen-level ad placement, app.json plugin config, and .env.local ad unit IDs. Use this skill whenever the user asks to implement, code, insert, apply, or add AdMob ads based on a plan document, or mentions ADMOB-PLAN.md implementation, ad code generation, banner ad insertion, interstitial ad placement, rewarded ad component creation, or incremental ad implementation. Also triggers on Korean phrases like "ADMOB-PLAN 기반으로 구현해줘", "AdMob 구현해줘", "AdMob 적용해줘", "광고 구현해줘", "광고 적용해줘", "애드몹 구현", "배너 광고 코드 넣어줘", "전면 광고 구현해줘", "보상형 광고 컴포넌트 만들어줘", "광고 계획 실행해줘", "나머지 광고도 구현해줘".
---

# AdMob Implementation

You are implementing AdMob ads in a React Native Expo project. A planning document (`docs/plan/ADMOB-PLAN.md`) already exists with detailed specifications — ad types, placement screens, ad unit IDs, frequency capping, and initialization strategy. Your job is to turn that plan into working code.

Write all user-facing communication in **Korean (한글)**.

This skill is the **implementation counterpart** to `admob-plan` (which creates the plan). Do not re-plan — execute.

## Guiding Principles

1. **ADMOB-PLAN.md is the spec**: ad types, placement screens, ad unit IDs, frequency capping values, and component structure come from the plan
2. **Context7 is the live API reference**: before writing any ad code, query Context7 MCP for the latest `react-native-google-mobile-ads` function signatures, component props, and usage patterns. The plan may contain outdated snippets — Context7 results take precedence for API details
3. **The existing codebase is the style guide**: match naming conventions, import patterns, directory structure, and TypeScript usage already present in the project
4. **No duplicate ads**: check for existing ad code before inserting anything. Never show two ads on the same screen position
5. **Minimal changes**: add ad code without restructuring existing files
6. **Plan only, nothing extra**: implement exactly what the plan specifies — do not add ad types or placements not in the plan

---

## Phase 1: Understand What Needs to Be Done

### 1.1 Read the Plan

Read `docs/plan/ADMOB-PLAN.md` from the project root. **If the file doesn't exist, tell the user:**

> "ADMOB-PLAN.md 파일이 존재하지 않습니다. 먼저 AdMob 계획 문서를 작성해주세요."

**Then stop immediately.** Do not proceed with any implementation.

If the file exists, extract these implementation tasks:

- **Ad types to implement**: which of Banner, Interstitial, Rewarded, Rewarded Interstitial, App Open, Native Advanced are specified
- **Screen-by-screen placement map**: Section 4 table — which screen gets which ad type, at which position
- **Ad Unit ID inventory**: Section 5 table — environment variable keys and test IDs
- **SDK initialization**: where to call `mobileAds().initialize()` (usually root layout)
- **Frequency capping values**: Section 6 — minimum intervals, session caps per ad type
- **Preloading strategy**: which ads to preload and when
- **Ad-free screens**: screens explicitly marked as no-ads with rationale

### 1.2 Read Project Context

Read these files to understand the project:

- `CLAUDE.md` — project conventions, tech stack, directory structure
- `package.json` — installed dependencies, scripts
- `app.json` or `app.config.ts` — Expo configuration, existing plugins
- `.env.local` — existing environment variables (check for AdMob section)

### 1.3 Check Current State

Before writing any code, assess what already exists:

```
Check for:
├── package.json → is react-native-google-mobile-ads installed?
├── app.json → is the admob plugin configured?
├── src/ads/ → does an ad utility module exist?
├── .env.local → are ADMOB_* environment variables present?
├── Grep for existing BannerAd, InterstitialAd, RewardedAd imports in src/ and app/
└── Grep for existing mobileAds().initialize() calls
```

If ad code already exists:

- Compare existing implementation against ADMOB-PLAN.md
- Skip items already implemented correctly
- Flag items that differ from the plan (ask user before modifying)
- Focus only on gaps

### 1.4 Check for Previous Implementation Report

Read `docs/plan/ADMOB_IMPL_REPORT.md` if it exists. Compare its timestamp against ADMOB-PLAN.md's `Last Updated` date. If the plan is newer, identify what changed and implement only the delta.

---

## Phase 2: Look Up Live APIs via Context7

Context7 MCP provides the latest library documentation. The plan tells you _what_ to implement (ad types, screens, IDs); Context7 tells you _how_ (correct API calls, component props, configuration).

### 2.1 Resolve Library ID

Call `mcp__plugin_context7_context7__resolve-library-id` for `react-native-google-mobile-ads`.

### 2.2 Query Specific APIs

Call `mcp__plugin_context7_context7__query-docs` with the resolved library ID. Use focused queries — run in parallel:

- `"BannerAd component props sizes adaptive banner"` — Banner component API
- `"InterstitialAd createForAdRequest load show event listeners"` — Interstitial lifecycle
- `"RewardedAd createForAdRequest load show onUserEarnedReward"` — Rewarded ad lifecycle
- `"AppOpenAd createForAdRequest load show"` — App Open ad API
- `"mobileAds initialize requestConfiguration TestIds"` — SDK initialization and test mode
- `"useInterstitialAd useRewardedAd hooks"` — React hooks if available

### 2.3 Extract Key Findings

From Context7 results, extract:

1. **Component props**: `BannerAd` required/optional props, event handlers
2. **Static factory methods**: `InterstitialAd.createForAdRequest(adUnitId, requestOptions)`
3. **Event listener patterns**: `onAdLoaded`, `onAdFailedToLoad`, `onAdClosed`, `onUserEarnedReward`
4. **Hook APIs**: if the library provides React hooks (`useInterstitialAd`, `useRewardedAd`), prefer them over manual event listener management
5. **Import paths**: exact module structure (`import { BannerAd, BannerAdSize } from 'react-native-google-mobile-ads'`)
6. **Config plugin setup**: what goes in `app.json` plugins array

If Context7 and the plan disagree on API details, Context7 takes precedence.

### 2.4 Context7 Unavailable (fallback)

If Context7 MCP tool calls fail, proceed using ADMOB-PLAN.md specs. Add a warning banner to the implementation report: "⚠️ API verification skipped — Context7 MCP unavailable. Review generated code against latest react-native-google-mobile-ads docs before shipping."

---

## Phase 3: Implement

Work through implementation in this order. Use API details from Context7 — component props, function signatures, and import paths should match Context7 results, not hardcoded assumptions.

After each major step, run the project's type checker (`npm run typecheck`) to catch errors early.

### 3.1 Package Installation

Detect the package manager:

```
if yarn.lock exists → yarn
if pnpm-lock.yaml exists → pnpm
else → npm (default)
```

Check if `react-native-google-mobile-ads` is installed. If not:

```bash
npx expo install react-native-google-mobile-ads
```

After installation, verify it appears in `package.json` dependencies.

Then check `app.json` (or `app.config.ts`) for the AdMob plugin configuration:

- **plugins array**: Add `react-native-google-mobile-ads` with the AdMob App ID. The exact config format should come from Context7 docs — typically:
  ```json
  ["react-native-google-mobile-ads", {
    "androidAppId": "ca-app-pub-xxxxxxxx~xxxxxxxx",
    "iosAppId": "ca-app-pub-xxxxxxxx~xxxxxxxx"
  }]
  ```
- Use test App IDs from the plan or `ca-app-pub-3940256099942544~3347511713` (Google test app ID)
- Never modify `android/` or `ios/` directories directly — the config plugin handles native setup
- Check that `expo-dev-client` is installed (AdMob requires a custom dev build, not Expo Go). If missing, inform the user.

### 3.2 Environment Variables

Read `.env.local` for existing AdMob variables. If the plan's ad unit IDs aren't already there:

- Read the plan's Section 5 (Ad Unit ID inventory)
- Add/update the AdMob section in `.env.local` between `# ===== AdMob` and `# ===== End AdMob =====` markers
- Use Google official test IDs as values (from the plan)
- Preserve existing non-AdMob content

### 3.3 Ad Utility Module

Create `src/ads/` (or the path specified in the plan) with these files:

**`src/ads/adUnitIds.ts`** — Ad Unit ID constants

- Read IDs from environment variables (e.g., `process.env.ADMOB_BANNER_HOME`)
- Provide Google test ID fallbacks for `__DEV__` mode
- Export typed constants: `AD_UNIT_IDS.BANNER_HOME`, `AD_UNIT_IDS.INTERSTITIAL_SUMMARY_COMPLETE`, etc.
- Map environment variable keys from the plan's Section 5 table

**`src/ads/adConfig.ts`** — Configuration constants

- Frequency capping values from the plan's Section 6
- Request configuration (e.g., max ad content rating, tag for child-directed treatment if applicable)
- Feature flags: `ADS_ENABLED`, environment checks

**`src/ads/hooks/useBannerAd.ts`** — Banner ad hook (if plan includes banners)

- Handles ad loaded/failed states
- Manages container height to prevent layout jumps when ad loads
- Returns `{ BannerComponent, isAdLoaded }` or similar

**`src/ads/hooks/useInterstitialAd.ts`** — Interstitial ad hook (if plan includes interstitials)

- Preload logic: load the next ad after showing one
- Frequency capping: check last shown timestamp against minimum interval
- Session counter: track impressions per session against max cap
- Returns `{ showAd, isLoaded, isShowable }` — where `isShowable` checks both loaded state and frequency cap
- Persist frequency data in MMKV or equivalent (match project's storage pattern)

**`src/ads/hooks/useRewardedAd.ts`** — Rewarded ad hook (if plan includes rewarded ads)

- Preload on mount
- Reward callback handling: what to grant the user upon completion
- Returns `{ showAd, isLoaded, reward }` — reward is non-null after user earns it
- Reload after showing

**`src/ads/hooks/useAppOpenAd.ts`** — App Open ad hook (if plan includes app open ads)

- AppState listener: detect background-to-foreground transitions
- Minimum background duration check (from plan's capping values, typically 30+ seconds)
- Cold start vs warm return behavior
- Session-level cap

**`src/ads/components/AdBanner.tsx`** — Reusable Banner component (if plan includes banners)

- Wraps `BannerAd` from the library with project-consistent styling
- Props: `adUnitId`, `size` (default: adaptive), `containerStyle`
- Handles loading state (reserve space to prevent layout jump)
- Error state: hide gracefully on load failure (no error shown to user)
- Use the project's styling approach for container

**`src/ads/initAds.ts`** — SDK initialization

- Call `mobileAds().initialize()`
- Set request configuration if needed
- Log initialization result in `__DEV__` mode

**`src/ads/index.ts`** — Barrel export

### 3.4 SDK Initialization

Modify the root layout file (usually `app/_layout.tsx`):

- Import `initAds` from `@/src/ads`
- Add `useEffect(() => { initAds(); }, [])` after existing hooks (fonts, splash screen, etc.)
- Keep changes minimal — only add the initialization call

### 3.5 Ad Placement — Screen by Screen

Work through the plan's Section 4 (화면별 광고 배치 맵) row by row:

For each screen that gets an ad:

1. Open the screen file at the specified route path
2. Read the existing code to understand the layout
3. Add the ad component at the specified position:

**Banner ads**:
- Import `AdBanner` from `@/src/ads`
- Place at the specified position (typically bottom of screen, above tab bar)
- Use the ad unit ID constant from `adUnitIds.ts`
- Ensure the banner doesn't overlap content — add appropriate spacing/padding

**Interstitial ads**:
- Import the interstitial hook from `@/src/ads/hooks`
- Call `showAd()` at the specified trigger point (e.g., after task completion, on screen transition)
- Check `isShowable` before calling `showAd()` — respect frequency capping
- Preload the next interstitial ad in the hook

**Rewarded ads**:
- Import the rewarded hook from `@/src/ads/hooks`
- Add an opt-in UI element (button, prompt) at the specified location
- User must explicitly choose to watch — never force a rewarded ad
- Handle the reward callback: grant the specified reward (from the plan)
- Handle the case where the ad fails to load: show appropriate messaging

**App Open ads**:
- Import the app open hook from `@/src/ads/hooks`
- Place in root layout to handle AppState transitions globally
- The hook manages showing/hiding automatically based on background duration

### 3.6 Preloading Strategy

Based on the plan's preloading recommendations:

- Preload interstitial ads one screen before the trigger point
- Preload rewarded ads when the screen containing the opt-in prompt loads
- App Open ads preload on app initialization
- Banner ads load inline (no preloading needed)

---

## Phase 4: Verify and Report

### 4.1 Type Check

```bash
npm run typecheck
```

Fix any type errors in created/modified files.

### 4.2 Lint Check

```bash
npm run lint
```

Fix any lint issues.

### 4.3 Test Existing Tests

```bash
npm test
```

If tests fail due to missing ad SDK mocks, add mock files following the project's existing mock patterns (check `__tests__/mocks/` or `jest.config.ts`). A typical mock:

```typescript
// __tests__/mocks/react-native-google-mobile-ads.ts
const mockBannerAd = jest.fn(() => null);
const mockInterstitialAd = { createForAdRequest: jest.fn(() => ({ load: jest.fn(), show: jest.fn(), addAdEventsListener: jest.fn(() => jest.fn()) })) };
const mockRewardedAd = { createForAdRequest: jest.fn(() => ({ load: jest.fn(), show: jest.fn(), addAdEventsListener: jest.fn(() => jest.fn()) })) };
export { mockBannerAd as BannerAd, mockInterstitialAd as InterstitialAd, mockRewardedAd as RewardedAd };
export const BannerAdSize = { ANCHORED_ADAPTIVE_BANNER: 'ANCHORED_ADAPTIVE_BANNER' };
export const TestIds = { BANNER: 'ca-app-pub-xxx/banner', INTERSTITIAL: 'ca-app-pub-xxx/interstitial', REWARDED: 'ca-app-pub-xxx/rewarded' };
export default () => ({ initialize: jest.fn().mockResolvedValue([{ name: 'admob', status: 1 }]) });
```

### 4.4 Implementation Checklist

Print a checklist comparing ADMOB-PLAN.md items vs what was implemented:

```
✅ react-native-google-mobile-ads 설치 완료
✅ app.json 플러그인 설정 완료
✅ src/ads/ 유틸리티 모듈 생성
✅ Banner: 홈 화면 하단 — app/(tabs)/index.tsx
✅ Banner: 검색 화면 하단 — app/(tabs)/search.tsx
✅ Interstitial: 요약 완료 전환 — app/summary/[chapterId].tsx
✅ Rewarded: 상세 요약 해금 — src/summary/SummaryViewerScreen.tsx
✅ App Open: 백그라운드 복귀 — app/_layout.tsx
⬜ Banner: 설정 화면 하단 — (다음 단계)
```

### 4.5 Generate Implementation Report

Create `docs/plan/ADMOB_IMPL_REPORT.md`:

```markdown
# AdMob 구현 리포트

> Implemented: YYYY-MM-DD HH:mm
> Based on: ADMOB-PLAN.md (Last Updated: <plan의 타임스탬프>)

## 구현 요약

- 설치된 패키지: N개 (신규) / N개 (이미 설치됨)
- 설정 파일 업데이트: N개
- 생성된 파일: N개
- 수정된 파일: N개
- 배치된 광고: Banner N개소, Interstitial N개소, Rewarded N개소, App Open N개소

## 패키지 설치 결과

| 패키지 | 설치 상태 | 버전 | 비고 |
| ------ | --------- | ---- | ---- |

## 설정 파일 변경

| 파일 | 변경 내용 |
| ---- | --------- |

## Context7 문서 기준 변경사항

| 항목 | ADMOB-PLAN.md 기준 | Context7 최신 문서 기준 | 적용된 버전 |
| ---- | ------------------- | ---------------------- | ----------- |

## 생성된 파일 목록

| 파일 경로 | 설명 |
| --------- | ---- |

## 수정된 파일 목록

| 파일 경로 | 변경 내용 |
| --------- | --------- |

## 구현된 항목 체크리스트

### SDK 초기화

- [x/] 항목

### Banner 광고

- [x/] 항목

### Interstitial 광고

- [x/] 항목

### Rewarded 광고

- [x/] 항목

### App Open 광고

- [x/] 항목

### 환경변수 (.env.local)

- [x/] 항목

## 테스트 방법

1. `npx expo prebuild` 또는 EAS Build로 네이티브 빌드 생성
2. `npx expo start --dev-client` 로 개발 서버 시작
3. 테스트 광고가 각 배치 위치에서 정상 표시되는지 확인
4. Interstitial/Rewarded: 트리거 조건 충족 후 광고 표시 확인
5. 빈도 캡핑: 최소 간격 내 재노출 차단 확인

## 미구현 항목

| 항목 | 사유 |
| ---- | ---- |

## 다음 단계

- Google AdMob Console에서 프로덕션 Ad Unit ID 발급
- `.env.local`의 테스트 ID를 프로덕션 ID로 교체
- 프로덕션 빌드에서 실제 광고 노출 테스트
- AdMob 대시보드에서 eCPM, Fill Rate 등 성과 지표 확인

## Changelog

- YYYY-MM-DD: 초기 구현
```

---

## Incremental Implementation

When re-invoked after partial implementation:

1. Read both `ADMOB-PLAN.md` and `ADMOB_IMPL_REPORT.md`
2. Diff the plan's `Last Updated` date against the report's `Based-on` date
3. If the plan is newer: identify added/changed/removed ad placements
4. Grep for existing `BannerAd`, `InterstitialAd`, `RewardedAd`, `AppOpenAd` usage to see what's in the codebase
5. Implement only the missing items
6. For existing implementations that differ from the updated plan: show both to the user and ask which to keep
7. Update (don't recreate) `ADMOB_IMPL_REPORT.md` with new items
8. Append to the report's Changelog

---

## Error Handling

- **ADMOB-PLAN.md not found**: Tell the user and stop. Do not guess or create a plan.
- **Context7 MCP unavailable**: Warn the user, proceed using plan specs, add "⚠️ API verification skipped" to report
- **Context7 returns no results**: Rephrase query. If still nothing, note as "unverified" in report
- **Target screen file not found**: Skip that placement, log as "파일 미존재" in report, continue with the rest
- **Conflicting existing ad code**: Show both versions to user, ask which to keep
- **Package installation failure**: Show the error and ask the user to resolve it manually
- **Missing expo-dev-client**: Inform user that `npx expo install expo-dev-client` is needed — AdMob doesn't work in Expo Go
- **Missing .env.local**: Create it with AdMob section only

## Safety Rules

- **Never `git push`** — implementation must not trigger any remote operations
- **Never modify `android/` or `ios/` directories** — Expo config plugins handle native setup
- **Always use test Ad Unit IDs** in development — never hardcode production IDs in source
- **Preserve existing `.env.local` content** — only add/update the AdMob section
