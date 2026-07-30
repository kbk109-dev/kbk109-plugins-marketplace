#!/usr/bin/env bash
# verify_plan.sh — Phase 4 증거 기반 검증
#
# Usage: verify_plan.sh <new_version>
# 예: verify_plan.sh 1.4.3
#
# 검증 항목:
#   1) task_list.json 존재 (docs/skills/release-plan/**/v<version>/task_list.json)
#   2) 작업 수 > 0
#   3) 현재 git 브랜치 == fix/v<version>
#
# Notion 재조회는 LLM 쪽 `notion-fetch`가 담당 (Bash에서 MCP 호출 불가).
# 본 스크립트는 파일/브랜치 증거만 판정한다.
#
# 종료코드: 0 = 모두 통과, 1 = 검증 실패, 2 = 인자 오류

set -u

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <new_version>" >&2
  exit 2
fi

NEW_VERSION="${1#v}"
EXPECTED_BRANCH="fix/v${NEW_VERSION}"
FAIL=0

echo "=== fix-plan-impl Phase 4 검증 (v${NEW_VERSION}) ==="

# 1) task_list.json 탐색
TASK_LIST=$(find docs/skills/release-plan -type f -name task_list.json -path "*/v${NEW_VERSION}/*" 2>/dev/null | head -1)
if [[ -z "${TASK_LIST}" ]]; then
  echo "[FAIL] task_list.json 없음: docs/skills/release-plan/**/v${NEW_VERSION}/task_list.json"
  FAIL=1
else
  echo "[OK]   task_list.json 발견: ${TASK_LIST}"

  # 2) 작업 수 > 0
  if command -v python3 >/dev/null 2>&1; then
    COUNT=$(python3 -c "import json,sys; d=json.load(open('${TASK_LIST}')); t=d.get('tasks') if isinstance(d,dict) else d; print(len(t) if isinstance(t,list) else 0)" 2>/dev/null || echo 0)
  else
    COUNT=$(grep -c '"id"' "${TASK_LIST}" 2>/dev/null || echo 0)
  fi
  if [[ "${COUNT}" -gt 0 ]]; then
    echo "[OK]   작업 수: ${COUNT}"
  else
    echo "[FAIL] 작업 수 0 — 계획이 비어있음"
    FAIL=1
  fi
fi

# 3) 브랜치 일치
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
if [[ "${CURRENT_BRANCH}" == "${EXPECTED_BRANCH}" ]]; then
  echo "[OK]   현재 브랜치: ${CURRENT_BRANCH}"
else
  echo "[FAIL] 브랜치 불일치 — 기대: ${EXPECTED_BRANCH}, 실제: ${CURRENT_BRANCH}"
  FAIL=1
fi

echo "=== 결과: $([[ ${FAIL} -eq 0 ]] && echo PASS || echo FAIL) ==="
exit ${FAIL}
