#!/usr/bin/env python3
"""Structural gate for a PRD document produced by the create-prd skill.

This script exists because the source article's four "common mistakes" include
*skipping acceptance criteria or metrics*, and a model asked to self-assess its
own PRD will report success anyway. So the checks that can be mechanized are
mechanized here, and the model is not allowed to declare the PRD complete until
this exits 0. Judgement calls that a regex cannot make (are the user stories
really user-shaped? is this drifting into a technical spec?) are deliberately
left to the three reviewer subagents instead of being faked here.

Checks
------
1. Frontmatter has name / slug / status, and status is draft or reviewed.
2. All ten sections from the article are present, numbered, and non-empty.
3. Every user story uses the article's `As a ... I want ... so that ...` shape.
4. Every functional requirement (FR-n) is referenced by at least one acceptance
   criterion  -- this is the article's mistake (3) made unskippable.
5. Every acceptance criterion carries Given / When / Then.
6. Every `[제안]` (model-drafted number) sits in a table with a 근거 column and
   has a non-placeholder 근거 cell. A draft number without a stated rationale is
   indistinguishable from a fabricated one.
7. No stub text (TBD / TODO / 작성 필요 / XXX) anywhere.

Exit codes
----------
0  gate passed
1  gate failed (findings printed; `[제안]` count still reported)
2  usage error or unreadable file

Usage
-----
    python3 validate_prd.py docs/plan/PRD-traveler-login.md
    python3 validate_prd.py --json docs/plan/PRD-traveler-login.md
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Canonical section list, straight from the article's "10 key sections in a PRD".
# The Korean name must appear in the heading; an English parenthetical is allowed
# and encouraged, matching the bilingual style of the source page.
SECTIONS: list[tuple[int, str]] = [
    (1, "문서 정보"),
    (2, "개요"),
    (3, "유저스토리"),
    (4, "기능 요구사항"),
    (5, "비기능 요구사항"),
    (6, "유저 플로우"),
    (7, "수용기준"),
    (8, "의존성"),
    (9, "위험·가정"),
    (10, "성공 지표"),
]

_HEADING_RE = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.MULTILINE)
_FR_ID_RE = re.compile(r"\bFR-(\d+)\b")
_US_ID_RE = re.compile(r"\bUS-(\d+)\b")
_AC_ID_RE = re.compile(r"\bAC-(\d+)\b")
_PROPOSAL = "[제안]"

# Stub markers. `...` is excluded on purpose: an ellipsis is legitimate prose in
# Korean, and the placeholder cases it would catch are already caught by the
# empty-cell and empty-section checks.
_STUB_RE = re.compile(r"\bTBD\b|\bTODO\b|\bXXX\b|작성 필요|추후 작성|미작성", re.IGNORECASE)

# Cells that look filled but say nothing.
_EMPTY_CELL = {"", "-", "—", "–", "n/a", "na", "없음", "미정", "?"}


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter dict, body). Body keeps original line count offset."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end]
    rest = text[end + 4 :]
    fm: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip("\"'")
    return fm, rest


def _sections(body: str) -> dict[int, str]:
    """Map section number -> (heading text + content)."""
    matches = list(_HEADING_RE.finditer(body))
    out: dict[int, str] = {}
    for i, m in enumerate(matches):
        try:
            num = int(m.group(1))
        except ValueError:  # pragma: no cover - regex guarantees digits
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out[num] = body[m.start() : end]
    return out


def _heading_titles(body: str) -> dict[int, str]:
    return {int(m.group(1)): m.group(2) for m in _HEADING_RE.finditer(body)}


def _table_rows(chunk: str) -> list[tuple[list[str], list[str]]]:
    """Extract markdown tables as (header cells, data rows) pairs."""
    tables: list[tuple[list[str], list[str]]] = []
    lines = chunk.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines):
            sep = lines[i + 1].strip()
            if set(sep) <= set("|-: ") and "-" in sep:
                header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows: list[str] = []
                j = i + 2
                while j < len(lines) and lines[j].lstrip().startswith("|"):
                    rows.append(lines[j])
                    j += 1
                tables.append((header, rows))
                i = j
                continue
        i += 1
    return tables


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def validate(path: Path) -> tuple[list[str], dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    findings: list[str] = []

    # --- 1. frontmatter -----------------------------------------------------
    for key in ("name", "slug", "status"):
        if not fm.get(key):
            findings.append(f"frontmatter: `{key}` 누락 또는 공백")
    status = fm.get("status", "")
    if status and status not in {"draft", "reviewed"}:
        findings.append(f"frontmatter: status='{status}' — draft 또는 reviewed 여야 함")

    # --- 2. ten sections, present and non-empty -----------------------------
    found = _sections(body)
    titles = _heading_titles(body)
    for num, korean in SECTIONS:
        if num not in found:
            findings.append(f"섹션 {num}. {korean} 누락 (원문 10개 핵심 섹션)")
            continue
        if korean not in titles.get(num, ""):
            findings.append(
                f"섹션 {num} 제목이 '{titles.get(num, '')}' — '{korean}' 을 포함해야 함"
            )
        content = _HEADING_RE.sub("", found[num], count=1).strip()
        if not content:
            findings.append(f"섹션 {num}. {korean} 본문이 비어 있음")

    # --- 3. user story shape ------------------------------------------------
    us_section = found.get(3, "")
    story_lines = [
        ln for ln in us_section.splitlines() if _US_ID_RE.search(ln)
    ]
    if not story_lines:
        findings.append("섹션 3: 유저스토리(US-n)가 0건 — 원문 Step 3 미충족")
    for ln in story_lines:
        lowered = ln.lower()
        if not ("as a" in lowered and "i want" in lowered and "so that" in lowered):
            sid = _US_ID_RE.search(ln)
            findings.append(
                f"섹션 3 {sid.group(0) if sid else '?'}: "
                "`As a ... I want ... so that ...` 형식 위반 (원문 Step 3)"
            )

    # --- 4/5. FR <-> AC coverage and Given-When-Then -------------------------
    fr_section = found.get(4, "")
    ac_section = found.get(7, "")
    fr_ids = {f"FR-{n}" for n in _FR_ID_RE.findall(fr_section)}
    if not fr_ids:
        findings.append("섹션 4: 기능 요구사항(FR-n)이 0건 — 원문 Step 4 미충족")

    ac_lines = [ln for ln in ac_section.splitlines() if _AC_ID_RE.search(ln)]
    if not ac_lines:
        findings.append(
            "섹션 7: 수용기준(AC-n)이 0건 — 원문이 지적한 흔한 실수 ③(수용기준 생략)"
        )

    referenced = {f"FR-{n}" for n in _FR_ID_RE.findall(ac_section)}
    for fr in sorted(fr_ids, key=lambda s: int(s.split("-")[1])):
        if fr not in referenced:
            findings.append(
                f"섹션 7: {fr} 을 검증하는 수용기준이 없음 — 모든 기능 요구사항은 "
                "최소 1건의 Given-When-Then 을 가져야 한다 (원문 Step 5)"
            )

    for ln in ac_lines:
        low = ln.lower()
        missing = [kw for kw in ("given", "when", "then") if kw not in low]
        if missing:
            aid = _AC_ID_RE.search(ln)
            findings.append(
                f"섹션 7 {aid.group(0) if aid else '?'}: "
                f"{'/'.join(m.title() for m in missing)} 누락 — Given-When-Then 필수"
            )

    # --- 6. [제안] numbers must carry a 근거 --------------------------------
    proposal_total = body.count(_PROPOSAL)
    grounded = 0
    for num, chunk in found.items():
        for header, rows in _table_rows(chunk):
            try:
                basis_col = next(
                    i for i, h in enumerate(header) if "근거" in h
                )
            except StopIteration:
                basis_col = -1
            for row in rows:
                if _PROPOSAL not in row:
                    continue
                cells = _cells(row)
                label = cells[0] if cells else "?"
                if basis_col == -1:
                    findings.append(
                        f"섹션 {num} '{label}': [제안] 수치가 근거 컬럼 없는 표에 있음 — "
                        "근거 없는 초안 수치는 날조와 구별되지 않는다"
                    )
                    continue
                basis = cells[basis_col] if basis_col < len(cells) else ""
                if basis.strip().lower() in _EMPTY_CELL:
                    findings.append(
                        f"섹션 {num} '{label}': [제안] 수치의 근거가 비어 있음 "
                        f"(근거='{basis}')"
                    )
                else:
                    grounded += 1

    # A [제안] outside any table cannot be checked, so it is not allowed.
    in_table_proposals = sum(
        row.count(_PROPOSAL)
        for chunk in found.values()
        for _, rows in _table_rows(chunk)
        for row in rows
    )
    if proposal_total > in_table_proposals:
        findings.append(
            f"[제안] {proposal_total - in_table_proposals}건이 표 밖에 있음 — "
            "근거를 검증할 수 없으므로 근거 컬럼이 있는 표 안에만 쓴다"
        )

    # --- 7. stub text -------------------------------------------------------
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = _STUB_RE.search(line)
        if m:
            findings.append(f"{lineno}행: 스텁 표현 '{m.group(0)}' — 실제 내용으로 대체")

    summary: dict[str, object] = {
        "path": str(path),
        "status": status,
        "sections_found": sorted(found),
        "user_stories": len(story_lines),
        "functional_requirements": len(fr_ids),
        "acceptance_criteria": len(ac_lines),
        "proposals_total": proposal_total,
        "proposals_grounded": grounded,
        "findings": len(findings),
        "verdict": "pass" if not findings else "fail",
    }
    return findings, summary


def main(argv: list[str]) -> int:
    args = argv[1:]
    as_json = False
    if args and args[0] == "--json":
        as_json = True
        args = args[1:]

    if len(args) != 1:
        print("usage: validate_prd.py [--json] <PRD.md>", file=sys.stderr)
        return 2

    path = Path(args[0])
    if not path.is_file():
        print(f"파일을 찾을 수 없습니다: {path}", file=sys.stderr)
        return 2

    findings, summary = validate(path)

    if as_json:
        print(json.dumps({**summary, "detail": findings}, ensure_ascii=False, indent=2))
    else:
        print(f"PRD 검증: {path}")
        print(
            f"  섹션 {len(summary['sections_found'])}/10 · "
            f"US {summary['user_stories']} · FR {summary['functional_requirements']} · "
            f"AC {summary['acceptance_criteria']} · "
            f"[제안] {summary['proposals_total']}건(근거 확인 {summary['proposals_grounded']}건)"
        )
        if findings:
            print(f"\n실패 {len(findings)}건:")
            for f in findings:
                print(f"  ✗ {f}")
        else:
            print("\n통과 — 모든 구조 검사 충족.")
            if summary["proposals_total"]:
                print(
                    f"  ⚠ [제안] {summary['proposals_total']}건은 팀 확정이 필요한 "
                    "초안 수치다 (구조는 통과)."
                )

    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
