#!/usr/bin/env python3
"""Synchronize PROGRESS.md header with feature_list.json.

PROGRESS.md has a header block of the form:

    > Last Updated: YYYY-MM-DD HH:MM
    > Total Tasks: N | Pass: P | Fail: F | Blocked: B

which must match the summary counters in feature_list.json at all times. The
model tends to drift these two apart across sessions. This script either
rewrites the header (default) or only checks it (--check) so that a
pre-commit hook can fail fast on drift.

Usage:
    python3 sync_progress.py <version_dir>            # rewrite PROGRESS.md header
    python3 sync_progress.py --check <version_dir>    # exit 1 if out of sync

<version_dir> must contain both feature_list.json and PROGRESS.md.

Exit codes:
    0  header in sync (or successfully rewritten)
    1  drift detected in --check mode
    2  usage / IO error
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import sys
from pathlib import Path


HEADER_RE = re.compile(
    r"^> Last Updated: [^\n]*\n> Total Tasks: \d+ \| Pass: \d+ \| Fail: \d+ \| Blocked: \d+\n",
    re.MULTILINE,
)


def _summary_line(summary: dict) -> str:
    return (
        f"> Total Tasks: {summary.get('total', 0)} | "
        f"Pass: {summary.get('pass', 0)} | "
        f"Fail: {summary.get('fail', 0)} | "
        f"Blocked: {summary.get('blocked', 0)}"
    )


def _rebuild_header(summary: dict, now: str | None = None) -> str:
    ts = now or _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"> Last Updated: {ts}\n{_summary_line(summary)}\n"


def sync(version_dir: Path, check_only: bool) -> int:
    fl = version_dir / "feature_list.json"
    pg = version_dir / "PROGRESS.md"
    if not fl.exists():
        print(f"{fl}: not found", file=sys.stderr)
        return 2
    if not pg.exists():
        print(f"{pg}: not found", file=sys.stderr)
        return 2

    try:
        summary = json.loads(fl.read_text(encoding="utf-8")).get("summary", {})
    except json.JSONDecodeError as exc:
        print(f"{fl}: invalid JSON ({exc})", file=sys.stderr)
        return 2

    text = pg.read_text(encoding="utf-8")
    expected_summary_line = _summary_line(summary)

    if check_only:
        m = HEADER_RE.search(text)
        if not m:
            print(f"{pg}: header block not found (expected two '> ...' lines)", file=sys.stderr)
            return 1
        if expected_summary_line not in m.group(0):
            print(
                f"{pg}: counters drift — expected line:\n  {expected_summary_line}\n"
                f"found block:\n  {m.group(0).rstrip()}",
                file=sys.stderr,
            )
            return 1
        print("OK")
        return 0

    # Rewrite mode
    new_header = _rebuild_header(summary)
    if HEADER_RE.search(text):
        text_new = HEADER_RE.sub(new_header, text, count=1)
    else:
        # No existing header — prepend after the first H1 if present, else at top.
        if text.startswith("# "):
            lines = text.splitlines(keepends=True)
            text_new = lines[0] + "\n" + new_header + "\n" + "".join(lines[1:])
        else:
            text_new = new_header + "\n" + text
    pg.write_text(text_new, encoding="utf-8")
    print("rewritten")
    return 0


def main(argv: list[str]) -> int:
    args = argv[1:]
    check_only = False
    if args and args[0] == "--check":
        check_only = True
        args = args[1:]
    if len(args) != 1:
        print("usage: sync_progress.py [--check] <version_dir>", file=sys.stderr)
        return 2
    return sync(Path(args[0]), check_only)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
