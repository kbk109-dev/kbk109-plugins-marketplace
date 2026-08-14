#!/usr/bin/env python3
"""Deterministic installer for the AGENTS.md-as-SSoT layout.

Moves the project's CLAUDE.md body into AGENTS.md, rewrites CLAUDE.md as a
pointer, renders each selected rule into BOTH .claude/rules/ and
.cursor/rules/, and inserts one managed marker block per rule into AGENTS.md.

Why a script instead of letting the model write these files: the .mdc mirror
must stay byte-identical to the .md rule, and the marker block must be
byte-stable across re-runs. A model rewriting them by hand drifts on
whitespace alone, which is exactly the failure this plugin exists to prevent.

Usage:
    install_agent_rules.py [--project-root PATH]
                           [--main-branch NAME]
                           [--pre-commit-check CMD]
                           [--codegraph-rule {auto,on,off}]
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
    - AGENTS.md exists, non-blank, and carries exactly one marker block per
      installed rule
    - .cursor/rules/<rule>.mdc body == .claude/rules/<rule>.md byte-for-byte
      (modulo the .mdc frontmatter and surrounding blank lines)
    - Re-running replaces each marker block instead of appending a second one
    - A rule that is not selected is left ALONE, not deleted
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# The rule table. `required` rules install everywhere; optional ones install only
# when their condition holds (see select_rules), because a rule for a tool the
# project does not have is noise the agent would follow anyway.
#
# The names and `required` flags are duplicated in
# check-agent-rules/scripts/check_agent_rules.py — the checker locates each block
# by exact string match, so a rule added here must be added there too. The two
# skills stay separate scripts on purpose: importing across skill directories
# would couple them to each other's layout.
RULES = (
    {
        "name": "git-branch-workflow",
        "required": True,
        "heading": "Git 브랜치 워크플로",
        "pointer": "브랜치·커밋·머지 절차는",
        "mdc_description": "{main} 직접 작업 금지, dev 에서 분기, 커밋 승인, dev 로만 머지",
    },
    {
        "name": "codegraph-search",
        "required": False,  # only where a .codegraph/ index exists
        "heading": "코드 검색",
        "pointer": "코드 검색 절차는",
        "mdc_description": "코드 검색은 codegraph 우선, 호출 불가 시 경고 후 grep 폴백",
    },
)


def claude_rel(name: str) -> str:
    return f".claude/rules/{name}.md"


def cursor_rel(name: str) -> str:
    return f".cursor/rules/{name}.mdc"


def mark_begin(name: str) -> str:
    return f"<!-- >>> agent-rules: {name} >>> -->"


def mark_end(name: str) -> str:
    return f"<!-- <<< agent-rules: {name} <<< -->"


def marker_block(rule: dict) -> str:
    name = rule["name"]
    return f"""{mark_begin(name)}
## {rule["heading"]}

{rule["pointer"]} `{claude_rel(name)}` 를 따른다.
Cursor 는 `{cursor_rel(name)}` 로 같은 내용을 받는다.

이 블록은 `/project-conventions:init-agent-rules` 가 관리한다. 직접 고치지 말 것 —
재실행하면 덮어쓴다. 규칙 본문을 바꾸려면 `{claude_rel(name)}` 를 고치고
`/project-conventions:check-agent-rules` 로 사본과의 일치를 확인한다.
{mark_end(name)}"""


CLAUDE_POINTER = """# CLAUDE.md

이 프로젝트의 에이전트 지시는 `AGENTS.md` 에 있다 — Claude 와 Cursor 가 공유하는 단일 소스다.

**이 파일에는 내용을 쓰지 않는다.** 여기에 쓰면 Cursor 가 그것을 못 읽어 두 도구의 지시가
갈라진다. 지시를 추가하려면 `AGENTS.md` 를 고친다.

@AGENTS.md
"""

MDC_FRONTMATTER = """---
description: {description}
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


def mdc_frontmatter(rule: dict, main_branch: str) -> str:
    """Frontmatter for a rule's .mdc mirror.

    `.format(main=…)` is harmless for descriptions that carry no {main} slot.
    """
    return MDC_FRONTMATTER.format(
        description=rule["mdc_description"].format(main=main_branch)
    )


def select_rules(root: Path, codegraph_mode: str) -> tuple[list[dict], list[str]]:
    """Return (rules to install, notes explaining anything skipped).

    Optional rules are decided from the project, not from the user: a rule that
    tells the agent to search with codegraph is only useful where an index
    exists. Skipping NEVER deletes an already-installed rule — see main().
    """
    selected: list[dict] = []
    notes: list[str] = []
    for rule in RULES:
        if rule["required"]:
            selected.append(rule)
            continue
        if rule["name"] == "codegraph-search":
            if codegraph_mode == "on":
                selected.append(rule)
            elif codegraph_mode == "off":
                notes.append("--codegraph-rule off — codegraph-search 규칙 건너뜀")
            elif (root / ".codegraph").is_dir():
                selected.append(rule)
            else:
                notes.append(
                    ".codegraph/ 없음 — codegraph-search 규칙 건너뜀 "
                    "(색인을 만든 뒤 재실행하거나 --codegraph-rule on)"
                )
    return selected, notes


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
    """Re-mirror every .cursor/rules/<rule>.mdc from its CURRENT .claude/rules/<rule>.md.

    A full install renders each rule from the plugin's template, so any
    project-specific edit to a .md would be overwritten. This mode exists so
    the .md can be edited and the mirror brought back in line without losing
    that edit — which is what the checker actually asserts (it compares .mdc to
    .md, not to the template).

    Only rules that are actually installed are mirrored; a project that never
    took the optional rule is not a failure.
    """
    pending: list[tuple[dict, str]] = []
    for rule in RULES:
        md = root / claude_rel(rule["name"])
        if md.is_file():
            pending.append((rule, md.read_text(encoding="utf-8")))

    if not pending:
        print(
            "no .claude/rules/*.md found — nothing to mirror.",
            file=sys.stderr,
        )
        return 3

    for rule, body in pending:
        name = rule["name"]
        frontmatter = existing_mdc_frontmatter(root / cursor_rel(name))
        if frontmatter is None:
            frontmatter = mdc_frontmatter(rule, main_branch)
        print(f"  - {cursor_rel(name)} ← {claude_rel(name)} 본문으로 재생성")
        if dry_run:
            continue
        try:
            out = root / cursor_rel(name)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(frontmatter + "\n" + body, encoding="utf-8")
        except OSError as exc:
            print(f"write failed: {exc}", file=sys.stderr)
            return 1
    if not dry_run:
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


def upsert_marker_block(text: str, rule: dict) -> str:
    """Insert this rule's marker block, or replace it in place if already present."""
    name = rule["name"]
    begin, end_mark = mark_begin(name), mark_end(name)
    block = marker_block(rule)

    start = text.find(begin)
    if start == -1:
        body = text.rstrip("\n")
        return f"{body}\n\n{block}\n"
    end = text.find(end_mark, start)
    if end == -1:
        # Opening marker without a closing one — truncate from the opener and
        # re-append. Leaving a half block would make the checker fail forever.
        return text[:start].rstrip("\n") + f"\n\n{block}\n"
    end += len(end_mark)
    return text[:start] + block + text[end:]


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--main-branch", default=None)
    ap.add_argument("--pre-commit-check", default="")
    ap.add_argument(
        "--codegraph-rule",
        choices=["auto", "on", "off"],
        default="auto",
        help="auto: install only when .codegraph/ exists (default); on/off: force",
    )
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

    templates_dir = Path(__file__).resolve().parent.parent / "templates"
    selected, notes = select_rules(root, args.codegraph_rule)
    for rule in selected:
        if not (templates_dir / f"{rule['name']}.md").is_file():
            print(
                f"template missing: {templates_dir / (rule['name'] + '.md')}",
                file=sys.stderr,
            )
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

    # ---- render every selected rule ---------------------------------------
    # Rules that are NOT selected are left untouched: an existing rule file and
    # its marker block survive a re-run made from a machine where the condition
    # no longer holds. Removing a rule is a manual, deliberate act.
    writes: list[tuple[str, str]] = []
    for rule in selected:
        name = rule["name"]
        template = (templates_dir / f"{name}.md").read_text(encoding="utf-8")
        rule_body = render(template, main_branch, args.pre_commit_check)
        writes.append((claude_rel(name), rule_body))
        writes.append((cursor_rel(name), mdc_frontmatter(rule, main_branch) + "\n" + rule_body))

        agents_text = upsert_marker_block(agents_text, rule)
        steps.append(f"AGENTS.md 마커 블록 삽입/교체 ({name})")
        # Only rules that actually carry the token get the branch name reported —
        # the skill asks the user to confirm this value, so printing it for a
        # rule it does not affect would invite a pointless confirmation.
        detail = f" (main branch: {main_branch})" if "{{MAIN_BRANCH}}" in template else ""
        steps.append(f"{claude_rel(name)} 생성{detail}")
        steps.append(f"{cursor_rel(name)} 생성 (동일 본문 + 프론트매터)")

    steps.append("CLAUDE.md → 포인터로 재작성")
    steps.extend(notes)

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

        for rel, content in writes:
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
