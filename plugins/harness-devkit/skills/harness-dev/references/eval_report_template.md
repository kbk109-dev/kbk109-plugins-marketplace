# Eval: {FID} {기능명} — 시도 {n}

VERDICT: {PASS|FAIL}

evaluator 가 쓴다. `VERDICT: PASS` 줄은 러너가 모든 TC 를 통과로 기록했고 감사와 기계 검사가
통과했을 때만 쓴다 (`validate_feature_list.py` 가 이 줄과 `logs/<FID>/summary.json` 을 본다).

## 기계 검사
`validate_feature_list.py --stubs <구현 경로>` 출력 JSON 을 그대로 붙인다.

## TC 결과
러너(`run_tc.py --feature <FID>`)의 출력 JSON 한 줄을 그대로 붙이고, 감사 결과를 표로 적는다.

| TC | 러너 | 단언 위치 | 증거 로그 |
|---|---|---|---|
| TC-F001-1 | exit 0 | tests/x.test.ts:42 | logs/F001/1.log |

`단언 위치` 는 그 TC 의 `expected` 를 실제로 단언하는 코드다. 찾지 못했으면 그 TC 는 FAIL 이다.
로그는 러너가 쓴 그대로다 (명령 · 종료 코드 · 출력 끝 100줄).

## 회귀
`run_tc.py --regression <FID>` 의 출력 JSON 한 줄 (직접 의존 기능의 TC + PLAN `test`).
범위를 넓혀 더 돌렸으면 그 실행도 적는다.

## 실패 시 피드백
문제 위치(파일:줄), 원인, 수정 방향. generator 가 그대로 따라 할 수 있게 구체적으로.
