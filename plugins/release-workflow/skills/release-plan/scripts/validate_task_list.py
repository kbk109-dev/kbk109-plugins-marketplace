#!/usr/bin/env python3
"""Validator for release-plan task_list.json.

The release-plan skill must produce a task_list.json that downstream skills
(release-impl, fix-plan-impl) can consume without field-mapping guesswork.
Encoding those rules as a script prevents the LLM from drifting: the model
cannot rename fields, skip acceptance_criteria, or leave dangling [Task N]
references without the script flagging it.

Checks performed:
    A. Top-level schema has the expected keys.
    B. Each task has required fields with correct primitive types.
    C. status ∈ {"fail","pass","blocked"}; all start as "fail" at creation.
    D. acceptance_criteria is a non-empty list of non-empty strings.
    E. task_number values match `1..N` contiguously within each version.
    F. name matches `^\\[Task <task_number>\\] .+` exactly.
    G. depends_on_labels / parallel_with_labels entries:
       - match `^\\[Task \\d+\\]$`
       - refer to tasks that exist in the same task_list.json
       - do not appear in BOTH lists for the same task (mutual exclusion)
       - do not reference the task itself
    H. summary counters are consistent with task statuses.

Exit codes:
    0  valid
    1  validation error(s) — details printed to stderr, one per line
    2  usage / IO error

Usage:
    python3 validate_task_list.py path/to/task_list.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path


TASK_LABEL_RE = re.compile(r"^\[Task (\d+)\]$")
TASK_NAME_RE = re.compile(r"^\[Task (\d+)\] .+")

REQUIRED_TOP_KEYS = {
    "version",
    "created_at",
    "notion_page",
    "notion_database",
    "input_version",
    "summary",
    "tasks",
    "fact_check",
}

ALLOWED_FACT_CHECK_VERDICTS = {"pass", "unverified-user-approved"}

REQUIRED_TASK_KEYS = {
    "id",
    "task_number",
    "name",
    "version",
    "category",
    "status",
    "acceptance_criteria",
    "implementation_details",
    "depends_on_labels",
    "parallel_with_labels",
    "retry_count",
    "completed_at",
}

ALLOWED_STATUSES = {"fail", "pass", "blocked"}


def validate(path: Path) -> list[str]:
    errors: list[str] = []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"{path}: file not found"]
    except json.JSONDecodeError as exc:
        return [f"{path}: invalid JSON ({exc})"]

    # A. top-level schema
    missing_top = REQUIRED_TOP_KEYS - data.keys()
    for key in sorted(missing_top):
        errors.append(f"top-level: missing key '{key}'")

    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        errors.append("top-level: 'tasks' must be a list")
        return errors
    if not tasks:
        errors.append("top-level: 'tasks' must be non-empty")

    # B–D. per-task
    task_labels: set[str] = set()
    label_to_task: dict[str, dict] = {}
    by_version: dict[str, list[dict]] = defaultdict(list)

    for idx, task in enumerate(tasks):
        loc = f"tasks[{idx}]"
        if not isinstance(task, dict):
            errors.append(f"{loc}: must be an object")
            continue

        missing = REQUIRED_TASK_KEYS - task.keys()
        for key in sorted(missing):
            errors.append(f"{loc}: missing key '{key}'")

        status = task.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{loc}.status: {status!r} not in {sorted(ALLOWED_STATUSES)}")

        ac = task.get("acceptance_criteria")
        if not isinstance(ac, list) or not ac:
            errors.append(f"{loc}.acceptance_criteria: must be a non-empty list")
        else:
            for i, item in enumerate(ac):
                if not isinstance(item, str) or not item.strip():
                    errors.append(f"{loc}.acceptance_criteria[{i}]: must be non-empty string")

        task_number = task.get("task_number")
        name = task.get("name")
        version = task.get("version")

        if isinstance(task_number, int) and isinstance(name, str):
            m = TASK_NAME_RE.match(name)
            if not m:
                errors.append(f"{loc}.name: {name!r} does not match '[Task N] <title>'")
            elif int(m.group(1)) != task_number:
                errors.append(
                    f"{loc}.name: label number {m.group(1)} != task_number {task_number}"
                )
            label = f"[Task {task_number}]"
            if label in task_labels:
                errors.append(f"{loc}.task_number: duplicate label {label}")
            task_labels.add(label)
            label_to_task[label] = task

        if isinstance(version, str):
            by_version[version].append(task)

    # E. contiguous task_number within each version
    for ver, vtasks in by_version.items():
        numbers = sorted(t.get("task_number") for t in vtasks if isinstance(t.get("task_number"), int))
        expected = list(range(1, len(numbers) + 1))
        if numbers != expected:
            errors.append(
                f"version {ver}: task_number sequence {numbers} is not contiguous 1..{len(numbers)}"
            )

    # G. depends_on_labels / parallel_with_labels
    for idx, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue
        loc = f"tasks[{idx}]"
        name = task.get("name") if isinstance(task.get("name"), str) else ""
        self_label_match = TASK_NAME_RE.match(name) if name else None
        self_label = f"[Task {self_label_match.group(1)}]" if self_label_match else None

        depends = task.get("depends_on_labels")
        parallel = task.get("parallel_with_labels")

        for field_name, value in (("depends_on_labels", depends), ("parallel_with_labels", parallel)):
            if not isinstance(value, list):
                errors.append(f"{loc}.{field_name}: must be a list")
                continue
            for i, label in enumerate(value):
                if not isinstance(label, str) or not TASK_LABEL_RE.match(label):
                    errors.append(
                        f"{loc}.{field_name}[{i}]: {label!r} must match '[Task N]'"
                    )
                    continue
                if label not in task_labels:
                    errors.append(
                        f"{loc}.{field_name}[{i}]: {label} refers to non-existent task"
                    )
                if self_label and label == self_label:
                    errors.append(
                        f"{loc}.{field_name}[{i}]: self-reference {label} not allowed"
                    )

        if isinstance(depends, list) and isinstance(parallel, list):
            overlap = set(depends) & set(parallel)
            if overlap:
                errors.append(
                    f"{loc}: labels appear in both depends_on and parallel_with: "
                    f"{sorted(overlap)}"
                )

    # G1. implementation_root: optional, must be string or null when present
    if "implementation_root" in data:
        impl_root = data.get("implementation_root")
        if impl_root is not None and not isinstance(impl_root, str):
            errors.append(
                f"implementation_root: must be string or null (got {type(impl_root).__name__})"
            )

    # G2. fact_check shape (deep evidence-file checks live in verify_tech_tokens.py)
    fact_check = data.get("fact_check")
    if fact_check is not None:
        if not isinstance(fact_check, dict):
            errors.append("fact_check: must be an object")
        else:
            verdict = fact_check.get("verdict")
            if verdict not in ALLOWED_FACT_CHECK_VERDICTS:
                errors.append(
                    f"fact_check.verdict: {verdict!r} not in {sorted(ALLOWED_FACT_CHECK_VERDICTS)}"
                )
            for key in ("tokens_path", "checked_at"):
                value = fact_check.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"fact_check.{key}: missing or empty")
            if not isinstance(fact_check.get("unverified_tokens"), list):
                errors.append("fact_check.unverified_tokens: must be a list")
            if not isinstance(fact_check.get("evidence_logs"), dict):
                errors.append("fact_check.evidence_logs: must be an object")

    # H. summary consistency
    summary = data.get("summary")
    if isinstance(summary, dict):
        counts = defaultdict(int)
        for task in tasks:
            status = task.get("status") if isinstance(task, dict) else None
            if status in ALLOWED_STATUSES:
                counts[status] += 1
        if summary.get("total") != len(tasks):
            errors.append(f"summary.total: {summary.get('total')} != {len(tasks)}")
        for status in ALLOWED_STATUSES:
            if summary.get(status) != counts[status]:
                errors.append(
                    f"summary.{status}: {summary.get(status)} != observed {counts[status]}"
                )

    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_task_list.py <task_list.json>", file=sys.stderr)
        return 2
    errors = validate(Path(argv[1]))
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
