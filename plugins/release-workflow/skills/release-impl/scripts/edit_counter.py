#!/usr/bin/env python3
"""Externalize Loop Detection state so it survives session restarts.

release-impl forbids editing the same file more than 5 times within a single
task implementation, and triggers a 'blocked' transition if the same error
recurs 3 times. Both counters used to live only in the model's attention, so
they reset whenever the session restarts — which is the worst time to lose
them.

This script maintains a JSON state file at
    docs/skills/release-impl/v{version}/.loop_state.json

with the shape:

    {
      "edits":  { "<task_id>": { "<rel_path>": int, ... }, ... },
      "errors": { "<task_id>": { "<error_hash>": int, ... }, ... }
    }

Callers:
    edit_counter.py edit  <version_dir> <task_id> <path>   # increment edit count
    edit_counter.py error <version_dir> <task_id> <msg>    # increment error count
    edit_counter.py show  <version_dir> <task_id>          # pretty-print totals
    edit_counter.py reset <version_dir> <task_id>          # clear one task

Exit codes:
    0  ok (below threshold)
    1  threshold exceeded — caller must stop and escalate
    2  usage / IO error

Thresholds match SKILL.md:
- edits:  5 per file triggers loop-break warning
- errors: 3 identical signatures triggers blocked transition
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


EDIT_LIMIT = 5
ERROR_LIMIT = 3


def _state_path(version_dir: Path) -> Path:
    return version_dir / ".loop_state.json"


def _load(version_dir: Path) -> dict:
    p = _state_path(version_dir)
    if not p.exists():
        return {"edits": {}, "errors": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"edits": {}, "errors": {}}
    data.setdefault("edits", {})
    data.setdefault("errors", {})
    return data


def _save(version_dir: Path, data: dict) -> None:
    _state_path(version_dir).write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def cmd_edit(version_dir: Path, task_id: str, path: str) -> int:
    data = _load(version_dir)
    bucket = data["edits"].setdefault(task_id, {})
    bucket[path] = bucket.get(path, 0) + 1
    _save(version_dir, data)
    count = bucket[path]
    if count > EDIT_LIMIT:
        print(
            f"⚠️ {path}: edited {count} times for {task_id} (> {EDIT_LIMIT}). "
            "Stop and reconsider the approach or escalate to the user.",
            file=sys.stderr,
        )
        return 1
    print(f"{task_id} {path} edits={count}")
    return 0


def cmd_error(version_dir: Path, task_id: str, msg: str) -> int:
    data = _load(version_dir)
    h = hashlib.sha1(msg.strip().encode("utf-8")).hexdigest()[:12]
    bucket = data["errors"].setdefault(task_id, {})
    bucket[h] = bucket.get(h, 0) + 1
    _save(version_dir, data)
    count = bucket[h]
    if count >= ERROR_LIMIT:
        print(
            f"⚠️ {task_id}: error signature {h} recurred {count}×. "
            "Transition task to 'blocked' and escalate to the user.",
            file=sys.stderr,
        )
        return 1
    print(f"{task_id} error={h} count={count}")
    return 0


def cmd_show(version_dir: Path, task_id: str) -> int:
    data = _load(version_dir)
    edits = data["edits"].get(task_id, {})
    errors = data["errors"].get(task_id, {})
    print(json.dumps({"task_id": task_id, "edits": edits, "errors": errors}, ensure_ascii=False, indent=2))
    return 0


def cmd_reset(version_dir: Path, task_id: str) -> int:
    data = _load(version_dir)
    data["edits"].pop(task_id, None)
    data["errors"].pop(task_id, None)
    _save(version_dir, data)
    print(f"reset {task_id}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(
            "usage: edit_counter.py <edit|error|show|reset> <version_dir> <task_id> [<path|msg>]",
            file=sys.stderr,
        )
        return 2
    cmd, vdir = argv[1], Path(argv[2])
    if cmd in {"edit", "error"}:
        if len(argv) != 5:
            print(f"usage: edit_counter.py {cmd} <version_dir> <task_id> <path|msg>", file=sys.stderr)
            return 2
        task_id, extra = argv[3], argv[4]
        return cmd_edit(vdir, task_id, extra) if cmd == "edit" else cmd_error(vdir, task_id, extra)
    if cmd in {"show", "reset"}:
        if len(argv) != 4:
            print(f"usage: edit_counter.py {cmd} <version_dir> <task_id>", file=sys.stderr)
            return 2
        return cmd_show(vdir, argv[3]) if cmd == "show" else cmd_reset(vdir, argv[3])
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
