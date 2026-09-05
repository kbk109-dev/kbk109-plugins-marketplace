#!/usr/bin/env python3
"""Drift checker for the AGENTS.md-as-SSoT layout.

AGENTS.md and CLAUDE.md cannot drift by construction — CLAUDE.md only points at
AGENTS.md. What CAN drift is the .cursor/rules/*.mdc mirror: it is a generated
copy, editing it produces no error, and from that moment Cursor and Claude
follow different rules. Check 5 is the reason this script exists; the rest guard
the structure that makes check 5 meaningful.

Usage:
    check_agent_rules.py [--project-root PATH] [--quiet]

Exit codes:
    0  every check passed
    1  at least one check failed (details on stderr, one line each)
    2  usage / IO error

Checks:
    1  AGENTS.md exists and is non-blank
    2  CLAUDE.md contains the @AGENTS.md import
    3  CLAUDE.md carries no project body of its own
    4  .claude/rules/<rule>.md exists and is non-blank
    5  .cursor/rules/<rule>.mdc body == check 4's content, byte-for-byte
    6  AGENTS.md carries exactly one intact marker block per rule
    7  (notion-api-only only) .claude/scripts/notion_api.py matches the plugin's template
    8  (notion-api-only only) .claude/hooks/notion_mcp_gate.py matches the plugin's template
    9  (notion-api-only only) .claude/settings.json registers exactly one PreToolUse hook
       for notion_mcp_gate.py, pointing at the file check 8 verified

Checks 4–6 run once per rule. A rule counts as installed when ANY of its three
artefacts is present (.md, .mdc, marker block) — that way half an install is a
failure rather than an invisible no-op. Checks 7–9 run only when notion-api-only
is installed by that same definition — they compare the PROJECT'S installed
copy against THIS PLUGIN'S OWN template, the same "generated copy can drift"
concern check 5 already covers for the .mdc mirror, not a cross-plugin check.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Duplicated from init-agent-rules/scripts/install_agent_rules.py — the installer
# owns the rule bodies, this script only needs each rule's identity. Add a rule
# there and it must be added here too, or the new rule silently escapes
# checking. Kept as a copy rather than an import: the two skills are installed
# as independent directories.
RULES = (
    {"name": "git-branch-workflow", "required": True},
    {"name": "notion-api-only", "required": False},
)

# Also duplicated from install_agent_rules.py — same reasoning.
SCRIPT_INSTALLS = (
    {"template": "notion_api.py", "dest": ".claude/scripts/notion_api.py"},
    {"template": "notion_mcp_gate.py", "dest": ".claude/hooks/notion_mcp_gate.py"},
)
HOOK_MARKER = "notion_mcp_gate.py"


def claude_rel(name: str) -> str:
    return f".claude/rules/{name}.md"


def cursor_rel(name: str) -> str:
    return f".cursor/rules/{name}.mdc"


def mark_begin(name: str) -> str:
    return f"<!-- >>> agent-rules: {name} >>> -->"


def mark_end(name: str) -> str:
    return f"<!-- <<< agent-rules: {name} <<< -->"

# A pointer CLAUDE.md is a heading plus a short note. Any h2 section, or more
# prose than this, means a project body has crept back in.
MAX_POINTER_LINES = 12


def strip_mdc_frontmatter(text: str) -> str:
    """Return the .mdc body with its leading YAML frontmatter removed."""
    if not text.startswith("---"):
        return text
    lines = text.splitlines(keepends=True)
    for i in range(1, len(lines)):
        if lines[i].rstrip("\n") == "---":
            return "".join(lines[i + 1:])
    return text  # unterminated frontmatter — compare as-is and let check 5 fail


def check_rule(root: Path, agents_text: str, rule: dict) -> list[str]:
    """Checks 4, 5 and 6 for one rule."""
    name = rule["name"]
    errors: list[str] = []
    rule_md = root / claude_rel(name)
    rule_mdc = root / cursor_rel(name)
    has_marker = mark_begin(name) in agents_text or mark_end(name) in agents_text

    if not (rule_md.is_file() or rule_mdc.is_file() or has_marker):
        # required=False 규칙(예: notion-api-only)이 아예 없는 것은 실패가 아니다 — 이
        # 프로젝트가 그 규칙을 선택하지 않은 것뿐이다. required 규칙만 부재를 실패로 본다.
        if rule.get("required", True):
            errors.append(
                f"4. {claude_rel(name)}: not found — "
                "run /project-conventions:init-agent-rules"
            )
        return errors

    # 4 --------------------------------------------------------------------
    md_body = None
    if not rule_md.is_file():
        errors.append(f"4. {claude_rel(name)}: not found")
    else:
        md_body = rule_md.read_text(encoding="utf-8")
        if not md_body.strip():
            errors.append(f"4. {claude_rel(name)}: file is blank")
            md_body = None

    # 5 --------------------------------------------------------------------
    if not rule_mdc.is_file():
        errors.append(f"5. {cursor_rel(name)}: not found — Cursor gets no rule")
    elif md_body is not None:
        mdc_text = rule_mdc.read_text(encoding="utf-8")
        if not mdc_text.startswith("---"):
            errors.append(f"5. {cursor_rel(name)}: missing .mdc frontmatter")
        mdc_body = strip_mdc_frontmatter(mdc_text)
        if mdc_body.strip("\n") != md_body.strip("\n"):
            errors.append(
                f"5. {cursor_rel(name)}: body differs from {claude_rel(name)} — "
                "the mirror drifted. Re-run /project-conventions:init-agent-rules "
                "after moving any intended edit into the .md file."
            )

    # 6 --------------------------------------------------------------------
    if agents_text:
        n_begin = agents_text.count(mark_begin(name))
        n_end = agents_text.count(mark_end(name))
        if n_begin == 0 and n_end == 0:
            errors.append(
                f"6. AGENTS.md: {name} 마커 블록 없음 — 규칙 파일은 있는데 포인터가 없다"
            )
        elif n_begin != 1 or n_end != 1:
            errors.append(
                f"6. AGENTS.md: {name} 마커 블록 malformed (open={n_begin}, close={n_end}; "
                "expected 1 each)"
            )
        elif agents_text.find(mark_end(name)) < agents_text.find(mark_begin(name)):
            errors.append(f"6. AGENTS.md: {name} 마커 블록이 열리기 전에 닫힌다")

    return errors


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def check_notion_scripts(root: Path) -> list[str]:
    """Checks 7, 8, 9 — only when notion-api-only is installed (same three-artefact
    definition as check_rule uses for the other rules)."""
    name = "notion-api-only"
    agents_path = root / "AGENTS.md"
    agents_text = agents_path.read_text(encoding="utf-8") if agents_path.is_file() else ""
    has_marker = mark_begin(name) in agents_text or mark_end(name) in agents_text
    installed = (root / claude_rel(name)).is_file() or (root / cursor_rel(name)).is_file() or has_marker
    if not installed:
        return []

    errors: list[str] = []
    templates_dir = Path(__file__).resolve().parents[2] / "init-agent-rules" / "templates"
    hook_dest = None

    for n, item in enumerate(SCRIPT_INSTALLS, start=7):
        dest = root / item["dest"]
        template = templates_dir / item["template"]
        if item["template"] == "notion_mcp_gate.py":
            hook_dest = dest
        if not dest.is_file():
            errors.append(f"{n}. {item['dest']}: not found — run /project-conventions:init-agent-rules --notion-rule on")
            continue
        template_hash = _sha256(template)
        if template_hash is None:
            print(f"warning: template not found, skipping check {n}: {template}", file=sys.stderr)
            continue
        if _sha256(dest) != template_hash:
            errors.append(
                f"{n}. {item['dest']}: drifted from the plugin template — "
                "re-run /project-conventions:init-agent-rules --notion-rule on"
            )

    # 9 -----------------------------------------------------------------
    settings_path = root / ".claude" / "settings.json"
    if not settings_path.is_file():
        errors.append("9. .claude/settings.json: not found — Notion MCP is not blocked")
    else:
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(f"9. .claude/settings.json: parse failed — {exc}")
            data = {}
        entries = [
            h
            for entry in (data.get("hooks", {}).get("PreToolUse", []) if isinstance(data, dict) else [])
            for h in entry.get("hooks", [])
            if HOOK_MARKER in h.get("command", "")
        ]
        if len(entries) != 1:
            errors.append(
                f"9. .claude/settings.json: expected exactly 1 PreToolUse hook for "
                f"{HOOK_MARKER}, found {len(entries)} — "
                "re-run /project-conventions:init-agent-rules --notion-rule on"
            )
        elif hook_dest is not None:
            # $CLAUDE_PROJECT_DIR 는 실행 시점에만 전개되므로 command 문자열엔 그대로
            # 남는다 — 대조는 파일명(basename)으로 한다.
            command = entries[0].get("command", "")
            if hook_dest.name not in command:
                errors.append(
                    f"9. .claude/settings.json: registered hook command does not point at "
                    f".claude/hooks/{hook_dest.name}"
                )

    return errors


def check(root: Path) -> list[str]:
    errors: list[str] = []
    agents = root / "AGENTS.md"
    claude = root / "CLAUDE.md"

    # 1 --------------------------------------------------------------------
    agents_text = ""
    if not agents.is_file():
        errors.append("1. AGENTS.md: not found — run /project-conventions:init-agent-rules")
    else:
        agents_text = agents.read_text(encoding="utf-8")
        if not agents_text.strip():
            errors.append("1. AGENTS.md: file is blank")

    # 2, 3 -----------------------------------------------------------------
    if not claude.is_file():
        errors.append("2. CLAUDE.md: not found — Claude Code will not load AGENTS.md via import")
    else:
        claude_text = claude.read_text(encoding="utf-8")
        if "@AGENTS.md" not in claude_text:
            errors.append("2. CLAUDE.md: missing the '@AGENTS.md' import line")

        body = [ln for ln in claude_text.splitlines() if ln.strip()]
        headings = [ln for ln in body if ln.lstrip().startswith("##")]
        if headings:
            errors.append(
                f"3. CLAUDE.md: has {len(headings)} section heading(s) "
                f"(first: {headings[0].strip()!r}) — content belongs in AGENTS.md"
            )
        elif len(body) > MAX_POINTER_LINES:
            errors.append(
                f"3. CLAUDE.md: {len(body)} non-blank lines exceeds the pointer budget "
                f"of {MAX_POINTER_LINES} — content belongs in AGENTS.md"
            )

    # 4, 5, 6 — once per rule ----------------------------------------------
    for rule in RULES:
        errors.extend(check_rule(root, agents_text, rule))

    # 7, 8, 9 — notion-api-only only, and only when it's installed -----------
    errors.extend(check_notion_scripts(root))

    return errors


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv[1:])

    root = Path(args.project_root).resolve()
    if not root.is_dir():
        print(f"--project-root is not a directory: {root}", file=sys.stderr)
        return 2

    try:
        errors = check(root)
    except OSError as exc:
        print(f"read failed: {exc}", file=sys.stderr)
        return 2

    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1
    if not args.quiet:
        print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
