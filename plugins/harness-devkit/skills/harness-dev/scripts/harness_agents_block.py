#!/usr/bin/env python3
"""harness-dev 의 작업 규율을 대상 프로젝트의 AGENTS.md 에 마커 블록으로 설치·제거한다.

사용:
    harness_agents_block.py --install [--project-root PATH]
    harness_agents_block.py --remove  [--project-root PATH]

왜 필요한가. 8가지 제약 중 넷은 코드가 검사하지만(훅 + validate_feature_list.py) 나머지
넷 — "한 번에 하나씩", "자기 평가 불신", "진행 기록 필수" — 은 판단이라 코드가 볼 수 없다.
그 넷은 모델이 기억해야 지켜지는데, 긴 스프린트에서 컨텍스트가 압축되면 SKILL.md 가
컨텍스트에서 빠지면서 함께 사라진다. AGENTS.md 는 매 턴 다시 로드되므로 압축을 견딘다.

**여기에는 진행 상태를 쓰지 않는다.** slug 도, "진행 중" 도 넣지 않는다. 그것은
`docs/harness/*/feature_list.json` 을 보면 아는 사실이고, 두 번째 사본을 만들면 중단된
실행에서 AGENTS.md 가 틀린 지시를 하게 된다 — 틀린 지시는 없는 지시보다 나쁘다. 진행 상태는
progress.md 와 feature_list.json 의 몫이고, 이 블록은 실행과 무관한 항구적 규약만 담는다.
그래서 slug 인자가 없고, 재설치는 멱등이며, 스킬이 이것을 제거하지 않는다.

`--remove` 는 사람이 쓰는 되돌리기다. 설치에 되돌리는 길이 없으면 사용자 파일에 일방통행
변경을 남기게 된다. 스킬 흐름에서는 호출하지 않는다.
"""
from __future__ import annotations

import argparse
import os
import sys

MARKER = "harness-dev"
BEGIN = f"<!-- >>> {MARKER} >>> -->"
END = f"<!-- <<< {MARKER} <<< -->"

# project-conventions 는 `<!-- >>> agent-rules: {name} >>> -->` 를 쓴다. 이름공간이 다르므로
# 두 플러그인의 블록이 한 AGENTS.md 에 공존해도 서로를 건드리지 않는다.

BLOCK_BODY = """## Harness 작업 규율

`harness-devkit:harness-dev` 로 진행하는 작업에 적용된다. 이 절은 그 스킬이 관리한다 —
직접 고치지 말 것, 재설치하면 덮어쓴다.

**harness 상태는 `docs/harness/*/` 에 있다.** 작업을 재개할 때 그 폴더의
`progress.md` → `feature_list.json` 순으로 **먼저 읽는다.** 이 문서에는 진행 상태를 적지 않는다.

**재정의할 수 없는 제약:**

1. **한 번에 하나의 기능만** 구현한다 — 여러 기능을 동시에 작업하지 않는다
2. `acceptance_criteria` 를 **수정·삭제하지 않는다** — 어려운 기능을 쉽게 통과시키는 지름길이 된다
3. Generator 의 자체 평가는 참고일 뿐, **Evaluator 의 판정이 최종**이다
4. **스텁·TODO·placeholder·mock 으로 기능을 통과시키지 않는다**
5. 매 스프린트 종료 시 **`progress.md` 를 갱신한다**
6. `feature_list.json` 은 **JSON 형식을 유지한다** — Markdown 으로 바꾸지 않는다
7. 동일 스프린트 **재시도는 2회까지**. 그 뒤에는 사용자에게 에스컬레이션한다
8. `status` 기본값은 **`"fail"`**. `"pending"` 은 존재하지 않는다 — 통과를 증명해야 `"pass"` 가 된다

2·6·7·8 은 PreToolUse 훅과 아래 검사가 기계적으로 잡는다. 1·3·5 는 판단 영역이라 검사할 수 없다.

```bash
python3 <플러그인>/skills/harness-dev/scripts/validate_feature_list.py \\
  docs/harness/<slug>/feature_list.json --stubs src
```"""


def block() -> str:
    return f"{BEGIN}\n{BLOCK_BODY}\n{END}"


def target_file(project_root: str) -> tuple[str, bool]:
    """블록을 넣을 파일과 신규 생성 여부.

    AGENTS.md 가 있으면 거기다. 없고 CLAUDE.md 만 있으면 CLAUDE.md 에 넣는다 — 그 프로젝트의
    에이전트 지시 단일 소스가 CLAUDE.md 라는 뜻이고, 옆에 AGENTS.md 를 새로 만들면 로드되지
    않는 파일에 규율을 적어 두는 셈이 된다. 둘 다 없으면 AGENTS.md 를 만든다.
    """
    agents = os.path.join(project_root, "AGENTS.md")
    claude = os.path.join(project_root, "CLAUDE.md")
    if os.path.isfile(agents):
        return agents, False
    if os.path.isfile(claude):
        return claude, False
    return agents, True


def upsert(text: str) -> str:
    """블록을 넣거나 제자리에서 교체한다. 재실행해도 두 개가 되지 않는다."""
    start = text.find(BEGIN)
    if start == -1:
        separator = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
        return f"{text}{separator}{block()}\n"
    end = text.find(END, start)
    if end == -1:
        # 시작만 있고 끝이 없다 — 반쪽 블록을 남기면 이후 모든 재설치가 여기서 어긋난다.
        return text[:start] + block() + "\n"
    return text[:start] + block() + text[end + len(END):]


def strip_block(text: str) -> str:
    start = text.find(BEGIN)
    if start == -1:
        return text
    end = text.find(END, start)
    tail = text[end + len(END):] if end != -1 else ""
    return (text[:start].rstrip("\n") + ("\n" + tail.lstrip("\n") if tail.strip() else "\n"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--install", action="store_true")
    action.add_argument("--remove", action="store_true")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    root = os.path.abspath(args.project_root)
    if not os.path.isdir(root):
        print(f"프로젝트 루트가 없습니다: {root}", file=sys.stderr)
        return 3

    path, created = target_file(root)
    try:
        text = "" if created else open(path, "r", encoding="utf-8").read()
    except OSError as exc:
        print(f"읽을 수 없습니다: {exc}", file=sys.stderr)
        return 3

    updated = upsert(text) if args.install else strip_block(text)

    if updated == text and not created:
        print(f"변경 없음 — {path}")
        return 0
    if args.remove and created:
        print("제거할 블록이 없습니다.")
        return 0

    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(updated)
    except OSError as exc:
        print(f"쓸 수 없습니다: {exc}", file=sys.stderr)
        return 3

    verb = "설치" if args.install else "제거"
    suffix = " (새로 만듦)" if created else ""
    print(f"{verb} 완료 — {path}{suffix}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
