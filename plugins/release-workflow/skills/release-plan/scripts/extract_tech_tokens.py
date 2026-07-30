#!/usr/bin/env python3
"""Extract technology tokens (model IDs, npm packages) from task_list.json.

This script is the *first half* of the release-plan external-fact-verification
gate (Step 4-8 → 4-9 → 4-10). Its job is purely deterministic extraction —
it does not call the network, does not judge whether a token is real, and
does not modify task_list.json. The fact-checker subagent (agents/fact-checker.md)
consumes this script's output and performs the actual verification.

Why a script and not LLM extraction:
    LLMs hallucinate model IDs precisely because the same generative process
    that writes them also "extracts" them — the LLM never doubts what it
    just produced. Pulling tokens out with a regex breaks that loop:
    extraction is now a function of the literal text, not of the model's
    self-belief about what it wrote.

Patterns deliberately kept conservative to avoid false-positive flooding:
    - model_id: lowercase token chains containing at least one digit-bearing
      segment, optionally suffixed with a known instruction-tuning marker
      (it / instruct / base / chat / pt / hf / sft / dpo). Examples:
      ``gemma-3-27b-it``, ``claude-opus-4-7``, ``llama-3-70b-instruct``.
      A pure prose kebab-case phrase like ``logout-after-redirect`` will
      not match because no segment contains a digit.
    - npm_scoped: ``@org/pkg`` form.
    - npm_known_prefix: packages we know almost always show up in this repo's
      release plans (react-native-*, expo-*, @react-native-firebase/*,
      @react-navigation/*, @expo/*).
    - python_pin: ``pkg==1.2.3`` / ``pkg>=1.2`` style version pins.

Output schema (JSON, written to <output_path> and also printed to stdout):

    {
      "extracted_at": "2026-04-18T12:34:56",
      "task_list_path": "docs/skills/release-plan/{slug}/v{ver}/task_list.json",
      "tokens": [
        {
          "value": "gemma-3-27b-it",
          "kind": "model_id",
          "occurrences": [
            {
              "task_id": "TASK-001",
              "field": "implementation_details",
              "snippet": "Gemma 3 27B 모델(gemma-3-27b-it)로 ..."
            }
          ]
        }
      ]
    }

Tokens are deduplicated case-sensitively. ``occurrences`` preserves every
location for later debugging — the fact-checker logs each one in its
evidence file. An empty ``tokens`` array is a valid outcome (e.g. UI-only
release): downstream verify_tech_tokens.py treats ``[]`` as auto-pass.

Exit codes:
    0  extraction completed (regardless of how many tokens were found)
    2  usage / IO / JSON error
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import sys
from pathlib import Path

# At least one segment must contain a digit (e.g. "27b", "3", "4-7"). This
# is what separates real model IDs from incidental kebab-case prose. Suffix
# is optional but recognized to keep ``gemma-3-27b-it`` as a single token
# rather than splitting off ``-it``.
_MODEL_ID_RE = re.compile(
    r"\b"
    r"[a-z][a-z0-9]*"
    r"(?:-[a-z0-9]+){2,}"
    r"(?:-(?:it|instruct|base|chat|pt|hf|sft|dpo))?"
    r"\b"
)
_HAS_DIGIT_SEGMENT_RE = re.compile(r"-[a-z]*\d[a-z0-9]*(?:-|$)")

_NPM_SCOPED_RE = re.compile(r"@[a-z][\w.-]*\/[a-z][\w.-]*")
_NPM_KNOWN_PREFIX_RE = re.compile(
    r"\b(?:react-native-[\w-]+|expo-[\w-]+)\b"
)
_PYTHON_PIN_RE = re.compile(r"\b[a-z][\w.-]*(?:==|>=|<=|~=)\d[\w.]*\b")

_SNIPPET_RADIUS = 40


def _snippet(text: str, start: int, end: int) -> str:
    lo = max(0, start - _SNIPPET_RADIUS)
    hi = min(len(text), end + _SNIPPET_RADIUS)
    prefix = "…" if lo > 0 else ""
    suffix = "…" if hi < len(text) else ""
    return f"{prefix}{text[lo:hi]}{suffix}"


def _scan(text: str, kind: str, pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for m in pattern.finditer(text):
        value = m.group(0)
        if kind == "model_id" and not _HAS_DIGIT_SEGMENT_RE.search(f"-{value}-"):
            continue
        out.append((value, _snippet(text, m.start(), m.end())))
    return out


def _extract_from_field(text: str) -> list[tuple[str, str, str]]:
    """Return list of (value, kind, snippet) for one text blob."""
    found: list[tuple[str, str, str]] = []
    for kind, pattern in (
        ("npm_scoped", _NPM_SCOPED_RE),
        ("npm_known_prefix", _NPM_KNOWN_PREFIX_RE),
        ("python_pin", _PYTHON_PIN_RE),
        ("model_id", _MODEL_ID_RE),
    ):
        for value, snippet in _scan(text, kind, pattern):
            found.append((value, kind, snippet))
    return found


def extract(task_list_path: Path) -> dict:
    data = json.loads(task_list_path.read_text(encoding="utf-8"))
    by_value: dict[str, dict] = {}

    tasks = data.get("tasks", [])
    if not isinstance(tasks, list):
        raise ValueError("task_list.json: 'tasks' is not a list")

    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id", "<unknown>")
        for field_name in ("implementation_details", "acceptance_criteria"):
            field = task.get(field_name, [])
            if isinstance(field, list):
                blob = "\n".join(x for x in field if isinstance(x, str))
            elif isinstance(field, str):
                blob = field
            else:
                continue
            for value, kind, snippet in _extract_from_field(blob):
                entry = by_value.setdefault(
                    value,
                    {"value": value, "kind": kind, "occurrences": []},
                )
                # If the same literal matches multiple kinds, keep the most
                # specific one (npm_scoped > npm_known_prefix > python_pin > model_id).
                priority = {"npm_scoped": 0, "npm_known_prefix": 1, "python_pin": 2, "model_id": 3}
                if priority[kind] < priority[entry["kind"]]:
                    entry["kind"] = kind
                entry["occurrences"].append(
                    {"task_id": task_id, "field": field_name, "snippet": snippet}
                )

    tokens = sorted(by_value.values(), key=lambda e: (e["kind"], e["value"]))
    return {
        "extracted_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "task_list_path": str(task_list_path),
        "tokens": tokens,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "usage: extract_tech_tokens.py <task_list.json> <output_tokens.json>",
            file=sys.stderr,
        )
        return 2
    task_list_path = Path(argv[1])
    output_path = Path(argv[2])
    try:
        result = extract(task_list_path)
    except FileNotFoundError:
        print(f"{task_list_path}: file not found", file=sys.stderr)
        return 2
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"{task_list_path}: {exc}", file=sys.stderr)
        return 2

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
