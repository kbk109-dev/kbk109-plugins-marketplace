# 에픽 종료 절차

stage 가 `epic-close` 일 때만 읽는다. 순서를 지킨다 — `/simplify` 는 코드를 고치므로
승인 앞에서 끝나야 하고, 고친 코드는 회귀 평가를 다시 거쳐야 한다.

1. **정적 검사**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/harness-dev/scripts/validate_feature_list.py \
     <epic_dir>/feature_list.json --stubs <구현 경로>
   ```
   종료 코드 0 이 아니면 종료하지 않는다.
2. **`/simplify`** — 여기서 한 번 호출한다. 대상 프로젝트에 `.claude/rules/commit-agent.md` 가 있으면
   그 규칙의 "승인 전 `/simplify`" 가 바로 이 호출이다 — 4번에서 다시 부르지 않는다. 회귀 평가 뒤에
   부르면 검증되지 않은 수정이 커밋된다.
3. **회귀 평가** — `evaluator` 를 "에픽 회귀 모드" 로 호출한다 (`epic_dir`, `mode: epic`).
   러너로 확정 TC 전체를 다시 실행하고(`logs/_epic/`) `eval/EPIC.md` 에 `VERDICT: PASS|FAIL` 을 쓴다.
   기능 평가 때는 직접 의존 기능만 회귀했으므로, 기능 사이의 파손은 여기서 처음 드러날 수 있다.
   FAIL 이면 실패한 TC 의 기능을 `blocked → fail` 이 아니라 사용자에게 보고하고 판단을 받는다.
4. **요약 제시 후 사용자 승인** — 변경 파일, pass/blocked 기능, 남은 이슈(`notes/*.md` 의
   `- ISSUE:` 줄을 Grep 으로 모은다), `eval/EPIC.md` 결과.
5. **커밋** — 승인 뒤에만. `.claude/rules/commit-agent.md` 가 있으면 `project-conventions:commit-agent`
   에 위임하고, 없으면 메인이 커밋한다. **push 하지 않는다.**
6. `<epic_dir>/CLOSED.md` 작성 (종료 일시, 커밋 해시, 남은 이슈) 후 `harness_state.py log` 로
   `PROGRESS.md` 에 한 줄을 남긴다.
7. 사용자에게 안내: 다음 에픽은 **새 세션**에서 `harness-dev` 를 다시 부르면 이어진다.

`blocked` 기능이 남은 채 종료하려면 사용자가 인정해야 한다: 인정 사실과 사유를
`<epic_dir>/blocked_ack.md` 에 적는다 (이 파일이 있어야 stage 가 `epic-close` 로 넘어간다).
