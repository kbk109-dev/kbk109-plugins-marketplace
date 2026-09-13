#!/usr/bin/env python3
"""PreToolUse 훅: 이 프로젝트에서 메인 에이전트의 `git commit` 실행을 막는다.

이 훅은 플러그인이 아니라 **프로젝트**가 설치한다 (`project-conventions:init-agent-rules`
가 사용자의 옵트인에 따라 `.claude/settings.json` 에 등록한다). 그래서 harness-devkit 의
`harness_feature_list_gate.py` 와 달리 탈출구(같은 위반은 한 번만 차단)가 없다 — "전역
발화 훅은 재시도하면 반드시 통과해야 한다"는 저장소 규칙은 **플러그인이 켜진 모든 프로젝트에
번들 훅이 뜨는 상황**을 전제한 것이고, 이 훅은 사용자가 이 프로젝트에서 명시적으로 옵트인한
정책이라 그 전제가 적용되지 않는다. 발화 조건 자체(옵트인 여부)가 안전장치다: 규칙을
설치하지 않은 프로젝트에서는 절대 발화하지 않는다.

commit-agent 서브에이전트 자신의 커밋은 통과시켜야 한다 — 프로젝트 훅은 서브에이전트의
도구 호출에도 그대로 발화하므로, 이 whitelist(§ agent_type 검사)가 없으면 commit-agent 가
자기 자신에게 막힌다.

stdin 으로 PreToolUse 페이로드를 읽는다:
    {session_id, agent_id?, agent_type?, cwd, hook_event_name, tool_name, tool_input}

차단할 때만 stdout 에 hookSpecificOutput 을 쓰고, 그 외에는 아무것도 쓰지 않는다.
언제나 exit 0.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

REASON = """`git commit` 을 막았습니다.

이 프로젝트는 커밋을 `project-conventions:commit-agent` 서브에이전트(모델 haiku)에게
위임합니다. `Task` 도구로 그 서브에이전트를 기동해 커밋을 맡기세요 — 변경을 논리 그룹으로
나눠 그룹마다 커밋합니다.

자세한 내용은 `.claude/rules/commit-agent.md` 를 읽으세요.

이 규칙을 이 프로젝트에서 끄려면 환경변수 COMMIT_AGENT_GATE=off 로 실행하세요."""

# "git commit" 이 실제 호출인지 문자열로만 본다 — 존재만 본다는 점에서 notion_mcp_gate.py
# 와 같은 태도다. 오탐(예: echo 안의 문자열)은 최악의 경우 commit-agent 로 위임을
# 유도하는 정도의 마찰이지, 잘못된 커밋을 만들지는 않는다.
GIT_COMMIT_RE = re.compile(r"\bgit\s+commit\b")

# release 커밋 예외 — main-branch-merge Step 8 은 heredoc 으로 커밋 메시지를 넣는다
# (`git commit -m "$(cat <<'EOF'\nrelease: {버전}\n...`). 그 경우 "release: ..." 가 원시
# 명령 문자열에서 줄의 시작에 그대로 나타난다. 단순 한 줄 형태(-m "release: ...")도 함께
# 받아준다 — 어느 쪽이든 릴리스 커밋은 원자적 단일 커밋이어야 하므로 그룹 분할 대상이 아니다.
RELEASE_COMMIT_RE = re.compile(r"(?m)(^release:\s|-m\s*[\"']release:\s)")


def find_project_root(start: Path) -> Path:
    cur = start.resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / ".git").exists():
            return candidate
    return cur


def is_opted_in(cwd: str) -> bool:
    try:
        root = find_project_root(Path(cwd))
    except OSError:
        return False
    return (root / ".claude" / "rules" / "commit-agent.md").is_file()


def run() -> None:
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    if not raw.strip():
        return
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return

    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name:
        return

    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return  # os.getcwd() 를 쓰지 않는다 — 훅 프로세스의 cwd 는 프로젝트와 다를 수 있다

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return

    command = tool_input.get("command")
    if not isinstance(command, str) or not GIT_COMMIT_RE.search(command):
        return  # 가장 흔한 경로 — git commit 이 아닌 Bash 호출

    if os.environ.get("COMMIT_AGENT_GATE", "").strip().lower() == "off":
        return  # 프로젝트 단위 옵트아웃

    # commit-agent 자신 — 접두사(project-conventions:commit-agent)와 사용자가
    # .claude/agents/ 로 복사했을 bare 형태(commit-agent) 둘 다 통과시킨다.
    agent_type = payload.get("agent_type")
    if isinstance(agent_type, str) and (
        agent_type == "commit-agent" or agent_type.endswith(":commit-agent")
    ):
        return

    if RELEASE_COMMIT_RE.search(command):
        return  # main-branch-merge 의 릴리스 커밋 예외

    if not is_opted_in(cwd):
        return  # 이 프로젝트가 규칙을 설치하지 않았다 — 발화하지 않는다

    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": REASON,
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
