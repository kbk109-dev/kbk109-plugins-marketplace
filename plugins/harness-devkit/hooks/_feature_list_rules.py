#!/usr/bin/env python3
"""harness-dev 의 "기계적 제약" 중 기계로 판정 가능한 것들.

SKILL.md 는 제약을 "어떤 상황에서도 재정의할 수 없다" 고 선언하지만, 그중 검사할 수 있는 것은
일부뿐이다 — #2(criteria 불변) #6(JSON 유지) #7(재시도 상한) #8(status enum), 그리고 2.0 에서
더한 #9(v2: pass 는 evaluator 만) #10(status 전이) #11(v2: pass 는 증거 로그 필수).
"한 번에 하나씩" 같은 나머지는 판단이 필요해 코드가 볼 수 없다. 그것은 AGENTS.md 규율
블록으로 넘긴다.

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

# 제약 10 — 허용 전이. pass 는 종착이고, blocked 에서 pass 로 곧장 갈 수 없다.
ALLOWED_TRANSITIONS = {("fail", "pass"), ("fail", "blocked"), ("blocked", "fail")}

# acceptance_criteria 잠금 파일 이름. 훅·검증 스크립트·상태 판정이 같은 파일을 봐야 한다.
CRITERIA_LOCK_NAME = ".criteria_lock.json"

# 제약 9 — v2 에서 pass 를 쓸 수 있는 에이전트.
EVALUATOR_NAME = "evaluator"

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


def _features_by_id(feature_list) -> dict:
    """{id: feature}. 모양이 깨졌으면 빈 dict — 모양 위반은 check() 가 따로 잡는다."""
    if not isinstance(feature_list, dict) or not isinstance(feature_list.get("features"), list):
        return {}
    return {f["id"]: f for f in feature_list["features"]
            if isinstance(f, dict) and isinstance(f.get("id"), str) and f["id"]}


def is_v2(feature_list) -> bool:
    return isinstance(feature_list, dict) and feature_list.get("schema_version") == 2


def is_evaluator(agent_type) -> bool:
    """evaluator 서브에이전트인가. 플러그인 에이전트는 `harness-devkit:evaluator` 로 오므로
    접미사로 맞춘다 (commit_agent_gate 와 같은 방식)."""
    return isinstance(agent_type, str) and (
        agent_type == EVALUATOR_NAME or agent_type.endswith(":" + EVALUATOR_NAME))


def newly_passed(old, new) -> list:
    """이번 변경으로 새로 pass 가 된 기능 id. old 에 없던 기능은 fail 에서 왔다고 본다."""
    before = _features_by_id(old)
    return [fid for fid, f in _features_by_id(new).items()
            if f.get("status") == "pass" and before.get(fid, {}).get("status") != "pass"]


def check_transition(old, new) -> list:
    """제약 10 — status 전이가 상태 머신을 따르는지. old 가 None 이면 판정하지 않는다."""
    if old is None:
        return []
    violations = []
    before = _features_by_id(old)
    for fid, feature in _features_by_id(new).items():
        prev = before.get(fid)
        if prev is None:
            continue
        o, n = prev.get("status"), feature.get("status")
        # 허용값 밖의 값은 제약 8 이 이미 잡는다 — 같은 원인을 두 번 보고하지 않는다.
        if o != n and o in ALLOWED_STATUS and n in ALLOWED_STATUS \
                and (o, n) not in ALLOWED_TRANSITIONS:
            violations.append(violation(10, f"status {o} → {n} 은 허용되지 않는 전이다", fid))
        oa, na = prev.get("attempts", 0), feature.get("attempts", 0)
        if isinstance(oa, int) and isinstance(na, int) and not isinstance(oa, bool) \
                and not isinstance(na, bool) and na < oa:
            violations.append(violation(10, f"attempts {oa} → {na} — 재시도 횟수는 줄일 수 없다", fid))
    return violations


def check_pass_author(old, new, agent_type) -> list:
    """제약 9 — v2 에서 pass 는 evaluator 만 기록한다.

    agent_type 이 None 이면 누가 썼는지 모르는 것이므로 판정하지 않는다 (validate 스크립트).
    빈 문자열은 "서브에이전트가 아닌 메인 세션" 이고 위반이다.
    """
    if agent_type is None or not is_v2(new) or is_evaluator(agent_type):
        return []
    return [violation(9, f"evaluator 가 아닌 주체({agent_type or '메인 세션'})가 pass 로 바꿨다. "
                         "pass 는 evaluator 서브에이전트만 기록한다", fid)
            for fid in newly_passed(old, new)]


def check_evidence(feature_list, base_dir=None, fresh=None) -> list:
    """제약 11 — pass 는 증거 로그 없이 성립하지 않는다.

    대상: v2 파일의 모든 pass 항목, 또는 `fresh` 로 지목된 항목. v1 파일의 기존 pass 는
    증거 필드가 없는 것이 정상이므로 건드리지 않는다. base_dir 이 있으면 파일 실존까지 본다
    (훅은 쓰기 직전이라 base_dir 없이 모양만 본다).
    """
    violations = []
    v2 = is_v2(feature_list)
    fresh = set(fresh or [])
    for fid, feature in _features_by_id(feature_list).items():
        if feature.get("status") != "pass" or not (v2 or fid in fresh):
            continue
        evidence = feature.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            violations.append(violation(11, "pass 인데 evidence 가 비어 있다", fid))
            continue
        prefix = f"logs/{fid}/"
        for rel in evidence:
            if not isinstance(rel, str) or not rel.startswith(prefix) or ".." in rel:
                violations.append(violation(11, f"evidence {rel!r} — `{prefix}` 아래 로그만 인정한다", fid))
            elif base_dir:
                try:
                    if os.path.getsize(os.path.join(base_dir, rel)) == 0:
                        violations.append(violation(11, f"{rel} 이 비어 있다", fid))
                except OSError:
                    violations.append(violation(11, f"{rel} 이 없다", fid))
        if base_dir:
            report = os.path.join(base_dir, "eval", f"{fid}.md")
            try:
                with open(report, "r", encoding="utf-8") as fh:
                    if "VERDICT: PASS" not in fh.read():
                        violations.append(violation(11, f"eval/{fid}.md 에 `VERDICT: PASS` 가 없다", fid))
            except OSError:
                violations.append(violation(11, f"eval/{fid}.md 가 없다", fid))
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
