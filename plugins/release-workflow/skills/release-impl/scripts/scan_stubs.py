#!/usr/bin/env python3
"""Reject stub code in files that a task claims to have completed.

release-impl forbids TODO / FIXME / NotImplementedError / placeholder / stub
markers in the files touched by a 'pass' task. The evaluator runs this script
over changed files before accepting a task as complete. Without a script the
model can (and historically does) write 'TODO: implement me' and still mark
the task done.

Usage:
    python3 scan_stubs.py <path> [<path> ...]

Exit codes:
    0  no stubs found
    1  stubs detected (stderr shows 'path:line:pattern' per hit)
    2  usage / IO error

Patterns are intentionally narrow to avoid false positives on legitimate
'todo' mentions inside docstrings or user-facing copy. Case-sensitive.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


# Line-level patterns. Each must be unambiguous: a legitimate mention would
# not normally match these exact forms.
PATTERNS = [
    re.compile(r"\bTODO\b"),
    re.compile(r"\bFIXME\b"),
    re.compile(r"\bXXX\b"),
    re.compile(r"\bHACK\b"),
    re.compile(r"\bplaceholder\b", re.IGNORECASE),
    re.compile(r"NotImplementedError"),
    re.compile(r"raise\s+NotImplemented\b"),
    re.compile(r"pass\s*#\s*stub", re.IGNORECASE),
    re.compile(r"pass\s*#\s*todo", re.IGNORECASE),
    re.compile(r"\bunimplemented!\s*\("),  # Rust macro
    re.compile(r"\btodo!\s*\("),            # Rust macro
]

# Directories we never scan (keep the noise down).
SKIP_DIR_NAMES = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next"}

# Binary / generated extensions to skip.
SKIP_SUFFIXES = {".lock", ".min.js", ".map", ".png", ".jpg", ".jpeg", ".gif", ".webp",
                 ".pdf", ".zip", ".gz", ".tgz", ".jar", ".so", ".dylib"}


def _iter_files(roots: list[Path]):
    for root in roots:
        if root.is_file():
            yield root
            continue
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in p.parts):
                continue
            if p.suffix.lower() in SKIP_SUFFIXES:
                continue
            yield p


def scan(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for fp in _iter_files(paths):
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pat in PATTERNS:
                if pat.search(line):
                    hits.append(f"{fp}:{lineno}: {line.strip()[:120]}")
                    break
    return hits


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: scan_stubs.py <path> [<path> ...]", file=sys.stderr)
        return 2
    hits = scan([Path(a) for a in argv[1:]])
    if hits:
        for h in hits:
            print(h, file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
