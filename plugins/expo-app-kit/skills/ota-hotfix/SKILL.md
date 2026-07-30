---
name: ota-hotfix
description: "Expo 프로젝트에서 EAS Update(OTA)가 앱에 반영되지 않을 때, fingerprint(runtimeVersion) 불일치를 진단하고 빌드 커밋 기반 임시 브랜치에서 JS 변경만 적용하여 OTA를 재배포하는 자동화 스킬. 반드시 이 스킬을 사용해야 하는 경우: 'OTA 업데이트 안 돼', 'OTA 반영 안 됨', 'eas update 반영 안 돼', 'OTA 핫픽스', 'OTA 재배포', 'fingerprint 불일치', 'runtime version 안 맞아', '업데이트가 앱에 안 뜸', '업데이트 다이얼로그 안 나와', 'OTA 디버깅', '앱 업데이트 안 됨', 'eas update 했는데 적용 안 돼', 'OTA update not working', 'eas update not reflecting', 'fingerprint mismatch', 'runtime version mismatch', 'OTA hotfix', 'OTA redeploy', 'app not updating after eas update', 'update not detected'. runtimeVersion.policy: fingerprint 정책을 사용하는 Expo 프로젝트에서 OTA 관련 문제를 언급하면 이 스킬을 트리거할 것."
---

# ota-hotfix — Fingerprint 불일치 OTA 진단 & 재배포

`runtimeVersion.policy: "fingerprint"` 정책을 사용하는 Expo 프로젝트에서 EAS Update(OTA)가 앱에 반영되지 않는 문제를 자동으로 진단하고 해결한다. 핵심 원인은 빌드 이후 네이티브 설정(version, buildNumber, versionCode 등)이 변경되어 fingerprint 해시가 달라진 것이다. 설치된 앱은 다른 fingerprint의 업데이트를 "호환되지 않음"으로 무시한다.

이 스킬은 빌드 커밋으로 돌아가서 JS 변경만 적용한 뒤 OTA를 재배포함으로써, 설치된 앱이 인식할 수 있는 fingerprint로 업데이트를 전달한다.

---

## 전제 조건

실행 전 아래 조건이 충족되는지 확인한다. 하나라도 미충족 시 사용자에게 안내하고 중단한다.

- Expo 프로젝트에서 `runtimeVersion.policy: "fingerprint"` 사용 중
- `eas.json`에 채널별 빌드 프로필 설정 완료 (development/preview/production)
- `eas update`가 이미 실행되었지만 앱에 반영되지 않는 상태
- 빌드와 업데이트 사이에 **JS 변경만** 있어야 함 (네이티브 패키지 추가/제거가 있으면 OTA가 아닌 새 네이티브 빌드가 필요)

---

## 입력값 확인 (게이트)

스킬 실행 전 사용자에게 두 가지를 확인받는다.

1. **대상 채널**: `production` / `preview` 중 어느 채널에 배포할 것인지
2. **업데이트 메시지**: `eas update --message`에 포함할 메시지

미입력 시 질문하고 응답을 대기한다. 채널 기본값은 `production`이다.

---

## Phase 1: 진단

빌드와 업데이트의 fingerprint를 비교하여 불일치 여부를 판단한다. fingerprint가 일치하면 다른 원인을 안내하고, 불일치하면 Phase 2로 진행한다.

### Step 0: Git 상태 사전 점검

Phase 2 진행 가능성에 대비하여 git 상태를 먼저 확인한다. dirty 상태에서 진단만 마치고 "Phase 2 진행하려면 stash 해주세요"라고 하면 사용자 경험이 나쁘다.

```bash
# 현재 브랜치명과 HEAD 커밋 저장 (Phase 2에서 참조)
ORIGINAL_BRANCH=$(git branch --show-current)
CURRENT_COMMIT=$(git rev-parse HEAD)

# working tree clean 확인
git status --porcelain
```

working tree에 변경사항이 있으면 사용자에게 stash 또는 commit을 안내하고 중단한다.

### Step 1: 빌드 정보 수집

```bash
eas build:list --limit 5 --json --channel <채널>
```

출력에서 추출할 정보:
- `runtimeVersion` (fingerprint 해시)
- `channel`
- `buildProfile`
- `appVersion`
- `gitCommitHash` — Phase 2에서 임시 브랜치의 기반 커밋으로 사용

가장 최근 production 빌드를 기준으로 한다. iOS와 Android 빌드가 각각 있을 수 있으므로 둘 다 확인한다.

### Step 2: 업데이트 정보 수집

```bash
eas update:list --branch <채널> --limit 5 --json
```

출력에서 가장 최근 업데이트의 `runtimeVersion`을 추출한다.

### Step 3: Fingerprint 비교

**빌드의 `runtimeVersion`** vs **업데이트의 `runtimeVersion`**을 비교한다.

#### 일치하는 경우 → Phase 2를 실행하지 않는다

fingerprint가 같다면 OTA가 반영되지 않는 원인이 fingerprint 불일치가 아니다. 아래 체크리스트를 안내한다:

1. **채널 불일치**: 빌드 채널과 업데이트 브랜치가 다른 경우 (예: 빌드는 `production`인데 업데이트는 `preview` 브랜치에 배포)
2. **Development 빌드**: development 빌드로 설치된 앱은 `expo-dev-client`를 통해 업데이트를 건너뛸 수 있음
3. **네트워크 문제**: 디바이스가 오프라인이거나 CDN 캐시 미반영
4. **앱 미재시작**: OTA 업데이트는 앱이 완전히 종료(kill) 후 재시작해야 적용됨. 백그라운드→포그라운드 전환으로는 부족할 수 있음
5. **expo-updates 설정**: `updates.checkAutomatically`가 `ON_ERROR_RECOVERY`로 설정된 경우 자동 확인하지 않음
6. **EAS Update 전파 시간**: 배포 직후 수 분 내에는 CDN 전파가 완료되지 않았을 수 있음

#### 불일치하는 경우 → Phase 2 진행

어떤 설정이 변경되었는지 확인한다:

```bash
git diff <빌드커밋>..<현재커밋> -- app.config.js app.config.ts app.json
```

변경된 네이티브 설정(version, buildNumber, versionCode 등)을 사용자에게 보여준다.

### Step 4: 변경 커밋 분석

빌드 이후 어떤 변경이 있었는지 확인한다:

```bash
git log <빌드커밋>..<현재커밋> --oneline --stat
```

이 목록에서 JS/TS 파일 변경 커밋을 식별한다. 동시에 네이티브 패키지 변경(package.json의 dependencies 중 네이티브 모듈 추가/제거)이 있는지 확인한다.

**네이티브 패키지 변경이 감지되면**: OTA로는 해결할 수 없다. 새 네이티브 빌드가 필요하다는 것을 안내하고 중단한다.

```bash
git diff <빌드커밋>..<현재커밋> -- package.json
```

`dependencies`/`devDependencies`에서 네이티브 모듈(react-native-*, expo-*, @react-native-* 등)의 추가/제거/버전 변경이 있으면 네이티브 빌드 필요로 판단한다.

---

## Phase 2: OTA 재배포

빌드 커밋 기반 임시 브랜치에서 JS 변경만 적용하여 OTA를 재배포한다. 이렇게 하면 빌드와 동일한 fingerprint로 업데이트가 생성되어, 설치된 앱이 업데이트를 인식한다.

### Step 1: 임시 브랜치 생성

빌드 커밋에서 임시 브랜치를 생성한다. 이 브랜치의 네이티브 설정은 빌드와 동일하므로 fingerprint가 일치한다. `ORIGINAL_BRANCH`와 `CURRENT_COMMIT`은 Phase 1 Step 0에서 이미 저장되어 있다.

```bash
git checkout <빌드_gitCommitHash> -b hotfix/ota-<appVersion>
```

### Step 2: JS 변경 적용

cherry-pick은 충돌 위험이 높으므로, 파일 단위로 직접 가져온다. `CURRENT_COMMIT`(Phase 1에서 저장한 원래 HEAD)을 사용하여 빌드 이후 변경된 JS/TS 파일만 추출한다.

```bash
# 변경된 JS/TS 파일 목록 추출 (네이티브 config 파일 제외)
git diff --name-only <빌드커밋>..$CURRENT_COMMIT -- '*.js' '*.jsx' '*.ts' '*.tsx' \
  | grep -v -E '^(app\.config\.(js|ts)|app\.json|eas\.json|metro\.config\.js)$'
```

추출된 파일들을 원래 커밋에서 가져온다:

```bash
git checkout $CURRENT_COMMIT -- <파일1> <파일2> ...
```

`grep -v`로 제외하는 이유: `git diff --name-only -- '*.js'`는 `app.config.js` 같은 네이티브 설정 파일도 포함한다. fingerprint에 영향을 주는 이 파일들이 빌드 커밋과 달라지면 OTA가 실패하므로 반드시 제외해야 한다.

### Step 3: 네이티브 파일 무결성 검증

핵심 안전장치다. JS 파일을 가져온 뒤, 네이티브 관련 파일이 빌드 커밋과 동일한지 **staging area 포함**하여 검증한다. 이 시점에서 HEAD는 빌드 커밋이므로, working tree와 index의 변경을 모두 확인해야 한다.

```bash
# staging area + working tree 모두 확인 (커밋 전이므로 HEAD = 빌드 커밋)
git diff --cached -- app.config.js app.config.ts app.json eas.json package.json \
  '*.gradle' '*.plist' '*.pbxproj' 'Podfile*'
git diff -- app.config.js app.config.ts app.json eas.json package.json \
  '*.gradle' '*.plist' '*.pbxproj' 'Podfile*'
```

두 명령 모두 출력이 비어 있어야 한다. **차이가 있으면 즉시 중단**하고 어떤 파일이 변경되었는지 경고한다. 이 검증을 통과해야만 OTA 배포로 진행한다.

### Step 4: 커밋

```bash
git add -A
git commit -m "$(cat <<'EOF'
hotfix(ota): OTA 핫픽스 — fingerprint 일치 상태에서 JS 변경 적용

빌드 커밋(<빌드커밋 short hash>) 기반으로 JS/TS 변경만 적용하여
설치된 앱이 인식할 수 있는 runtimeVersion으로 OTA 업데이트 재배포.

🤖 Generated with [Claude Code](https://claude.ai/code)
Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### Step 5: EAS Update 실행

```bash
# 환경변수 로드 (.env.local이 존재하는 경우)
if [ -f .env.local ]; then
  source .env.local
fi

eas update --channel <채널> --message "<사용자가 입력한 메시지>"
```

#### 에러 처리: p-limit concurrency 에러

`eas update` 실행 중 fingerprint 계산 관련 에러(예: `p-limit concurrency` 에러)가 발생하면, 샌드박스 제한이 원인일 수 있다. `required_permissions: ["all"]`로 재시도한다.

#### 에러 처리: iOS 빌드 부재

iOS 빌드가 없는 경우 Android만 대상으로 진행한다. 사용자에게 iOS는 별도 네이티브 빌드가 필요하다고 안내한다.

### Step 6: 배포 결과 검증

배포 완료 후 새 업데이트의 runtimeVersion이 빌드의 runtimeVersion과 일치하는지 최종 확인한다.

```bash
eas update:list --branch <채널> --limit 1 --json
```

- **일치** → 성공. Phase 3으로 진행한다.
- **불일치** → 에러. 가능한 원인을 분석하여 안내한다:
  - `app.config.js`가 동적으로 환경변수에 따라 값을 변경하는 경우
  - `expo-updates` 플러그인 설정이 fingerprint에 영향을 주는 경우
  - `npx expo-updates fingerprint:generate`로 로컬 fingerprint를 직접 확인하도록 안내

---

## Phase 3: 정리

### Step 1: 원래 브랜치 복귀

```bash
git checkout <ORIGINAL_BRANCH>
```

### Step 2: 임시 브랜치 삭제

```bash
git branch -d hotfix/ota-<appVersion>
```

삭제에 실패하면(머지되지 않은 변경사항 경고), 사용자에게 `-D` 옵션으로 강제 삭제할지 확인받는다.

### Step 3: 최종 결과 요약

아래 형식으로 결과를 출력한다:

```
## OTA 핫픽스 결과

| 항목                    | 값                          |
|------------------------|----------------------------|
| 빌드 fingerprint       | <빌드 runtimeVersion>       |
| 업데이트 fingerprint    | <새 업데이트 runtimeVersion> |
| 매칭 여부              | ✅ 일치 / ❌ 불일치          |
| 채널                   | <채널>                      |
| 대상 플랫폼            | iOS / Android / 둘 다       |

### 앱에서 확인하는 방법
1. 앱을 완전히 종료한다 (백그라운드가 아닌 kill)
2. 앱을 다시 실행한다
3. 업데이트 다이얼로그가 나타나거나, 자동으로 업데이트가 적용된다
4. 반영까지 CDN 전파 시간(최대 수 분)이 소요될 수 있다
```

---

## 에러 처리 요약

| 상황 | 대응 |
|------|------|
| fingerprint 일치 (Phase 1) | Phase 2 실행하지 않음. 다른 원인 체크리스트 안내 |
| 네이티브 패키지 변경 감지 | OTA 불가 안내. 새 네이티브 빌드 필요 |
| working tree dirty | stash/commit 안내 후 중단 |
| 파일 복사 시 충돌 | 중단하고 수동 해결 필요 안내 |
| 네이티브 파일 무결성 검증 실패 | 즉시 중단. 변경된 파일 경고 |
| `eas update` p-limit 에러 | 샌드박스 제한 해제 후 재시도 |
| iOS 빌드 부재 | Android만 진행, iOS 별도 빌드 안내 |
| 배포 후 fingerprint 불일치 | 동적 config, 플러그인 설정 확인 안내 |
