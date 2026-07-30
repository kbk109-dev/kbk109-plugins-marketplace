#!/usr/bin/env python3
"""Validator for release-impl feature_list.json.

release-impl's feature_list.json is the single source of truth for the Task
State Machine of a given release version. Encoding the rules as a script
prevents silent drift: the model cannot invent new statuses, corrupt the
summary counters, or exceed the retry cap without this validator flagging it.

Checks performed:
    A. Top-level required keys and primitive types.
    B. version matches '^v\\d+\\.\\d+\\.\\d+$'.
    C. summary counters are consistent with observed task statuses.
    D. acceptance_criteria_hashes keys match each task id exactly (no missing,
       no dangling).
    E. previous_context entries use the allowed type enum.
    F. Each task:
        - id matches '^TASK-\\d{3,}$' and is unique.
        - status in {"fail","pass","blocked","in_progress"}.
        - acceptance_criteria is a non-empty list of non-empty strings.
        - retry_count is 0..2.
        - status=="pass" implies completed_at is a non-empty string.
        - status=="blocked" implies retry_count == 2.
        - retry_count > 0 implies evaluator_feedback is a non-empty string.
        - dependencies reference existing task ids (no self-reference).

jsonschema library is NOT required. If it is installed, we additionally run
the full Draft-2020-12 schema defined in schemas/feature_list.schema.json for
defense-in-depth. If absent, the hand-written checks above are sufficient for
pre-commit enforcement.

Exit codes:
    0  valid
    1  validation error(s) — one per line on stderr
    2  usage / IO error

Usage:
    python3 validate_feature_list.py <feature_list.json>
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")
TASK_ID_RE = re.compile(r"^TASK-\d{3,}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_TOP_KEYS = {
    "version",
    "source",
    "notion_page",
    "notion_database",
    "created_at",
    "summary",
    "acceptance_criteria_hashes",
    "previous_context",
    "tasks",
}

REQUIRED_TASK_KEYS = {
    "id",
    "title",
    "description",
    "acceptance_criteria",
    "status",
    "priority",
    "dependencies",
    "retry_count",
    "evaluator_feedback",
    "completed_at",
}

ALLOWED_STATUSES = {"fail", "pass", "blocked", "in_progress"}
ALLOWED_CONTEXT_TYPES = {"blocked_task", "known_issue", "architecture_decision", "dependency"}
ALLOWED_SOURCES = {"release-plan/task_list.json", "notion-direct"}


def _hash(criteria: list) -> str:
    payload = json.dumps(criteria, ensure_ascii=False, sort_keys=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate(path: Path) -> list[str]:
    errors: list[str] = []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"{path}: file not found"]
    except json.JSONDecodeError as exc:
        return [f"{path}: invalid JSON ({exc})"]

    # A/B. top-level
    missing_top = REQUIRED_TOP_KEYS - data.keys()
    for key in sorted(missing_top):
        errors.append(f"top-level: missing key '{key}'")

    version = data.get("version")
    if isinstance(version, str) and not VERSION_RE.match(version):
        errors.append(f"version: {version!r} does not match '^v\\d+\\.\\d+\\.\\d+$'")

    current_task_id = data.get("current_task_id", None)
    if current_task_id is not None:
        if not isinstance(current_task_id, str) or not TASK_ID_RE.match(current_task_id):
            errors.append(
                f"current_task_id: {current_task_id!r} must be null or match '^TASK-\\d{{3,}}$'"
            )

    source = data.get("source")
    if isinstance(source, str) and source not in ALLOWED_SOURCES:
        errors.append(f"source: {source!r} not in {sorted(ALLOWED_SOURCES)}")

    impl_root = data.get("implementation_root", None)
    if impl_root is not None and not isinstance(impl_root, str):
        errors.append(
            f"implementation_root: must be string or null (got {type(impl_root).__name__})"
        )

    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        errors.append("top-level: 'tasks' must be a list")
        return errors
    if not tasks:
        errors.append("top-level: 'tasks' must be non-empty")

    # E. previous_context
    pctx = data.get("previous_context")
    if not isinstance(pctx, list):
        errors.append("previous_context: must be a list (use [] for first release)")
    else:
        for i, entry in enumerate(pctx):
            if not isinstance(entry, dict):
                errors.append(f"previous_context[{i}]: must be an object")
                continue
            for key in ("version", "type", "source", "summary", "relevance"):
                if key not in entry:
                    errors.append(f"previous_context[{i}]: missing '{key}'")
            t = entry.get("type")
            if t is not None and t not in ALLOWED_CONTEXT_TYPES:
                errors.append(
                    f"previous_context[{i}].type: {t!r} not in {sorted(ALLOWED_CONTEXT_TYPES)}"
                )
            v = entry.get("version")
            if isinstance(v, str) and not VERSION_RE.match(v):
                errors.append(
                    f"previous_context[{i}].version: {v!r} does not match '^v\\d+\\.\\d+\\.\\d+$'"
                )

    # F. per-task + id uniqueness
    task_ids: list[str] = []
    counts: dict[str, int] = defaultdict(int)

    for idx, task in enumerate(tasks):
        loc = f"tasks[{idx}]"
        if not isinstance(task, dict):
            errors.append(f"{loc}: must be an object")
            continue

        missing = REQUIRED_TASK_KEYS - task.keys()
        for key in sorted(missing):
            errors.append(f"{loc}: missing key '{key}'")

        task_id = task.get("id")
        if isinstance(task_id, str):
            if not TASK_ID_RE.match(task_id):
                errors.append(f"{loc}.id: {task_id!r} does not match '^TASK-\\d{{3,}}$'")
            task_ids.append(task_id)

        status = task.get("status")
        if status in ALLOWED_STATUSES:
            counts[status] += 1
        else:
            errors.append(f"{loc}.status: {status!r} not in {sorted(ALLOWED_STATUSES)}")

        ac = task.get("acceptance_criteria")
        if not isinstance(ac, list) or not ac:
            errors.append(f"{loc}.acceptance_criteria: must be a non-empty list")
        else:
            for i, item in enumerate(ac):
                if not isinstance(item, str) or not item.strip():
                    errors.append(f"{loc}.acceptance_criteria[{i}]: must be non-empty string")

        retry = task.get("retry_count")
        if not isinstance(retry, int) or retry < 0 or retry > 2:
            errors.append(f"{loc}.retry_count: must be integer in 0..2 (got {retry!r})")

        feedback = task.get("evaluator_feedback")
        if isinstance(retry, int) and retry > 0:
            if not isinstance(feedback, str) or not feedback.strip():
                errors.append(
                    f"{loc}.evaluator_feedback: required non-empty string when retry_count > 0"
                )

        completed = task.get("completed_at")
        if status == "pass":
            if not isinstance(completed, str) or not completed.strip():
                errors.append(f"{loc}.completed_at: required non-empty string when status=='pass'")
        if status == "blocked":
            if retry != 2:
                errors.append(
                    f"{loc}: status='blocked' requires retry_count==2 (got {retry!r})"
                )

        # evaluator_feedback_history checks (optional field, but if present must be list[str])
        hist = task.get("evaluator_feedback_history")
        if hist is not None:
            if not isinstance(hist, list):
                errors.append(f"{loc}.evaluator_feedback_history: must be an array")
            else:
                for hi, item in enumerate(hist):
                    if not isinstance(item, str) or not item.strip():
                        errors.append(
                            f"{loc}.evaluator_feedback_history[{hi}]: must be non-empty string"
                        )

        # evidence_logs checks
        ev = task.get("evidence_logs")
        if ev is not None:
            if not isinstance(ev, dict):
                errors.append(f"{loc}.evidence_logs: must be an object (criterion index → path)")
            else:
                for k, v in ev.items():
                    if not isinstance(k, str) or not k.isdigit():
                        errors.append(f"{loc}.evidence_logs: key {k!r} must be a digit string")
                    if not isinstance(v, str) or not v.strip():
                        errors.append(f"{loc}.evidence_logs[{k}]: path must be non-empty string")
                    if isinstance(ac, list) and isinstance(k, str) and k.isdigit():
                        if int(k) >= len(ac):
                            errors.append(
                                f"{loc}.evidence_logs[{k}]: index out of range "
                                f"(criteria length={len(ac)})"
                            )
        if status == "pass":
            if not isinstance(ev, dict) or not ev:
                errors.append(
                    f"{loc}.evidence_logs: status=='pass' requires at least one evidence entry"
                )

        deps = task.get("dependencies")
        if not isinstance(deps, list):
            errors.append(f"{loc}.dependencies: must be a list")
        else:
            for i, dep in enumerate(deps):
                if not isinstance(dep, str) or not TASK_ID_RE.match(dep):
                    errors.append(
                        f"{loc}.dependencies[{i}]: {dep!r} must match '^TASK-\\d{{3,}}$'"
                    )

    # id uniqueness
    seen = set()
    for tid in task_ids:
        if tid in seen:
            errors.append(f"tasks: duplicate id {tid!r}")
        seen.add(tid)

    # dependencies resolve to existing ids; no self-reference
    for idx, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue
        loc = f"tasks[{idx}]"
        tid = task.get("id")
        deps = task.get("dependencies")
        if isinstance(deps, list):
            for i, dep in enumerate(deps):
                if dep == tid:
                    errors.append(f"{loc}.dependencies[{i}]: self-reference {dep} not allowed")
                if isinstance(dep, str) and TASK_ID_RE.match(dep) and dep not in seen:
                    errors.append(f"{loc}.dependencies[{i}]: {dep} refers to non-existent task")

    # C. summary consistency
    summary = data.get("summary")
    if isinstance(summary, dict):
        if summary.get("total") != len(tasks):
            errors.append(f"summary.total: {summary.get('total')} != {len(tasks)}")
        # summary has only pass/fail/blocked (in_progress is transient, rolled into fail)
        for s in ("pass", "fail", "blocked"):
            observed = counts[s]
            if s == "fail":
                observed += counts["in_progress"]  # in_progress rolls into fail for summary
            if summary.get(s) != observed:
                errors.append(f"summary.{s}: {summary.get(s)} != observed {observed}")

    # D. acceptance_criteria_hashes coverage
    hashes = data.get("acceptance_criteria_hashes")
    if not isinstance(hashes, dict):
        errors.append("acceptance_criteria_hashes: must be an object")
    else:
        for tid in seen:
            if tid not in hashes:
                errors.append(f"acceptance_criteria_hashes: missing hash for {tid}")
        for tid in hashes:
            if tid not in seen:
                errors.append(f"acceptance_criteria_hashes: dangling hash for {tid!r}")
            h = hashes[tid]
            if not isinstance(h, str) or not SHA256_RE.match(h):
                errors.append(f"acceptance_criteria_hashes[{tid}]: invalid sha256 {h!r}")

        # Cross-check hash matches current criteria values
        for task in tasks:
            if not isinstance(task, dict):
                continue
            tid = task.get("id")
            ac = task.get("acceptance_criteria")
            if tid in hashes and isinstance(ac, list):
                expected = hashes[tid]
                actual = _hash(ac)
                if actual != expected:
                    errors.append(
                        f"acceptance_criteria_hashes[{tid}]: hash mismatch "
                        f"(recorded {expected[:12]}..., actual {actual[:12]}...) — "
                        "acceptance_criteria must not change after creation"
                    )

    # Optional: full jsonschema validation if available
    try:
        import jsonschema  # type: ignore

        schema_path = Path(__file__).parent / "schemas" / "feature_list.schema.json"
        if schema_path.exists():
            try:
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                validator = jsonschema.Draft202012Validator(schema)
                for err in sorted(validator.iter_errors(data), key=lambda e: e.path):
                    errors.append(f"schema: {'/'.join(str(p) for p in err.path) or '<root>'}: {err.message}")
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(f"schema: could not run jsonschema validator ({exc})")
    except ImportError:
        pass  # hand-written checks above are sufficient

    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_feature_list.py <feature_list.json>", file=sys.stderr)
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
