#!/usr/bin/env python3
"""PRD.md · PLAN.md · TC.md 가 하네스가 요구하는 모양을 갖췄는지 검사하고 TC 를 잠근다.

사용:
    validate_harness_doc.py prd <PRD.md>
    validate_harness_doc.py plan <PLAN.md>
    validate_harness_doc.py tc <TC.md>
    validate_harness_doc.py tc-review-prep <TC.md>   # tc-critic 호출 직전: 검사 + 스냅샷 + 검토 범위
    validate_harness_doc.py tc-lock <TC.md> [--user-approved]
                                                     # TC.md 해시를 .tc_lock.json 에 쓴다
    validate_harness_doc.py tc-check <TC.md>         # 잠금 이후 TC.md 가 바뀌었는지 본다
    (tc · tc-review-prep · tc-lock 은 TC.md 옆의 feature_list.json 을 읽는다.
     다른 경로면 --feature-list <feature_list.json>)

출력: stdout JSON { ok, violations[] } (tc·tc-review-prep 은 warnings[] 도)
종료코드: 0 = 통과, 1 = 위반, 3 = 입력 오류

왜 코드인가. "PLAN 에 Run & Verify 가 있어야 승인한다" 와 "모든 acceptance_criterion 이 TC 로
덮여야 한다" 는 산문으로 적어 두면 컨텍스트 압축과 함께 사라진다. 이 검사는 내용의 좋고 나쁨이
아니라 모양과 추적성만 본다 — 내용의 타당성은 critic 서브에이전트의 몫이다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

# 잠금 이름과 잠금 읽기의 원본은 hooks/ 의 규칙 모듈이다 (제약 11 이 같은 잠금을 본다).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "..", "hooks"))
from _feature_list_rules import TC_LOCK_NAME, tc_locked_sha  # noqa: E402

# (키, 정규식). 한글·영문 제목 어느 쪽이든 인정한다 — 대상 프로젝트의 언어를 강제하지 않는다.
PRD_SECTIONS = [
    ("문제", r"문제|Problem"),
    ("사용자", r"사용자|Users?|Personas?"),
    ("목표와 비목표", r"목표|Goals?"),
    ("요구사항", r"요구사항|Requirements?"),
    ("성공 지표", r"성공 지표|Success"),
    ("리스크와 가정", r"리스크|가정|Risks?|Assumptions?"),
]
PLAN_SECTIONS = [
    ("아키텍처", r"아키텍처|Architecture"),
    ("에픽", r"에픽|Epics?"),
    ("Run & Verify", r"Run\s*(&|and)\s*Verify"),
]
RUN_KEYS = ("start", "test", "e2e")
# 비었거나 TBD 류이거나, 템플릿의 `<...>`·`{...}` 자리표시자가 그대로 남은 값.
EMPTY_VALUE = re.compile(r"^((tbd|todo|n/?a|none|-|—)|[<{].*[>}])?$", re.IGNORECASE)
TC_FIELDS = ("criterion", "type", "precondition", "steps", "expected", "command")
TC_TYPES = {"unit", "integration", "e2e"}
EPIC_ROW = re.compile(r"^\|\s*(\d{2}-[a-z0-9][a-z0-9-]*)\s*\|", re.MULTILINE)
TC_HEADING = re.compile(r"^###\s+(TC-([A-Za-z0-9]+)-(\d+))\s*[:：]?\s*(.*)$")
# 판정은 run_tc.py 가 종료 코드로 한다. 끝에서 종료 코드를 0 으로 덮는 명령은 항상 통과한다.
EXIT_MASK = re.compile(r"(\|\||;)\s*(true|:|exit\s+0)\s*$")
# 이보다 큰 블록은 경고한다. TC.md 는 writer·critic·generator·evaluator 가 모두 읽으므로 블록
# 하나의 군살이 네 번 과금된다. 실측에서 4KB 초과는 블록의 5% 인데 바이트의 26% 를 차지했다.
MAX_BLOCK_BYTES = 4000
REVIEW_PREFIX = "tc-critic"


def out(violations, code_ok=0, **extra) -> int:
    json.dump({"ok": not violations, "violations": violations, **extra}, sys.stdout,
              ensure_ascii=False)
    return 1 if violations else code_ok


def fail(message: str) -> None:
    json.dump({"ok": False, "error": message}, sys.stdout, ensure_ascii=False)
    sys.exit(3)


def read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        fail(f"파일을 읽을 수 없습니다: {exc}")


def read_text(path: str) -> str:
    """없어도 되는 파일을 읽는다 — 못 읽으면 빈 문자열 (harness_state.py · run_tc.py 도 쓴다)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def read_json(path: str):
    """없어도 되는 JSON 을 읽는다 — 못 읽거나 깨졌으면 None."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def unwrap(value: str) -> str:
    """값을 감싼 백틱 한 쌍만 벗긴다 (명령 안의 백틱은 그대로)."""
    value = value.strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    return value


def headings(text: str) -> list:
    return re.findall(r"^#{1,4}\s+(.+?)\s*$", text, re.MULTILINE)


def missing_sections(text: str, required) -> list:
    found = headings(text)
    return [{"detail": f"필수 섹션 없음: {key}"} for key, pattern in required
            if not any(re.search(pattern, h, re.IGNORECASE) for h in found)]


def section_body(text: str, pattern: str) -> str:
    """제목이 pattern 에 맞는 섹션의 본문 (다음 같은 깊이 이하 제목 전까지)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,4})\s+(.+?)\s*$", line)
        if m and re.search(pattern, m.group(2), re.IGNORECASE):
            depth = len(m.group(1))
            body = []
            for nxt in lines[i + 1:]:
                n = re.match(r"^(#{1,4})\s", nxt)
                if n and len(n.group(1)) <= depth:
                    break
                body.append(nxt)
            return "\n".join(body)
    return ""


def check_prd(text: str) -> list:
    return missing_sections(text, PRD_SECTIONS)


def run_keys(plan_text: str) -> dict:
    """PLAN 의 Run & Verify 값 {start, test, e2e}. 줄이 없으면 None (run_tc.py 도 쓴다)."""
    body = section_body(plan_text, r"Run\s*(&|and)\s*Verify")
    values = {}
    for key in RUN_KEYS:
        m = re.search(rf"^\s*[-*]\s*{key}\s*:\s*(.*)$", body, re.MULTILINE | re.IGNORECASE)
        values[key] = unwrap(m.group(1)) if m else None
    return values


def check_plan(text: str) -> list:
    violations = missing_sections(text, PLAN_SECTIONS)
    if not EPIC_ROW.search(section_body(text, r"에픽|Epics?")):
        violations.append({"detail": "에픽 표에 `| NN-slug | ... |` 형식의 행이 없다"})
    for key, value in run_keys(text).items():
        if value is None:
            violations.append({"detail": f"Run & Verify 에 `- {key}: <명령>` 이 없다"})
        elif EMPTY_VALUE.match(value):
            violations.append({"detail": f"Run & Verify 의 {key} 값이 비어 있다"})
    return violations


def parse_tcs(text: str) -> list:
    """`### TC-F001-1: 제목` 블록과 그 아래 `- 필드: 값` 줄들.

    블록은 다음 `#`~`###` 제목에서 끝난다. 끝내지 않으면 `## 제외한 관점` 같은 뒤 절의
    `- command:` 줄이 마지막 TC 의 명령을 덮어쓰고, 러너가 그 명령을 실행한다.
    코드 펜스 안의 `#` 줄은 제목이 아니다.
    """
    tcs = []
    current = None
    fenced = False
    for index, line in enumerate(text.splitlines()):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced:
            h = TC_HEADING.match(line)
            if h:
                current = {"id": h.group(1), "fid": h.group(2), "n": int(h.group(3)),
                           "title": h.group(4), "fields": {}, "start": index, "lines": []}
                tcs.append(current)
            elif re.match(r"^#{1,3}\s", line):
                current = None
        if current is None:
            continue
        current["lines"].append(line)
        f = re.match(r"^\s*[-*]\s*(\w+)\s*:\s*(.*)$", line)
        if f and not fenced and f.group(1).lower() in TC_FIELDS:
            current["fields"][f.group(1).lower()] = f.group(2).strip()
    return tcs


def tc_command(tc: dict) -> str:
    return unwrap(tc["fields"].get("command", ""))


def tc_criteria(tc: dict) -> set:
    """이 TC 가 덮는 acceptance_criteria 번호 (1부터)."""
    return {int(token) for token in re.split(r"[,\s]+", tc["fields"].get("criterion", ""))
            if token.isdigit()}


def tc_warnings(text: str) -> list:
    warnings = []
    for tc in parse_tcs(text):
        size = len("\n".join(tc["lines"]).encode("utf-8"))
        if size > MAX_BLOCK_BYTES:
            warnings.append({"detail": f"{tc['id']} — 블록이 {size}바이트다 "
                                       f"({MAX_BLOCK_BYTES} 초과). steps·expected 를 줄인다"})
    return warnings


def check_tc(text: str, feature_list) -> list:
    violations = []
    features = {f["id"]: f for f in feature_list.get("features", [])
                if isinstance(f, dict) and isinstance(f.get("id"), str)}
    tcs = parse_tcs(text)
    if not tcs:
        return [{"detail": "TC 블록(`### TC-<FID>-<n>: 제목`)이 하나도 없다"}]

    seen = set()
    covered = {fid: set() for fid in features}
    for tc in tcs:
        tid = tc["id"]
        if tid in seen:
            violations.append({"detail": f"{tid} 가 중복이다"})
        seen.add(tid)
        fid = tc["fid"]
        if EXIT_MASK.search(tc_command(tc)):
            violations.append({"detail": f"{tid} — `command` 끝이 종료 코드를 가린다 "
                                         "(판정은 종료 코드로 한다)"})
        if fid not in features:
            violations.append({"detail": f"{tid} — feature_list 에 {fid} 가 없다"})
            continue
        for field in TC_FIELDS:
            value = tc["fields"].get(field, "")
            if EMPTY_VALUE.match(value.strip("`")):
                violations.append({"detail": f"{tid} — `{field}` 가 비어 있다"})
        if tc["fields"].get("type", "").lower() not in TC_TYPES:
            violations.append({"detail": f"{tid} — type 은 {'/'.join(sorted(TC_TYPES))} 중 하나"})
        covered[fid] |= tc_criteria(tc)

    for fid, feature in features.items():
        criteria = feature.get("acceptance_criteria")
        count = len(criteria) if isinstance(criteria, list) else 0
        for index in range(1, count + 1):
            if index not in covered[fid]:
                violations.append({"detail": f"{fid} 의 acceptance_criteria #{index} 를 덮는 TC 가 없다"})
    return violations


def digest(path: str) -> str:
    # 바이트 그대로 해시한다 — criteria 잠금과 달리 공백 한 글자 수정도 "바뀜" 이다. TC 는 확정 뒤
    # 한 글자도 바뀌면 안 되는 문서이고, 표현만 고친 경우도 critic 재검토를 거치게 하려는 의도다.
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def lock_path(tc_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(tc_path)), TC_LOCK_NAME)


def tc_lock_ok(tc_path: str):
    """True = 잠금과 일치, False = 달라졌다, None = 잠금 없음 (harness_state.py 도 쓴다)."""
    stored = tc_locked_sha(os.path.dirname(os.path.abspath(tc_path)))
    try:
        return None if stored is None else stored == digest(tc_path)
    except OSError:
        return None


def latest_review(reviews_dir: str, prefix: str):
    """(라운드 N, VERDICT, 경로). 리뷰가 없으면 (0, None, None). harness_state.py 도 쓴다."""
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


def reviews_dir_of(tc_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(tc_path)), "reviews")


def snapshot_path(reviews_dir: str, prefix: str, n: int) -> str:
    return os.path.join(reviews_dir, f"{prefix}-r{n}.blocks.json")


def read_snapshot(reviews_dir: str, prefix: str, n: int):
    """라운드 N 리뷰가 본 문서의 지문. 없거나 깨졌으면 None."""
    snap = read_json(snapshot_path(reviews_dir, prefix, n))
    return snap if isinstance(snap, dict) and isinstance(snap.get("sha256"), str) else None


def changed_since_review(doc: str, reviews_dir: str, prefix: str, n: int):
    """리뷰 r{n} 이 본 내용과 지금 문서가 다른가 (내용 해시 비교).

    그 리뷰에 스냅샷이 없으면 None — 판정할 근거가 없으니 호출자가 옛 판정으로 물러난다
    (이 검사 이전에 시작한 작업, 또는 tc-review-prep 을 건너뛴 라운드). harness_state.py 도 쓴다.
    """
    snapshot = read_snapshot(reviews_dir, prefix, n)
    return None if snapshot is None else snapshot["sha256"] != digest(doc)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_snapshot(tc_path: str, text: str) -> dict:
    """블록별 지문과, 블록 밖 본문(머리말·`## 제외한 관점` 등)의 지문."""
    tcs = parse_tcs(text)
    in_block = {tc["start"] + offset for tc in tcs for offset in range(len(tc["lines"]))}
    rest = "\n".join(line for index, line in enumerate(text.splitlines())
                     if index not in in_block)
    return {"sha256": digest(tc_path), "rest": _sha(rest),
            "blocks": {tc["id"]: _sha("\n".join(tc["lines"]).rstrip()) for tc in tcs}}


def scope_markdown(text: str, feature_list: dict, n: int, previous: dict, snapshot: dict) -> str:
    """2라운드부터 tc-critic 이 읽는 검토 범위. 바뀐 블록이 속한 기능의 블록을 통째로 싣는다 —
    바뀐 블록만 떼어 주면 같은 기능의 이웃 TC 와 겹치는지 볼 수 없다."""
    old, new = previous["blocks"], snapshot["blocks"]
    changed = [i for i in new if i in old and new[i] != old[i]]
    added = [i for i in new if i not in old]
    removed = [i for i in old if i not in new]
    tcs = parse_tcs(text)
    touched = set(changed) | set(added)
    fids = sorted({tc["fid"] for tc in tcs if tc["id"] in touched})
    lines = [f"# tc-critic r{n} 검토 범위 (기계 생성 — 고치지 않는다)", "",
             f"직전 리뷰: `{REVIEW_PREFIX}-r{n - 1}.md`", "",
             f"- 변경: {', '.join(changed) or '없음'}",
             f"- 추가: {', '.join(added) or '없음'}",
             f"- 삭제: {', '.join(removed) or '없음'}",
             "- 블록 밖 본문: " + ("바뀜 — TC.md 의 머리말과 `## ` 절을 다시 읽는다"
                                 if previous.get("rest") != snapshot["rest"] else "그대로"),
             "", "## 추적성 (기계 판정)", "", "| 기능 | criterion # | TC |", "|---|---|---|"]
    features = {f.get("id"): f for f in feature_list.get("features", []) if isinstance(f, dict)}
    for fid in fids:
        criteria = features.get(fid, {}).get("acceptance_criteria") or []
        for index in range(1, len(criteria) + 1):
            covering = [tc["id"] for tc in tcs if tc["fid"] == fid and index in tc_criteria(tc)]
            lines.append(f"| {fid} | {index} | {', '.join(covering)} |")
    lines += ["", "## 범위 기능의 블록", ""]
    for tc in tcs:
        if tc["fid"] in fids:
            mark = "  <!-- 이번 라운드에 바뀜 -->" if tc["id"] in touched else ""
            lines += [tc["lines"][0] + mark, *tc["lines"][1:], ""]
    return "\n".join(lines).rstrip() + "\n"


def review_prep(tc_path: str, text: str, feature_list: dict) -> int:
    """tc-critic 을 부르기 직전의 한 번 — 이 라운드가 볼 내용의 스냅샷을 남기고, 직전 라운드의
    스냅샷이 있으면 그 뒤에 바뀐 블록만 담은 검토 범위(`scope_file`)를 쓴다."""
    violations = check_tc(text, feature_list)
    warnings = tc_warnings(text)
    if violations:
        return out(violations, warnings=warnings)
    reviews = reviews_dir_of(tc_path)
    n = latest_review(reviews, REVIEW_PREFIX)[0] + 1
    snapshot = build_snapshot(tc_path, text)
    previous = read_snapshot(reviews, REVIEW_PREFIX, n - 1)
    scope_file = None
    try:
        os.makedirs(reviews, exist_ok=True)
        if previous and isinstance(previous.get("blocks"), dict):
            scope_file = os.path.join(reviews, f"{REVIEW_PREFIX}-r{n}.scope.md")
            with open(scope_file, "w", encoding="utf-8") as fh:
                fh.write(scope_markdown(text, feature_list, n, previous, snapshot))
        with open(snapshot_path(reviews, REVIEW_PREFIX, n), "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh)
    except OSError as exc:
        fail(f"리뷰 디렉토리에 쓸 수 없습니다: {exc}")
    return out([], warnings=warnings, round=n, scope_file=scope_file)


def lock_violations(tc_path: str) -> list:
    """잠글 수 있는가 — 지금 내용이 tc-critic 의 PASS 를 받은 그 내용인가.

    스냅샷이 없는 리뷰(이 검사 이전에 시작한 작업)는 VERDICT 만 본다.
    """
    reviews = reviews_dir_of(tc_path)
    n, verdict, _ = latest_review(reviews, REVIEW_PREFIX)
    if verdict != "PASS":
        return [{"detail": "최신 tc-critic 리뷰가 PASS 가 아니다 — 잠글 수 없다"}]
    if changed_since_review(tc_path, reviews, REVIEW_PREFIX, n):
        return [{"detail": f"tc-critic r{n} PASS 이후 TC.md 가 바뀌었다 — 재검토가 필요하다"}]
    return []


def read_feature_list(path: str) -> dict:
    try:
        feature_list = json.loads(read(path))
    except ValueError as exc:
        fail(f"feature_list JSON 파싱 실패: {exc}")
    return feature_list if isinstance(feature_list, dict) else {}


def load_feature_list(argv, tc_path: str) -> dict:
    """`--feature-list` 가 없으면 TC.md 옆의 feature_list.json — 에픽 디렉토리의 고정 배치다."""
    path = os.path.join(os.path.dirname(os.path.abspath(tc_path)), "feature_list.json")
    if "--feature-list" in argv:
        index = argv.index("--feature-list") + 1
        if index >= len(argv):
            fail("--feature-list 뒤에 경로가 필요합니다.")
        path = argv[index]
    return read_feature_list(path)


def main(argv) -> int:
    commands = {"prd", "plan", "tc", "tc-review-prep", "tc-lock", "tc-check"}
    if len(argv) < 2 or argv[0] not in commands:
        fail("사용: validate_harness_doc.py prd|plan|tc|tc-review-prep|tc-lock|tc-check <파일> "
             "[--feature-list <feature_list.json>] [--user-approved]")
    cmd, path = argv[0], argv[1]
    text = read(path)

    if cmd == "prd":
        return out(check_prd(text))
    if cmd == "plan":
        return out(check_plan(text))
    if cmd == "tc":
        return out(check_tc(text, load_feature_list(argv, path)), warnings=tc_warnings(text))
    if cmd == "tc-review-prep":
        return review_prep(path, text, load_feature_list(argv, path))
    if cmd == "tc-lock":
        # 러너는 잠금만 믿고 명령을 실행한다. 그래서 모양이 깨진 TC 는 어떤 경로로도 잠기지
        # 않는다. --user-approved 가 면제하는 것은 critic 의 VERDICT 뿐이다 — 에스컬레이션에서
        # 사용자가 남은 지적을 안고 잠그기로 한 경우.
        violations = check_tc(text, load_feature_list(argv, path))
        if "--user-approved" not in argv:
            violations += lock_violations(path)
        if violations:
            return out(violations)
        try:
            with open(lock_path(path), "w", encoding="utf-8") as fh:
                json.dump({"sha256": digest(path)}, fh)
        except OSError as exc:
            fail(f"잠금 파일을 쓸 수 없습니다: {exc}")
        return out([])
    state = tc_lock_ok(path)  # tc-check
    if state is None:
        return out([{"detail": "잠금이 없다 — TC 가 아직 확정되지 않았다"}])
    return out([] if state else [{"detail": "TC.md 가 확정(잠금) 이후 바뀌었다 — tc-critic 재검토가 필요하다"}])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
