# product-planning

노션 문서·회의록·요구사항 메모를 PRD(제품 요구사항 문서) 10개 섹션으로 정규화하는 도구.
스킬 1개.

## 설치

```
/plugin install product-planning@kbk109-plugins-marketplace
```

## 선행 요건

| 요건 | 비고 |
|---|---|
| Notion 연동 (선택) | 원본 문서를 Notion 페이지로 주거나 PRD 를 Notion 에 발행하려면 필요. 프로젝트에 `.claude/rules/notion-api-only.md`(`project-conventions:init-agent-rules --notion-rule on`)가 있으면 그것을 쓰고, 없으면 원본은 로컬 파일/직접 입력으로, 발행은 로컬 저장만으로 대체한다 |
| context7 MCP | `engineering-reviewer` 서브에이전트의 기술 토큰 실존성 확인 |
| WebSearch | context7 로 확인 안 되는 토큰의 2차 검증 |
| `python3` | `prd_slug.py`, `validate_prd.py` 실행 |

## 스킬

### `create-prd`

노션 페이지·회의록·요구사항 메모를 입력으로 받아 문서 정보 / 개요 / 유저스토리 / 기능·
비기능 요구사항 / 유저 플로우 / 수용기준 / 의존성 / 위험·가정 / 성공 지표, 10개 섹션을
갖춘 PRD 를 만든다. `docs/plan/PRD-{slug}.md` 가 SSoT 이고, Notion 연동이 있으면 사용자가
지정한 부모 페이지 아래에 사본을 발행한다.

핵심 안전장치:
- 디자인·엔지니어링·QA 리뷰어 서브에이전트 3개를 **별개 컨텍스트에서 병렬** 기동해 초안을
  교차 검토한다 — 생성 주체가 자기 PRD를 검토하지 않는다
- 원본 문서에 없는 성공 지표는 예외 없이 `[제안]` 표기 + 근거를 요구한다
- 모든 기능 요구사항(FR)은 유저스토리(US)를 참조하고, 모든 FR 은 최소 1개의
  Given-When-Then 수용기준(AC)을 가져야 한다 — `validate_prd.py` 게이트가 강제한다

트리거 — "PRD 만들어줘", "회의록을 PRD로", "요구사항 정리해줘", "수용기준 만들어줘"

## 산출물 위치

| 경로 | 내용 |
|---|---|
| `docs/plan/PRD-{slug}.md` | PRD 본문 (SSoT) |
| `docs/plan/logs/review/{design,engineering,qa}.log` | 리뷰어 3개의 근거 로그 |

`{slug}` 는 반드시 `prd_slug.py` 의 출력을 쓴다 — 모델이 kebab-case 를 직접 만들면 다음
세션이 기존 PRD 를 찾지 못하고 중복 문서를 만든다.
