#!/usr/bin/env python3
"""Deterministic initializer for docs/skills/release-impl/v{version}/.

Creates feature_list.json (with correct schema shape, defaults, and a
pre-computed acceptance_criteria_hashes table) and a PROGRESS.md whose
header is already in sync with the summary counters. Running a script
instead of hand-writing these files prevents template drift: every new
version starts from the same shape, which makes validator failures about
the contents rather than the boilerplate.

Typical callers:
- release-impl Phase 1 Step 5/6 after the tasks are assembled from
  release-plan's task_list.json.
- Eval fixtures that need a known-good starting point.

Input: a 'source' JSON on stdin describing the batch, shape:

    {
      "version": "v0.9.0",
      "source": "release-plan/task_list.json",
      "notion_page": "...",
      "notion_database": "...",
      "previous_context": [...],
      "tasks": [
        {
          "id": "TASK-001",
          "title": "[Task 1] ...",
          "description": "...",
          "acceptance_criteria": ["...", "..."],
          "priority": 1,
          "dependencies": []
        },
        ...
      ]
    }

Output written:
    <out_dir>/feature_list.json
    <out_dir>/PROGRESS.md   (only if --with-progress; otherwise left alone)

Usage:
    python3 init_version.py <out_dir> [--with-progress] < source.json

Exit codes:
    0  files written
    1  input invalid
    2  usage / IO error
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path


PROGRESS_TEMPLATE = """# Progress — release-impl {version}

> Last Updated: {ts}
> Total Tasks: {total} | Pass: 0 | Fail: {total} | Blocked: 0

## 현재 상태

- 단계: 초기화 완료, 구현 대기
- 다음 작업: {first_task}
- 차단 사항: 없음

## 이전 버전 컨텍스트

{prev_context_block}

## 세션 로그

- [{date}] 초기화: {total}개 작업 로드, feature_list.json 생성{prev_scan_suffix}

## 발견된 이슈

(없음)

## 다음 단계

1. {first_task}부터 순차 구현 시작
"""


def _hash(criteria: list) -> str:
    payload = json.dumps(criteria, ensure_ascii=False, sort_keys=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _build_feature_list(src: dict) -> dict:
    tasks_out = []
    hashes: dict[str, str] = {}
    for t in src.get("tasks", []):
        task = {
            "id": t["id"],
            "title": t["title"],
            "description": t.get("description", ""),
            "acceptance_criteria": list(t["acceptance_criteria"]),
            "status": "fail",
            "priority": int(t.get("priority", 0)),
            "dependencies": list(t.get("dependencies", [])),
            "retry_count": 0,
            "evaluator_feedback": None,
            "completed_at": None,
            "evidence_logs": {},
        }
        tasks_out.append(task)
        hashes[task["id"]] = _hash(task["acceptance_criteria"])

    impl_root = src.get("implementation_root", None)
    if impl_root is not None and not isinstance(impl_root, str):
        raise ValueError(f"implementation_root must be a string or null (got {type(impl_root).__name__})")
    return {
        "version": src["version"],
        "source": src.get("source", "release-plan/task_list.json"),
        "notion_page": src["notion_page"],
        "notion_database": src["notion_database"],
        "created_at": _dt.date.today().isoformat(),
        "current_task_id": None,
        "implementation_root": impl_root,
        "summary": {
            "total": len(tasks_out),
            "pass": 0,
            "fail": len(tasks_out),
            "blocked": 0,
        },
        "acceptance_criteria_hashes": hashes,
        "previous_context": list(src.get("previous_context", [])),
        "tasks": tasks_out,
    }


def _build_progress(fl: dict) -> str:
    tasks = fl["tasks"]
    first = tasks[0]["title"] if tasks else "(없음)"
    prev = fl.get("previous_context", [])
    if prev:
        lines = []
        for p in prev:
            lines.append(f"- **[{p['version']} · {p['type']}]** {p['summary']} — {p['relevance']}")
        prev_block = "\n".join(lines)
        suffix = f", 이전 버전 {len(prev)}개 스캔 완료"
    else:
        prev_block = "(해당 없음 — 첫 릴리즈)"
        suffix = ""
    return PROGRESS_TEMPLATE.format(
        version=fl["version"],
        ts=_dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        total=len(tasks),
        first_task=first,
        prev_context_block=prev_block,
        prev_scan_suffix=suffix,
        date=_dt.date.today().isoformat(),
    )


def main(argv: list[str]) -> int:
    args = argv[1:]
    with_progress = False
    if "--with-progress" in args:
        with_progress = True
        args.remove("--with-progress")
    if len(args) != 1:
        print("usage: init_version.py <out_dir> [--with-progress] < source.json", file=sys.stderr)
        return 2

    out_dir = Path(args[0])
    try:
        src = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"stdin: invalid JSON ({exc})", file=sys.stderr)
        return 1

    required_src = {"version", "notion_page", "notion_database", "tasks"}
    missing = required_src - src.keys()
    if missing:
        print(f"stdin: missing keys {sorted(missing)}", file=sys.stderr)
        return 1

    try:
        fl = _build_feature_list(src)
    except ValueError as exc:
        print(f"stdin: {exc}", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sprint_contracts").mkdir(exist_ok=True)
    (out_dir / "logs").mkdir(exist_ok=True)
    (out_dir / "feature_list.json").write_text(
        json.dumps(fl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if with_progress:
        (out_dir / "PROGRESS.md").write_text(_build_progress(fl), encoding="utf-8")
    print(f"wrote {out_dir}/feature_list.json"
          + (f" and PROGRESS.md" if with_progress else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
