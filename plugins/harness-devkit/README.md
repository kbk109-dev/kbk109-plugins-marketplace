# harness-devkit

요구사항을 스프린트로 분해해 도는 3-에이전트 개발 워크플로와, dev 서버를 띄워 감시하는 도구.
스킬 2개 · 훅 1개.

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
| `python3` | harness-dev | 검증 스크립트와 훅 |

## 스킬

### `harness-dev`
한두 문장짜리 요구사항을 **Planner → Generator → Evaluator** 3-에이전트로 나눠 구현한다.
Planner 가 기능 목록과 스프린트 계획을 짜고, 스프린트마다 Generator 가 **한 번에 하나씩** 구현한 뒤
Evaluator 가 독립적으로 5기준(각 7점 미만이면 실패) 채점한다. 실패하면 피드백과 함께 재작업하고,
2회 실패하면 사용자에게 넘긴다.

상태는 `docs/harness/{slug}/` 의 `feature_list.json` · `progress.md` 로 외부화한다. 모든 기능의
`status` 는 `"fail"` 로 시작하며, **통과를 증명해야만** `"pass"` 가 된다.

8가지 기계적 제약 중 넷(criteria 불변 · JSON 유지 · 재시도 상한 · status enum)은 아래 훅과
`validate_feature_list.py` 가 실제로 검사한다. 스텁 금지는 `--stubs` 가 잡는다. 나머지 셋은
판단 영역이라, Phase 1 승인 직후 대상 프로젝트의 `AGENTS.md` 에 설치되는 **규율 블록**이
컨텍스트 압축을 견디게 한다 — 그 블록에는 진행 상태를 쓰지 않으므로 상하지 않고, 작업이 끝나도
제거하지 않는다. 되돌리려면 `harness_agents_block.py --remove`.

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

## `feature_list.json` 규율 훅

규칙 문서만으로는 규율이 지켜지지 않는다. 긴 스프린트에서 컨텍스트가 압축되면 SKILL.md 의
8가지 제약이 컨텍스트에서 사라지고, `acceptance_criteria` 를 두 줄 지우면 어려운 기능이 갑자기
통과한다. 훅은 그 순간을 본다.

`PreToolUse` 로 `Write|Edit` 를 받아, 대상이 `docs/harness/*/feature_list.json` 일 때만 결과
내용을 미리 판정하고 제약 2·6·7·8 위반이면 `deny` 한다.

**전역 배포가 안전한 이유는 세 가지다.**

**조건 미충족이면 아무것도 출력하지 않는다.** 첫 분기가 `file_path` 문자열 검사뿐이라 무관한
Write/Edit 은 파일을 열기도 전에 빠진다. harness 가 끝난 프로젝트에서도 그 파일을 다시 쓰지
않는 한 발화하지 않는다.

**전 구간 fail-open.** 예외는 통째로 삼키고 언제나 exit 0. Edit 의 치환이 애매하면(다중 매치 등)
판정하지 않고 통과시킨다 — 잘못 재현한 내용으로 멀쩡한 편집을 막는 것이 더 나쁘다.

**차단이 복구 가능하다.** 같은 `(에이전트, 위반)` 은 많아야 한 번 차단되므로 동일한 호출을 그대로
다시 하면 **반드시** 통과한다. 상태는 `{tmpdir}/harness-feature-list-gate/{에이전트 해시}.json` 에
두고, 기록에 실패하면 차단하지 않는다 — 기록 없이 차단하면 재시도도 차단되어 이 훅이 절대 만들면
안 되는 루프가 된다. 오판의 최대 대가는 도구 호출 한 번 재시도다.

키를 파일 내용이 아니라 **위반의 종류**로 잡는다. 내용 해시로 잡으면 무관한 한 글자만 바꿔도 새
키가 되어 매번 차단되고, 그게 곧 루프다.

**그래서 이 훅은 제약을 불가능하게 만들지 못한다.** 만드는 것은 조용한 지름길을 의도적인 선택으로
바꾸는 것이다. 불가능하게 만드는 쪽은 스프린트마다 도는 `validate_feature_list.py` 이고, 사람이
그 결과를 본다.

**비용을 알고 지불한다.** `Write|Edit` 매처는 이 플러그인이 켜진 **모든 프로젝트의 모든
Write/Edit 마다** 파이썬 프로세스를 띄운다(호출당 수십 ms). 그래서 첫 분기를 파일시스템 접근
없는 문자열 검사로 두었다.
