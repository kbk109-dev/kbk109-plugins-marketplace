---
name: main-branch-merge
description: "dev->main 릴리스 자동화 스킬. 버전 업데이트, Notion 문서 정합성 동기화, README/Release Note 생성, main 머지 & 태그 생성까지 한번에 수행. 반드시 이 스킬을 사용해야 하는 경우: 'main 머지', '릴리스', 'release note', 'README 업데이트', '버전 올려줘', 'dev에서 main으로', '배포 문서', '태그 찍어줘', 버전명(v1.0.0 등)과 함께 머지/릴리스/배포를 언급할 때, 'Notion 보고 README', 'Notion 기반 릴리스 노트'. 한국어/영어 모두 트리거."
---

# Main Branch Merge — 릴리스 자동화

버전명을 입력받아 dev 브랜치에서 릴리스 프로세스를 자동화하는 스킬.

**입력:** `$ARGUMENTS`에서 버전명을 추출한다. 없으면 사용자에게 요청.

---

## 실행 순서

아래 10단계를 **순서대로** 실행한다. 각 단계에서 실패하면 해당 단계의 에러 처리를 따른다.

---

### Step 1: 입력 수집 & 검증

1. `$ARGUMENTS`에서 버전명 추출
2. 버전명이 없으면: "릴리스 버전명을 알려주세요. 예: v1.0.0" 안내 후 **중단**
3. Semantic Versioning 형식 검증 (`vMAJOR.MINOR.PATCH` 또는 `MAJOR.MINOR.PATCH`)
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

# 5. 태그 중복 확인
git tag -l {버전명}
# 이미 존재 → "태그 {버전명}이 이미 존재합니다. 다른 버전명을 입력해주세요." 안내 후 중단
```

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
Read: .claude/skills/main-branch-merge/references/readme-best-practices.md
```

이 레퍼런스에 README 구조, 필수 섹션, 포맷팅 규칙, RN/Expo 특화 가이드가 모두 포함되어 있으므로, 외부 웹 검색 없이 바로 적용한다.

**기존 README.md 존재 시:** 기존 구조를 최대한 유지하면서 증분 업데이트.
**신규 생성 시:** 레퍼런스의 풀 템플릿 적용.
**언어:** 한국어 기본.

---

### Step 7: Release Note 생성

**작성 전 반드시** 이 스킬의 레퍼런스 파일을 읽는다:

```
Read: .claude/skills/main-branch-merge/references/release-note-best-practices.md
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
