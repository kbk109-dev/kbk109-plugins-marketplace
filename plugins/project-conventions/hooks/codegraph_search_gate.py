#!/usr/bin/env python3
"""PreToolUse hook: route symbol searches through codegraph instead of grep.

Why this exists. The codegraph search rule tells the model to reach for
codegraph before grep. It is a rule in a document, so the model follows it
sometimes. The sibling hook (codegraph_subagent_guard.py) carries the same rule
into subagent prompts, but that is still a *directive* — a subagent can ignore
it exactly the way the main session ignores the rule file.

This hook stops asking. A search whose pattern looks like a symbol is denied,
and the denial reason tells the model how to run codegraph instead. The model's
cooperation is not required.

Bash counts as a search tool. Blocking only the Grep/Glob tools leaves the hole
wide open — the harness itself tells the model to prefer `grep` through Bash in
some modes, so there Bash is not an evasion but the DEFAULT path. The cost is
real and deliberate: this hook now runs once per Bash call in every project the
plugin is enabled for, which is why the Bash branch bails on the cheapest
possible check before it parses anything.

Reads the PreToolUse payload on stdin:
    {session_id, agent_id?, cwd, hook_event_name, tool_name, tool_input}

Prints a PreToolUse hookSpecificOutput on stdout when it denies, and NOTHING
otherwise. Always exits 0.

THE DENIAL MUST BE RECOVERABLE. This hook is shipped by a plugin, so it fires in
every project the plugin is enabled for, and it takes away a tool the model
needs. What makes that safe is the escape hatch: the same (tool, pattern) is
denied at most once per agent, so repeating the identical call always gets
through. Every wrong guess this hook makes therefore costs exactly one retried
tool call — never a blocked task. Everything else is fail-open: any condition
that is not clearly "this is a symbol search in an indexed project" stays
silent, and unexpected exceptions are swallowed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path

from _codegraph_index import has_codegraph_index

# NOTE: there is deliberately no list of tool NAMES here. The names live in
# hooks.json's matcher and nowhere else. Keeping a second copy meant both had to
# be right for the hook to work, and a mismatch produced no error at all — the
# matcher would fire and this file would silently wave the call through. One of
# the two had to go, and the matcher is the one the harness actually consults.
# What this file dispatches on instead is the SHAPE of tool_input: a `command`
# string is a shell call, a `pattern` string is a search. See extract_pattern.

# Bash commands that search source. `find` is absent on purpose: searching by
# filename is what the rule document hands to Glob, not to codegraph.
SEARCH_BINARIES = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "ack-grep"}

# The fast exit. This runs on EVERY Bash call, so it has to be the cheapest
# thing that can rule the command out — anything heavier belongs after it.
HAS_BINARY = re.compile(r"\b(?:grep|rg|ag|ack)\b")

# `VAR=value` prefixes (`LC_ALL=C grep …`) sit in front of the real binary.
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Tokens that end one command and start another.
SEPARATORS = {"|", "||", "&&", ";", "&", "|&"}

# Flags whose value is a SEPARATE token that is not the pattern. Missing one
# here means reading its value as the pattern — which the symbol heuristic then
# almost always rejects, so the failure stays a silent no-op.
VALUE_FLAGS = {
    "-f", "--file", "-m", "--max-count", "-A", "--after-context",
    "-B", "--before-context", "-C", "--context", "-d", "--directories",
    "--include", "--exclude", "--exclude-dir", "-t", "--type",
    "-g", "--glob", "--color", "--colour", "--max-columns",
}

# Flags whose value IS the pattern.
PATTERN_FLAGS = {"-e", "--regexp"}

# What counts as "a symbol search". Deliberately narrow, because the two failure
# directions are not symmetric: missing a symbol search leaves today's behaviour
# untouched, while catching a text search interrupts a search the rule document
# itself calls correct ("문자열 리터럴·설정값·파일명 패턴 검색은 grep 이 맞다").
#
# IDENTIFIER drops anything a bare identifier cannot contain — regex
# metacharacters, spaces, quotes, dots, slashes — which also removes essentially
# every Glob pattern.
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{2,}$")
# COMPOUND is what separates `handleSubmit` from `error`. A single lowercase
# word is far more often prose being grepped for than a symbol; a camelCase
# boundary or an underscore is the cheap signal that someone named this thing.
COMPOUND = re.compile(r"[a-z][A-Z]|_")

# Bounds the state file. A pattern pushed out can be denied a second time, which
# costs one more retry — the same bounded price every other misfire costs.
MAX_REMEMBERED = 200

REASON = """이 프로젝트는 codegraph 색인(`.codegraph/`)을 갖고 있다. 심볼 검색은 grep 이 아니라 codegraph 로 한다.

- MCP: `codegraph_explore` — 도구 목록에 없고 deferred 라면
  `ToolSearch("select:mcp__codegraph__codegraph_explore")` 로 먼저 로드한다
- 셸: `codegraph explore "{pattern}"`

한 번의 호출로 관련 심볼의 원본과 그 사이 호출 경로까지 함께 온다. grep 이 따라가지 못하는 동적
디스패치 구간이 여기 포함되므로, "grep → 파일 열람 → 다시 grep" 반복이 한 번으로 줄어든다.

**codegraph 로 답이 나오지 않으면 이 검색을 그대로 다시 호출한다 — 같은 패턴의 재호출은 통과한다.**
문자열 리터럴·설정값을 찾던 것이었다면 그렇게 넘어가면 된다.

(이 차단은 project-conventions 플러그인의 PreToolUse 훅이 걸었다.)"""


def is_symbol_shaped(pattern: str) -> bool:
    return bool(IDENTIFIER.match(pattern) and COMPOUND.search(pattern))


def _segments(tokens: list):
    """Split a token list into (segment, downstream_of_pipe) pairs.

    The pipe flag is the whole point. `ps aux | grep nodeServer` filters another
    command's stdout — it never touches the source tree, and blocking it would
    be pure noise. Segments after `&&`/`;` ARE independent commands, so a grep
    there is a real file search and stays in scope.
    """
    segment: list = []
    piped = False
    for token in tokens:
        if token in SEPARATORS:
            if segment:
                yield segment, piped
            piped = token in ("|", "|&")
            segment = []
        else:
            segment.append(token)
    if segment:
        yield segment, piped


def _pattern_from_segment(tokens: list):
    """The search pattern this segment looks for, or None if it is not a search.

    Only the FIRST token is ever treated as the binary. That restraint is what
    keeps `echo "run grep later"` and command substitutions from being read as
    searches — their grep is never in leading position.
    """
    i = 0
    while i < len(tokens) and ENV_ASSIGN.match(tokens[i]):
        i += 1
    if i >= len(tokens):
        return None

    binary = os.path.basename(tokens[i])
    if binary == "git":
        if i + 1 >= len(tokens) or tokens[i + 1] != "grep":
            return None
        i += 2
    elif binary in SEARCH_BINARIES:
        i += 1
    else:
        return None

    while i < len(tokens):
        token = tokens[i]
        if token in PATTERN_FLAGS or token == "--":
            return tokens[i + 1] if i + 1 < len(tokens) else None
        if token.startswith("--regexp="):
            return token.split("=", 1)[1]
        if token in VALUE_FLAGS:
            i += 2
            continue
        if token.startswith("-") and token != "-":
            i += 1  # a flag, including bundled short forms like -rn and -A3
            continue
        return token
    return None


def pattern_from_command(command: str):
    """The symbol a shell command searches for, or None.

    Every branch that is not certain returns None. A missed search leaves
    today's behaviour untouched; a wrong hit interrupts a shell command that had
    nothing to do with searching, which is the strictly worse failure.
    """
    if not HAS_BINARY.search(command):
        return None
    # Heredocs are the one construct that reliably fools this: shlex sees the
    # body's words as tokens, so `cat > f <<'EOF' … && grep foo … EOF` yields a
    # segment that starts with grep even though nothing is being searched.
    if "<<" in command:
        return None
    # Split on newlines first — shlex treats a newline as plain whitespace, so a
    # multi-line script would otherwise collapse into one segment and hide every
    # command after the first.
    for line in command.splitlines():
        try:
            tokens = shlex.split(line)
        except ValueError:
            continue  # unbalanced quotes — cannot parse, so do not judge
        for segment, piped in _segments(tokens):
            if piped:
                continue
            pattern = _pattern_from_segment(segment)
            if pattern:
                return pattern
    return None


def extract_pattern(tool_name: str, tool_input: dict):
    """Both tool shapes reduced to one thing: the pattern being searched for.

    Shape, not name. `Bash` is the one name that has to appear because a shell
    command needs parsing before it yields a pattern; everything else is judged
    by whether tool_input carries a `pattern` string. So a search tool this hook
    has never heard of still gets gated the moment hooks.json routes it here.
    """
    if tool_name == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str) or not command.strip():
            return None
        return pattern_from_command(command)
    pattern = tool_input.get("pattern")
    return pattern if isinstance(pattern, str) else None


def state_path(agent_key: str) -> Path:
    digest = hashlib.sha256(agent_key.encode("utf-8", "replace")).hexdigest()[:32]
    return Path(tempfile.gettempdir()) / "codegraph-search-gate" / f"{digest}.json"


def load_denied(path: Path) -> list:
    # A missing or corrupt file means "nothing denied yet", not an error. Losing
    # the record costs one extra denial; refusing to run costs the whole gate.
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    denied = data.get("denied") if isinstance(data, dict) else None
    return denied if isinstance(denied, list) else []


def remember(path: Path, denied: list, key: str) -> bool:
    """Persist the denial. False means "could not", and the caller must allow.

    Recording BEFORE denying is what keeps the escape hatch real: if the write
    fails and we denied anyway, the retry would be denied too and the model
    would be stuck in the one loop this hook must never create.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"denied": (denied + [key])[-MAX_REMEMBERED:]}),
            encoding="utf-8",
        )
    except OSError:
        return False
    return True


def run() -> None:
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    if not raw.strip():
        return
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return

    # Only that it exists — it is the state key's prefix, not a gate. Which
    # tools reach this hook is hooks.json's decision.
    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name:
        return

    if not has_codegraph_index(payload.get("cwd") or os.getcwd()):
        return

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    pattern = extract_pattern(tool_name, tool_input)
    if not isinstance(pattern, str) or not is_symbol_shaped(pattern):
        return

    # Subagents share the parent's session_id but carry their own agent_id, so
    # agent_id is what makes "once per agent" mean once per agent. Without any
    # identifier the escape hatch cannot be tracked, and a gate that cannot
    # remember what it denied would deny the retry too — so it stays silent.
    agent_key = payload.get("agent_id") or payload.get("session_id")
    if not isinstance(agent_key, str) or not agent_key:
        return

    path = state_path(agent_key)
    denied = load_denied(path)
    # Keyed per TOOL on purpose. Sharing one key across tools would mean a model
    # denied on Grep could run the same search through Bash and sail past — tool
    # shopping is not "retrying the identical call". One symbol therefore costs
    # at most one denial per surface, each independently recoverable.
    key = f"{tool_name} {pattern}"
    if key in denied:
        return  # the escape hatch: this exact search was already denied once
    if not remember(path, denied, key):
        return

    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": REASON.format(pattern=pattern),
                }
            }
        )
    )


def main() -> int:
    try:
        run()
    except Exception:  # noqa: BLE001 — see the fail-open note in the docstring
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
