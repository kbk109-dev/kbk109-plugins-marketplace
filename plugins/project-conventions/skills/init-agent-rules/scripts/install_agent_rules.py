#!/usr/bin/env python3
"""Deterministic installer for the AGENTS.md-as-SSoT layout.

Moves the project's CLAUDE.md body into AGENTS.md, rewrites CLAUDE.md as a
pointer, renders the git branch workflow rule into BOTH .claude/rules/ and
.cursor/rules/, and inserts a managed marker block into AGENTS.md.

Why a script instead of letting the model write these files: the .mdc mirror
must stay byte-identical to the .md rule, and the marker block must be
byte-stable across re-runs. A model rewriting them by hand drifts on
whitespace alone, which is exactly the failure this plugin exists to prevent.

Usage:
    install_agent_rules.py [--project-root PATH]
                           [--main-branch NAME]
                           [--pre-commit-check CMD]
                           [--on-existing-agents {abort,append-claude,keep-agents}]
                           [--force] [--dry-run]
    install_agent_rules.py --sync-mdc [--project-root PATH]

--sync-mdc re-mirrors the .mdc from the CURRENT .md instead of the template,
so a project-specific edit to the rule survives. Use it after editing
.claude/rules/<rule>.md; a full install would overwrite that edit.

Exit codes:
    0  installed (or --dry-run plan printed)
    1  an operation failed
    2  usage / IO error
    3  gate failure — caller must stop and ask the user
         * CLAUDE.md missing or blank
         * AGENTS.md already exists and --on-existing-agents=abort (default)
         * keep-agents would discard uncommitted CLAUDE.md content
         * --sync-mdc with no .claude/rules/<rule>.md to mirror

Invariants established:
    - CLAUDE.md contains the pointer and no project body
    - AGENTS.md exists, non-blank, and carries exactly one marker block
    - .cursor/rules/<rule>.mdc body == .claude/rules/<rule>.md byte-for-byte
      (modulo the .mdc frontmatter and surrounding blank lines)
    - Re-running replaces the marker block instead of appending a second one
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

RULE_NAME = "git-branch-workflow"
CLAUDE_RULE_REL = f".claude/rules/{RULE_NAME}.md"
CURSOR_RULE_REL = f".cursor/rules/{RULE_NAME}.mdc"

# These two markers are duplicated in check-agent-rules/scripts/check_agent_rules.py.
# If you change them here, change them there — the checker locates the block by
# exact string match.
MARK_BEGIN = f"<!-- >>> agent-rules: {RULE_NAME} >>> -->"
MARK_END = f"<!-- <<< agent-rules: {RULE_NAME} <<< -->"

MARKER_BLOCK = f"""{MARK_BEGIN}
## Git 브랜치 워크플로

브랜치·커밋·머지 절차는 `{CLAUDE_RULE_REL}` 를 따른다.
Cursor 는 `{CURSOR_RULE_REL}` 로 같은 내용을 받는다.

이 블록은 `/project-conventions:init-agent-rules` 가 관리한다. 직접 고치지 말 것 —
재실행하면 덮어쓴다. 규칙 본문을 바꾸려면 `{CLAUDE_RULE_REL}` 를 고치고
`/project-conventions:check-agent-rules` 로 사본과의 일치를 확인한다.
{MARK_END}"""

CLAUDE_POINTER = """# CLAUDE.md

이 프로젝트의 에이전트 지시는 `AGENTS.md` 에 있다 — Claude 와 Cursor 가 공유하는 단일 소스다.

**이 파일에는 내용을 쓰지 않는다.** 여기에 쓰면 Cursor 가 그것을 못 읽어 두 도구의 지시가
갈라진다. 지시를 추가하려면 `AGENTS.md` 를 고친다.

@AGENTS.md
"""

MDC_FRONTMATTER = """---
description: {main} 직접 작업 금지, 브랜치 네이밍, 커밋 승인, --no-ff 머지
alwaysApply: true
---
"""


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def git(root: Path, *args: str) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=False
        )
    except (OSError, ValueError):
        return 1, ""
    return p.returncode, p.stdout.strip()


def in_git_repo(root: Path) -> bool:
    code, out = git(root, "rev-parse", "--is-inside-work-tree")
    return code == 0 and out == "true"


def detect_main_branch(root: Path) -> str:
    """origin/HEAD → local main/master → sole local branch → 'main'.

    The sole-branch rule catches repos whose trunk is named something else
    ('develop', 'trunk'). It deliberately does NOT fall back to the current
    branch when several exist: the caller is often sitting on a feature branch,
    and baking that name into the rule would be worse than guessing 'main'.
    The skill surfaces this value for confirmation before writing.
    """
    code, out = git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if code == 0 and out.startswith("origin/"):
        return out[len("origin/"):]
    for name in ("main", "master"):
        code, _ = git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}")
        if code == 0:
            return name
    code, out = git(root, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    branches = [b for b in out.splitlines() if b.strip()]
    if code == 0 and len(branches) == 1:
        return branches[0]
    return "main"


def is_committed(root: Path, rel: str) -> bool:
    """True when the path is tracked and has no staged/unstaged changes."""
    code, out = git(root, "ls-files", "--error-unmatch", rel)
    if code != 0:
        return False
    code, out = git(root, "status", "--porcelain", "--", rel)
    return code == 0 and out == ""


def render(template: str, main_branch: str, pre_commit_check: str) -> str:
    """Substitute placeholders; drop any line whose placeholder stayed empty.

    Dropping the whole line (rather than leaving `커밋 전 반드시: ` dangling)
    is what lets one template serve projects that have no validation command.
    """
    values = {"{{MAIN_BRANCH}}": main_branch, "{{PRE_COMMIT_CHECK}}": pre_commit_check}
    out_lines: list[str] = []
    for line in template.splitlines():
        drop = False
        for token, value in values.items():
            if token in line:
                if not value:
                    drop = True
                    break
                line = line.replace(token, value)
        if not drop:
            out_lines.append(line)
    return "\n".join(out_lines).rstrip("\n") + "\n"


def existing_mdc_frontmatter(path: Path) -> str | None:
    """Return the leading '---...---' block of an .mdc file, if it has one."""
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    lines = text.splitlines(keepends=True)
    for i in range(1, len(lines)):
        if lines[i].rstrip("\n") == "---":
            return "".join(lines[: i + 1])
    return None


def sync_mdc(root: Path, main_branch: str, dry_run: bool) -> int:
    """Re-mirror .cursor/rules/<rule>.mdc from the CURRENT .claude/rules/<rule>.md.

    A full install renders the rule from the plugin's template, so any
    project-specific edit to the .md would be overwritten. This mode exists so
    the .md can be edited and the mirror brought back in line without losing
    that edit — which is what the checker actually asserts (it compares .mdc to
    .md, not to the template).
    """
    md = root / CLAUDE_RULE_REL
    if not md.is_file():
        print(f"{CLAUDE_RULE_REL} not found — nothing to mirror.", file=sys.stderr)
        return 3
    body = md.read_text(encoding="utf-8")
    frontmatter = existing_mdc_frontmatter(root / CURSOR_RULE_REL)
    if frontmatter is None:
        frontmatter = MDC_FRONTMATTER.format(main=main_branch)

    print(f"  - {CURSOR_RULE_REL} ← {CLAUDE_RULE_REL} 본문으로 재생성")
    if dry_run:
        return 0
    try:
        out = root / CURSOR_RULE_REL
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(frontmatter + "\n" + body, encoding="utf-8")
    except OSError as exc:
        print(f"write failed: {exc}", file=sys.stderr)
        return 1
    print("OK")
    return 0


def retitle(text: str) -> str:
    """Rewrite a literal `# CLAUDE.md` H1 to `# AGENTS.md` after migration.

    Only the literal filename heading is touched — a project-named H1
    ("# PayFlow") is the author's title and stays.
    """
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        if line.strip() in ("# CLAUDE.md", "# CLAUDE.MD", "# claude.md"):
            lines[i] = line.replace(line.strip(), "# AGENTS.md")
        break
    return "".join(lines)


def upsert_marker_block(text: str) -> str:
    """Insert MARKER_BLOCK, or replace it in place if already present."""
    start = text.find(MARK_BEGIN)
    if start == -1:
        body = text.rstrip("\n")
        return f"{body}\n\n{MARKER_BLOCK}\n"
    end = text.find(MARK_END, start)
    if end == -1:
        # Opening marker without a closing one — truncate from the opener and
        # re-append. Leaving a half block would make the checker fail forever.
        return text[:start].rstrip("\n") + f"\n\n{MARKER_BLOCK}\n"
    end += len(MARK_END)
    return text[:start] + MARKER_BLOCK + text[end:]


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--main-branch", default=None)
    ap.add_argument("--pre-commit-check", default="")
    ap.add_argument(
        "--on-existing-agents",
        choices=["abort", "append-claude", "keep-agents"],
        default="abort",
    )
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--sync-mdc",
        action="store_true",
        help="only re-mirror the .mdc from the current .md; touch nothing else",
    )
    args = ap.parse_args(argv[1:])

    root = Path(args.project_root).resolve()
    if not root.is_dir():
        print(f"--project-root is not a directory: {root}", file=sys.stderr)
        return 2

    if args.sync_mdc:
        branch = args.main_branch or (
            detect_main_branch(root) if in_git_repo(root) else "main"
        )
        return sync_mdc(root, branch, args.dry_run)

    template_path = Path(__file__).resolve().parent.parent / "templates" / f"{RULE_NAME}.md"
    if not template_path.is_file():
        print(f"template missing: {template_path}", file=sys.stderr)
        return 2

    claude_md = root / "CLAUDE.md"
    agents_md = root / "AGENTS.md"

    # ---- gate 1: CLAUDE.md must exist and carry something -----------------
    if not claude_md.is_file():
        print(
            "CLAUDE.md not found — this skill migrates an existing CLAUDE.md and "
            "will not invent one. Run /init first.",
            file=sys.stderr,
        )
        return 3
    claude_text = claude_md.read_text(encoding="utf-8")
    if not claude_text.strip():
        print("CLAUDE.md is blank — nothing to migrate.", file=sys.stderr)
        return 3

    already_pointer = "@AGENTS.md" in claude_text and agents_md.is_file()

    # ---- gate 2: pre-existing AGENTS.md -----------------------------------
    mode = args.on_existing_agents
    if agents_md.is_file() and not already_pointer:
        if mode == "abort":
            print(
                "AGENTS.md already exists and differs from CLAUDE.md. Stopping so the "
                "user can choose: append-claude / keep-agents / abort.",
                file=sys.stderr,
            )
            return 3
        if mode == "keep-agents" and not args.force:
            if not in_git_repo(root) or not is_committed(root, "CLAUDE.md"):
                print(
                    "keep-agents would discard the CLAUDE.md body, but CLAUDE.md is not "
                    "committed — it would be unrecoverable. Commit it first or pass --force.",
                    file=sys.stderr,
                )
                return 3

    steps: list[str] = []
    use_git = in_git_repo(root)
    main_branch = args.main_branch or (detect_main_branch(root) if use_git else "main")

    # ---- build the new AGENTS.md content ----------------------------------
    if already_pointer:
        agents_text = agents_md.read_text(encoding="utf-8")
        steps.append("AGENTS.md 이미 존재 (재실행) — 본문 유지")
    elif not agents_md.is_file():
        agents_text = retitle(claude_text)
        steps.append("CLAUDE.md 본문 → AGENTS.md 이관")
    elif mode == "append-claude":
        existing = agents_md.read_text(encoding="utf-8").rstrip("\n")
        agents_text = (
            f"{existing}\n\n"
            "<!-- 아래는 CLAUDE.md 에서 이전된 내용이다. 위 내용과 중복·모순되는 부분을 "
            "정리할 것. -->\n\n"
            f"{claude_text.lstrip()}"
        )
        steps.append("기존 AGENTS.md 뒤에 CLAUDE.md 본문 이어붙임")
    else:  # keep-agents
        agents_text = agents_md.read_text(encoding="utf-8")
        steps.append("기존 AGENTS.md 유지, CLAUDE.md 본문 폐기")

    agents_text = upsert_marker_block(agents_text)
    steps.append("AGENTS.md 마커 블록 삽입/교체")

    rule_body = render(
        template_path.read_text(encoding="utf-8"), main_branch, args.pre_commit_check
    )
    mdc_text = MDC_FRONTMATTER.format(main=main_branch) + "\n" + rule_body
    steps.append(f"{CLAUDE_RULE_REL} 생성 (main branch: {main_branch})")
    steps.append(f"{CURSOR_RULE_REL} 생성 (동일 본문 + 프론트매터)")
    steps.append("CLAUDE.md → 포인터로 재작성")

    if args.dry_run:
        for s in steps:
            print(f"  - {s}")
        return 0

    # ---- write ------------------------------------------------------------
    try:
        # git mv preserves rename history when AGENTS.md is genuinely new.
        if use_git and not agents_md.exists() and is_committed(root, "CLAUDE.md"):
            code, _ = git(root, "mv", "CLAUDE.md", "AGENTS.md")
            if code != 0:
                shutil.copyfile(claude_md, agents_md)
        agents_md.write_text(agents_text, encoding="utf-8")

        for rel, content in (
            (CLAUDE_RULE_REL, rule_body),
            (CURSOR_RULE_REL, mdc_text),
        ):
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        claude_md.write_text(CLAUDE_POINTER, encoding="utf-8")
    except OSError as exc:
        print(f"write failed: {exc}", file=sys.stderr)
        return 1

    for s in steps:
        print(f"  - {s}")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
