#!/usr/bin/env python3
"""Deterministic slug generator for PRD feature names.

Used by the create-prd skill to turn an arbitrary feature name into a stable
path segment for `docs/plan/PRD-{slug}.md`. Running this script instead of
letting the model invent a slug guarantees that the same feature name always
maps to the same file across sessions — that is what lets a later session find
and update an existing PRD instead of silently starting a second one.

WHY THIS IS NOT release-plan/scripts/slugify.py
-----------------------------------------------
Do not "deduplicate" these two scripts. They deliberately differ.

`slugify.py` collapses every non-ASCII run into '-' and returns 'untitled' when
nothing is left — its own docstring records `"릴리즈 플랜" -> untitled`. That is
acceptable there because a Notion *database* name is chosen once per project and
is typically ASCII.

PRD *feature* names are Korean by default in this repo (`여행자 로그인`,
`결제 연동`). Under slugify.py's rules every one of them collapses to
`untitled`, so every PRD in a project would fight over a single file
`docs/plan/PRD-untitled.md`. Partial-ASCII names are just as dangerous:
`결제 API 연동` and `인증 API 개편` both reduce to `api`.

So this script keeps slugify.py's rules but detects *lossy* conversion — the
case where alphanumeric characters were dropped, not just punctuation — and
appends a deterministic hash of the original name:

    Traveler Login   -> traveler-login          (pure ASCII, nothing lost)
    결제 API 연동      -> api-8d2f4a91            (Korean dropped -> hash)
    여행자 로그인      -> untitled-1c7b3e05       (nothing left -> hash)

The hash is sha256 over the NFKC-normalized name, so it is stable across
sessions, machines, and Python versions. Never substitute time or randomness
here: a slug that changes between runs breaks session-to-session state linking,
which is the whole reason this script exists.

Because a hashed slug is not human-readable, the skill asks the user once for a
short English slug and records it in the PRD frontmatter `slug:` field. Later
sessions read it from the document rather than regenerating — the same
state-externalization pattern the rest of this repo uses to avoid re-asking.

Rules:
1. NFKC-normalize, then lowercase.
2. Collapse any run of characters outside [a-z0-9] into a single '-'.
3. Strip leading/trailing '-', then truncate to 60 characters (path hygiene).
4. If any *alphanumeric* character was dropped by rule 2, append '-{hash8}'.
   Dropped punctuation and whitespace alone do not count as loss.
5. If nothing survives rule 3, use 'untitled' as the stem (rule 4 still applies,
   so the result is 'untitled-{hash8}', never a bare 'untitled').

Usage:
    python3 prd_slug.py "Traveler Login"            -> traveler-login
    python3 prd_slug.py "여행자 로그인"                -> untitled-1c7b3e05
    python3 prd_slug.py --explain "여행자 로그인"      -> {"slug": ..., "lossy": true, ...}

`--explain` emits JSON so the skill can tell whether it must ask the user for a
readable slug (`lossy: true`) or can proceed silently (`lossy: false`).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata


_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")
_MAX_STEM = 60
_HASH_LEN = 8


def _hash8(normalized: str) -> str:
    """Stable short digest of the NFKC-normalized name.

    sha256 (not Python's hash()) because hash() is salted per process and would
    produce a different slug on every run.
    """
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:_HASH_LEN]


def prd_slug(name: str) -> dict[str, object]:
    normalized = unicodedata.normalize("NFKC", name).lower()

    # Rule 4 detection: did rule 2 discard anything that carried meaning?
    # Only alphanumerics count — dropping spaces and punctuation is not loss.
    dropped = _NON_SLUG_RE.findall(normalized)
    lossy = any(ch.isalnum() for run in dropped for ch in run)

    stem = _NON_SLUG_RE.sub("-", normalized).strip("-")[:_MAX_STEM].strip("-")
    if not stem:
        stem = "untitled"
        lossy = True  # nothing readable survived; the hash is the only identity

    digest = _hash8(normalized)
    slug = f"{stem}-{digest}" if lossy else stem

    return {"slug": slug, "stem": stem, "lossy": lossy, "hash": digest}


def main(argv: list[str]) -> int:
    args = argv[1:]
    explain = False
    if args and args[0] == "--explain":
        explain = True
        args = args[1:]

    if len(args) != 1:
        print("usage: prd_slug.py [--explain] <feature name>", file=sys.stderr)
        return 2

    result = prd_slug(args[0])
    if explain:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(result["slug"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
