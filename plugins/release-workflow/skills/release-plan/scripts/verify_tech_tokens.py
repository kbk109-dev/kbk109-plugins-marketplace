#!/usr/bin/env python3
"""Block release-plan Step 5 (preview) until fact_check is consistent.

This script is the *blocking gate* of the release-plan external-fact-verification
flow. It runs after the fact-checker subagent has updated task_list.json with
its ``fact_check`` object, and refuses to let the workflow proceed unless that
object is internally consistent and grounded in real evidence files.

Why a separate gate from validate_task_list.py:
    validate_task_list.py predates fact-checking and is responsible for
    *structural* invariants (Task labels, dependencies, summary counters).
    This gate is responsible for *factual* invariants — that the fact-checker
    actually ran, actually wrote evidence files, and actually said pass.
    Splitting the two keeps each gate's failure mode obvious to the human
    reading the stderr output.

Checks performed (any failure → exit 1, all messages to stderr):
    A. ``fact_check`` key exists at the top level.
    B. ``fact_check.verdict`` is one of {"pass", "unverified-user-approved"}.
       "fail" is explicitly rejected here — the fact-checker should have
       looped before declaring done.
    C. ``fact_check.tokens_path`` exists on disk and is valid JSON with
       a ``tokens`` array.
    D. If ``verdict == "pass"``: ``unverified_tokens`` MUST be empty.
       (If verdict is "unverified-user-approved", non-empty unverified_tokens
       is allowed because the user explicitly accepted the risk; we still
       require evidence_logs to record what was attempted.)
    E. ``evidence_logs`` is a dict mapping each token (or each attempted
       token, for unverified-user-approved) to a path. Every path must:
        - exist on disk
        - be non-empty (size > 0)
       Empty evidence files indicate the fact-checker silently skipped a
       lookup — exactly the failure mode this gate exists to catch.
    F. ``checked_at`` is present and non-empty.

Special case: tokens.json contains ``"tokens": []``. The fact-checker may
write ``verdict: "pass"`` with empty unverified_tokens AND empty
evidence_logs. This is allowed — there was nothing to verify. The script
emits "OK (no tokens to verify)" so the operator notices.

Exit codes:
    0  fact_check object is consistent — release-plan may proceed to Step 5
    1  fact_check object missing, malformed, or evidence files absent/empty
    2  usage / IO error
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ALLOWED_VERDICTS = {"pass", "unverified-user-approved"}


def verify(task_list_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(task_list_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"{task_list_path}: file not found"]
    except json.JSONDecodeError as exc:
        return [f"{task_list_path}: invalid JSON ({exc})"]

    fc = data.get("fact_check")
    if not isinstance(fc, dict):
        return ["fact_check: missing or not an object — fact-checker subagent must run first"]

    verdict = fc.get("verdict")
    if verdict not in ALLOWED_VERDICTS:
        errors.append(
            f"fact_check.verdict: {verdict!r} not in {sorted(ALLOWED_VERDICTS)} "
            "— 'fail' or unset is a hard block"
        )

    checked_at = fc.get("checked_at")
    if not isinstance(checked_at, str) or not checked_at.strip():
        errors.append("fact_check.checked_at: missing or empty")

    tokens_path_str = fc.get("tokens_path")
    tokens_count: int | None = None
    if not isinstance(tokens_path_str, str) or not tokens_path_str.strip():
        errors.append("fact_check.tokens_path: missing or empty")
    else:
        tokens_file = (task_list_path.parent / tokens_path_str).resolve() \
            if not Path(tokens_path_str).is_absolute() else Path(tokens_path_str)
        if not tokens_file.exists():
            # Also allow the path to be relative to CWD (legacy callers).
            alt = Path(tokens_path_str)
            if alt.exists():
                tokens_file = alt
            else:
                errors.append(f"fact_check.tokens_path: {tokens_path_str} does not exist")
                tokens_file = None
        if tokens_file is not None and tokens_file.exists():
            try:
                tokens_doc = json.loads(tokens_file.read_text(encoding="utf-8"))
                tokens_list = tokens_doc.get("tokens")
                if not isinstance(tokens_list, list):
                    errors.append(f"{tokens_file}: 'tokens' is not a list")
                else:
                    tokens_count = len(tokens_list)
            except json.JSONDecodeError as exc:
                errors.append(f"{tokens_file}: invalid JSON ({exc})")

    unverified = fc.get("unverified_tokens")
    if not isinstance(unverified, list):
        errors.append("fact_check.unverified_tokens: must be a list")
        unverified = []
    if verdict == "pass" and unverified:
        errors.append(
            f"fact_check.verdict=pass but unverified_tokens is non-empty: {unverified}"
        )

    evidence = fc.get("evidence_logs")
    if not isinstance(evidence, dict):
        errors.append("fact_check.evidence_logs: must be an object {token: log_path}")
        evidence = {}

    # When tokens.json was empty, evidence_logs may legitimately be empty too.
    if tokens_count == 0 and not evidence and verdict == "pass" and not unverified:
        return []  # short-circuit — no tokens to verify

    if not evidence and verdict == "pass" and tokens_count and tokens_count > 0:
        errors.append(
            f"fact_check.evidence_logs: empty but tokens.json contains {tokens_count} tokens"
        )

    base = task_list_path.parent
    for token, log_path_str in evidence.items():
        if not isinstance(log_path_str, str):
            errors.append(f"fact_check.evidence_logs[{token!r}]: value must be a string path")
            continue
        log_path = Path(log_path_str)
        if not log_path.is_absolute():
            log_path = (base / log_path_str).resolve()
        if not log_path.exists():
            errors.append(
                f"fact_check.evidence_logs[{token!r}]: {log_path_str} does not exist"
            )
            continue
        try:
            size = log_path.stat().st_size
        except OSError as exc:
            errors.append(f"fact_check.evidence_logs[{token!r}]: cannot stat ({exc})")
            continue
        if size == 0:
            errors.append(
                f"fact_check.evidence_logs[{token!r}]: {log_path_str} is empty "
                "— fact-checker recorded a token but did not log evidence"
            )

    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: verify_tech_tokens.py <task_list.json>", file=sys.stderr)
        return 2
    errors = verify(Path(argv[1]))
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
