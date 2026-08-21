---
name: main-branch-merge
description: "dev->main 릴리스 자동화 스킬. 버전 업데이트, Notion 문서 정합성 동기화, README/Release Note 생성, main 머지 & 태그 생성까지 한번에 수행. 반드시 이 스킬을 사용해야 하는 경우: 'main 머지', '릴리스', 'release note', 'README 업데이트', '버전 올려줘', 'dev에서 main으로', '배포 문서', '태그 찍어줘', 버전명(v1.0.0 등)과 함께 머지/릴리스/배포를 언급할 때, 'Notion 보고 README', 'Notion 기반 릴리스 노트'. 한국어/영어 모두 트리거."
---

# Main Branch Merge — 릴리스 자동화

버전명을 입력받아 dev 브랜치에서 릴리스 프로세스를 자동화하는 스킬.

**입력:** `$ARGUMENTS`에서 버전명을 추출한다. 없으면 Step 2.5에서 저장소 문맥으로 후보를 계산해 제안하고 승인받는다.

---

## 실행 순서

아래 단계를 **순서대로** 실행한다. 각 단계에서 실패하면 해당 단계의 에러 처리를 따른다.

---

### Step 1: 입력 수집 & 검증

1. `$ARGUMENTS`에서 버전명 추출
2. 버전명이 없으면 **중단하지 않는다.** `버전 미정`으로 표시하고 Step 2 → Step 2.5(버전 제안 게이트)로 진행
3. 버전명이 있으면 Semantic Versioning 형식 검증 (`vMAJOR.MINOR.PATCH` 또는 `MAJOR.MINOR.PATCH`)
   - `v` 접두사 없으면 자동 추가 (태그명용)
   - 형식 오류 시: "Semantic Versioning 형식이 필요합니다 (예: v1.2.0)" 안내 후 **중단**
4. CLAUDE.md에서 Notion 연동 정보 읽기 (Parent Page ID, PRD/TRD Page ID, Tasks DB ID, Screen Spec DB ID 등)
   - CLAUDE.md가 없거나 Notion 정보 누락 시: "CLAUDE.md에서 Notion 연동 정보를 찾을 수 없습니다. Notion 프로젝트 페이지 URL을 알려주세요." 안내

---

### Step 2: Git 사전 조건 체크

아래 조건을 **모두** 통과해야 다음 단계로 진행한다:

```bash
# 1. Git 저장소 확인
git rev-parse --is-inside-work-tree
# 실패 → "현재 디렉토리가 Git 저장소가 아닙니다." 안내 후 중단

# 2. 현재 브랜치 확인
git branch --show-current
# dev가 아니면 → "현재 {브랜치}입니다. dev로 체크아웃할까요?" 확인

# 3. 워킹 트리 클린 상태 확인
git status --porcelain
# 출력 있으면 → "커밋되지 않은 변경사항이 있습니다. commit 또는 stash 후 다시 시도해주세요." 안내 후 중단

# 4. main 브랜치 존재 확인
git branch --list main
# 없으면 master 확인 → 둘 다 없으면 안내 후 중단

# 5. 태그 중복 확인 — 버전이 정해진 경우에만 지금 수행
git tag -l {버전명}
# 이미 존재 → "태그 {버전명}이 이미 존재합니다. 다른 버전명을 입력해주세요." 안내 후 중단
# `버전 미정`이면 이 체크만 건너뛰고, Step 2.5에서 버전이 정해진 직후에 수행한다
```

체크 5만 조건부인 이유: 버전 제안은 `git tag` 조회가 전제라 저장소 확인(체크 1) 뒤여야 하고,
반대로 태그 중복 확인은 버전이 있어야 한다. 두 요구가 맞물리므로 체크 5만 뒤로 미룬다.

---

### Step 2.5: 버전 제안 & 승인 게이트

**버전이 이미 정해졌으면(인자로 받았으면) 이 단계 전체를 건너뛴다.** `버전 미정`일 때만 수행한다.

버전은 태그·커밋 메시지·`docs/release/{버전명}.md` 파일명에 모두 박히고, Step 9.6에서 push하고
나면 되돌리기 어렵다(아래 "에러 발생 시 롤백 안내" 표 참조). 그래서 추측해서 정하지 않고,
저장소 문맥에서 후보를 계산해 사용자가 고르게 한다.

**① 문맥 수집**

```bash
git tag -l --sort=-v:refname          # 기준선 소스
git log main..dev --oneline           # 변경 성격 판단용 (main 없으면 master)
```

매니페스트 소스는 **Step 3이 버전을 기록할 바로 그 파일들**(`package.json`, `app.json`의
`expo.version`, `app.config.ts` / `app.config.js`)의 **현재** 값을 읽는다. 기준선을 잡는 파일과
갱신 대상 파일이 같아야 기준선이 실제 프로젝트 상태를 뜻한다. 해당 파일이 하나도 없으면
태그만으로 기준선을 잡는다.

**② 후보 계산 — 스크립트에 위임**

버전 파싱·정렬·증가는 LLM이 직접 수행하지 않는다. 같은 저장소인데 호출마다 다른 후보가 나오면
게이트의 의미가 없기 때문이다.

```bash
echo '{"tags":["v1.13.0","v1.12.0"],"manifests":[{"file":"package.json","version":"1.12.0"}]}' \
  | python3 ${CLAUDE_PLUGIN_ROOT}/skills/main-branch-merge/scripts/compute_next_versions.py
```

출력에서 `baseline`, `baseline_source`, `candidates.{patch,minor,major}`, `mismatch`,
`mismatch_detail`, `warnings`를 얻는다. 기준선은 태그와 매니페스트를 통틀어 **최대값**이다 —
이미 공개된 버전보다 낮은 값을 제안하지 않기 위함이다.

- 종료코드 `2` (유효 X.Y.Z 없음) → 초기 릴리스다. `candidates` 대신 출력의 `initial_candidates`
  두 개(`0.1.0`, `1.0.0`)를 후보로 제시한다
- 종료코드 `3` (입력 오류) → 조립한 JSON을 확인하고 재시도. 그래도 실패하면 사용자에게 버전을
  직접 물어본다

**③ 추천 단계 판단**

`main..dev` 커밋 메시지로 어느 후보를 추천할지 정한다. **이 판단만 LLM이 하고, 산술은 하지 않는다.**

| 신호                                                    | 추천                                                                          |
| ------------------------------------------------------- | ----------------------------------------------------------------------------- |
| 본문에 `BREAKING CHANGE`, 또는 `feat!:`·`fix!:` 등 `!` 표기 | major                                                                         |
| `feat:` 접두사 1건 이상                                  | minor                                                                         |
| `fix:`·`chore:`·`docs:`·`refactor:`·`test:`만            | patch                                                                         |
| 접두사를 판별할 수 없음                                  | **추천 표시 없이** 후보만 제시하고, 근거란에 "커밋 접두사 판별 불가"를 적는다 |

마지막 행을 반드시 지킨다 — 근거가 없는데 추천을 붙이면 사용자는 그것을 근거가 있는 것으로 읽는다.
추천은 힌트일 뿐이고, 어느 단계로 올릴지는 사용자의 판단이다.

**④ 제시 형식**

```
[YYYY-MM-DD] 릴리스 버전 제안

기준선    : v1.13.0 (최신 태그)
매니페스트 : package.json 1.12.0   ⚠ 태그와 불일치 — 더 큰 값을 기준선으로 채택했습니다
변경      : main..dev 커밋 5건 — feat 3, fix 2, BREAKING 0

  [1] v1.13.1  patch — 버그 수정만
  [2] v1.14.0  minor — 기능 추가 포함   ← 추천
  [3] v2.0.0   major — 호환성 깨짐

번호를 입력하거나 원하는 버전을 직접 알려주세요 ('중단'이라고 답하면 종료합니다).
```

- `mismatch`가 false면 매니페스트 줄에서 `⚠` 이하를 뺀다. 매니페스트를 하나도 못 읽었으면 그 줄 자체를 생략한다
- `mismatch_detail`이 여러 건이면 줄을 나눠 모두 보여준다 — 어느 파일이 뒤처졌는지가 정보다
- `warnings`(pre-release 무시 등)가 있으면 `변경` 줄 아래에 덧붙인다

**⑤ 승인 게이트**

**사용자 응답 전 진행 금지.** Step 3 이후는 파일을 고치고 커밋·태그·push까지 가므로, 여기서
멈추지 않으면 잘못된 버전을 되돌릴 기회가 없다.

- 번호(`1`/`2`/`3`) 또는 사용자가 직접 입력한 버전만 통과로 간주한다
- `중단`·`아니오`·`취소` 등 부정 응답 → **파일·커밋·태그를 일절 만들지 않고 즉시 종료**
- 애매한 응답("음…", "글쎄")은 재확인 요청으로 처리한다

**⑥ 선택 후 검증**

1. Semantic Versioning 형식 검증 — Step 1의 3번과 같은 규칙. `v` 접두사가 없으면 자동 부여
2. **Step 2에서 미뤄 둔 태그 중복 확인** — `git tag -l {선택 버전}`. 이미 존재하면 재선택을 요청한다
   (후보 3개는 기준선에서 계산되므로 충돌하지 않는다. 사용자가 직접 입력한 버전에서만 발생한다)
3. 선택한 버전이 기준선보다 낮으면 **경고만** 하고 진행한다 — 릴리스 매니지먼트는 사용자의 판단이다

---

### Step 3: 프로젝트 버전 업데이트

dev 브랜치에서 아래 파일들의 버전을 업데이트한다:

| 파일                              | 필드                       | 처리                                    |
| --------------------------------- | -------------------------- | --------------------------------------- |
| `package.json`                    | `"version"`                | 새 버전으로 교체                        |
| `app.json`                        | `expo.version`             | 새 버전으로 교체                        |
| `app.json`                        | `expo.ios.buildNumber`     | 기존값 +1 (문자열). 없으면 `"1"`        |
| `app.json`                        | `expo.android.versionCode` | 기존값 +1 (정수). 없으면 `1`            |
| `app.config.ts` / `app.config.js` | 동일 필드                  | 존재하는 경우에만 패턴매칭으로 업데이트 |

- 버전 업데이트 전후 변경사항을 사용자에게 간략히 보여준다
- `package-lock.json` 존재 시 → `npm install --package-lock-only`로 동기화

---

### Step 4: Notion 문서 전체 읽기

CLAUDE.md의 Notion 연동 정보를 사용하여 프로젝트 문서를 수집한다.

**수집 대상:**

| 소스                               | Notion 도구                      | 추출 정보                                |
| ---------------------------------- | -------------------------------- | ---------------------------------------- |
| 프로젝트 메인 페이지 (Parent Page) | `notion-fetch`                   | 프로젝트명, 개요, 목적, 하위 페이지 목록 |
| PRD 페이지                         | `notion-fetch`                   | 기능 요구사항, 유저 플로우, KPI          |
| TRD 페이지                         | `notion-fetch`                   | 기술 스택, 아키텍처, DB 스키마           |
| Tasks DB                           | `notion-fetch` (Data Source URL) | 전체 태스크 (완료/미완료), Sprint별 분류 |
| Screen Spec DB                     | `notion-fetch` (Data Source URL) | 화면 목록, 컴포넌트                      |
| 기타 하위 페이지                   | `notion-fetch` (재귀)            | 모든 하위 문서 내용                      |

**재귀 탐색:** 메인 페이지의 children을 확인하고, 각 child를 `notion-fetch`하여 전체 문서 트리를 수집한다.

**Notion 연결 실패 시:** "Notion 연결이 필요합니다. Tools 메뉴에서 Notion을 연결해주세요." 안내. Notion 수집에 실패해도 Step 5의 코드 분석은 계속 진행하며, Notion 기반 정보는 TODO placeholder로 표시한다.

---

### Step 5: 코드 vs Notion 비교 & Notion 수정

실제 코드베이스의 현황을 분석하고, Notion 문서와 비교하여 불일치를 수정한다.

**코드베이스 분석 대상:**

| 항목                   | 확인 방법                   | Notion 비교 대상   |
| ---------------------- | --------------------------- | ------------------ |
| 프로젝트 구조          | 파일/폴더 트리 탐색         | TRD 아키텍처       |
| 사용 라이브러리 & 버전 | `package.json` dependencies | TRD 기술 스택      |
| 구현된 화면            | `app/` 디렉토리 구조        | Screen Spec DB     |
| 구현된 컴포넌트        | `src/components/` 탐색      | Design System      |
| 구현된 기능            | 코드 로직 분석              | PRD 기능 요구사항  |
| 환경 설정              | `app.json`, `eas.json` 등   | TRD 배포 전략      |
| Tasks 완료 상태        | 코드 구현 여부              | Tasks DB Done 필드 |

**불일치 처리 규칙:**

```
코드에 구현 O + Notion 미기재   → Notion에 추가
코드에 구현 O + Notion 내용 다름 → Notion을 코드 현황에 맞게 수정
코드에 미구현 + Notion 기재 O   → 미구현으로 표시 (삭제하지 않음)
```

- `notion-update-page`로 Notion 직접 수정
- 수정 실패 시: 리포트만 하고, 이후 단계를 **블로킹하지 않음**
- 수정이 끝나면 **수정 리포트**를 사용자에게 보여준다:

```
📝 Notion 문서 수정 내역

1. TRD > 기술 스택
   - 변경: OOO → XXX (코드에서 XXX 사용 확인)

2. PRD > 기능 요구사항
   - 상태 업데이트: "OOO" → 구현 완료

3. Screen Spec DB
   - 추가: Settings 화면 (app/settings.tsx 존재, DB에 미등록)
```

---

### Step 6: README.md 생성/업데이트

**Step 5에서 정합성이 확보된 Notion 정보 + 코드베이스 분석 결과**를 기반으로 README.md를 작성한다.

**작성 전 반드시** 이 스킬의 레퍼런스 파일을 읽는다:

```
Read: ${CLAUDE_PLUGIN_ROOT}/skills/main-branch-merge/references/readme-best-practices.md
```

이 레퍼런스에 README 구조, 필수 섹션, 포맷팅 규칙, RN/Expo 특화 가이드가 모두 포함되어 있으므로, 외부 웹 검색 없이 바로 적용한다.

**기존 README.md 존재 시:** 기존 구조를 최대한 유지하면서 증분 업데이트.
**신규 생성 시:** 레퍼런스의 풀 템플릿 적용.
**언어:** 한국어 기본.

---

### Step 7: Release Note 생성

**작성 전 반드시** 이 스킬의 레퍼런스 파일을 읽는다:

```
Read: ${CLAUDE_PLUGIN_ROOT}/skills/main-branch-merge/references/release-note-best-practices.md
```

이 레퍼런스에 Keep a Changelog 포맷, 섹션 분류, Notion Tasks 매핑 가이드가 포함되어 있다.

**파일 생성:**

- 경로: `docs/release/{버전명}.md` (예: `docs/release/v1.2.0.md`)
- `docs/release/` 없으면 `mkdir -p`로 생성
- 같은 버전의 파일이 이미 존재하면 → 사용자에게 덮어쓸지 확인

**데이터 소스:**

- Notion Tasks DB에서 완료(`Done: __YES__`) 태스크 목록 → 릴리스 항목에 매핑
- Tasks DB가 비어있거나 없으면 → "수동 항목 추가 필요" 안내 후 코드 변경 기반으로 작성
- 이전 릴리스 파일이 같은 폴더에 있으면 스타일/포맷 일관성 유지
- 날짜는 생성 시점의 날짜 자동 삽입

---

### Step 8: Git Commit (dev 브랜치)

```bash
git add -A
git commit -m "$(cat <<'EOF'
release: {버전명}

- Update project version to {버전명}
- Sync Notion docs with current implementation
- Update README.md
- Add docs/release/{버전명}.md
EOF
)"
```

---

### Step 9: Main 브랜치 머지 & 태그

```bash
git checkout main
git pull origin main          # remote 최신 반영 (실패해도 계속)
git merge dev --no-ff -m "Merge release {버전명} from dev"
```

**머지 충돌 발생 시:**

- 충돌 내용을 분석하여 자동 해결을 시도한다 (버전 필드 등 단순 충돌은 dev 쪽 채택)
- 자동 해결이 어려운 복잡한 충돌은 파일 목록을 표시하고 "머지 충돌이 발생했습니다. 수동으로 해결해주세요." 안내
- 롤백 방법 안내: `git merge --abort`

---

### Step 9.5: 태그 생성

머지 및 충돌 해결이 모두 끝난 후, main HEAD에 릴리스 태그를 생성한다.
lint-staged 등 pre-commit hook이 추가 커밋을 만들 수 있으므로, 태그는 반드시 main의 **최종 HEAD**에 찍어야 한다.

```bash
git tag -a {버전명} -m "Release {버전명}"
```

---

### Step 9.6: Remote Push & dev 동기화

태그 생성이 완료되면, main 브랜치와 태그를 remote에 push하고 dev 브랜치를 동기화한다.

```bash
# main + 태그 push
git push origin main --tags

# dev 브랜치 동기화
git checkout dev
git merge main
git push origin dev
```

**push 실패 시:**

- 네트워크/인증 오류 → 에러 메시지를 표시하고, 수동 push 명령어를 안내한다. 이후 Step 10은 정상 진행.
- remote reject (force push 필요 등) → 절대 `--force` 사용하지 않는다. 원인을 안내하고 사용자가 직접 해결하도록 한다.

---

### Step 10: 결과 요약

모든 작업 완료 후, 아래 형식으로 요약을 출력한다:

```
✅ 릴리스 완료 — {버전명}

📝 Notion 수정: {N}건 수정 (상세 내역은 Step 5 리포트 참조)

📁 변경/생성된 파일:
  - package.json (version: {이전} → {새 버전})
  - app.json (version + buildNumber/versionCode)
  - README.md (업데이트/생성)
  - docs/release/{버전명}.md (생성)

🔀 Git:
  - dev 커밋: release: {버전명}
  - main 머지: Merge release {버전명} from dev
  - 태그: {버전명}
  - push: main + tags → origin ✅
  - dev 동기화: main → dev → origin ✅
```

---

## 에러 발생 시 롤백 안내

전체 프로세스 중 어느 단계에서든 치명적 실패가 발생하면, 이미 완료된 변경사항의 롤백 방법을 안내한다:

| 실패 시점                   | 롤백 방법                                                                                                         |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Step 3 (버전 업데이트) 이후 | `git checkout -- .`                                                                                               |
| Step 8 (커밋) 이후          | `git reset HEAD~1`                                                                                                |
| Step 9 (머지) 이후          | `git checkout dev && git checkout main && git reset --hard HEAD~1 && git tag -d {버전명}`                         |
| Step 9.6 (push) 이후        | remote에 이미 push됨 — `git push origin :refs/tags/{버전명}`으로 태그 삭제 후, main 되돌리기는 사용자와 협의 필요 |

---

## Notion 정보가 전혀 없는 경우의 Fallback

Notion MCP가 미연결이거나 모든 Notion 호출이 실패한 경우에도 릴리스 프로세스는 계속 진행한다:

1. **버전 업데이트** → 정상 진행
2. **Notion 동기화** → 건너뜀 (리포트에 "Notion 미연결" 표시)
3. **README.md** → 코드베이스 분석만으로 작성. Notion에서 가져왔을 섹션은 `<!-- TODO: Notion 연동 후 업데이트 -->` placeholder
4. **Release Note** → git log 기반으로 변경사항 정리. Tasks DB 매핑 불가 표시
5. **Git 커밋/머지/태그/push** → 정상 진행
