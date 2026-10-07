# Generator 상세 가이드

`agents/generator.md` 가 정본이다. 이 문서는 그 절차의 이유와 세부를 설명한다.
generator 는 **기능 하나**를 구현하고, 판정은 하지 않는다. 최우선 목표는 "동작하는 소프트웨어"다.

## 시작 오리엔테이션 (매번 같은 순서)

새 서브에이전트는 이전 대화를 모른다. 같은 순서로 읽어야 어느 세션에서든 같은 위치에서 출발한다.

1. `PROGRESS.md` — 어디까지 갔는가
2. `epic_dir/feature_list.json` — 이 기능의 `acceptance_criteria` 와 `dependencies`
3. `epic_dir/TC.md` 의 해당 FID 블록 — 구현이 통과해야 할 확정 TC (레거시는 criteria 만)
4. `git log -5 --oneline` — 직전 변경

선행 기능(`dependencies`)이 `pass` 가 아니면 시작하지 않고 `error` 로 반환한다.

## Ralph Loop — 목표 재주입

읽은 직후, 대상 기능의 id·이름·`acceptance_criteria` 를 **원문 그대로** 다시 선언한다. 긴 작업에서 목표가
조용히 바뀌는 것(목표 표류)을 막는다. 계약 파일(`sprint_contracts/<FID>.md`)이 그 선언의 영속 형태다:
대화 안의 선언은 컨텍스트와 함께 사라지지만 파일은 evaluator 가 읽는다.

## Reasoning Sandwich

- 계획: 최대 노력 — 어떤 파일을 어떻게 바꿀지, TC 가 요구하는 동작이 무엇인지
- 구현: 중간 노력 — 코드 작성에 집중
- 검증: 최대 노력 — 코드가 써졌다고 추론을 줄이지 않는다. TC 의 `command` 를 직접 돌려 본다

## 구현 규칙

- **스텁 금지** — `TODO`, `FIXME`, `placeholder`, `NotImplementedError`, `pass  # placeholder`,
  빈 함수 본문으로 통과시키지 않는다. 마커가 아니어도 "동작하는 척" 하는 하드코딩도 같다.
  `validate_feature_list.py --stubs` 가 마커를 파일:줄로 짚는다.
- **동작 확인** — 코드를 쓰는 것과 동작하는 것은 다르다. TC `command` 로 실제 실행해 결과를 본다.
  결과는 참고일 뿐 판정이 아니다 (자기 평가 불신).
- **한 기능만** — 다른 기능의 버그를 발견하면 고치지 않고 `PROGRESS.md` 의 이슈로 남긴다.

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
4. 재작업 내역을 `PROGRESS.md` 에 남긴다.

## PROGRESS.md 에 남길 것

작업 요약, 바꾼 파일, 발견한 이슈, 다음 참고사항. 사실만 쓴다 — "잘 됐다" 는 평가이므로 쓰지 않는다.
