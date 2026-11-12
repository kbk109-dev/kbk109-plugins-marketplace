#!/usr/bin/env python3
"""docs/harness/ 의 파일 상태에서 "지금 어느 단계인가" 를 판정한다.

사용:
    harness_state.py status <docs/harness> [--slug S]
    harness_state.py slug "<제품 이름>" <docs/harness>
    harness_state.py log <product_dir> <stage> <status> [artifact]   # PROGRESS.md 에 한 줄

출력: stdout JSON { slug, stage, epic, epic_dir, feature, round, reason, candidates? }
종료코드: 0 (단계 판정은 위반이 아니다), 3 = 입력 오류

왜 코드인가. 새 세션은 앞선 대화를 모른다. 파일만 보고 같은 단계를 같은 이름으로 판정해야
재진입이 흔들리지 않는다 — 모델에게 맡기면 재진입할 때마다 판정이 달라진다.

판정 순서와 승인 표지:
    PRD/PLAN 승인   frontmatter `status: approved`
    에픽 승인       epics/<NN>/.criteria_lock.json
    TC 확정         epics/<NN>/.tc_lock.json
    에픽 종료       epics/<NN>/CLOSED.md
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "..", "..", "hooks"))
from _feature_list_rules import CRITERIA_LOCK_NAME, TC_LOCK_NAME  # noqa: E402
from validate_harness_doc import (  # noqa: E402
    EPIC_ROW,
    REVIEW_PREFIX,
    changed_since_review,
    check_tc,
    latest_review,
    read_json,
    read_text,
    reviews_dir_of,
    tc_lock_ok,
)

MAX_ROUNDS = 2
# PROGRESS.md 한 줄의 상한. 상세는 산출물 파일에 있다 — 이 파일은 매 시작에 읽히는 색인이다.
LOG_LINE_MAX = 200


def fail(message: str) -> None:
    json.dump({"ok": False, "error": message}, sys.stdout, ensure_ascii=False)
    sys.exit(3)


def exists(*parts) -> bool:
    return os.path.exists(os.path.join(*parts))


def frontmatter_status(path: str):
    m = re.match(r"^---\s*\n(.*?)\n---", read_text(path), re.DOTALL)
    if not m:
        return None
    s = re.search(r"^status\s*:\s*(\w+)", m.group(1), re.MULTILINE)
    return s.group(1) if s else None


def review_loop(doc: str, reviews_dir: str, prefix: str) -> tuple:
    """작성 → critic → 수정 루프의 다음 동작. (동작, 라운드, 마지막 VERDICT)

    동작: critic | revise | done. `done` 은 PASS 이거나 라운드를 다 쓴 것이다 —
    후자는 남은 blocking 을 사용자에게 보여야 하므로 호출자가 라운드로 구분한다.

    "마지막 리뷰 뒤에 문서가 바뀌었는가" 는 그 리뷰의 스냅샷이 있으면 내용 해시로, 없으면
    mtime 으로 본다 (스냅샷은 TC 의 tc-review-prep 만 남긴다). mtime 은 checkout 한 번에
    흔들리므로, 해시로 확인된 "PASS 뒤 변경" 만 라운드를 다 쓴 뒤에도 다시 critic 으로 보낸다 —
    mtime 판정만으로는 2라운드를 넘긴 수정본이 재검토 없이 잠금으로 갔다.
    """
    n, verdict, review_path = latest_review(reviews_dir, prefix)
    hashed = changed_since_review(doc, reviews_dir, prefix, n) if n else None
    if n == 0:
        changed = True
    elif hashed is None:
        changed = os.path.getmtime(doc) > os.path.getmtime(review_path)
    else:
        changed = hashed
    if changed:
        again = n < MAX_ROUNDS or (hashed and verdict == "PASS")
        return ("critic", n + 1, verdict) if again else ("done", n, verdict)
    if verdict == "PASS" or n >= MAX_ROUNDS:
        return "done", n, verdict
    return "revise", n, verdict


def result(slug, stage, reason, **extra) -> dict:
    base = {"slug": slug, "stage": stage, "epic": None, "epic_dir": None,
            "feature": None, "round": None, "reason": reason}
    base.update(extra)
    return base


def epic_ids(plan_path: str) -> list:
    return sorted(set(EPIC_ROW.findall(read_text(plan_path))))


def eligible_feature(feature_list):
    """의존이 모두 pass 인 fail 기능 중 id 가 가장 앞선 것. (기능, 남은 fail 수)"""
    features = [f for f in feature_list.get("features", []) if isinstance(f, dict)]
    passed = {f.get("id") for f in features if f.get("status") == "pass"}
    pending = [f for f in features if f.get("status") == "fail"]
    ready = [f for f in pending
             if all(d in passed for d in (f.get("dependencies") or []))]
    ready.sort(key=lambda f: str(f.get("id")))
    return (ready[0] if ready else None), len(pending)


def epic_stage(slug: str, epic: str, epic_dir: str, legacy: bool = False) -> dict:
    def r(stage, reason, **extra):
        return result(slug, stage, reason, epic=epic, epic_dir=epic_dir, **extra)

    if exists(epic_dir, "CLOSED.md"):
        return r("closed", "에픽 종료됨")
    fl_path = os.path.join(epic_dir, "feature_list.json")
    feature_list = read_json(fl_path)
    if feature_list is None:
        return r("feature-plan", "feature_list.json 이 없거나 읽을 수 없다")
    if not exists(epic_dir, CRITERIA_LOCK_NAME):
        return r("epic-approval", "feature_list 가 아직 승인(잠금)되지 않았다")

    if not legacy:
        tc = os.path.join(epic_dir, "TC.md")
        if not exists(tc):
            return r("tc-draft", "TC.md 가 없다", round=1)
        if not exists(epic_dir, TC_LOCK_NAME):
            action, n, verdict = review_loop(tc, reviews_dir_of(tc), REVIEW_PREFIX)
            if action == "critic":
                # 코드가 잡을 수 있는 결함에는 critic 라운드를 쓰지 않는다.
                violations = check_tc(read_text(tc), feature_list)
                if violations:
                    return r("tc-revise", f"TC 모양·추적성 위반 {len(violations)}건 — "
                             "critic 을 부르기 전에 tc-writer 가 고친다",
                             round=n, violations=violations[:20])
                return r("tc-critic", "TC 검토 대기", round=n)
            if action == "revise":
                return r("tc-revise", "tc-critic 이 REVISE", round=n)
            if verdict == "PASS":
                return r("tc-lock", "tc-critic PASS — 잠금 대기", round=n)
            return r("escalate", "tc-critic 이 2라운드 뒤에도 REVISE — 남은 누락을 사용자에게", round=n)
        if tc_lock_ok(tc) is False:
            return r("escalate", "확정된 TC.md 가 잠금 이후 바뀌었다")

    feature, pending = eligible_feature(feature_list)
    if feature:
        return r("dev", "다음 기능", feature=feature.get("id"))
    blocked = [f.get("id") for f in feature_list.get("features", [])
               if isinstance(f, dict) and f.get("status") == "blocked"]
    if pending or (blocked and not exists(epic_dir, "blocked_ack.md")):
        return r("escalate", f"진행 불가 — blocked {blocked}, 의존이 풀리지 않은 fail {pending}건",
                 blocked=blocked)
    return r("epic-close", "모든 기능이 pass 이거나 blocked 인정됨")


def is_v2_slug(path: str) -> bool:
    return any(exists(path, name) for name in ("BRIEF.md", "PRD.md", "PLAN.md", "epics"))


def is_legacy_slug(path: str) -> bool:
    return exists(path, "feature_list.json") and not is_v2_slug(path)


def status(harness_dir: str, slug_arg) -> dict:
    try:
        entries = sorted(e for e in os.listdir(harness_dir)
                         if os.path.isdir(os.path.join(harness_dir, e)))
    except OSError:
        entries = []
    candidates = [e for e in entries
                  if is_v2_slug(os.path.join(harness_dir, e))
                  or is_legacy_slug(os.path.join(harness_dir, e))]
    if slug_arg is None:
        if not candidates:
            return result(None, "interview", "진행 중인 제품이 없다")
        if len(candidates) > 1:
            return result(None, "choose", "이어 갈 제품을 사용자에게 묻는다", candidates=candidates)
        slug_arg = candidates[0]
    root = os.path.join(harness_dir, slug_arg)
    if not os.path.isdir(root):
        return result(slug_arg, "interview", "이 slug 의 디렉토리가 없다")

    if is_legacy_slug(root):
        stage = epic_stage(slug_arg, "legacy", root, legacy=True)
        if stage["stage"] == "closed":
            return result(slug_arg, "final", "v1 레이아웃 작업 종료")
        return stage

    prd, plan = os.path.join(root, "PRD.md"), os.path.join(root, "PLAN.md")
    reviews = os.path.join(root, "reviews")

    for name, doc, prefix, prereq in (("prd", prd, "prd-critic", True),
                                      ("plan", plan, "plan-critic", frontmatter_status(prd) == "approved")):
        if not prereq:
            continue
        if not os.path.exists(doc):
            if name == "prd" and not exists(root, "BRIEF.md"):
                return result(slug_arg, "interview", "BRIEF.md 가 없다")
            return result(slug_arg, f"{name}-draft", f"{name.upper()}.md 가 없다", round=1)
        if frontmatter_status(doc) == "approved":
            continue
        action, n, verdict = review_loop(doc, reviews, prefix)
        if action == "critic":
            return result(slug_arg, f"{name}-critic", "검토 대기", round=n)
        if action == "revise":
            return result(slug_arg, f"{name}-revise", "critic 이 REVISE", round=n)
        return result(slug_arg, f"{name}-approval", "사용자 승인 대기", round=n,
                      unresolved_blocking=verdict != "PASS")

    for epic in epic_ids(plan):
        stage = epic_stage(slug_arg, epic, os.path.join(root, "epics", epic))
        if stage["stage"] != "closed":
            return stage
    return result(slug_arg, "final", "모든 에픽이 종료됐다")


def slugify(text: str, harness_dir: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "product"
    slug, n = base, 2
    while os.path.exists(os.path.join(harness_dir, slug)):
        slug, n = f"{base}-{n}", n + 1
    return slug


def log_line(product_dir: str, stage: str, status_text: str, artifact) -> str:
    """PROGRESS.md 에 `- <일시> <stage> → <status> (<artifact>)` 한 줄을 덧붙인다.

    시각을 코드가 찍어야 단계별 소요 시간을 나중에 잴 수 있고, 길이를 코드가 잘라야 이 파일이
    매 시작에 읽을 수 있는 크기로 남는다.
    """
    if not os.path.isdir(product_dir):
        fail(f"디렉토리가 없습니다: {product_dir}")
    name = "PROGRESS.md"
    if not exists(product_dir, name) and exists(product_dir, "progress.md"):
        name = "progress.md"  # 1.x 레이아웃
    body = " ".join(f"{stage} → {status_text}".split())
    if artifact:
        body += f" ({' '.join(artifact.split())})"
    line = f"- {time.strftime('%Y-%m-%d %H:%M')} {body}"[:LOG_LINE_MAX]
    try:
        with open(os.path.join(product_dir, name), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:
        fail(f"진행 기록을 쓸 수 없습니다: {exc}")
    return line


def main(argv) -> int:
    if len(argv) >= 2 and argv[0] == "status":
        slug = argv[argv.index("--slug") + 1] if "--slug" in argv[2:] else None
        json.dump(status(argv[1], slug), sys.stdout, ensure_ascii=False)
        return 0
    if len(argv) >= 3 and argv[0] == "slug":
        json.dump({"slug": slugify(argv[1], argv[2])}, sys.stdout, ensure_ascii=False)
        return 0
    if len(argv) in (4, 5) and argv[0] == "log":
        line = log_line(argv[1], argv[2], argv[3], argv[4] if len(argv) == 5 else None)
        json.dump({"ok": True, "line": line}, sys.stdout, ensure_ascii=False)
        return 0
    fail('사용: harness_state.py status <docs/harness> [--slug S] | slug "<이름>" <docs/harness> '
         "| log <product_dir> <stage> <status> [artifact]")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
