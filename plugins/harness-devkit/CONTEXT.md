# harness-devkit

제품 아이디어를 PRD 에서 QA 까지 단계별 서브에이전트로 끌고 가는 하네스의 용어집이다. 구현 세부는
쓰지 않는다 — 용어의 뜻만 정한다.

## Language

**Product**:
하나의 PRD 가 정의하는 제품 또는 마일스톤. `docs/harness/<slug>/` 하나가 하나의 Product 다.
_Avoid_: 프로젝트, 앱

**PRD**:
Product 의 문제·사용자·범위·요구사항·성공 지표를 적은 문서. 사용자가 승인하기 전에는 초안이다.
_Avoid_: 기획서, 스펙

**PLAN**:
승인된 PRD 를 아키텍처·에픽·실행 방법으로 쪼갠 문서. 앱 기동·테스트·E2E 명령(Run & Verify)을 반드시 포함한다.
_Avoid_: 설계서, 로드맵

**Epic**:
독립적으로 검증하고 종료할 수 있는 작업 묶음. 자기 feature_list 와 TC 를 가진다.
_Avoid_: 스프린트, 마일스톤

**Feature**:
Epic 안에서 한 번에 하나씩 구현·판정하는 단위. `acceptance_criteria` 와 `status` 를 가진다.
_Avoid_: 태스크, 스토리

**Acceptance criterion**:
Feature 가 참이어야 하는 조건 한 문장. 관찰·기계 판정이 가능해야 하고 승인 뒤에는 바꿀 수 없다.
_Avoid_: 완료 조건, AC

**TC**:
Epic 의 테스트 케이스 문서(`TC.md`). 모든 acceptance criterion 을 덮고, 구현을 보기 전에 쓰고, critic 이 확정하면 잠긴다.
_Avoid_: 테스트 계획, QA 시트

**Sprint contract**:
Generator 가 구현 전에 파일로 남기는 "이 Feature 에서 무엇을 하겠다" 는 선언. Evaluator 가 읽는다.
_Avoid_: 작업 계획

**Writer**:
문서(PRD·PLAN·TC)를 쓰는 서브에이전트.
_Avoid_: 작성 에이전트

**Critic**:
Writer 의 문서를 회의적으로 검토해 `VERDICT` 와 blocking 항목을 내는 서브에이전트. 문서는 고치지 않는다.
_Avoid_: 리뷰어

**Generator**:
Feature 하나를 구현하는 서브에이전트. 판정하지 않고 `pass` 를 기록하지 않는다.
_Avoid_: 구현 에이전트

**Evaluator**:
확정 TC 를 실앱에서 실행해 판정하고 `pass` 를 기록하는 유일한 서브에이전트.
_Avoid_: 심사자, QA 에이전트

**Evidence log**:
Evaluator 가 TC 한 개를 실행한 명령·종료 코드·출력을 그대로 남긴 로그. 이것이 없으면 `pass` 는 성립하지 않는다.
_Avoid_: 테스트 결과 요약

**Stage**:
파일 상태에서 판정되는 "지금 어느 단계인가". 진입 스킬은 Stage 가 시키는 일만 한다.
_Avoid_: 페이즈, 단계 번호

**Lock**:
승인·확정된 내용이 바뀌지 않게 남기는 지문(`.criteria_lock.json`, `.tc_lock.json`). 바꾸려면 다시 검토를 거친다.
_Avoid_: 동결
