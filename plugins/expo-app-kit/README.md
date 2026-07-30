# expo-app-kit

Expo/React Native 앱의 AdMob 광고 도입과 EAS Update(OTA) 핫픽스를 다루는 스킬 4개.

## 설치

```
/plugin install expo-app-kit@kbk109-plugins-marketplace
```

## 선행 요건

| 요건 | 쓰는 곳 | 비고 |
|---|---|---|
| context7 MCP | admob-plan, admob-impl, admob-impl-harness | `react-native-google-mobile-ads` 최신 API 확인. 훈련 컷오프 밖 API 를 추측하지 않기 위한 필수 요건 |
| Expo 프로젝트 | 전부 | `app.json` / `app.config.js` 존재 |
| EAS CLI (`eas`) | ota-hotfix | `eas update` / `eas build` 조회 |
| git | ota-hotfix | 빌드 커밋 기반 임시 브랜치 생성 |

## 스킬

### `admob-plan`
화면 단위로 코드베이스를 분석하고, 5인 가상 전문가 팀(Best Practices Researcher, Monetization
Expert, RN Implementation Specialist, Policy Compliance Reviewer, UX Designer)이 광고 타입·배치를
교차 검토한다. 결과는 `docs/plan/ADMOB-PLAN.md` 에 저장하고 테스트 Ad Unit ID 를 `.env.local` 에 쓴다.

트리거 — "광고 배치 계획", "어디에 광고 넣을지", "admob 설계", "전면 광고 언제 띄워야 해",
"광고 수익 최적화"

### `admob-impl`
`ADMOB-PLAN.md` 를 읽고 실제 소스를 생성·수정한다. 광고 유틸 모듈, Banner/Interstitial/Rewarded/
AppOpen 컴포넌트, 화면별 배치, `app.json` 플러그인 설정, `.env.local` Ad Unit ID 까지 다룬다.

트리거 — "ADMOB-PLAN 기반으로 구현해줘", "배너 광고 코드 넣어줘", "나머지 광고도 구현해줘"

### `admob-impl-harness`
`admob-impl` 과 같은 목적이지만 Harness 구조로 실행한다. Three-Agent Architecture
(Planner–Generator–Evaluator)와 Task State Machine 으로 기능을 개별 task 로 분해하고,
`acceptance_criteria` 기반 독립 검증 루프를 돌려 조기 완료 선언과 미완성 상태를 구조적으로 막는다.
광고 항목이 많거나 한 세션에 끝나지 않을 때 이쪽을 쓴다.

트리거 — "하네스로 광고 구현", "AdMob harness"

### `ota-hotfix`
`runtimeVersion.policy: fingerprint` 를 쓰는 Expo 프로젝트에서 EAS Update 가 앱에 반영되지 않을 때,
fingerprint(runtimeVersion) 불일치를 진단하고 빌드 커밋 기반 임시 브랜치에서 JS 변경만 적용해
OTA 를 재배포한다.

트리거 — "OTA 반영 안 됨", "fingerprint 불일치", "eas update 했는데 적용 안 돼",
"업데이트 다이얼로그 안 나와"

## 권장 흐름

```
admob-plan  →  admob-impl 또는 admob-impl-harness  →  (배포 후 문제 시) ota-hotfix
```
