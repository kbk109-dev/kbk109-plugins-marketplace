#!/usr/bin/env python3
"""Deterministic fact scanner for refresh-agent-rules.

Collects what the project ACTUALLY is — commands, package manager, toolchain,
directory shape — plus what git says changed since the last refresh, and emits
it as one JSON object. The model's job is then only to compare those facts
against AGENTS.md prose and decide; it never has to gather them, so two runs on
an unchanged repo produce the same input and can reach the same "no change"
verdict.

Why a script: a model re-deriving "the test command" by grepping picks a
different source each run, and its line count of a file it is about to rewrite
is always wrong. Both are decidable, so they are decided here.

Usage:
    scan_project_facts.py [--project-root PATH]
    scan_project_facts.py --record --result {updated,no-change} [--project-root PATH]

Default is READ-ONLY. --record is the only mode that writes, and it writes one
file: .claude/agent-rules.state.json. Record only AFTER the user approved and
the edits landed — the baseline it stores is what the next run diffs against.

Exit codes:
    0  scan printed (or state recorded)
    2  usage / IO error
    3  gate failure — not the AGENTS.md-as-SSoT layout; caller must stop and
       point the user at /project-conventions:init-agent-rules

Scanning is best-effort and language-agnostic: a manifest that is absent is
skipped, and one that fails to parse drops only its own entry. A scanner that
dies on an unfamiliar repo would make the skill unusable exactly where it is
most needed.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

STATE_REL = ".claude/agent-rules.state.json"
STATE_SCHEMA = 1

# Same target as init-agent-rules/scripts/install_agent_rules.py. Duplicated
# rather than imported for the same reason the RULES table is: the skills are
# installed as independent directories. A goal, not a limit — these files are
# loaded in full however long they get.
AGENTS_LINE_BUDGET = 200

# Directory names that say nothing about how the project is organised.
TREE_SKIP = {
    ".git", "node_modules", "dist", "build", "out", "target", "vendor",
    "__pycache__", ".venv", "venv", ".next", ".nuxt", ".expo", ".gradle",
    ".idea", ".vscode", "coverage", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}

# lockfile -> package manager. A repo may legitimately match several.
LOCKFILES = {
    "pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn", "bun.lockb": "bun",
    "bun.lock": "bun", "package-lock.json": "npm", "poetry.lock": "poetry",
    "uv.lock": "uv", "Pipfile.lock": "pipenv", "Cargo.lock": "cargo",
    "go.sum": "go", "composer.lock": "composer", "Gemfile.lock": "bundler",
    "pubspec.lock": "pub", "mix.lock": "mix",
}

# Config files worth reporting merely by existing.
TOOLCHAIN_FILES = (
    "tsconfig.json", ".editorconfig", ".nvmrc", ".python-version",
    ".tool-versions", "Dockerfile", "docker-compose.yml", "compose.yaml",
    ".pre-commit-config.yaml", "ruff.toml", ".flake8", "biome.json",
)
TOOLCHAIN_GLOBS = (".eslintrc*", "eslint.config.*", ".prettierrc*", "prettier.config.*")


def run_git(root: Path, *args: str) -> tuple[int, str]:
    try:
        p = subprocess.run(["git", *args], cwd=root, capture_output=True,
                           text=True, check=False, timeout=20)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 1, ""
    return p.returncode, p.stdout.strip()


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# --------------------------------------------------------------------------
# facts
# --------------------------------------------------------------------------

def scan_commands(root: Path) -> list[dict]:
    """Every runnable command the project declares, tagged with its source.

    The source matters: when AGENTS.md and reality disagree the user needs to
    know which file to trust, and "package.json scripts.test" is checkable in a
    way that "the test command" is not.
    """
    out: list[dict] = []

    pkg = read_json(root / "package.json")
    if isinstance(pkg, dict) and isinstance(pkg.get("scripts"), dict):
        out.append({"source": "package.json scripts",
                    "commands": {k: str(v) for k, v in pkg["scripts"].items()}})

    for name in ("Makefile", "makefile", "GNUmakefile"):
        mk = root / name
        if mk.is_file():
            try:
                text = mk.read_text(encoding="utf-8", errors="replace")
            except OSError:
                break
            targets = [m.group(1) for m in
                       re.finditer(r"^([A-Za-z0-9][A-Za-z0-9_.-]*):(?!=)", text, re.M)]
            if targets:
                out.append({"source": name, "targets": sorted(set(targets))})
            break

    for name in ("justfile", "Justfile", ".justfile"):
        jf = root / name
        if jf.is_file():
            try:
                text = jf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                break
            recipes = [m.group(1) for m in
                       re.finditer(r"^([a-zA-Z0-9][a-zA-Z0-9_-]*)\s*(?:[a-zA-Z0-9_ =\"']*)?:",
                                   text, re.M)]
            if recipes:
                out.append({"source": name, "targets": sorted(set(recipes))})
            break

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        entry = {"source": "pyproject.toml"}
        try:
            import tomllib  # py3.11+
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            scripts = data.get("project", {}).get("scripts") or \
                data.get("tool", {}).get("poetry", {}).get("scripts") or {}
            if scripts:
                entry["commands"] = {k: str(v) for k, v in scripts.items()}
            tools = sorted(data.get("tool", {}).keys())
            if tools:
                entry["tools"] = tools
        except Exception:
            entry["note"] = "parse skipped"
        out.append(entry)

    composer = read_json(root / "composer.json")
    if isinstance(composer, dict) and isinstance(composer.get("scripts"), dict):
        out.append({"source": "composer.json scripts",
                    "commands": {k: str(v) for k, v in composer["scripts"].items()}})

    for name in ("deno.json", "deno.jsonc"):
        deno = read_json(root / name)
        if isinstance(deno, dict) and isinstance(deno.get("tasks"), dict):
            out.append({"source": f"{name} tasks",
                        "commands": {k: str(v) for k, v in deno["tasks"].items()}})
            break

    # Repos whose "commands" are loose shell scripts declare nothing at all —
    # this marketplace is one of them (bash scripts/validate-marketplace.sh).
    # Without this the scanner returns no commands for them and the skill has
    # nothing to compare the documented command against.
    for dirname in ("scripts", "bin", "tools"):
        d = root / dirname
        if not d.is_dir():
            continue
        found = sorted(
            f"{dirname}/{p.name}" for p in d.iterdir()
            if p.is_file() and (p.suffix in (".sh", ".bash", ".py", ".rb", ".js", ".ts")
                                or p.stat().st_mode & 0o111)
        )
        if found:
            out.append({"source": f"{dirname}/ directory", "files": found[:40]})

    # Ecosystems whose commands are conventional rather than declared. Naming
    # the manifest lets the model infer `cargo test` / `go test ./...` without
    # the scanner pretending to know the project's preferred invocation.
    for name in ("Cargo.toml", "go.mod", "build.gradle", "build.gradle.kts",
                 "pom.xml", "Gemfile", "pubspec.yaml", "mix.exs", "CMakeLists.txt"):
        if (root / name).is_file():
            out.append({"source": name, "conventional": True})

    return out


def scan_facts(root: Path) -> dict:
    managers = sorted({mgr for f, mgr in LOCKFILES.items() if (root / f).is_file()})

    toolchain = [f for f in TOOLCHAIN_FILES if (root / f).is_file()]
    for pattern in TOOLCHAIN_GLOBS:
        toolchain.extend(sorted(p.name for p in root.glob(pattern) if p.is_file()))

    tsconfig = read_json(root / "tsconfig.json")
    ts_strict = None
    if isinstance(tsconfig, dict):
        ts_strict = tsconfig.get("compilerOptions", {}).get("strict")

    ci = sorted(p.name for p in (root / ".github" / "workflows").glob("*.y*ml")) \
        if (root / ".github" / "workflows").is_dir() else []

    tree: list[str] = []
    try:
        for first in sorted(p for p in root.iterdir() if p.is_dir()):
            if first.name in TREE_SKIP or first.name.startswith("."):
                continue
            tree.append(f"{first.name}/")
            for second in sorted(p for p in first.iterdir() if p.is_dir()):
                if second.name in TREE_SKIP or second.name.startswith("."):
                    continue
                tree.append(f"{first.name}/{second.name}/")
    except OSError:
        pass

    return {
        "command_sources": scan_commands(root),
        "package_managers": managers,
        "toolchain_files": sorted(set(toolchain)),
        "typescript_strict": ts_strict,
        "ci_workflows": ci,
        "tree": tree[:120],
        "tree_truncated": len(tree) > 120,
    }


# --------------------------------------------------------------------------
# AGENTS.md
# --------------------------------------------------------------------------

MARK_OPEN = re.compile(r"^<!-- >>> agent-rules: (\S+) >>> -->\s*$")
MARK_CLOSE = re.compile(r"^<!-- <<< agent-rules: (\S+) <<< -->\s*$")


def scan_agents_md(root: Path) -> dict:
    """Line count against the budget, plus the line span of each marker block.

    The spans exist so the skill can EXCLUDE those lines from comparison rather
    than merely being told not to touch them — install_agent_rules.py owns that
    region and overwrites it on every re-run, so an edit there is silently lost.
    """
    path = root / "AGENTS.md"
    if not path.is_file():
        return {"exists": False}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {"exists": False}

    ranges: list[dict] = []
    open_at: tuple[int, str] | None = None
    for i, line in enumerate(lines, start=1):
        m = MARK_OPEN.match(line)
        if m:
            open_at = (i, m.group(1))
            continue
        m = MARK_CLOSE.match(line)
        if m and open_at and open_at[1] == m.group(1):
            ranges.append({"rule": m.group(1), "start": open_at[0], "end": i})
            open_at = None

    n = len(lines)
    return {
        "exists": True,
        "lines": n,
        "budget": AGENTS_LINE_BUDGET,
        "over_by": max(0, n - AGENTS_LINE_BUDGET + 1),
        "marker_ranges": ranges,
    }


def scan_structure(root: Path) -> dict:
    """Is this the AGENTS.md-as-SSoT layout? Refresh edits AGENTS.md, so a repo
    that never migrated has nothing for it to edit — that is init's job."""
    agents = root / "AGENTS.md"
    claude = root / "CLAUDE.md"
    reasons: list[str] = []
    if not agents.is_file():
        reasons.append("AGENTS.md not found")
    try:
        pointer = claude.is_file() and "@AGENTS.md" in claude.read_text(encoding="utf-8")
    except OSError:
        pointer = False
    if not pointer:
        reasons.append("CLAUDE.md missing or has no @AGENTS.md import")
    return {"ok": not reasons, "reasons": reasons}


# --------------------------------------------------------------------------
# state + git
# --------------------------------------------------------------------------

def read_state(root: Path) -> dict:
    data = read_json(root / STATE_REL)
    if not isinstance(data, dict):
        return {"exists": False}
    return {
        "exists": True,
        "schema": data.get("schema"),
        "baseline_commit": data.get("baseline_commit"),
        "last_refreshed": data.get("last_refreshed"),
        "last_result": data.get("last_result"),
    }


def scan_git(root: Path, baseline: str | None) -> dict:
    code, _ = run_git(root, "rev-parse", "--is-inside-work-tree")
    if code != 0:
        return {"is_repo": False}

    _, head = run_git(root, "rev-parse", "HEAD")
    _, dirty = run_git(root, "status", "--porcelain")
    info = {
        "is_repo": True,
        "head": head or None,
        "dirty": bool(dirty),
        "baseline_valid": False,
        "changed_files": None,
        "deleted_files": None,
        "renamed_files": None,
        "commits_since": None,
    }
    if not baseline:
        return info
    code, _ = run_git(root, "cat-file", "-e", f"{baseline}^{{commit}}")
    if code != 0:
        # Baseline rewritten or unreachable (rebase, shallow clone). Fall back
        # to a full comparison rather than reporting an empty diff, which would
        # read as "nothing changed" and skip a refresh that is actually due.
        return info

    info["baseline_valid"] = True
    _, count = run_git(root, "rev-list", "--count", f"{baseline}..HEAD")
    info["commits_since"] = int(count) if count.isdigit() else None

    code, out = run_git(root, "diff", "--name-status", f"{baseline}..HEAD")
    changed, deleted, renamed = [], [], []
    if code == 0:
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            status = parts[0]
            if status.startswith(("R", "C")) and len(parts) >= 3:
                # A move is reported as R, not D, so the OLD path would vanish
                # from the report entirely — and the old path is exactly what a
                # stale "handlers live in src/legacy/" line points at. Kept
                # separate from deletions because the right fix is updating the
                # path, not deleting the line.
                renamed.append({"from": parts[1], "to": parts[2]})
                changed.append(parts[2])
                continue
            (deleted if status.startswith("D") else changed).append(parts[-1])
    info["changed_files"] = changed[:200]
    info["deleted_files"] = deleted[:200]
    info["renamed_files"] = renamed[:200]
    info["files_truncated"] = max(len(changed), len(deleted), len(renamed)) > 200
    return info


def record_state(root: Path, head: str | None, result: str) -> int:
    path = root / STATE_REL
    payload = {
        "schema": STATE_SCHEMA,
        "baseline_commit": head,
        "last_refreshed": date.today().isoformat(),
        "last_result": result,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    except OSError as exc:
        print(f"write failed: {exc}", file=sys.stderr)
        return 2
    print(f"{STATE_REL} 기록: baseline={head or 'none'} result={result}")
    print("이 파일은 커밋 대상이다 — 팀원이 같은 기준점을 보게 하려는 것이다.")
    return 0


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--record", action="store_true",
                    help="write the state file; use only after edits are approved")
    ap.add_argument("--result", choices=["updated", "no-change"], default=None)
    args = ap.parse_args(argv[1:])

    root = Path(args.project_root).resolve()
    if not root.is_dir():
        print(f"--project-root is not a directory: {root}", file=sys.stderr)
        return 2
    if args.record and not args.result:
        print("--record requires --result {updated,no-change}", file=sys.stderr)
        return 2

    structure = scan_structure(root)
    if not structure["ok"]:
        print(
            "not the AGENTS.md-as-SSoT layout (" + "; ".join(structure["reasons"]) + "). "
            "refresh-agent-rules edits AGENTS.md and does not migrate — run "
            "/project-conventions:init-agent-rules first.",
            file=sys.stderr,
        )
        return 3

    state = read_state(root)
    git = scan_git(root, state.get("baseline_commit"))

    if args.record:
        return record_state(root, git.get("head"), args.result)

    print(json.dumps({
        "structure": structure,
        "state": state,
        "git": git,
        "facts": scan_facts(root),
        "agents_md": scan_agents_md(root),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
