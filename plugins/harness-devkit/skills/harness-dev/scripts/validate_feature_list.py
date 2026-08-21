#!/usr/bin/env python3
"""feature_list.json 이 harness-dev 의 기계적 제약을 지키는지 검사한다.

사용:
    validate_feature_list.py <feature_list.json> [--stubs PATH ...] [--update-lock]

출력: stdout JSON { ok, violations[], checked{} }
종료코드: 0 = 통과, 1 = 위반 있음, 3 = 입력 오류(파일 없음·JSON 깨짐·인자 오류)

`--update-lock` 은 acceptance_criteria 잠금을 새로 쓰는 **유일한** 경로다. Phase 1 에서
사용자가 계획을 승인한 직후에만 쓴다 — 승인 전에 잠그면 사용자의 계획 수정이 그대로 위반으로
잡히고, 스프린트 도중에 쓰면 제약 2 가 무의미해진다.

훅(harness_feature_list_gate.py)과 판정 로직을 공유한다. 훅은 쓰기 순간을 잡고 이 스크립트는
스프린트 끝에 사람이 보는 보고를 만든다 — 같은 규칙이어야 둘의 결과가 어긋나지 않는다.
"""
from __future__ import annotations

import json
import os
import sys

# 규칙 원본은 hooks/ 에 있다. 훅의 런타임 계약이 더 엄격해 원본을 그쪽에 두었고, 사본을 만들면
# 훅의 판정과 이 검사가 갈라진다 — 그게 이 플러그인이 막으려는 실패다. 플러그인 안에서의
# 고정 상대 경로이므로 이 한 단계는 안전하다.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "..", "hooks"))
from _feature_list_rules import check, criteria_digest, scan_stubs  # noqa: E402

LOCK_NAME = ".criteria_lock.json"


def fail(message: str, code: int) -> None:
    json.dump({"ok": False, "error": message}, sys.stdout, ensure_ascii=False)
    sys.exit(code)


def parse_args(argv):
    if not argv:
        fail("사용: validate_feature_list.py <feature_list.json> [--stubs PATH ...] "
             "[--update-lock]", 3)
    path = argv[0]
    stubs = []
    update_lock = False
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == "--update-lock":
            update_lock = True
            i += 1
        elif arg == "--stubs":
            i += 1
            while i < len(argv) and not argv[i].startswith("--"):
                stubs.append(argv[i])
                i += 1
            if not stubs:
                fail("--stubs 뒤에 검사할 경로가 필요합니다.", 3)
        else:
            fail(f"알 수 없는 인자: {arg}", 3)
    return path, stubs, update_lock


def build_lock(feature_list) -> dict:
    lock = {}
    for feature in feature_list.get("features", []):
        if not isinstance(feature, dict):
            continue
        fid = feature.get("id")
        criteria = feature.get("acceptance_criteria")
        if isinstance(fid, str) and fid and isinstance(criteria, list):
            lock[fid] = {"digest": criteria_digest(criteria), "count": len(criteria)}
    return lock


def main() -> int:
    path, stub_paths, update_lock = parse_args(sys.argv[1:])

    try:
        with open(path, "r", encoding="utf-8") as fh:
            feature_list = json.load(fh)
    except OSError as exc:
        fail(f"파일을 읽을 수 없습니다: {exc}", 3)
    except ValueError as exc:
        # 제약 6 위반이지만 파일을 파싱조차 못 했으므로 입력 오류로 돌려준다 — 나머지 검사를
        # 할 수 없으니 "위반 1건" 이라고 보고하면 통과 항목까지 검사한 것처럼 읽힌다.
        fail(f"JSON 파싱 실패 (제약 6 위반): {exc}", 3)

    lock_path = os.path.join(os.path.dirname(os.path.abspath(path)), LOCK_NAME)

    if update_lock:
        lock = build_lock(feature_list)
        try:
            with open(lock_path, "w", encoding="utf-8") as fh:
                json.dump(lock, fh, ensure_ascii=False, indent=2)
        except OSError as exc:
            fail(f"잠금 파일을 쓸 수 없습니다: {exc}", 3)
    else:
        try:
            with open(lock_path, "r", encoding="utf-8") as fh:
                lock = json.load(fh)
            if not isinstance(lock, dict):
                lock = None
        except (OSError, ValueError):
            lock = None  # 잠금이 아직 없는 것은 위반이 아니다 — 제약 2 만 건너뛴다

    violations = check(feature_list, lock)
    if stub_paths:
        violations.extend(scan_stubs(stub_paths))

    features = feature_list.get("features")
    json.dump(
        {
            "ok": not violations,
            "violations": violations,
            "checked": {
                "features": len(features) if isinstance(features, list) else 0,
                "lock": lock_path if lock else None,
                "lock_written": update_lock,
                "stub_paths": stub_paths,
            },
        },
        sys.stdout,
        ensure_ascii=False,
    )
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
