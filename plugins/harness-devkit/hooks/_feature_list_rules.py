#!/usr/bin/env python3
"""harness-dev 의 "8가지 기계적 제약" 중 기계로 판정 가능한 것들.

SKILL.md 는 8개를 "어떤 상황에서도 재정의할 수 없다" 고 선언하지만, 그중 검사할 수 있는 것은
넷뿐이다 — #2(criteria 불변) #6(JSON 유지) #7(재시도 상한) #8(status enum). 나머지 넷은
"한 번에 하나씩" 처럼 판단이 필요해 코드가 볼 수 없다. 이 모듈은 넷만 다루고, 나머지는
AGENTS.md 규율 블록으로 넘긴다.

이 파일이 `hooks/` 에 있고 스킬 스크립트가 이쪽을 import 하는 이유: 규칙을 양쪽에 복제하면
훅의 판정과 사람이 돌리는 검사가 갈라진다 — 통과했다고 믿었는데 막히거나, 막혔어야 할 것이
통과한다. 이 플러그인이 막으려는 실패와 같은 종류다. 훅 쪽 런타임 계약이 더 엄격하므로
(예외 삼킴·무출력) 원본을 그쪽에 둔다.

순수 함수만 둔다 — stdout 에 쓰지 않고, 종료하지 않고, 예외 정책도 호출자 몫이다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

# status 전이는 fail → pass 또는 fail → blocked 뿐이다. "pending" 이 없는 것이 요점이라
# 별도 메시지로 짚어 준다 — 모델이 가장 흔히 만들어 내는 값이다.
ALLOWED_STATUS = ("fail", "pass", "blocked")

# 제약 7 — "동일 스프린트 최대 2회 재시도 후 사용자에게 에스컬레이션".
MAX_ATTEMPTS = 2

# 제약 4. `mock` 은 일부러 뺐다 — 테스트의 mock 은 정상이고, 그걸 잡으면 경고가 소음이 되어
# 나머지 판정까지 무시된다. 남긴 것들은 구현이 비어 있다는 뜻 외에는 쓰이지 않는 표지다.
STUB_MARKERS = re.compile(
    r"TODO|FIXME|PLACEHOLDER|placeholder|NotImplementedError|[Nn]ot implemented"
)

# 스캔에서 제외한다. 남의 코드와 빌드 산출물에서 나온 TODO 는 이 harness 의 위반이 아니다.
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".next", "__pycache__", "vendor",
             ".venv", "venv", "coverage", ".expo"}
MAX_SCAN_BYTES = 512 * 1024


def violation(rule: int, detail: str, feature_id: str | None = None) -> dict:
    v = {"rule": rule, "detail": detail}
    if feature_id:
        v["feature_id"] = feature_id
    return v


def criteria_digest(criteria) -> str:
    """acceptance_criteria 의 내용 지문.

    공백을 접고 정렬한 뒤 해시한다 — 순서만 바꾼 것은 위반이 아니고(내용이 그대로다),
    문구를 고치거나 항목을 지우면 반드시 달라진다.
    """
    items = sorted(" ".join(str(c).split()) for c in criteria)
    payload = json.dumps(items, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def check(feature_list, lock=None) -> list:
    """feature_list.json 의 내용에 대해 제약 2·6·7·8 을 판정한다.

    lock 이 None 이면 제약 2 는 건너뛴다 — 잠금이 아직 없는 것(Phase 1 승인 전)은 위반이 아니다.
    """
    violations = []

    if not isinstance(feature_list, dict):
        return [violation(6, "최상위가 JSON 객체가 아니다")]
    features = feature_list.get("features")
    if not isinstance(features, list):
        return [violation(6, "`features` 가 배열이 아니다")]

    seen_ids = set()
    for idx, feature in enumerate(features):
        if not isinstance(feature, dict):
            violations.append(violation(6, f"features[{idx}] 가 객체가 아니다"))
            continue

        raw_id = feature.get("id")
        fid = raw_id if isinstance(raw_id, str) and raw_id else f"features[{idx}]"
        seen_ids.add(fid)

        status = feature.get("status")
        if status == "pending":
            violations.append(violation(
                8, "status 'pending' — 이 상태 머신에 존재하지 않는 값이다. "
                   "통과를 증명하기 전까지는 'fail' 이다", fid))
        elif status not in ALLOWED_STATUS:
            violations.append(violation(
                8, f"status {status!r} — 허용값은 {'/'.join(ALLOWED_STATUS)}", fid))

        # 필드가 없으면 0. 이 필드는 뒤늦게 생겼으므로 없는 것이 정상인 실행이 있다.
        attempts = feature.get("attempts", 0)
        if isinstance(attempts, bool) or not isinstance(attempts, int):
            violations.append(violation(7, f"attempts 가 정수가 아니다: {attempts!r}", fid))
        elif attempts > MAX_ATTEMPTS:
            violations.append(violation(
                7, f"attempts {attempts} — 상한 {MAX_ATTEMPTS} 회를 넘겼다. "
                   "재시도 대신 사용자에게 에스컬레이션해야 한다", fid))

        criteria = feature.get("acceptance_criteria")
        if not isinstance(criteria, list):
            violations.append(violation(6, "acceptance_criteria 가 배열이 아니다", fid))
            continue

        if lock and fid in lock:
            if criteria_digest(criteria) != lock[fid].get("digest"):
                was = lock[fid].get("count")
                now = len(criteria)
                detail = (f"acceptance_criteria {was} → {now}건"
                          if isinstance(was, int) and was != now
                          else f"acceptance_criteria 내용이 잠금과 다르다 ({now}건)")
                violations.append(violation(2, detail, fid))

    if lock:
        for fid in lock:
            if fid not in seen_ids:
                violations.append(violation(2, "잠긴 기능이 목록에서 사라졌다", fid))

    return violations


def scan_stubs(paths) -> list:
    """제약 4 — 주어진 경로에서 미구현 표지를 찾는다."""
    violations = []
    for root_path in paths:
        if os.path.isfile(root_path):
            violations.extend(_scan_file(root_path))
            continue
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                violations.extend(_scan_file(os.path.join(dirpath, name)))
    return violations


def _scan_file(path: str) -> list:
    try:
        if os.path.getsize(path) > MAX_SCAN_BYTES:
            return []
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except (OSError, UnicodeDecodeError):
        return []  # 바이너리·권한 없음 — 검사 대상이 아니다
    found = []
    for lineno, line in enumerate(lines, 1):
        match = STUB_MARKERS.search(line)
        if match:
            found.append(violation(4, f"{path}:{lineno} — {match.group(0)}"))
    return found
