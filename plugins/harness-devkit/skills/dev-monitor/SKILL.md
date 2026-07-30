---
name: dev-monitor
description: "프로젝트 CLAUDE.md에서 서버 실행 명령을 추출한 뒤, 지정한 포트의 기존 프로세스를 정리하고 서버를 백그라운드로 기동한다. 이후 로그를 실시간 모니터링하면서 WARNING/ERROR/CRITICAL/스택 트레이스/HTTP 4xx·5xx를 감지할 때마다 [날짜, 시간] 헤더와 함께 원인·해결책을 한국어로 분석 보고한다. 상태는 ~/.claude/dev-monitor/port-<port>.state.json 에 외부화되어 /loop·재호출 시 기존 Monitor·서버를 재사용하고 중복 기동을 방지한다. 포트번호는 필수 입력. 하위 명령 'stop'/'stop <port>'/'stop-all'/'status'를 지원한다. 서버 기동 명령은 CLAUDE.md가 단일 소스(SSoT)이며, 없거나 모호하면 즉시 중단한다. 기술적 사실은 context7 MCP로, 외부 이벤트는 WebSearch로 근거를 확보한다. 트리거: '서버 모니터링', '포트 정리하고 서버 실행', 'dev 서버 띄우고 로그 감시', '/harness-devkit:dev-monitor', '/harness-devkit:dev-monitor stop'."
disable-model-invocation: true
argument-hint: <port> [log-path] | stop [port] | stop-all | status
allowed-tools: Bash, Read, Grep, Glob, WebSearch, WebFetch
---

# Dev Server Auto-Monitor

## Phase 0 — 입력 검증 (하드 게이트 1)

### 0-0. 특수 하위 명령 선분기

`$1`이 다음 토큰이면 일반 포트 검증을 건너뛰고 해당 경로로만 진행한다:

- `stop` 또는 `stop-all` → **Phase 8 (종료 절차)** 로 직행. 이후 Phase 0 숫자 검증·Phase 1 탐색·Phase 2 cleanup 전부 건너뜀.
- `status` → Phase 0.5의 상태 파일 스캔 결과만 Phase 7 포맷으로 출력하고 종료. 새 기동·재등록 없음.
- `stop` + `$2=<port>` 형식 → 해당 포트의 상태 파일 한 개만 종료 (전체 정리는 `stop-all`).

이 선분기는 재진입 안전성의 1차 방어선이다 — 사용자가 `/harness-devkit:dev-monitor stop`을 입력했을 때 "포트가 숫자가 아니다" 오류로 중단되는 회귀를 막는다.

### 0-1. 포트 검증

`$1`이 특수 명령이 아니면 **PORT로 간주**하고 아래를 검증한다. 하나라도 해당하면 **즉시 중단**하고 안내만 출력한다:

- `$1`이 비어 있음
- `$1`이 숫자가 아님
- `$1`이 1~65535 범위를 벗어남
- `$1`이 well-known reserved port(0, 22, 80, 443, 3306, 5432, 6379 등)에 해당 → **경고 후 명시적 확인 요청** (확인 전 진행 금지)

**중단 시 출력 포맷**:
````
[YYYY-MM-DD HH:MM] /harness-devkit:dev-monitor 실행 중단

포트번호는 필수 입력입니다.

사용법:
  /harness-devkit:dev-monitor <port> [log-path]

예시:
  /harness-devkit:dev-monitor 8000
  /harness-devkit:dev-monitor 8080 /tmp/api.log

- port: 필수. 1~65535 사이의 정수
- log-path: 선택. 미지정 시 /tmp/dev_server_<port>.log
- server-cmd: CLAUDE.md에서 자동 추출 (아래 Phase 1 참조)
````

## Phase 0.5 — 재진입 감지 (중복 기동 방지, 상태 외부화)

### 왜 이 Phase가 필요한가

LLM은 세션 간 영구 메모리가 없다. `/loop 10m /harness-devkit:dev-monitor 8000` 같은 재호출 시 `TaskList`는 현재 세션만 반영하므로 이전 세션에서 등록한 Monitor가 "없는 것"으로 보인다. 상태를 **파일로 외부화**해서 매 실행 첫 단계에서 복원해야, 같은 포트에 Monitor가 중복 등록되고 서버가 이중 기동되는 사고를 구조적으로 막을 수 있다(CLAUDE.md 실패 모드 1 "세션 간 상태 소실" 대응).

### 상태 파일 계약

- **경로**: `~/.claude/dev-monitor/port-${PORT}.state.json`
- **디렉토리 생성**: `mkdir -p ~/.claude/dev-monitor` (Phase 4 기동 전 보장)
- **스키마**:
  ````
  {
    "port": 8000,
    "server_pid": 12345,
    "monitor_pid": 12346,
    "log_path": "/tmp/dev_server_8000.log",
    "server_cmd": "uv run uvicorn api.main:app --reload --port 8000",
    "claude_md_path": "./CLAUDE.md",
    "started_at": "2026-04-19T02:30:00Z",
    "last_heartbeat_at": "2026-04-19T02:50:00Z"
  }
  ````

### 재진입 절차

1. 상태 파일 경로에서 JSON 로드 시도
2. 파일이 **없으면** Phase 1로 진행 (신규 세션)
3. 파일이 **있으면** 프로세스 생존 확인:
   - `ps -p ${server_pid} -o pid= 2>/dev/null` — 종료코드 0이면 서버 생존
   - `ps -p ${monitor_pid} -o pid= 2>/dev/null` — 동일, Monitor 생존
4. 분기:

| 서버 PID | Monitor PID | 조치 |
|---|---|---|
| 생존 + 포트 일치 | 생존 | **기존 세션 재연결**. Phase 1~5 전부 건너뛰고 Phase 7(상태 보고)로 직행. "기존 Monitor 재사용" 메시지 출력. |
| 생존 | 죽음 | Monitor만 재등록(Phase 5). 서버 재기동 금지. |
| 죽음 | 생존 | Monitor kill → stale state 삭제 → Phase 1부터 정상 진행 |
| 죽음 | 죽음 | stale state 삭제 → Phase 1부터 정상 진행 |
| 생존, 포트 불일치 | - | 경고 + 사용자 확인 요청(서버가 다른 포트에 있다면 의도적? 상태파일 오염?) |

### 포트 점유자 교차 검증

상태 파일의 `server_pid`와 `lsof -ti :${PORT}` 결과가 일치해야 "같은 서버"라고 단정할 수 있다. 불일치하면:
- **lsof에 PID 있음, 상태파일과 다름**: 외부에서 기동된 서버 존재 → stale state 삭제 안 함, 사용자에게 결정 위임
- **lsof 비어 있음, 상태파일에 PID 있음**: 서버가 이미 죽었음 → stale state 삭제, 정상 진행

### 재연결 시 출력 포맷

````
[YYYY-MM-DD HH:MM, 기존 Monitor 재연결]

| 항목 | 값 |
|---|---|
| PORT | 8000 |
| Server PID | 12345 (생존) |
| Monitor PID | 12346 (생존) |
| 최초 기동 | 2026-04-19 02:30 |
| 경과 시간 | 20분 |
| Log | /tmp/dev_server_8000.log |

기존 세션을 그대로 사용합니다. 서버·Monitor 재기동은 건너뜁니다.
중단하려면 /harness-devkit:dev-monitor stop 또는 /harness-devkit:dev-monitor stop 8000 을 입력하세요.
````

## Phase 1 — CLAUDE.md에서 SERVER_CMD 추출 (하드 게이트 2)

### 1-1. 탐색 순서

프로젝트 루트 기준으로 다음 경로를 **순차 탐색**한다:

1. `./CLAUDE.md` (프로젝트 루트, 최우선)
2. `./.claude/CLAUDE.md`
3. `./docs/CLAUDE.md`
4. `~/.claude/CLAUDE.md` (개인 기본값, 마지막 폴백)

첫 번째로 발견되는 파일을 **단일 소스(SSoT)**로 사용한다. 발견된 경로를 사용자에게 표시한다.

**하나도 없으면 즉시 중단** (아래 1-5 참조).

### 1-2. 추출 전략 (우선순위 순)

발견된 CLAUDE.md에서 다음 패턴을 **위에서 아래 순서로** 시도한다:

**전략 A — 명시적 섹션 (가장 신뢰도 높음)**
````
## Dev Server / ## 개발 서버 / ## Run / ## How to Run / ## Getting Started / ## Local Dev
````
위 헤딩 아래에 있는 **첫 번째 코드블록(```bash 또는 ```sh)**의 명령을 채택.

**전략 B — 키-값 라인**
````
- dev server: <명령>
- run command: <명령>
- start: <명령>
- 실행: <명령>
````
정규식: `(?i)^[\s\-\*]*(dev\s*server|run\s*command|start|실행|기동)[\s:]+(?P<cmd>.+)$`

**전략 C — 전체 파일에서 서버 관련 코드블록 스캔**
파일 전체의 모든 bash/sh 코드블록을 훑어 다음 시그니처 중 하나를 포함하는 라인을 후보로 수집:
- `uvicorn`, `fastapi dev`, `uv run ... uvicorn`
- `pnpm dev`, `npm run dev`, `yarn dev`, `bun dev`
- `next dev`, `nest start`, `vite`, `astro dev`
- `rails server`, `python manage.py runserver`, `flask run`
- `go run`, `cargo run`, `air`

**후보가 2개 이상이면 Phase 1-4로 진행 (모호성 해소).**

### 1-3. 포트 일치 검증

추출된 명령에 포트 지정 플래그가 포함되어 있으면 **PORT(`$1`) 값과 일치하는지 확인**:
- `--port 8080`, `-p 3000`, `PORT=3000`, `--host 0.0.0.0:3000` 등

**불일치 시**: 사용자에게 차이를 보여주고 다음 중 선택 요청:
````
[YYYY-MM-DD HH:MM] 포트 불일치 감지

CLAUDE.md 추출 명령: uv run uvicorn api.main:app --port 8000
사용자 입력 포트: 3000

어떻게 진행할까요?
  A) CLAUDE.md 명령의 --port를 3000으로 치환해 실행
  B) 입력 포트를 8000으로 변경하고 명령 그대로 실행
  C) 중단
````

포트 플래그가 **없는 명령**(예: `pnpm dev`)인 경우, 프레임워크의 환경변수 관례를 적용:
- Next.js / Node: `PORT=${PORT} <command>`
- Python/Uvicorn: 사용자에게 확인 요청 (`--port` 플래그 필요 여부)

### 1-4. 모호성 해소

후보가 2개 이상이거나 명령이 불분명한 경우:
````
[YYYY-MM-DD HH:MM] CLAUDE.md에서 서버 실행 명령 후보 N개 발견

발견 위치: ./CLAUDE.md

후보:
  [1] uv run uvicorn api.main:app --reload --port 8000   (## Dev Server 섹션)
  [2] pnpm dev                                            (## Getting Started 섹션)
  [3] docker compose up api                               (## Docker 섹션)

어느 것을 사용할까요? (번호 입력 또는 '중단')
````

**사용자 응답 전 진행 금지.**

### 1-5. 추출 실패 시 (하드 게이트)

다음 상황에서 **즉시 중단**:
- CLAUDE.md 파일을 어느 경로에서도 찾지 못함
- 파일은 있으나 서버 실행 명령을 전략 A/B/C 어디에서도 찾을 수 없음
- 후보 명령이 포트 지정과 프레임워크 관례 모두에서 PORT 바인딩 불가

**중단 시 출력 포맷**:
````
[YYYY-MM-DD HH:MM] /harness-devkit:dev-monitor 실행 중단

CLAUDE.md에서 서버 실행 명령을 찾을 수 없습니다.
탐색 경로: ./CLAUDE.md, ./.claude/CLAUDE.md, ./docs/CLAUDE.md, ~/.claude/CLAUDE.md
발견 파일: <경로 또는 '없음'>

CLAUDE.md에 다음과 같은 섹션을 추가해 주세요:

  ## Dev Server

```bash
  uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

또는 키-값 형태:

  - dev server: uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

추가 후 /harness-devkit:dev-monitor <port> 를 다시 실행해 주세요.
````

## 변수 확정 (Phase 0, 1 통과 후)

- **PORT** = `$1` (필수, 검증 완료)
- **SERVER_CMD** = CLAUDE.md에서 추출 + 포트 치환 완료된 최종 명령
- **LOG_PATH** = `$2` (미지정 시 `/tmp/dev_server_${PORT}.log`)
- **CLAUDE_MD_PATH** = 추출에 사용된 실제 파일 경로

**세션 시작 시 출력 (필수)**:
````
[YYYY-MM-DD HH:MM, 세션 시작]

| 항목 | 값 |
|---|---|
| PORT | <port> |
| SERVER_CMD | <추출된 최종 명령> |
| LOG_PATH | <경로> |
| CLAUDE.md 출처 | <경로> (전략 A/B/C 중 무엇으로 추출했는지) |
````

## Phase 2 — 포트 정리

1. `lsof -ti :${PORT}` 로 점유 PID 목록 확보
2. `lsof -i :${PORT} -n -P` 로 각 PID의 COMMAND/상태 확인 → 사용자에게 표로 보고
3. **서버 프로세스만** `kill -9 <PID>` (uvicorn/node/python/ruby 등)
4. **브라우저/클라이언트 프로세스(Chrome, Safari, Postman 등)는 절대 kill 하지 않음** — CLOSE_WAIT 소켓은 서버 종료 후 자연 해제
5. 2초 대기 후 포트 재확인. CLOSE_WAIT만 남았다면 "서버 기동하면 즉시 해제됨"으로 설명하고 Phase 4 진행

## Phase 3 — 의존성 체크 (선택적)

프로젝트 루트에 `docker-compose.yml` 또는 `compose.yml`이 존재하면:
````bash
docker compose ps
````
- 주요 서비스(db, redis, kafka 등) Up/healthy 확인
- 비정상 서비스 발견 시 **기동 중단하고 사용자에게 먼저 보고**

## Phase 4 — 서버 백그라운드 기동

````bash
nohup ${SERVER_CMD} > ${LOG_PATH} 2>&1 &
SERVER_PID=$!
echo "Server PID: ${SERVER_PID}"
````

- 3초 대기 후 `tail -30 ${LOG_PATH}` 로 부팅 로그 확인
- 추가 4초 대기 후 health 엔드포인트 탐색:
  - `/health`, `/healthz`, `/api/health`, `/ping` 순으로 `curl -s http://localhost:${PORT}/...` 시도
  - 200 응답 확보 시 JSON을 포맷해 출력
- 기동 실패 시 `tail -50 ${LOG_PATH}` 를 보여주고 원인 분석 후 중단
  - **원인이 SERVER_CMD 자체에 있으면 CLAUDE.md 내용이 최신인지 사용자에게 확인 요청**

### Phase 4 후처리 — 상태 파일 기록 (필수)

서버 기동이 확인되면 **즉시** 상태 파일을 기록한다. Monitor 등록 전이라도 `server_pid` + 메타데이터를 먼저 저장해야, 이후 Phase 5가 크래시해도 다음 세션이 stale 서버를 정리할 수 있다.

````bash
mkdir -p ~/.claude/dev-monitor
STATE_FILE=~/.claude/dev-monitor/port-${PORT}.state.json
cat > ${STATE_FILE} <<JSON
{
  "port": ${PORT},
  "server_pid": ${SERVER_PID},
  "monitor_pid": null,
  "log_path": "${LOG_PATH}",
  "server_cmd": "${SERVER_CMD}",
  "claude_md_path": "${CLAUDE_MD_PATH}",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "last_heartbeat_at": null
}
JSON
````

상태 파일 기록 실패 시에는 **서버를 kill하고 중단**한다 — 재진입 안전장치가 없는 상태로 스킬을 계속 진행하면 중복 기동을 유발한다.

## Phase 5 — 실시간 모니터링 루프 등록

### 사전 체크 (중복 등록 방지)

상태 파일의 `monitor_pid` 필드가 `null`이 아니고 해당 PID가 생존 중이면 **재등록을 건너뛴다**. Phase 0.5에서 이미 처리되었어야 하지만, Phase 0.5를 우회한 경로(예: Phase 4 직후 Phase 5로 직행한 fresh 세션에서 재시도가 발생)에서도 최종 방어선으로 한 번 더 확인한다.

### Monitor 등록

**Monitor 백그라운드 태스크를 persistent로 등록**한다:

````bash
tail -f ${LOG_PATH} | grep --line-buffered -E "\[(warning|error|critical)\]|Traceback|Exception|raise |AssertionError| [45][0-9]{2} [A-Z]|panic|OOM|FATAL"
````

등록 직후 Monitor의 PID를 확보하고 상태 파일을 갱신한다:

````bash
MONITOR_PID=<확보한 PID>
python3 -c "
import json, sys, pathlib
p = pathlib.Path.home() / '.claude/dev-monitor/port-${PORT}.state.json'
d = json.loads(p.read_text())
d['monitor_pid'] = ${MONITOR_PID}
p.write_text(json.dumps(d, indent=2))
"
````

Fallback heartbeat: 20분. heartbeat 때마다 상태 파일의 `last_heartbeat_at`을 갱신해 "최근 살아 있던 시각" 추적이 가능하게 한다.

**grep 패턴 주의**:
- HTTP 상태 매칭은 반드시 `[45][0-9]{2} [A-Z]` (uvicorn 액세스 로그 포맷) — 단독 `[0-9]{3}`은 버전 해시·포트 번호 오탐 유발
- `failed|timeout|error` 같은 범용 단어 단독 매칭 금지 — structlog 레벨 태그 `[warning]/[error]/[critical]` 우선

## Phase 6 — 이상 감지 시 응답 규칙

### 필수 응답 포맷

1. **머리글**: `[YYYY-MM-DD HH:MM]` (KST, 24시간제) — **모든 응답 예외 없이**
2. **언어**: 한국어
3. **구조**:
   - 🔴/🟠/🟡 심각도 + 이슈 요약 한 줄
   - 원문 로그 라인 인용 (코드 블록)
   - **원인**: 근본 원인 해설
   - **해결 방향**: 표 (우선순위 | 조치 | 효과)
   - 현재 영향 범위 + 자동 복구 가능 여부

### 근거 확보 절차

프레임워크·라이브러리·프로토콜 사양(HTTP 코드, 표준 예외 등) → **context7 MCP 우선 조회**:
````
1. context7:resolve-library-id 로 라이브러리 식별
2. context7:query-docs 로 공식 문서 확인
````

context7에 없는 경우, 또는 외부 이벤트(사이트 차단 정책, CVE, 최근 장애) → **WebSearch/WebFetch**로 보강.

**근거 없이 추측 금지.**

### 심각도 분류

| 패턴 | 심각도 | 응답 속도 |
|---|---|---|
| `[critical]`, `Traceback` 연속, 5xx 5회+, `OOM`, `panic`, `FATAL` | 🔴 즉시 | 감지 즉시 |
| `[error]`, 4xx 연속 발생, `proxy_pool_exhausted`, `early_abort`, `circuit_breaker_open` | 🟠 단기 | 30초 내 |
| `[warning]` 단발, 4xx 단발, `sample_lt_n`, 단발 `timeout` | 🟡 관찰 | heartbeat 시 묶어서 |

## Phase 7 — 이상 없음 보고 (heartbeat 또는 사용자 "상태 확인" 요청)

간결한 테이블 한 개:

| 항목 | 상태 |
|---|---|
| 서버 | 정상 가동 (PID: ..., Port: ${PORT}) |
| 마지막 신규 이벤트 | `[HH:MM]` ... |
| 이후 신규 이상 | 없음 / N건 (기보고) |
| Monitor ID | ... |
| 다음 heartbeat | `HH:MM` |

## Phase 8 — 종료 절차 (`/harness-devkit:dev-monitor stop`, `stop-all`)

### 대상 선정

- `/harness-devkit:dev-monitor stop <port>` → `~/.claude/dev-monitor/port-<port>.state.json` 한 파일만
- `/harness-devkit:dev-monitor stop` 또는 `/harness-devkit:dev-monitor stop-all` → `~/.claude/dev-monitor/port-*.state.json` 전부 순회

### 각 상태 파일에 대해

1. JSON 로드. 필드 없어도 best-effort로 진행.
2. `monitor_pid`부터 종료: `kill <monitor_pid>` → 2초 대기 → 살아 있으면 `kill -9 <monitor_pid>`
3. `server_pid` 종료: `kill <server_pid>` → 3초 대기 → 살아 있으면 `kill -9 <server_pid>`
4. `lsof -ti :<port>`로 해당 포트가 비었는지 재확인. 잔여 PID가 있고 **상태 파일의 server_pid와 일치하면** 추가 `kill -9` (외부 프로세스는 건드리지 않음)
5. 상태 파일 삭제: `rm ~/.claude/dev-monitor/port-<port>.state.json`
6. 종료 리포트 출력 (아래 포맷)

### 종료 리포트 포맷

````
[YYYY-MM-DD HH:MM, /harness-devkit:dev-monitor stop 실행]

| 포트 | Server PID | Monitor PID | 결과 |
|---|---|---|---|
| 8000 | 12345 → terminated | 12346 → terminated | ✅ 정리 완료 |
| 3000 | 22222 (이미 종료됨) | null | ⚠️ stale state만 삭제 |

정리 대상 상태 파일: N개
실제 종료된 프로세스: M개
남은 Monitor: 없음
````

`stop`이 "외부 프로세스까지 무차별 kill"이 아니라 "이 스킬이 기동한 것만 정리"임을 명확히 해야 한다 — 상태 파일에 기록된 PID만 신뢰한다.

## 사용자가 다른 작업을 요청하면

- Monitor는 백그라운드에 둔 채 요청한 작업 수행
- 작업 중에도 Monitor 이벤트가 오면 현 작업 마무리 후 즉시 분석 보고
- 사용자가 `/harness-devkit:dev-monitor stop` 또는 명시적 중단 지시 시에만 Monitor 태스크 종료

## `/loop` / 재호출 시나리오 요약

- `/loop 10m /harness-devkit:dev-monitor 8000` 같은 반복 호출에서도 **매 tick마다 Phase 0.5가 상태 파일을 먼저 확인**한다
- 기존 Monitor + 서버가 살아 있으면 Phase 1~5 전부 건너뛰고 Phase 7 상태 보고만 수행 → Monitor 중복 등록 불가
- TaskList가 비어 있다고 해서 "새로 만들어야 한다"고 판단해선 안 된다. TaskList는 세션 메모리, 상태 파일은 영속 메모리. **상태 파일이 우선**이다.

## 금지 사항

- **포트 미입력 시 기본값 가정 금지** (Phase 0 하드 게이트)
- **CLAUDE.md 없이 서버 명령 하드코딩 금지** (Phase 1 하드 게이트)
- **SERVER_CMD 자체 추론으로 기동 금지** — 반드시 CLAUDE.md에서 추출된 명령만 사용
- **상태 파일 확인 없이 Phase 2 진행 금지** (Phase 0.5 게이트) — 재진입 시 중복 기동의 근본 원인
- **기존 Monitor 생존 시 새 Monitor 등록 금지** — `/loop`/재호출에서도 동일
- **상태 파일 기록 실패 시 서버 방치 금지** — 기록 실패하면 방금 띄운 서버를 kill 후 중단
- **TaskList만 보고 "Monitor 없음" 판단 금지** — 세션 메모리는 휘발성, 상태 파일이 Ground Truth
- Chrome 등 브라우저 프로세스 kill 금지
- grep 패턴에 `[0-9]{3}` 단독 사용 금지
- `[YYYY-MM-DD HH:MM]` 머리글 생략 금지
- context7/WebSearch 확인 없이 기술적 단정 금지
- `disable-model-invocation: true` 이므로 사용자가 `/harness-devkit:dev-monitor <port>`를 명시적으로 입력해야만 실행됨
