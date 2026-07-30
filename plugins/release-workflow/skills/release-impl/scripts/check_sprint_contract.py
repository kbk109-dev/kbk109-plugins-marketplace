#!/usr/bin/env python3
"""Verify Generator produced a well-formed sprint contract before Evaluator runs.

release-impl requires that Generator writes a sprint contract in
    {version_dir}/sprint_contracts/{task_id}.md
before implementing any code. The contract pins down three things:
  - 예상 수정 파일       (which files will change)
  - 예상 검증 커맨드     (which commands Evaluator should run)
  - 예상 실패 가능점     (what the Generator already anticipates could fail)

Without a contract, the Evaluator has no prior-art to compare actual output
against, and the Generator has no incentive to think through failure modes
before coding. This script is the Evaluator's first gate: no contract means
immediate fail.

Usage:
    python3 check_sprint_contract.py <version_dir> <task_id>

Exit codes:
    0  contract exists and has all three required sections
    1  contract missing or malformed
    2  usage / IO error
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED_SECTIONS = [
    ("예상 수정 파일", re.compile(r"^## ?예상 수정 파일\s*$", re.MULTILINE)),
    ("예상 검증 커맨드", re.compile(r"^## ?예상 검증 커맨드\s*$", re.MULTILINE)),
    ("예상 실패 가능점", re.compile(r"^## ?예상 실패 가능점\s*$", re.MULTILINE)),
]

# A section "has content" if there is at least one non-empty, non-heading
# line between the heading and the next '## ' heading or EOF.
SECTION_SPLIT = re.compile(r"^##\s+", re.MULTILINE)


def _section_has_content(body: str, heading: str) -> bool:
    parts = SECTION_SPLIT.split(body)
    for part in parts[1:]:
        title = part.splitlines()[0].strip() if part.strip() else ""
        # allow optional leading whitespace around heading text
        if title.lstrip(" ").startswith(heading):
            lines = [ln.strip() for ln in part.splitlines()[1:] if ln.strip()]
            return bool(lines)
    return False


def check(version_dir: Path, task_id: str) -> list[str]:
    contract = version_dir / "sprint_contracts" / f"{task_id}.md"
    if not contract.exists():
        return [f"{contract}: not found — Generator must write the contract before coding"]
    try:
        body = contract.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{contract}: read error ({exc})"]

    errors: list[str] = []
    for heading, pat in REQUIRED_SECTIONS:
        if not pat.search(body):
            errors.append(f"{contract}: missing section '## {heading}'")
        elif not _section_has_content(body, heading):
            errors.append(f"{contract}: section '## {heading}' is empty")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: check_sprint_contract.py <version_dir> <task_id>", file=sys.stderr)
        return 2
    errors = check(Path(argv[1]), argv[2])
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
