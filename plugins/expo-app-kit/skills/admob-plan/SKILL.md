---
name: admob-plan
description: Plans AdMob ad placement strategy for React Native Expo projects — analyzes the codebase screen-by-screen, assembles a 5-expert virtual agent team (Best Practices Researcher, Monetization Expert, RN Implementation Specialist, Policy Compliance Reviewer, UX Designer) that cross-reviews ad type selection and placement, then produces a structured plan saved to docs/plan/ADMOB-PLAN.md and writes test Ad Unit IDs to .env.local. Use this skill whenever the user mentions AdMob integration, ad placement planning, ad monetization strategy, banner/interstitial/rewarded ad placement, ad unit ID setup, or wants to update an existing ADMOB-PLAN.md. Also triggers on Korean phrases like "admob 계획", "광고 배치 계획", "광고 전략 수립", "어디에 광고 넣을지", "광고 타입별 배치", "admob 설계", "광고 ID 정리", "admob 환경변수", "광고 unit id", "ADMOB-PLAN 수정해줘", "광고 수익 최적화", "배너 광고 어디에 넣어", "전면 광고 언제 띄워야 해", "보상형 광고 설계".
---

# AdMob Ad Placement Plan

You are creating a comprehensive AdMob ad placement strategy for a React Native Expo project. The plan tells the developer **exactly where to place each ad type, when to show it, and why** — but does not modify source files directly.

Write the plan document in **Korean (한글)**.

**Important: This is a PLAN, not implementation.** Focus on which ad types to use, where to place them, optimal timing/frequency, and revenue-UX balance — not on code. Keep code snippets to an absolute minimum (only a brief one-liner example if needed). The plan should be readable by a product manager, not just an engineer.

## Phase 0: Expert Agent Best Practices

Before analyzing the project, think through five expert perspectives. Each agent contributes domain-specific recommendations. Then resolve conflicts between them.

The reason for five agents (instead of the typical four) is that AdMob placement requires balancing an unusually wide range of concerns: industry best practices, revenue optimization, technical feasibility, policy compliance, and user experience. Agent 1 (Best Practices Researcher) produces foundational context that elevates the quality of all subsequent agent analyses.

### The Five Agents

**Agent 1: AdMob Best Practices Researcher** — Industry research expert

This agent runs first. Its output feeds into every other agent's analysis.

- Research AdMob official best practices for the app's category (education/productivity/reading apps)
- Identify proven ad placement patterns from similar apps: which ad types work best, where they're typically placed, what timing strategies succeed
- Google official guidelines on ad density, ad refresh intervals, and placement DO's/DON'Ts
- Ad fatigue management strategies: how many ads per session before user engagement drops
- A/B testing best practices: which variables to test first for maximum learning
- Reading/focus app-specific insights: users in reading apps are in a focused state — intrusive ads cause disproportionately high churn compared to casual apps

**Agent 2: Ad Performance & Monetization Expert** — Revenue optimization expert

- eCPM hierarchy by ad type (typical ranges): Rewarded ($10-30) > Rewarded Interstitial ($8-20) > Interstitial ($4-12) > App Open ($3-8) > Banner ($0.5-3) > Native ($1-5)
- Fill Rate considerations: banners have highest fill rate (~99%), rewarded ads lower (~70-90%) — plan fallback logic
- Frequency capping strategy: interstitials max 1 per 3-5 minutes, rewarded unlimited (user-initiated), banner refresh 30-60 seconds
- Session-level ad budget: recommend total ad exposures per session to avoid fatigue (typically 3-5 interstitial-equivalent impressions)
- Placement-per-unit-ID principle: each placement gets its own Ad Unit ID for per-placement performance tracking (eCPM, fill rate, click rate)
- Mediation/waterfall consideration: note if AdMob mediation should be considered for fill rate optimization

**Agent 3: React Native Ad Implementation Specialist** — Technical feasibility expert

- Library: `react-native-google-mobile-ads` (the standard library for RN AdMob)
- Use Context7 MCP (`mcp__plugin_context7_context7__resolve-library-id` then `mcp__plugin_context7_context7__query-docs`) to look up the latest API for `react-native-google-mobile-ads`
- Expo compatibility: requires `expo-dev-client` (not Expo Go); Config Plugin setup in `app.json` / `app.config.ts`
- Ad loading lifecycle: preload interstitials/rewarded ads ahead of display; banners load inline
- Component architecture: recommend an `src/ads/` utility module with typed helpers
- Memory management: destroy ad instances on screen unmount; avoid multiple simultaneous interstitial loads
- Expo Router integration: ad display timing relative to screen transitions (show interstitial AFTER transition completes, not during)
- Error handling: no-fill fallback, load failure retry with exponential backoff, network offline graceful degradation
- `app.json` / `app.config.ts` plugin configuration for AdMob App ID

**Agent 4: Ad Policy Compliance Reviewer** — Policy compliance expert

- Google AdMob Program Policies: ads must not be placed where accidental clicks are likely (near interactive elements, in scrollable content that causes misclicks)
- Prohibited placements: ads must not cover content, auto-redirect, or appear before app content loads (except App Open ads which are explicitly designed for this)
- Interstitial timing: must not show during loading, immediately at app launch (wait for first user action), or when user is about to perform an action (e.g., right when they tap a button)
- Rewarded ads: user must explicitly opt in; reward must be delivered even if ad fails to show
- COPPA compliance: if app could be used by children under 13, special ad treatment is required (tag for child-directed treatment)
- App Store Review Guidelines: both Apple and Google require ads to be clearly distinguishable from content; no deceptive ad layouts
- Content adjacency: ads should not appear next to sensitive or mature content
- Ad density: Google recommends no more than 1 ad visible per screen at a time for most ad types

**Agent 5: UX/UI Ad Experience Designer** — User experience expert

- Natural break points: identify moments where users naturally pause (after completing a task, between content consumption sessions, returning from background) — these are ideal for interstitial/app-open ads
- Reading app UX sensitivity: users in a reading/summarization app are in a focused mindset; interrupting this flow causes outsized frustration compared to casual apps
- Ad placement hierarchy by intrusiveness: Banner (lowest) < Native < App Open < Interstitial < Rewarded Interstitial < Rewarded (highest, but user-initiated so perceived intrusiveness is low)
- Screen-by-screen density check: no screen should feel "ad-heavy"; max 1 banner per screen, interstitials only at natural transitions
- Progressive ad introduction: first-time users should have a reduced ad experience to allow onboarding without friction
- Visual integration: banners should feel part of the layout (consistent margins, not overlapping content); reserve adequate space so content doesn't jump when ads load
- Exit path preservation: users must always be able to dismiss or skip ads without confusion

### Conflict Resolution

These tensions almost always arise in ad placement planning. Resolve them upfront:

| Tension                                                                                                     | Resolution                                                                                                                                                                                                      |
| ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Monetization wants frequent interstitials for high eCPM vs UX wants minimal interruption                    | Use natural break points only (task completion, content transition); enforce frequency cap (1 per 3-5 min); compensate revenue with strategic rewarded ad placements which have higher eCPM and user acceptance |
| Monetization wants banners on every screen vs UX wants clean reading experience                             | Place banners on utility screens (home, settings, search) but NOT on content consumption screens (summary viewer, camera, capture review) where focus matters                                                   |
| Implementation wants simple ad loading vs Performance wants preloading for instant display                  | Preload interstitial/rewarded ads one screen before the trigger point; accept the memory cost for better user experience (no loading delay = less frustration)                                                  |
| Policy prohibits ads near interactive elements vs Implementation wants banner at screen bottom near tab bar | Maintain safe distance (minimum 16px padding) between banner and interactive elements; consider placing banner above tab bar with clear visual separation                                                       |
| Best Practices suggest App Open ads vs UX wants clean app launch                                            | Use App Open ads only on background-to-foreground return (not cold start); add minimum background duration threshold (e.g., 30 seconds) to avoid showing ads on quick app switches                              |

Produce a brief summary of each agent's **top 3 recommendations** and any conflict resolutions.

## Phase 1: Project Structure Analysis

Read the project to understand the ad placement opportunities.

### Step 1.1: Read CLAUDE.md

Read the project's `CLAUDE.md` file to understand:

- App purpose and target audience
- Screen specifications and user flows
- Design system constraints (spacing, layout patterns)
- Any existing monetization or ad-related notes

### Step 1.2: Expo Router Structure

Use Glob to find all `app/**/*.tsx` files. Map:

- Root `_layout.tsx` → AdMob SDK initialization point
- Tab layouts → screens where persistent banners might live
- Individual screen files → ad placement candidates
- Modal/overlay routes → typically NOT suitable for ads

Build a complete route-to-screen mapping table.

### Step 1.3: Screen Flow Analysis

For each screen, assess:

- **Dwell time**: How long users typically spend (high dwell = good banner placement)
- **User intent**: Consuming content vs performing action vs navigating (content screens = fewer ads)
- **Transition points**: Where users move between screens (natural interstitial opportunities)
- **Task completion moments**: Where users finish a meaningful task (ideal rewarded/interstitial timing)

### Step 1.4: Existing Ad Setup Detection

Use Grep to check:

- `package.json` for `react-native-google-mobile-ads` or other ad SDKs
- `app.json` / `app.config.ts` for AdMob plugin configuration
- Source files for any existing ad imports, ad components, or ad-related code
- `.env` / `.env.local` for existing ad unit ID environment variables

If ad code already exists, identify what's in place and focus the plan on **gaps and improvements only**.

### Step 1.5: Package & Plugin Verification

Check whether `react-native-google-mobile-ads` is installed:

- If installed: note the version, check for any existing configuration
- If not installed: note that installation is needed, and specify required `app.json` plugin config

Produce a structure summary with:

- Complete route-to-screen mapping
- Screen dwell-time and intent classification
- Natural break points in user flow
- Existing ad infrastructure inventory

## Phase 2: Ad Placement Strategy

### 2.1 SDK Initialization & Configuration

Describe the initialization approach (minimal code — just locations and responsibilities):

- **Ad utility module** location (recommend `src/ads/`)
  - What it exports: `initializeAds`, `showInterstitial`, `showRewarded`, `showAppOpenAd`, typed ad unit ID constants
  - Debug mode behavior: use test ad IDs in `__DEV__`, load from environment variables in production
  - Platform-aware ID selection: use `Platform.OS` to pick the correct `_ANDROID` or `_IOS` unit ID at runtime
  - Consent handling: integrate with UMP (User Messaging Platform) for GDPR consent if targeting EU users
- **Root layout integration** — which file and which lifecycle point for `mobileAds().initialize()`
- **app.json plugin config** — `react-native-google-mobile-ads` plugin with AdMob App ID (references `ADMOB_ANDROID_APP_ID` / `ADMOB_IOS_APP_ID` from `.env.local`)

### 2.2 Ad Type Strategy

For each ad type, decide whether to use it and design the placement strategy. Not every ad type needs to be used — recommend only what makes sense for the app.

#### 2.2.1 Banner Ad

- Which screens get banners and why (high dwell time, utility screens preferred)
- Position: bottom of screen (above tab bar if applicable), or top below header
- Size: adaptive banner recommended (auto-adjusts to screen width)
- Refresh interval: 30-60 seconds (Google minimum is 30s)
- Which screens explicitly should NOT have banners and why

#### 2.2.2 Interstitial Ad

- Trigger conditions: which user actions or transitions trigger an interstitial
- Frequency capping: maximum frequency (e.g., 1 per 3 minutes minimum gap)
- Preloading strategy: when to preload the next interstitial
- Prohibited moments: when NOT to show (during content consumption, immediately after app launch, during user input)

#### 2.2.3 Rewarded Ad

- What reward to offer (must provide genuine value to the user)
- Where to surface the opt-in prompt (which screen, which UI element)
- Reward delivery: how to grant the reward, including fallback if ad fails to load
- Expected eCPM advantage over interstitials

#### 2.2.4 Rewarded Interstitial Ad

- Whether to use (only if there's a natural opt-in moment that doesn't fit pure rewarded)
- If yes: trigger condition, reward design, placement

#### 2.2.5 App Open Ad

- Whether to use and under what conditions
- Cold start vs background return behavior
- Minimum background duration before showing (recommend 30+ seconds)
- Loading strategy (preload on app initialization)

#### 2.2.6 Native Advanced Ad

- Whether to use (typically for feed-like UIs)
- If yes: which list/feed view, template design, frequency in list

### 2.3 Screen-by-Screen Placement Map

The core output table. For every screen in the app, specify what ads (if any) appear:

| Screen Route | Screen Name | Ad Type | Position/Timing | Env Variable Key (Android/iOS) | Expected Performance | Agent Rationale |
| ------------ | ----------- | ------- | --------------- | ------------------------------ | -------------------- | --------------- |

Include screens that explicitly have NO ads, with rationale (e.g., "Camera: no ads — user is in active capture flow, any interruption risks photo loss and high frustration").

### 2.4 Ad Unit ID Inventory

**Core principle: 1 Ad Unit ID per placement location per platform.** AdMob registers Android and iOS apps separately, so each placement needs two Unit IDs — one for each platform. Even if two screens both show banners, they get separate Ad Unit IDs so performance can be tracked per-placement.

The `.env.local` must also include **AdMob App IDs** (the app-level identifiers used for SDK initialization in `app.json` plugin config). These are different from individual Ad Unit IDs.

Naming conventions:

- **App IDs**: `ADMOB_ANDROID_APP_ID`, `ADMOB_IOS_APP_ID`
- **Unit IDs**: `ADMOB_{AD_TYPE}_{SCREEN/LOCATION}_{ANDROID|IOS}`

| Env Variable Key | Ad Type | Platform | Placement Screen/Location | Test ID | Notes |
| ---------------- | ------- | -------- | ------------------------- | ------- | ----- |

Google official test IDs (use these as defaults in `.env.local`):

App IDs (SDK initialization):

- Android: `ca-app-pub-3940256099942544~3347511713`
- iOS: `ca-app-pub-3940256099942544~1458002511`

Ad Unit IDs (per ad type — same test ID works on both platforms):

- Banner: `ca-app-pub-3940256099942544/9214589741`
- Interstitial: `ca-app-pub-3940256099942544/1033173712`
- Rewarded: `ca-app-pub-3940256099942544/5224354917`
- Rewarded Interstitial: `ca-app-pub-3940256099942544/5354046379`
- Native Advanced: `ca-app-pub-3940256099942544/3986624511`
- App Open: `ca-app-pub-3940256099942544/9257395921`

### 2.5 Revenue Optimization Recommendations

- Frequency capping values for each ad type
- Ad type priority ranking (which types to focus on first)
- A/B test recommendations: which variables to test and expected impact
- Session-level ad budget (total impressions per session)
- Fill rate fallback strategy

### 2.6 Implementation Guidelines

- Technical constraints and Expo-specific considerations
- Ad loading and preloading strategy per ad type
- Error handling approach (no-fill, load failure, network offline)
- Memory management (ad instance lifecycle)
- Policy compliance checklist for each placement

## Phase 3: Document Output

### 3.1 ADMOB-PLAN.md

#### File Management

1. Check if `docs/plan/ADMOB-PLAN.md` exists
2. **If not**: create `docs/plan/` directory and write the full plan
3. **If yes**: read existing file, update only changed sections, preserve unchanged content
4. Always update the `Last Updated` timestamp
5. Append to `## Changelog`

#### Document Template

**Document template:** see `references/plan_document_template.md` — it holds the full
skeleton (sections 0 through 8 plus Changelog). Fill in that block.

### 3.2 .env.local Update

After generating `ADMOB-PLAN.md`, update `.env.local`:

1. Read existing `.env.local` if it exists
2. Look for existing AdMob section (between `# ===== AdMob` and `# ===== End AdMob =====` markers)
3. **If section exists**: replace only the AdMob section, preserving everything else
4. **If section does not exist**: append the AdMob section at the end
5. Use Google official test IDs as values

The `.env.local` AdMob section has two parts:

- **App IDs** (top): Android/iOS app-level IDs for SDK initialization (`app.json` plugin references these)
- **Ad Unit IDs** (below): Per-placement IDs with `_ANDROID`/`_IOS` suffix for each platform

Format:

```env
# ===== AdMob (Test IDs - 프로덕션 전 교체 필요) =====
# App IDs (SDK 초기화용 — app.json 플러그인에서 참조)
ADMOB_ANDROID_APP_ID=ca-app-pub-3940256099942544~3347511713
ADMOB_IOS_APP_ID=ca-app-pub-3940256099942544~1458002511
# 배치 위치별 개별 Unit ID — 위치별 성과 추적 용도 (플랫폼별 분리)
# Banner
ADMOB_BANNER_HOME_ANDROID=ca-app-pub-3940256099942544/9214589741
ADMOB_BANNER_HOME_IOS=ca-app-pub-3940256099942544/9214589741
# Interstitial
ADMOB_INTERSTITIAL_SUMMARY_COMPLETE_ANDROID=ca-app-pub-3940256099942544/1033173712
ADMOB_INTERSTITIAL_SUMMARY_COMPLETE_IOS=ca-app-pub-3940256099942544/1033173712
# Rewarded
ADMOB_REWARDED_EXTRA_SUMMARY_ANDROID=ca-app-pub-3940256099942544/5224354917
ADMOB_REWARDED_EXTRA_SUMMARY_IOS=ca-app-pub-3940256099942544/5224354917
# App Open
ADMOB_APP_OPEN_ANDROID=ca-app-pub-3940256099942544/9257395921
ADMOB_APP_OPEN_IOS=ca-app-pub-3940256099942544/9257395921
# ===== End AdMob =====
```

The actual variable names and count will depend on the placement map from Phase 2. The variables listed in `.env.local` must exactly match the "필요 광고 Unit ID 목록" table in `ADMOB-PLAN.md`. Test IDs are identical across platforms (Google's official test IDs are universal), but the variables are split now so that production IDs can be dropped in per-platform without restructuring.

## Incremental Update Logic

When `ADMOB-PLAN.md` already exists and the user requests changes (e.g., "광고 추가해줘", "배너 위치 바꿔줘", "ADMOB-PLAN 수정해줘"):

1. Read the existing `docs/plan/ADMOB-PLAN.md`
2. Re-run Phase 1 to detect any project structure changes (new screens, removed screens)
3. Identify the specific change requested
4. Update only the affected sections:
   - New ad placements → add rows to placement map + Ad Unit ID table
   - Removed placements → remove rows, note in changelog
   - Changed ad types → update affected rows
   - New screens → update route mapping, assess ad suitability
   - Changed strategy → update the relevant ad type section
5. Update the `Last Updated` timestamp
6. Add a changelog entry describing the change
7. Sync `.env.local` to match the updated Ad Unit ID table
8. Show the user a diff summary of what changed

## Context7 MCP Usage

When analyzing technical feasibility (Agent 3), use Context7 MCP to look up the latest `react-native-google-mobile-ads` API:

1. First resolve the library: `mcp__plugin_context7_context7__resolve-library-id` with `libraryName: "react-native-google-mobile-ads"`
2. Then query docs: `mcp__plugin_context7_context7__query-docs` with the resolved ID and relevant topics (e.g., "BannerAd component", "InterstitialAd", "RewardedAd", "AppOpenAd", "initialize")

This ensures the plan references current API patterns, not outdated ones.

## Safety Rules

- **Never `git push`** — plan generation must not trigger any remote operations
- **Never modify source files** — this skill only creates/updates `docs/plan/ADMOB-PLAN.md` and `.env.local`
- **Always use test Ad Unit IDs** in `.env.local` — never write production ad IDs
- **Preserve existing `.env.local` content** — only add/update the AdMob section
