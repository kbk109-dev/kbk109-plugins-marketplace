#!/usr/bin/env python3
"""docs/harness/ 의 파일 상태에서 "지금 어느 단계인가" 를 판정한다.

사용:
    harness_state.py status <docs/harness> [--slug S]
    harness_state.py slug "<제품 이름>" <docs/harness>

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

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "..", "..", "hooks"))
from _feature_list_rules import CRITERIA_LOCK_NAME  # noqa: E402
from validate_harness_doc import EPIC_ROW, tc_lock_ok  # noqa: E402

MAX_ROUNDS = 2


def fail(message: str) -> None:
    json.dump({"ok": False, "error": message}, sys.stdout, ensure_ascii=False)
    sys.exit(3)


def read_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def exists(*parts) -> bool:
    return os.path.exists(os.path.join(*parts))


def frontmatter_status(path: str):
    m = re.match(r"^---\s*\n(.*?)\n---", read_text(path), re.DOTALL)
    if not m:
        return None
    s = re.search(r"^status\s*:\s*(\w+)", m.group(1), re.MULTILINE)
    return s.group(1) if s else None


def latest_review(reviews_dir: str, prefix: str):
    """(라운드 N, VERDICT, 경로). 리뷰가 없으면 (0, None, None)."""
    best = (0, None, None)
    try:
        names = os.listdir(reviews_dir)
    except OSError:
        return best
    for name in names:
        m = re.fullmatch(rf"{re.escape(prefix)}-r(\d+)\.md", name)
        if m and int(m.group(1)) > best[0]:
            path = os.path.join(reviews_dir, name)
            v = re.search(r"VERDICT:\s*(PASS|REVISE)", read_text(path))
            best = (int(m.group(1)), v.group(1) if v else None, path)
    return best


def review_loop(doc: str, reviews_dir: str, prefix: str) -> tuple:
    """작성 → critic → 수정 루프의 다음 동작. (동작, 라운드, 마지막 VERDICT)

    동작: critic | revise | done. `done` 은 PASS 이거나 라운드를 다 쓴 것이다 —
    후자는 남은 blocking 을 사용자에게 보여야 하므로 호출자가 라운드로 구분한다.
    문서가 마지막 리뷰보다 새로우면 그 리뷰 이후 수정된 것이다.
    """
    n, verdict, review_path = latest_review(reviews_dir, prefix)
    if n == 0 or os.path.getmtime(doc) > os.path.getmtime(review_path):
        return ("critic", n + 1, verdict) if n < MAX_ROUNDS else ("done", n, verdict)
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
        if not exists(epic_dir, ".tc_lock.json"):
            action, n, verdict = review_loop(tc, os.path.join(epic_dir, "reviews"), "tc-critic")
            if action == "critic":
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


def main(argv) -> int:
    if len(argv) >= 2 and argv[0] == "status":
        slug = argv[argv.index("--slug") + 1] if "--slug" in argv[2:] else None
        json.dump(status(argv[1], slug), sys.stdout, ensure_ascii=False)
        return 0
    if len(argv) >= 3 and argv[0] == "slug":
        json.dump({"slug": slugify(argv[1], argv[2])}, sys.stdout, ensure_ascii=False)
        return 0
    fail('사용: harness_state.py status <docs/harness> [--slug S] | slug "<이름>" <docs/harness>')


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
