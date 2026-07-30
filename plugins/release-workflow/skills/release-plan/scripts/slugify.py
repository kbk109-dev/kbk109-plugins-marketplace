#!/usr/bin/env python3
"""Deterministic slug generator for Notion DB names.

Used by the release-plan skill (Step 3 / Step 7) to produce a stable kebab-case
path segment from an arbitrary DB name. Running this script instead of letting
the model invent a slug guarantees that the same DB name always maps to the
same filesystem location across sessions.

Rules:
1. NFKC-normalize then lowercase.
2. Collapse any run of characters outside [a-z0-9] into a single '-'.
3. Strip leading/trailing '-'.
4. If the result is empty, return 'untitled'.

Non-ASCII scripts (e.g., Korean) become '-' separators by rule 2 — callers that
need to preserve a localized name should keep the original DB name elsewhere
(e.g., in release-plan.md frontmatter) and use the slug only for paths.

Usage:
    python3 slugify.py "Release Plan"       -> release-plan
    python3 slugify.py "v2.1 Tasks"         -> v2-1-tasks
    python3 slugify.py "릴리즈 플랜"          -> untitled
    python3 slugify.py "A/B (test)_v2"      -> a-b-test-v2
"""
from __future__ import annotations

import re
import sys
import unicodedata


_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name).lower()
    collapsed = _NON_SLUG_RE.sub("-", normalized).strip("-")
    return collapsed or "untitled"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: slugify.py <name>", file=sys.stderr)
        return 2
    print(slugify(argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
