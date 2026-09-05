#!/usr/bin/env python3
"""PreToolUse 훅: 이 프로젝트에서 Notion MCP 도구 호출을 막는다.

이 훅은 플러그인이 아니라 **프로젝트**가 설치한다 (`project-conventions:init-agent-rules`
가 사용자의 옵트인에 따라 `.claude/settings.json` 에 등록한다). 그래서 harness-devkit 의
`harness_feature_list_gate.py` 와 달리 탈출구(같은 위반은 한 번만 차단)가 없다 — "전역
발화 훅은 재시도하면 반드시 통과해야 한다"는 저장소 규칙은 **플러그인이 켜진 모든 프로젝트에
번들 훅이 뜨는 상황**을 전제한 것이고, 이 훅은 사용자가 이 프로젝트에서 명시적으로 옵트인한
정책이라 그 전제가 적용되지 않는다. 발화 조건 자체(토큰을 구할 수 있는가)가 안전장치다:
대체 경로가 없는 프로젝트에서는 절대 발화하지 않는다.

stdin 으로 PreToolUse 페이로드를 읽는다:
    {session_id, agent_id?, cwd, hook_event_name, tool_name, tool_input}

차단할 때만 stdout 에 hookSpecificOutput 을 쓰고, 그 외에는 아무것도 쓰지 않는다.
언제나 exit 0.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REASON = """Notion MCP 도구(`{tool_name}`) 호출을 막았습니다.

이 프로젝트는 Notion 을 토큰 기반 REST API 로만 다룹니다. MCP 서버는 환경마다 도구 이름과
응답 스키마가 달라({examples}) 같은 스킬이 사람마다 다른 결과를 냅니다.

`.claude/rules/notion-api-only.md` 를 읽고 `.claude/scripts/notion_api.py` 를 쓰세요:

  python3 .claude/scripts/notion_api.py --help

이 규칙을 이 프로젝트에서 끄려면 환경변수 NOTION_MCP_GATE=off 로 실행하세요."""

MCP_EXAMPLES = "mcp__claude_ai_Notion__…, mcp__plugin_Notion_notion__…"


def parse_env_file(path: Path) -> dict:
    """.env 파서. `notion_api.py` 의 규약과 동일하게 유지한다(둘 다 NOTION_TOKEN 만 본다)."""
    out = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value[:1] in ("'", '"'):
            quote = value[0]
            end = value.find(quote, 1)
            value = value[1:end] if end != -1 else value[1:]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if key:
            out[key] = value
    return out


def find_project_root(start: Path) -> Path:
    cur = start.resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / ".git").exists():
            return candidate
    return cur


def token_source(cwd: str) -> str | None:
    """토큰의 '출처 이름'만 돌려준다. 값은 읽지도 담지도 않는다."""
    if os.environ.get("NOTION_TOKEN", "").strip():
        return "env"
    try:
        root = find_project_root(Path(cwd))
    except OSError:
        return None
    for env_path in (root / ".env", root.parent / ".env"):
        if parse_env_file(env_path).get("NOTION_TOKEN", "").strip():
            return str(env_path)
    return None


def run() -> None:
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    if not raw.strip():
        return
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return

    # 존재만 본다 — 어느 도구가 여기 닿는지는 settings.json 의 matcher 가 정한다.
    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name:
        return

    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return  # os.getcwd() 를 쓰지 않는다 — 훅 프로세스의 cwd 는 프로젝트와 다를 수 있다

    if os.environ.get("NOTION_MCP_GATE", "").strip().lower() == "off":
        return  # 프로젝트 단위 옵트아웃

    source = token_source(cwd)
    if source is None:
        return  # 대체 경로가 없는데 막지 않는다 — 이게 이 훅의 유일한 안전장치다

    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": REASON.format(
                        tool_name=tool_name, examples=MCP_EXAMPLES
                    ),
                }
            }
        )
    )


def main() -> int:
    try:
        run()
    except Exception:  # noqa: BLE001 — 전 구간 fail-open
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
