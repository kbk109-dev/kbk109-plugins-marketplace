"""Shared by every hook in this directory: does this project have a codegraph index?

Not a hook itself — no stdin, no stdout, no exit code. It exists because two
hooks need the SAME answer to that question, and the answer is a bounded
directory walk whose bounds are the subtle part. A copy in each hook is how the
`~/.codegraph` false positive comes back (see the walk's docstring); one
definition is how it stays fixed.

Hooks import it as a plain module because they are launched as
`python3 "<abs path>/hooks/<hook>.py"`, which puts this directory on sys.path[0].
"""
from __future__ import annotations

from pathlib import Path


def has_codegraph_index(cwd: str) -> bool:
    """True when a .codegraph/ index sits at cwd or an ancestor inside the project.

    Walking up matters because a hook may fire from a package directory inside a
    monorepo whose index lives at the repo root — the same resolution the
    codegraph MCP server does.

    The walk is BOUNDED, which an unbounded resolver would not be. A stray
    `~/.codegraph` — trivially created by running `codegraph init` once in the
    home directory — is an ancestor of every project under it, so an unbounded
    walk would report "indexed" for all of them and these hooks would fire in
    every unrelated project. Two stops prevent that:

      * the git repo root (checked, then stop) — the project boundary
      * $HOME and the filesystem root (never inspected)

    Cost of the bound: a git subrepo whose index lives in the outer repo is
    missed. That is a silent no-op, whereas the false positive is noise in
    every unrelated project.
    """
    try:
        start = Path(cwd).resolve()
        home = Path.home().resolve()
    except (OSError, ValueError, RuntimeError):
        return False
    for directory in (start, *start.parents):
        if directory == home or directory == directory.parent:
            return False
        if (directory / ".codegraph").is_dir():
            return True
        if (directory / ".git").exists():
            return False
    return False
