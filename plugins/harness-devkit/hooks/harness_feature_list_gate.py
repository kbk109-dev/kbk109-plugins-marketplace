#!/usr/bin/env python3
"""PreToolUse hook: harness-dev 의 상태 파일이 규율을 깨는 모양으로 쓰이는 것을 잡는다.

왜 필요한가. harness-dev 의 SKILL.md 는 8가지를 "기계적 제약" 이라 부르지만 전부 산문이다.
긴 스프린트에서 컨텍스트가 압축되면 그 산문은 컨텍스트에서 사라지고, 규율은 조용히 깨진다.
`acceptance_criteria` 를 두 줄 지우면 어려운 기능이 갑자기 통과하고, 아무도 그것을 모른다.
이 훅은 모델이 무엇을 기억하는지와 무관하게 `feature_list.json` 을 쓰는 순간을 본다.

stdin 으로 PreToolUse 페이로드를 읽는다:
    {session_id, agent_id?, cwd, hook_event_name, tool_name, tool_input}

차단할 때만 stdout 에 hookSpecificOutput 을 쓰고, 그 외에는 **아무것도** 쓰지 않는다.
언제나 exit 0.

차단은 반드시 복구 가능해야 한다. 이 훅은 플러그인이 배포하므로 플러그인이 켜진 모든
프로젝트에서 발화한다. 그것을 안전하게 만드는 것은 탈출구뿐이다 — 같은 (에이전트, 위반)은
많아야 한 번 차단되므로 동일한 호출을 그대로 다시 하면 반드시 통과한다. 이 훅이 오판했을 때의
최대 대가는 도구 호출 한 번 재시도이고, 막힌 작업이 되는 일은 없다.

그래서 이 훅이 제약 #2 를 **불가능하게 만들지는 못한다.** 만드는 것은 조용한 지름길을
의도적인 선택으로 바꾸는 것이다 — 재호출하려면 모델이 위반을 읽고 다시 결정해야 하고, 그
사실이 상태 파일에 남는다. 불가능하게 만드는 쪽은 훅이 아니라 매 스프린트 끝에 돌리는
validate_feature_list.py 이고, 그건 사람이 결과를 본다.

그 밖은 전 구간 fail-open 이다. "색인된 harness 상태 파일을 규율을 깨는 내용으로 쓰고 있다"가
분명하지 않은 모든 조건은 조용히 통과시키고, 예상 못 한 예외는 통째로 삼킨다.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from _feature_list_rules import check

MAX_REMEMBERED = 200

# 훅이 보는 파일. harness-dev 가 만드는 경로는 `docs/harness/{slug}/feature_list.json` 하나뿐이라
# 이 두 조각의 문자열 검사만으로 판정된다 — 파일시스템을 건드리지 않는다. 이게 ① 무출력 조건의
# 값을 결정한다: 이 훅은 모든 Write/Edit 마다 뜨지만, 무관한 호출은 파일을 열기도 전에 빠진다.
TARGET_BASENAME = "feature_list.json"
TARGET_PARENT = "docs/harness/"

REASON = """harness-dev 의 기계적 제약을 깨는 변경입니다.

{violations}

`feature_list.json` 은 이 하네스의 Task State Machine 입니다. acceptance_criteria 를 고치면
어려운 기능을 "쉽게 통과"시키는 지름길이 되고, status 를 임의 값으로 두면 통과 증명이
무의미해집니다.

고쳐야 할 것을 고친 뒤 다시 쓰세요. **이 변경이 의도된 것이면 같은 호출을 그대로 다시 하면
통과합니다** — 범위가 실제로 바뀌었다면 사용자에게 먼저 확인받는 편이 낫습니다."""


def targets_feature_list(file_path) -> bool:
    if not isinstance(file_path, str) or not file_path:
        return False
    normalized = file_path.replace("\\", "/")
    return normalized.endswith("/" + TARGET_BASENAME) and TARGET_PARENT in normalized


def resulting_content(tool_name: str, tool_input: dict, file_path: str):
    """이 호출이 끝난 뒤 파일에 있을 내용. 모르겠으면 None (= 통과시킨다)."""
    content = tool_input.get("content")
    if isinstance(content, str):
        return content  # Write — 통째로 주어진다

    # Edit — 조각만 주어지므로 현재 파일에 적용해 봐야 결과를 안다. 애매하면 판정하지 않는다:
    # 여기서 잘못 재현한 내용으로 차단하면 멀쩡한 편집이 막힌다.
    old = tool_input.get("old_string")
    new = tool_input.get("new_string")
    if not isinstance(old, str) or not isinstance(new, str):
        return None
    try:
        current = Path(file_path).read_text("utf-8")
    except OSError:
        return None
    if tool_input.get("replace_all"):
        return current.replace(old, new)
    if current.count(old) != 1:
        return None  # 0건이면 도구가 실패할 것이고, 2건 이상이면 어디를 고칠지 모른다
    return current.replace(old, new, 1)


def load_lock(file_path: str):
    """같은 폴더의 .criteria_lock.json. 없으면 None — 제약 2 만 건너뛴다."""
    try:
        raw = (Path(file_path).parent / ".criteria_lock.json").read_text("utf-8")
        lock = json.loads(raw)
    except (OSError, ValueError):
        return None
    return lock if isinstance(lock, dict) else None


def state_path(agent_key: str) -> Path:
    digest = hashlib.sha256(agent_key.encode("utf-8", "replace")).hexdigest()[:32]
    return Path(tempfile.gettempdir()) / "harness-feature-list-gate" / f"{digest}.json"


def load_denied(path: Path) -> list:
    # 파일이 없거나 깨졌으면 "아직 아무것도 차단 안 함" 이지 오류가 아니다. 기록을 잃으면
    # 차단이 한 번 더 일어날 뿐이지만, 실행을 거부하면 게이트 전체가 죽는다.
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    denied = data.get("denied") if isinstance(data, dict) else None
    return denied if isinstance(denied, list) else []


def remember(path: Path, denied: list, key: str) -> bool:
    """차단을 기록한다. False 는 "못 했다" 이고, 호출자는 통과시켜야 한다.

    차단보다 기록을 먼저 하는 것이 탈출구를 진짜로 만든다: 기록에 실패했는데 차단까지 하면
    재시도도 차단되어, 이 훅이 절대 만들면 안 되는 그 루프에 모델이 갇힌다.
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


def format_violations(violations: list) -> str:
    lines = []
    for v in violations:
        fid = v.get("feature_id")
        prefix = f"  - 제약 #{v['rule']}"
        lines.append(f"{prefix} [{fid}] {v['detail']}" if fid else f"{prefix} {v['detail']}")
    return "\n".join(lines)


def run() -> None:
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    if not raw.strip():
        return
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return

    # 존재만 본다 — 상태 키의 접두어이지 게이트가 아니다. 어느 도구가 여기 닿는지는
    # hooks.json 의 matcher 가 정한다.
    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name:
        return

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return

    file_path = tool_input.get("file_path")
    if not targets_feature_list(file_path):
        return  # 가장 흔한 경로. 여기까지가 문자열 검사뿐이다

    content = resulting_content(tool_name, tool_input, file_path)
    if content is None:
        return

    try:
        feature_list = json.loads(content)
    except ValueError as exc:
        # 제약 6 — JSON 이 아니면 상태 머신이 아니다. 그 자체가 위반이다.
        violations = [{"rule": 6, "detail": f"JSON 파싱 실패: {exc}"}]
    else:
        violations = check(feature_list, load_lock(file_path))
    if not violations:
        return

    # 서브에이전트는 부모와 session_id 를 공유하지만 자기 agent_id 를 갖는다. "에이전트당 한 번"이
    # 에이전트당 한 번이 되게 하는 것이 agent_id 다. 식별자가 없으면 무엇을 차단했는지 기억할 수
    # 없고, 기억 못 하는 게이트는 재시도까지 차단하므로 조용히 있는다.
    agent_key = payload.get("agent_id") or payload.get("session_id")
    if not isinstance(agent_key, str) or not agent_key:
        return

    # 위반의 종류로 키를 만든다. 파일 내용 해시로 잡으면 모델이 무관한 한 글자를 바꾸는 것만으로
    # 새 키가 되어 매번 차단되고, 그건 루프다. 같은 위반을 다시 들고 오면 통과시킨다.
    signature = ";".join(sorted(f"{v['rule']}:{v.get('feature_id', '')}" for v in violations))
    key = f"{file_path} {signature}"

    path = state_path(agent_key)
    denied = load_denied(path)
    if key in denied:
        return  # 탈출구: 이 위반은 이미 한 번 알렸다
    if not remember(path, denied, key):
        return

    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": REASON.format(
                        violations=format_violations(violations)
                    ),
                }
            }
        )
    )


def main() -> int:
    try:
        run()
    except Exception:  # noqa: BLE001 — docstring 의 fail-open 항목 참조
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
