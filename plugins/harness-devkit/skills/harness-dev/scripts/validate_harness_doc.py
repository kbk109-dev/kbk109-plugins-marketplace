#!/usr/bin/env python3
"""PRD.md · PLAN.md · TC.md 가 하네스가 요구하는 모양을 갖췄는지 검사하고 TC 를 잠근다.

사용:
    validate_harness_doc.py prd <PRD.md>
    validate_harness_doc.py plan <PLAN.md>
    validate_harness_doc.py tc <TC.md> --feature-list <feature_list.json>
    validate_harness_doc.py tc-lock <TC.md>      # TC.md 해시를 .tc_lock.json 에 쓴다
    validate_harness_doc.py tc-check <TC.md>     # 잠금 이후 TC.md 가 바뀌었는지 본다

출력: stdout JSON { ok, violations[] }
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

LOCK_NAME = ".tc_lock.json"

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


def out(violations, code_ok=0) -> int:
    json.dump({"ok": not violations, "violations": violations}, sys.stdout, ensure_ascii=False)
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


def check_plan(text: str) -> list:
    violations = missing_sections(text, PLAN_SECTIONS)
    if not EPIC_ROW.search(section_body(text, r"에픽|Epics?")):
        violations.append({"detail": "에픽 표에 `| NN-slug | ... |` 형식의 행이 없다"})
    body = section_body(text, r"Run\s*(&|and)\s*Verify")
    for key in RUN_KEYS:
        m = re.search(rf"^\s*[-*]\s*{key}\s*:\s*(.*)$", body, re.MULTILINE | re.IGNORECASE)
        value = m.group(1).strip().strip("`").strip() if m else None
        if value is None:
            violations.append({"detail": f"Run & Verify 에 `- {key}: <명령>` 이 없다"})
        elif EMPTY_VALUE.match(value):
            violations.append({"detail": f"Run & Verify 의 {key} 값이 비어 있다"})
    return violations


def parse_tcs(text: str) -> list:
    """`### TC-F001-1: 제목` 블록과 그 아래 `- 필드: 값` 줄들."""
    tcs = []
    current = None
    for line in text.splitlines():
        h = re.match(r"^###\s+(TC-[A-Za-z0-9]+-\d+)\s*[:：]?\s*(.*)$", line)
        if h:
            current = {"id": h.group(1), "title": h.group(2), "fields": {}}
            tcs.append(current)
            continue
        if current is None:
            continue
        f = re.match(r"^\s*[-*]\s*(\w+)\s*:\s*(.*)$", line)
        if f and f.group(1).lower() in TC_FIELDS:
            current["fields"][f.group(1).lower()] = f.group(2).strip()
    return tcs


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
        fid = tid.split("-")[1]
        if fid not in features:
            violations.append({"detail": f"{tid} — feature_list 에 {fid} 가 없다"})
            continue
        for field in TC_FIELDS:
            value = tc["fields"].get(field, "")
            if EMPTY_VALUE.match(value.strip("`")):
                violations.append({"detail": f"{tid} — `{field}` 가 비어 있다"})
        if tc["fields"].get("type", "").lower() not in TC_TYPES:
            violations.append({"detail": f"{tid} — type 은 {'/'.join(sorted(TC_TYPES))} 중 하나"})
        for token in re.split(r"[,\s]+", tc["fields"].get("criterion", "")):
            if token.isdigit():
                covered[fid].add(int(token))

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
    return os.path.join(os.path.dirname(os.path.abspath(tc_path)), LOCK_NAME)


def tc_lock_ok(tc_path: str):
    """True = 잠금과 일치, False = 달라졌다, None = 잠금 없음 (harness_state.py 도 쓴다)."""
    try:
        with open(lock_path(tc_path), "r", encoding="utf-8") as fh:
            stored = json.load(fh).get("sha256")
        return stored == digest(tc_path)
    except (OSError, ValueError, AttributeError):
        return None


def main(argv) -> int:
    if len(argv) < 2 or argv[0] not in {"prd", "plan", "tc", "tc-lock", "tc-check"}:
        fail("사용: validate_harness_doc.py prd|plan|tc|tc-lock|tc-check <파일> "
             "[--feature-list <feature_list.json>]")
    cmd, path = argv[0], argv[1]
    text = read(path)

    if cmd == "prd":
        return out(check_prd(text))
    if cmd == "plan":
        return out(check_plan(text))
    if cmd == "tc":
        if "--feature-list" not in argv or argv.index("--feature-list") + 1 >= len(argv):
            fail("tc 는 --feature-list <feature_list.json> 이 필요합니다.")
        try:
            feature_list = json.loads(read(argv[argv.index("--feature-list") + 1]))
        except ValueError as exc:
            fail(f"feature_list JSON 파싱 실패: {exc}")
        return out(check_tc(text, feature_list if isinstance(feature_list, dict) else {}))
    if cmd == "tc-lock":
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
