# harness-devkit

요구사항을 스프린트로 분해해 도는 3-에이전트 개발 워크플로와, dev 서버를 띄워 감시하는 도구. 스킬 2개.

## 설치

```
/plugin install harness-devkit@kbk109-plugins-marketplace
```

## 선행 요건

| 요건 | 쓰는 곳 | 비고 |
|---|---|---|
| context7 MCP | dev-monitor | 기술적 사실 근거 확보 |
| WebSearch | dev-monitor | 외부 이벤트(장애·릴리즈) 근거 확보 |
| 프로젝트 `CLAUDE.md` | dev-monitor | 서버 실행 명령의 단일 소스(SSoT). 없으면 즉시 중단한다 |

## 스킬

### `harness-dev`
한두 문장짜리 요구사항을 **Planner → Generator → Evaluator** 3-에이전트로 나눠 구현한다.
Planner 가 기능 목록과 스프린트 계획을 짜고, 스프린트마다 Generator 가 **한 번에 하나씩** 구현한 뒤
Evaluator 가 독립적으로 5기준(각 7점 미만이면 실패) 채점한다. 실패하면 피드백과 함께 재작업하고,
2회 실패하면 사용자에게 넘긴다.

상태는 `docs/harness/{slug}/` 의 `feature_list.json` · `progress.md` 로 외부화한다. 모든 기능의
`status` 는 `"fail"` 로 시작하며, **통과를 증명해야만** `"pass"` 가 된다.

기능 5개 이상의 앱·서비스 빌드에 쓴다. 단순 버그 수정·단일 파일 리팩터·질문에는 쓰지 않는다.

참고 문서 — [`docs/harness-engineering/`](../../docs/harness-engineering/)

### `dev-monitor`
`CLAUDE.md` 에서 서버 실행 명령을 추출한 뒤, 지정한 포트의 기존 프로세스를 정리하고 서버를
백그라운드로 기동한다. 이후 로그를 실시간 감시하면서 WARNING/ERROR/CRITICAL/스택 트레이스/
HTTP 4xx·5xx 를 감지할 때마다 `[날짜, 시간]` 헤더와 함께 원인·해결책을 한국어로 분석 보고한다.

상태를 `~/.claude/dev-monitor/port-<port>.state.json` 에 외부화하므로 `/loop` 나 재호출 시
기존 Monitor·서버를 재사용하고 중복 기동을 막는다.

이 스킬은 `disable-model-invocation: true` — 자동 트리거되지 않고 명시적으로 호출해야 한다.

```
/harness-devkit:dev-monitor 3000              # 기동 + 감시
/harness-devkit:dev-monitor 3000 <log-path>   # 로그 경로 지정
/harness-devkit:dev-monitor status            # 상태 조회
/harness-devkit:dev-monitor stop 3000         # 해당 포트만 정리
/harness-devkit:dev-monitor stop-all          # 전부 정리
```

**서버 기동 명령은 `CLAUDE.md` 가 단일 소스다.** 없거나 모호하면 추측하지 않고 중단한다 —
잘못된 명령으로 서버를 띄우는 것보다 멈추는 게 낫다는 판단이다.

탐색 순서: `./CLAUDE.md` → `./.claude/CLAUDE.md` → `./docs/CLAUDE.md` → `~/.claude/CLAUDE.md`
