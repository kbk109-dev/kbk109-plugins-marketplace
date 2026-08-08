#!/usr/bin/env python3
"""PreToolUse hook: carry the codegraph search rule into every subagent.

Why this exists. The codegraph search rule reaches the main session two ways —
`.claude/rules/codegraph-search.md` loaded as a project instruction, and
codegraph's own `codegraph prompt-hook` on UserPromptSubmit. Neither reaches a
subagent: a subagent is not started by a user prompt, so UserPromptSubmit can
never fire for it, and inheritance of project instructions into a subagent is
not something the rule can rely on. So subagents reach for grep first.

This hook closes that hole at the only point that is guaranteed to run: the
Agent/Task tool call itself, in the parent's process. It rewrites the subagent's
prompt via `updatedInput` so the directive is physically present in the text the
subagent is started with. No cooperation from any model is required.

Reads the PreToolUse payload on stdin:
    {session_id, cwd, hook_event_name, tool_name, tool_input}

Prints a PreToolUse hookSpecificOutput on stdout when it injects, and NOTHING
otherwise. Always exits 0.

FAIL-OPEN IS THE WHOLE CONTRACT. This hook is shipped by a plugin, so it fires
in every project the plugin is enabled for — including projects that have no
codegraph index and no interest in one. A guard that can block subagent dispatch
is worse than no guard, so every branch that is not "inject" is "stay silent",
and any unexpected exception is swallowed.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# The subagent dispatch tool. Named `Agent` in current Claude Code; `Task` in
# older builds. Both are listed because hooks.json matches on the name the model
# sees, and a rename must not silently turn this hook off.
DISPATCH_TOOLS = {"Agent", "Task"}

# Appended verbatim to the subagent's prompt.
#
# It repeats things the rule file already says because a subagent may have none
# of that context — this block has to stand on its own. The attribution line is
# not decoration: without it neither the subagent nor anyone reading the
# transcript later can tell why the prompt contains a paragraph its author never
# wrote.
DIRECTIVE = """

---
이 프로젝트는 codegraph 색인(`.codegraph/`)을 갖고 있다. 코드 검색 규칙:

- 심볼의 위치·구조·호출 관계를 찾을 때는 grep·find·파일 열람보다 codegraph 를 먼저 쓴다.
  - MCP: `codegraph_explore` — 도구 목록에 없고 deferred 라면
    `ToolSearch("select:mcp__codegraph__codegraph_explore")` 로 먼저 로드한다
  - 셸: `codegraph explore "<심볼명 또는 질문>"`
- 문자열 리터럴·설정값·파일명 패턴 검색은 grep/Glob 이 맞다. 그건 그대로 쓴다.
- codegraph 를 호출할 수 없으면 조용히 grep 으로 넘어가지 말고 한 줄 남긴 뒤 진행한다:
  ⚠️ codegraph 를 호출할 수 없어 grep/Glob 으로 검색합니다 — 원인: {색인 없음 | MCP 미연결 | 명령 없음}
- 색인 생성(`codegraph init`)은 제안만 하고 승인 없이 실행하지 않는다.

(이 블록은 project-conventions 플러그인의 PreToolUse 훅이 자동으로 덧붙였다.)"""


def has_codegraph_index(cwd: str) -> bool:
    """True when a .codegraph/ index sits at cwd or an ancestor inside the project.

    Walking up matters because the subagent may be dispatched from a package
    directory inside a monorepo whose index lives at the repo root — the same
    resolution the codegraph MCP server does.

    The walk is BOUNDED, which an unbounded resolver would not be. A stray
    `~/.codegraph` — trivially created by running `codegraph init` once in the
    home directory — is an ancestor of every project under it, so an unbounded
    walk would report "indexed" for all of them and this hook would inject into
    every subagent everywhere. Two stops prevent that:

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


def build_output(tool_input: dict, prompt: str) -> dict:
    # Every original key is preserved: updatedInput must satisfy the tool's full
    # input schema, so returning only `prompt` would fail validation and drop
    # subagent_type, description, model and the rest.
    updated = dict(tool_input)
    updated["prompt"] = prompt + DIRECTIVE
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": updated,
        }
    }


def run() -> None:
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    if not raw.strip():
        return
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return

    if payload.get("tool_name") not in DISPATCH_TOOLS:
        return

    # This one check is why a plugin-level hook is safe to ship globally: in a
    # project without an index the hook does nothing and says nothing.
    if not has_codegraph_index(payload.get("cwd") or os.getcwd()):
        return

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return

    # Idempotent, and doubles as the caller's opt-out: a prompt that already
    # talks about codegraph is left exactly as written. Without this, a retried
    # or hook-chained dispatch would stack the block twice.
    if "codegraph" in prompt.lower():
        return

    # ensure_ascii keeps the payload pure ASCII, so a non-UTF-8 stdout on the
    # host cannot corrupt the Korean text on its way back to the harness.
    sys.stdout.write(json.dumps(build_output(tool_input, prompt)))


def main() -> int:
    try:
        run()
    except Exception:  # noqa: BLE001 — see the fail-open note in the docstring
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
