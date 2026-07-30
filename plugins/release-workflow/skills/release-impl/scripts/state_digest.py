#!/usr/bin/env python3
"""Compact state digest for sub-agent injection (Generator / Evaluator).

Generator and Evaluator are kicked off as separate Task sub-agents for every
task in a release. Re-injecting the full feature_list.json + PROGRESS.md +
.loop_state.json into each call is the largest accumulating cost in Phase 2,
since most of those files are unchanged from one call to the next. This script
emits a small JSON digest that contains only the fields a sub-agent actually
acts on:

    - identity: version_dir, task_id, version
    - run state: current_task_id, summary, status / retry / feedback for the
      task being worked on
    - last few PROGRESS.md session lines and an issue-count
    - loop counters (edits, errors) for the current task only

Validators (validate_feature_list.py, validate_task_list.py) still read the
full files; only the LLM-facing payload is shrunk.

Usage:
    python3 state_digest.py <version_dir> [--task-id TASK-NNN] [--session-tail N]

Outputs JSON to stdout. Non-zero exit only on missing version_dir or invalid
JSON in feature_list.json (we do not re-validate the full schema here).

Exit codes:
    0  success
    1  version_dir or feature_list.json missing/invalid
    2  usage error
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


_HEADER_LINE_RE = re.compile(r"^>\s*(Last Updated:.*|Total Tasks:.*)\s*$")
_SESSION_HEADER_RE = re.compile(r"^##\s*세션\s*로그\s*$", re.MULTILINE)
_ISSUES_HEADER_RE = re.compile(r"^##\s*발견된\s*이슈\s*$", re.MULTILINE)
_NEXT_HEADER_RE = re.compile(r"^##\s+", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$")


def _slice(text: str, header_re: re.Pattern[str]) -> str:
    m = header_re.search(text)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = _NEXT_HEADER_RE.search(rest)
    return rest[: nxt.start()] if nxt else rest


def _digest_progress(text: str, session_tail: int) -> dict[str, Any]:
    if not text:
        return {"header": [], "session_tail": [], "issue_count": 0}
    header_lines = [
        m.group(1).strip()
        for line in text.splitlines()
        for m in [_HEADER_LINE_RE.match(line)]
        if m
    ]
    session_body = _slice(text, _SESSION_HEADER_RE)
    bullets: list[str] = []
    for line in session_body.splitlines():
        m = _BULLET_RE.match(line)
        if not m:
            continue
        item = m.group(1).strip()
        if item:
            bullets.append(item)
    tail = bullets[-session_tail:] if session_tail > 0 else []
    issues_body = _slice(text, _ISSUES_HEADER_RE)
    issue_count = sum(
        1
        for line in issues_body.splitlines()
        for m in [_BULLET_RE.match(line)]
        if m and m.group(1).strip() != "(없음)"
    )
    return {"header": header_lines, "session_tail": tail, "issue_count": issue_count}


def _digest_feature_list(fl: dict[str, Any], task_id: str | None) -> dict[str, Any]:
    summary = fl.get("summary") or {}
    current = fl.get("current_task_id")
    target_id = task_id or current
    target: dict[str, Any] | None = None
    if target_id:
        for t in fl.get("tasks", []) or []:
            if isinstance(t, dict) and t.get("id") == target_id:
                target = t
                break

    target_digest: dict[str, Any] | None = None
    if target is not None:
        target_digest = {
            "id": target.get("id"),
            "title": target.get("title"),
            "status": target.get("status"),
            "retry_count": target.get("retry_count"),
            "evaluator_feedback": target.get("evaluator_feedback"),
            "dependencies": target.get("dependencies", []),
            "evidence_logs_keys": sorted((target.get("evidence_logs") or {}).keys()),
            "acceptance_criteria_count": len(target.get("acceptance_criteria") or []),
        }

    pending: list[dict[str, Any]] = []
    for t in fl.get("tasks", []) or []:
        if not isinstance(t, dict):
            continue
        if t.get("status") in {"fail", "in_progress"}:
            pending.append({
                "id": t.get("id"),
                "title": t.get("title"),
                "priority": t.get("priority"),
                "dependencies": t.get("dependencies", []),
                "retry_count": t.get("retry_count"),
            })
    return {
        "version": fl.get("version"),
        "implementation_root": fl.get("implementation_root"),
        "current_task_id": current,
        "summary": {
            "total": summary.get("total"),
            "pass": summary.get("pass"),
            "fail": summary.get("fail"),
            "blocked": summary.get("blocked"),
        },
        "task": target_digest,
        "pending_count": len(pending),
        "pending_preview": pending[:5],
    }


def _digest_loop_state(loop: dict[str, Any] | None, task_id: str | None) -> dict[str, Any]:
    if not isinstance(loop, dict):
        return {"edits": {}, "errors": {}}
    edits = (loop.get("edits") or {}).get(task_id or "", {}) if task_id else {}
    errors = (loop.get("errors") or {}).get(task_id or "", {}) if task_id else {}
    return {"edits": edits, "errors": errors}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="state_digest.py")
    parser.add_argument("version_dir", type=Path)
    parser.add_argument("--task-id", type=str, default=None)
    parser.add_argument("--session-tail", type=int, default=3)
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as exc:
        return int(getattr(exc, "code", 2) or 2)

    vdir: Path = args.version_dir
    if not vdir.is_dir():
        print(f"version_dir not found: {vdir}", file=sys.stderr)
        return 1

    fl_path = vdir / "feature_list.json"
    try:
        fl = _read_json(fl_path)
    except FileNotFoundError:
        print(f"feature_list.json not found: {fl_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"feature_list.json invalid JSON: {exc}", file=sys.stderr)
        return 1

    if not isinstance(fl, dict):
        print("feature_list.json must be a JSON object", file=sys.stderr)
        return 1

    progress_text = _safe_read_text(vdir / "PROGRESS.md")
    loop_state: dict[str, Any] | None = None
    loop_path = vdir / ".loop_state.json"
    if loop_path.is_file():
        try:
            data = _read_json(loop_path)
            if isinstance(data, dict):
                loop_state = data
        except json.JSONDecodeError:
            loop_state = None

    target_task_id = args.task_id or (fl.get("current_task_id") if isinstance(fl.get("current_task_id"), str) else None)

    payload = {
        "schema": "release-impl/state_digest@1",
        "version_dir": str(vdir),
        "task_id": target_task_id,
        "feature_list": _digest_feature_list(fl, target_task_id),
        "progress": _digest_progress(progress_text, args.session_tail),
        "loop_state": _digest_loop_state(loop_state, target_task_id),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
