# 커밋 — commit-agent 서브에이전트 전담

이 프로젝트에서 `git commit` 은 메인 에이전트가 직접 실행하지 않는다.
`project-conventions:commit-agent` 서브에이전트(모델 haiku)가 전담한다.

## 왜 위임하는가

커밋 전담을 분리하면 두 가지가 좋아진다. 하나, 값싼 모델이 도는 작업에 메인 컨텍스트를
쓰지 않는다. 둘, "변경을 논리 그룹으로 나눠 그룹마다 커밋"하는 규율이 산문이 아니라
서브에이전트의 고정 절차가 되어 컨텍스트 압축에도 사라지지 않는다.

## 무엇이 강제되는가

`.claude/hooks/commit_agent_gate.py` 가 `PreToolUse` 훅으로 설치되어 있다. 메인 에이전트가
`git commit` 을 직접 실행하려 하면 이 훅이 막고, `Task` 도구로 `project-conventions:commit-agent`
에 위임하라고 안내한다. `commit-agent` 자신의 커밋 호출은 통과시킨다.

**탈출구가 없다.** 이 훅은 이 프로젝트가 명시적으로 선택해 설치한 것이라, 같은 위반을
재시도해도 계속 막힌다 — 프로젝트가 옵트인하지 않으면 애초에 발화하지 않는 것이 안전장치다.
끄려면 환경변수 `COMMIT_AGENT_GATE=off` 로 실행한다.

## commit-agent 가 하는 일

1. **변경 그룹 분류** — 이미 staged 된 경로 우선 → 생성물–원본 짝(예: `.claude/rules/*.md` ↔
   `.cursor/rules/*.mdc`)은 반드시 같은 그룹 → 변경 종류(feat/fix/docs/chore) → 디렉토리 경계
2. **커밋 전 검증** 1회 실행: `bash scripts/validate-marketplace.sh` — 실패하면 아무것도 커밋하지 않는다
3. 그룹마다 `git add -- <명시 경로>` 후 커밋 (`git add -A` 는 쓰지 않는다)
4. `git push`, `--amend`, `git reset`, 브랜치 전환은 하지 않는다

메인 에이전트가 여전히 사용자 승인을 받은 뒤에만 커밋을 요청한다 — 위임은 실행 방식이
바뀌는 것이지, 승인 게이트를 없애는 것이 아니다.

## 릴리즈 커밋 예외

`project-conventions:main-branch-merge` 의 `release: {버전명}` 단일 커밋은 이 훅이 통과시킨다.
릴리스 커밋은 원자적 단일 커밋이어야 하고, 태그가 그 커밋의 최종 HEAD 를 가리켜야 하기 때문이다.
