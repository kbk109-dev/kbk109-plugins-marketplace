# Generator 상세 가이드

`agents/generator.md` 가 정본이다. 이 문서는 그 절차의 이유와 세부를 설명한다.
generator 는 **기능 하나**를 구현하고, 판정은 하지 않는다. 최우선 목표는 "동작하는 소프트웨어"다.

## 시작 오리엔테이션 (매번 같은 순서)

새 서브에이전트는 이전 대화를 모른다. 같은 순서로 읽어야 어느 세션에서든 같은 위치에서 출발한다.

1. `PROGRESS.md` 의 끝 40줄 — 어디까지 갔는가
2. `epic_dir/feature_list.json` — 이 기능의 `acceptance_criteria` 와 `dependencies`
3. `epic_dir/TC.md` 의 해당 FID 블록 — 구현이 통과해야 할 확정 TC (레거시는 criteria 만)
4. `dependencies` 에 적힌 기능의 `epic_dir/notes/<FID>.md` — 앞 기능이 남긴 인수인계
5. `git log -5 --oneline` — 직전 변경

선행 기능(`dependencies`)이 `pass` 가 아니면 시작하지 않고 `error` 로 반환한다.

`PROGRESS.md` 와 `TC.md` 는 통째로 읽지 않는다. 둘 다 기능 수에 비례해 커진다 — 실측에서 각각
수백 KB 였고, 전부 읽으면 구현을 시작하기도 전에 컨텍스트가 찬다. `PROGRESS.md` 는 메인이 단계마다
한 줄씩 남기는 색인이라 끝부분이면 충분하고, 이 기능에 필요한 상세는 의존 기능의 notes 에 있다.
TC 는 Grep `^### TC-<FID>-` 로 줄 번호를 찾아 그 범위와 문서 머리말만 읽는다.

## Ralph Loop — 목표 재주입

읽은 직후, 대상 기능의 id·이름·`acceptance_criteria` 를 **원문 그대로** 다시 선언한다. 긴 작업에서 목표가
조용히 바뀌는 것(목표 표류)을 막는다. 계약 파일(`sprint_contracts/<FID>.md`)이 그 선언의 영속 형태다:
대화 안의 선언은 컨텍스트와 함께 사라지지만 파일은 evaluator 가 읽는다.

## Reasoning Sandwich

- 계획: 최대 노력 — 어떤 파일을 어떻게 바꿀지, TC 가 요구하는 동작이 무엇인지
- 구현: 중간 노력 — 코드 작성에 집중
- 검증: 최대 노력 — 코드가 써졌다고 추론을 줄이지 않는다. 러너로 이 기능의 TC 를 돌려 본다

## 구현 규칙

- **스텁 금지** — `TODO`, `FIXME`, `placeholder`, `NotImplementedError`, `pass  # placeholder`,
  빈 함수 본문으로 통과시키지 않는다. 마커가 아니어도 "동작하는 척" 하는 하드코딩도 같다.
  `validate_feature_list.py --stubs` 가 마커를 파일:줄로 짚는다.
- **동작 확인** — 코드를 쓰는 것과 동작하는 것은 다르다. `run_tc.py <epic_dir> --feature <FID>
  --out _self/<FID>` 로 실제 실행해 결과를 본다. 결과는 참고일 뿐 판정이 아니다 (자기 평가 불신).
  `--out _self/…` 를 빼면 증거 자리(`logs/<FID>/`)에 쓰게 되므로 반드시 붙인다.
- **테스트는 단언한다** — TC 가 부르는 테스트는 `expected` 를 단언해야 한다. 러너는 종료 코드만
  보지만 evaluator 가 테스트 코드를 열어 단언을 확인한다. 0 을 내기만 하는 테스트는 거기서 FAIL 이다.
- **한 기능만** — 다른 기능의 버그를 발견하면 고치지 않고 notes 에 `- ISSUE: ` 줄로 남긴다.

## 읽기 전용 파일

`feature_list.json`·`TC.md`·`.tc_lock.json`·`.criteria_lock.json` 은 고치지 않는다.
`status` 를 `pass` 로 바꾸지 않는다 — v2 에서 pass 는 evaluator 만 기록하고, 훅이 한 번 막고 검증
스크립트가 잡는다. 커밋·push 도 하지 않는다 (커밋은 에픽 종료 때 사용자 승인 뒤).

## Loop Detection

같은 파일을 5회 이상 고치면 루프다. 현재 접근을 버리고 다른 방법을 쓴다. 접근을 2번 전환한 뒤에도
안 되면 `error` 로 반환해 상황을 보고한다 — 계속 같은 곳을 파는 것이 이 하네스가 막으려는 실패다.

## 재작업 (evaluator 가 FAIL 한 뒤)

1. `eval/<FID>.md` 의 피드백을 **전부** 읽는다. 일부만 고치면 같은 이유로 또 FAIL 한다.
2. 계약 파일의 `직전 평가 피드백 반영` 에 지적과 대응을 적는다.
3. 지적된 파일:줄부터 고친다. 접근 자체가 틀렸다는 지적이면 Loop Detection 의 전환을 쓴다.
4. 재작업 내역을 `notes/<FID>.md` 에 덧붙인다.

## notes/<FID>.md 에 남길 것

작업 요약, 바꾼 파일, 이 기능에 의존하는 다음 기능이 알아야 할 것. 다른 기능의 문제는
`- ISSUE: <기능 id> <내용>` 줄로 적는다 — 에픽 종료 때 이 줄을 모아 "남은 이슈" 로 보고한다.
사실만 쓴다. "잘 됐다" 는 평가이므로 쓰지 않는다.

계약 파일(`sprint_contracts/<FID>.md`)과 나눈 이유: 계약은 구현 **전**의 선언이고 evaluator 가
읽는다. 구현 **후**의 소감이 거기 섞이면 evaluator 가 구현자의 자기 평가를 읽게 된다.
`PROGRESS.md` 에 쓰지 않는 이유: 그 파일은 모든 에이전트가 시작할 때 읽는 색인이라, 기능마다
문단을 쌓으면 제품이 커질수록 모든 시작이 느려진다.
