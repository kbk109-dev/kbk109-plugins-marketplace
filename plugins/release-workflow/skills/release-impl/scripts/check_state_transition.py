#!/usr/bin/env python3
"""Reject illegal state transitions between two feature_list.json snapshots.

release-impl forbids certain mutations once a feature_list.json is created:

- acceptance_criteria for any existing task must not change (hash-locked).
- status transition 'pass' → anything else is forbidden.
- Existing task ids must not disappear (tasks can be added, never removed).
- acceptance_criteria_hashes entries must not change for pre-existing tasks.

These rules prevent a mid-session model from silently "fixing" the contract
by editing criteria or flipping a passed task back to fail. When misused the
file history would no longer be a reliable audit trail of the release.

Usage:
    python3 check_state_transition.py <old.json> <new.json>

Exit codes:
    0  ok
    1  illegal transition detected (stderr, one per line)
    2  usage / IO error
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def check(old: dict, new: dict) -> list[str]:
    errors: list[str] = []

    old_tasks = {t["id"]: t for t in old.get("tasks", []) if isinstance(t, dict) and "id" in t}
    new_tasks = {t["id"]: t for t in new.get("tasks", []) if isinstance(t, dict) and "id" in t}

    # Existing tasks must survive
    for tid in old_tasks:
        if tid not in new_tasks:
            errors.append(f"{tid}: removed from tasks (deletion forbidden)")

    # Check each existing task
    for tid, old_t in old_tasks.items():
        new_t = new_tasks.get(tid)
        if new_t is None:
            continue

        # acceptance_criteria immutability
        if old_t.get("acceptance_criteria") != new_t.get("acceptance_criteria"):
            errors.append(
                f"{tid}.acceptance_criteria: modified (must be immutable after creation)"
            )

        old_status = old_t.get("status")
        new_status = new_t.get("status")
        if old_status == "pass" and new_status != "pass":
            errors.append(
                f"{tid}.status: 'pass' → {new_status!r} forbidden "
                "(pass is terminal; register a new task if a regression appears)"
            )

    # Hashes for pre-existing tasks
    old_h = old.get("acceptance_criteria_hashes", {}) or {}
    new_h = new.get("acceptance_criteria_hashes", {}) or {}
    for tid, oh in old_h.items():
        if tid in new_h and new_h[tid] != oh:
            errors.append(
                f"acceptance_criteria_hashes[{tid}]: changed {oh[:12]}... → {new_h[tid][:12]}..."
            )

    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: check_state_transition.py <old.json> <new.json>", file=sys.stderr)
        return 2
    try:
        old = _load(Path(argv[1]))
        new = _load(Path(argv[2]))
    except FileNotFoundError as exc:
        print(f"IO error: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"JSON error: {exc}", file=sys.stderr)
        return 2

    errors = check(old, new)
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
