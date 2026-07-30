# release-workflow

Notion 데이터베이스를 상태 저장소로 쓰는 릴리즈 파이프라인. 스킬 4개.

이 플러그인의 스킬들은 **상태를 Notion + 로컬 `docs/skills/` 에 외부화**한다. 세션이 끊겨도
다음 세션이 같은 상태에서 이어받고, "구현했다"는 선언 대신 **증거 로그로 통과를 증명**하게 만든다.

## 설치

```
/plugin install release-workflow@kbk109-plugins-marketplace
```

## 선행 요건

| 요건 | 쓰는 곳 | 비고 |
|---|---|---|
| Notion MCP | 전부 | DB 생성·조회·상태 역동기화. 이게 없으면 동작하지 않는다 |
| context7 MCP | release-plan, release-impl | 기술 토큰 팩트체크 (모델 ID·라이브러리·버전) |
| WebSearch | release-plan | context7 로 확인 안 되는 토큰의 2차 검증 |
| `python3` | release-plan, release-impl, fix-plan-impl | 검증 스크립트 17개 실행 |
| git | fix-plan-impl, main-branch-merge | 브랜치 생성·머지·태그 |

## 스킬

### `release-plan`
Notion 페이지명·DB명·목표 버전(X.Y.Z)·업데이트 설명을 받아 버전별 작업 레코드를 만든다.
`[Task N]` 라벨, 의존관계, 병렬작업 메타데이터를 붙인다.

핵심 안전장치 — 작업 상세에 등장하는 **모든 기술 토큰**(모델 ID, 라이브러리명, 패키지 버전)을
별도 fact-checker 서브에이전트가 context7 MCP + WebSearch 로 검증하고,
`verify_tech_tokens.py` 게이트가 미검증 토큰이 하나라도 있으면 Notion 등록을 차단한다.
분해 주체와 검증 주체를 분리하는 것이 자기평가 편향과 "훈련 컷오프 밖 세계에 대한 자신감 있는
할루시네이션"을 막는 핵심이다.

트리거 — "릴리즈 계획", "버전 계획 세워줘", "작업 분해해서 노션에 등록", "다음 버전 계획"

### `release-impl`
`release-plan` 이 등록한 버전별 작업 목록을 읽어 3-에이전트 하네스로 실행한다.
Generator/Evaluator 서브에이전트 분리, fail/pass/blocked 전이를 갖는 Task State Machine,
증거 로그 없이는 pass 불가능한 게이트, 스프린트 계약, Notion 역방향 상태 동기화.

입력 3개 필요 — Notion 페이지명, DB명, 버전(`vX.Y.Z`).

트리거 — "v1.2.0 구현", "릴리즈 작업 시작", "릴리즈 구현 이어서"
(`구현/개발/작업 시작` 은 `vX.Y.Z` 토큰이 함께 있을 때만 트리거된다)

### `fix-plan-impl`
버그 수정 릴리즈의 계획+구현을 한 번에 진행하는 오케스트레이터. Notion Release Plan DB 에서
최신 shipped 버전을 조회해 patch 를 +1 한 버전으로 `fix/v{버전}` 브랜치를 만든 뒤
`release-plan` → `release-impl` 을 순차 호출한다.

계획만 또는 구현만 필요할 때는 트리거되지 않는다 — 둘을 묶어 처리할 때만 쓴다.

트리거 — "버그 수정 릴리즈", "패치 릴리즈", "핫픽스 계획+구현", "버그 고치고 릴리즈"

### `main-branch-merge`
dev→main 릴리스 자동화. 버전 업데이트, Notion 문서 정합성 동기화, README/릴리즈 노트 생성,
main 머지와 태그 생성까지 수행한다.

트리거 — "main 머지", "릴리스", "release note", "태그 찍어줘", "Notion 기반 릴리스 노트"

## 권장 흐름

```
일반 릴리즈:   release-plan  →  release-impl  →  main-branch-merge
패치 릴리즈:   fix-plan-impl (계획+구현 일괄)  →  main-branch-merge
```

## 산출물 위치

| 경로 | 내용 |
|---|---|
| `docs/skills/release-plan/{DB slug}/v{버전}/` | `release-plan.md`, `task_list.json`, `progress.md` |
| `docs/skills/release-impl/v{버전}/` | `feature_list.json`, `PROGRESS.md` |

`{DB slug}` 는 반드시 `slugify.py` 의 출력을 쓴다 — 모델이 kebab-case 를 직접 만들면 경로가
호출마다 달라진다.
