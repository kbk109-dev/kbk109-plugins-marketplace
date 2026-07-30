# Notion Release Plan DB — 버전 파싱 규칙

`fix-plan-impl` Phase 1 Step 3/4의 상세 규칙. 본 문서는 SKILL.md에서 레퍼런스로 참조되며, 복잡한 엣지 케이스 설명을 본문에서 분리하기 위한 것이다.

## 1. 정상 파싱 대상

- 형식: `X.Y.Z` (각 세그먼트는 0 이상의 정수).
- 선행 `v` / `V` 접두는 허용하고 strip.
- 공백은 양끝 trim.

## 2. pre-release 태그 (`-rc1`, `-alpha.2` 등)

- **무시**하고 warnings에 기록한다.
- 이유: pre-release는 "아직 배포되지 않은" 후보. base 버전으로 사용하면 shipped 릴리즈를 건너뛴 새 patch가 나올 수 있다.
- 사용자에게 경고 메시지로 고지: "pre-release N개는 집계에서 제외했습니다: {list}".

## 3. build metadata (`+build.5`, `+sha.abcdef`)

- strip 후 X.Y.Z로 비교한다.
- 이유: build metadata는 semver 규격상 비교에 영향을 주지 않는다. 동일 `1.3.9`로 취급.
- warnings에 strip 사실만 기록 (사용자 확인 불필요).

## 4. shipped vs in-progress 구분

Release Plan DB에 `Status`, `Release Date`, `배포`, `상태` 등 **상태 컬럼이 존재**하면 다음 규칙을 적용:

- **released / done / shipped / 배포완료** 상태의 레코드만 "최고 버전" 후보로 채택.
- in-progress / planning / doing 상태 레코드는 건너뛴다.
- 상태 컬럼이 없거나 비어있는 경우: 기존 동작(전체 레코드 대상) 유지.

이유: 진행 중인 `2.1.0` 옆에서 무심코 `1.4.3`을 찍으면 버전 라인이 꼬인다. shipped 기준이어야 "이미 고객이 보고 있는 최신 버전"에 정확히 +1 patch가 된다.

## 5. 유효 버전이 전혀 없는 경우

- `compute_next_patch.py` 종료코드 2.
- 사용자에게 확인 요청:
  > "Release Plan DB에 유효한 X.Y.Z 레코드가 없습니다. fix 릴리즈는 기존 shipped 버전이 있어야 성립합니다. `/release-workflow:release-plan`으로 초기 버전부터 등록하시겠습니까?"
- 사용자 명시적 승인 없이 `1.0.0`으로 진행하지 않는다.

## 6. 중복 버전 race (Phase 3 Step 0)

Phase 2 확인 후 브랜치 생성 직전에 1회 재조회.

- 동일 `new_version` 레코드가 새로 발견된 경우: 중단하고 사용자에게 "동일 버전이 방금 등록된 것으로 보입니다. 다음 patch(`X.Y.Z+2`)로 진행할까요, 기존 것을 이어받을까요?" 확인 요청.
- 동일 레코드가 없으면 그대로 Phase 3 Step 1(브랜치 중복 확인)로 진행.

## 7. 스크립트 호출 예시

```bash
# Notion에서 가져온 버전 문자열 배열을 JSON으로 stdin에 전달
echo '["1.4.2","1.4.1","2.0.0-rc1"]' | \
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/fix-plan-impl/scripts/compute_next_patch.py
```

출력:
```json
{
  "latest_version": "1.4.2",
  "new_version": "1.4.3",
  "warnings": ["pre-release 태그 무시: 2.0.0-rc1"],
  "ignored": ["2.0.0-rc1"]
}
```
