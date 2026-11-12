# TC: {에픽 NN-slug}

에픽의 테스트 케이스 문서다. 구현 코드를 보지 않고 PRD·PLAN·acceptance_criteria 만으로 쓴다 —
코드를 보고 쓰면 TC 가 구현에 맞춰 느슨해진다. 확정되면 `.tc_lock.json` 으로 잠기고, 이후 수정은
tc-critic 재검토를 거친다.

## 규칙
- feature 의 `acceptance_criteria` 는 1부터 번호를 센다. 모든 번호가 `criterion` 으로 ≥1 TC 에 걸려야 한다.
- 정상 경로뿐 아니라 경계값, 오류·실패, 권한, 빈 상태·데이터 상태, 회귀를 포함한다.
- `expected` 는 기계로 판정할 수 있게 쓴다 (종료 코드, 출력 문자열, HTTP 상태, 화면 요소 존재).
- `command` 는 PLAN 의 Run & Verify 명령 또는 그 인자 변형이다. 실제로 실행되는 명령만 쓴다.
- `command` 는 `expected` 를 스스로 판정해 **종료 코드로 답한다** — 맞으면 0, 아니면 0 이 아닌 값.
  러너(`run_tc.py`)가 종료 코드로 통과를 가린다. 출력 문자열이 기대 결과면 명령 안에서 확인한다
  (`… | grep -q '<문자열>'`). 끝을 `|| true` 로 가린 명령은 검사가 위반으로 잡는다.
- 필드 값은 한 줄로 쓴다. `command` 는 백틱 한 쌍으로 감싼다. 이 문서는 writer·critic·generator·
  evaluator 가 모두 읽으므로 블록 하나의 군살이 네 번 읽힌다.

## 케이스

### TC-F001-1: {한 줄 제목}
- criterion: 1
- type: unit
- precondition: {시작 상태}
- steps: {절차}
- expected: {기대 결과}
- command: `{실행 명령}`
