# Eval: {FID} {기능명} — 시도 {n}

VERDICT: {PASS|FAIL}

evaluator 가 쓴다. `VERDICT: PASS` 줄은 모든 TC 가 PASS 이고 기계 검사가 통과했을 때만 쓴다
(`validate_feature_list.py` 가 이 줄을 찾는다).

## 기계 검사
`validate_feature_list.py --stubs <구현 경로>` 출력 JSON 을 그대로 붙인다.

## TC 결과
| TC | 결과 | 증거 로그 |
|---|---|---|
| TC-F001-1 | PASS | logs/F001/1.log |

로그는 명령 · 종료 코드 · 출력 전문(길면 끝 100줄)을 담는다. 로그가 없는 PASS 는 인정하지 않는다.

## 회귀
기존에 pass 였던 기능의 TC 중 영향 범위를 골라 다시 실행한 결과.

## 실패 시 피드백
문제 위치(파일:줄), 원인, 수정 방향. generator 가 그대로 따라 할 수 있게 구체적으로.
