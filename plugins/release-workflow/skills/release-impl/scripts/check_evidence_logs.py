#!/usr/bin/env python3
"""Evidence-file verifier for release-impl Evaluator pass gate.

The Evaluator promises in agents/evaluator.md that every pass verdict carries
concrete execution evidence at {version_dir}/logs/{task_id}/{i}.log. This
script is the last gate before the Evaluator sets status="pass": it reads the
task's evidence_logs mapping and verifies that every referenced file actually
exists, is non-empty, and stays inside the version's logs directory.

Without this gate the evidence_logs object can be populated with phantom
paths the model invented — defeating the purpose of "execution evidence"
over "self-description".

Usage:
    python3 check_evidence_logs.py <version_dir> <task_id>

Exit codes:
    0  every referenced log file exists, is non-empty, and is in bounds
    1  at least one log missing / empty / out-of-bounds / task not pass-ready
    2  usage / IO error

Invariants checked:
    - task exists in feature_list.json
    - evidence_logs is an object with digit-string keys
    - each key index < len(acceptance_criteria)
    - every logged path resolves inside {version_dir}/logs/{task_id}/
    - every logged file exists and is non-empty
    - Number of logged criteria ≥ len(acceptance_criteria) (full coverage)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def check(version_dir: Path, task_id: str) -> list[str]:
    fl = version_dir / "feature_list.json"
    if not fl.exists():
        return [f"{fl}: not found"]

    try:
        data = json.loads(fl.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{fl}: invalid JSON ({exc})"]

    tasks = data.get("tasks", [])
    task = next((t for t in tasks if isinstance(t, dict) and t.get("id") == task_id), None)
    if task is None:
        return [f"{task_id}: not present in feature_list.json"]

    ac = task.get("acceptance_criteria", [])
    if not isinstance(ac, list) or not ac:
        return [f"{task_id}.acceptance_criteria: must be a non-empty list"]

    ev = task.get("evidence_logs")
    if not isinstance(ev, dict):
        return [f"{task_id}.evidence_logs: must be a dict (got {type(ev).__name__})"]

    errors: list[str] = []
    logs_root = (version_dir / "logs" / task_id).resolve()

    # Coverage: every criterion index 0..len(ac)-1 must have a log
    missing = [str(i) for i in range(len(ac)) if str(i) not in ev]
    for i in missing:
        errors.append(f"{task_id}.evidence_logs: missing criterion {i} "
                      f"(of {len(ac)} criteria)")

    for key, rel in ev.items():
        if not isinstance(key, str) or not key.isdigit():
            errors.append(f"{task_id}.evidence_logs: non-digit key {key!r}")
            continue
        if int(key) >= len(ac):
            errors.append(f"{task_id}.evidence_logs[{key}]: index out of range "
                          f"(len(ac)={len(ac)})")
            continue
        if not isinstance(rel, str) or not rel.strip():
            errors.append(f"{task_id}.evidence_logs[{key}]: empty path")
            continue

        # Resolve the path relative to version_dir
        target = (version_dir / rel).resolve()
        try:
            target.relative_to(logs_root)
        except ValueError:
            errors.append(
                f"{task_id}.evidence_logs[{key}]: path escapes {logs_root} ({rel!r})"
            )
            continue
        if not target.exists():
            errors.append(f"{task_id}.evidence_logs[{key}]: file not found ({rel})")
            continue
        if target.stat().st_size == 0:
            errors.append(f"{task_id}.evidence_logs[{key}]: empty file ({rel})")

    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: check_evidence_logs.py <version_dir> <task_id>", file=sys.stderr)
        return 2
    errors = check(Path(argv[1]), argv[2])
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
