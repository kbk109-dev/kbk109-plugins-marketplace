#!/usr/bin/env python3
"""Deterministic scanner for `docs/skills/release-impl/v*/` previous-version context.

Replaces the manual Phase 1 Step 2 procedure where the LLM directly read every
prior version's feature_list.json + PROGRESS.md and assembled previous_context
by hand. The script produces a JSON list of *candidate* previous_context
entries; the LLM still applies relevance filtering. This script does not judge
relevance — it just hands the model a structured candidate set so a single
Bash invocation replaces N×M Read calls.

Optionally emits a digest (`previous_context_digest.json`) into the current
version directory so the next release can read a small digest instead of
re-walking the whole tree. Drift is detected by recording sha256 of every
source file and rejecting the digest at consume-time if any file changed.

Modes:
    scan    list previous versions and emit candidate previous_context
    digest  scan + write a digest file
    consume read a digest file (verifying source sha256), fall back to scan

Outputs JSON to stdout.

Usage:
    python3 scan_previous_versions.py scan    <root> [--current vX.Y.Z] [--limit K]
    python3 scan_previous_versions.py digest  <root> --current vX.Y.Z [--limit K] --out <digest_path>
    python3 scan_previous_versions.py consume <digest_path>

Where:
    <root>          docs/skills/release-impl/   (parent of v*/ directories)
    --current       skip this version when scanning
    --limit K       take at most K most-recent prior versions (default: unlimited)
    --out           digest file path; defaults to {root}/{current}/previous_context_digest.json

Exit codes:
    0  success (stdout = JSON)
    1  invalid input (missing paths, bad version, drift)
    2  usage error
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

VERSION_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
ALLOWED_TYPES = {"blocked_task", "known_issue", "architecture_decision", "dependency"}


def _semver_key(name: str) -> tuple[int, int, int] | None:
    m = VERSION_RE.match(name)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _list_versions(root: Path, current: str | None) -> list[str]:
    if not root.is_dir():
        return []
    versions: list[tuple[tuple[int, int, int], str]] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        key = _semver_key(child.name)
        if key is None:
            continue
        if current is not None and child.name == current:
            continue
        versions.append((key, child.name))
    versions.sort(key=lambda x: x[0], reverse=True)
    return [name for _, name in versions]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _extract_blocked_tasks(version: str, fl: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for task in fl.get("tasks", []) or []:
        if not isinstance(task, dict):
            continue
        status = task.get("status")
        feedback = task.get("evaluator_feedback")
        if status != "blocked":
            continue
        summary = (
            f"{task.get('id', '')} {task.get('title', '')}".strip()
            or task.get("id", "")
            or "unnamed"
        )
        relevance_bits = []
        if isinstance(feedback, str) and feedback.strip():
            relevance_bits.append(feedback.strip())
        out.append({
            "version": version,
            "type": "blocked_task",
            "source": f"{version}/feature_list.json#tasks.{task.get('id', '?')}",
            "summary": summary,
            "relevance": " | ".join(relevance_bits) if relevance_bits else "blocked 상태로 종료 — 이번 버전에서 영역이 겹치면 evaluator_feedback 확인 필요",
        })
    return out


_ISSUES_HEADER_RE = re.compile(r"^##\s*발견된\s*이슈\s*$", re.MULTILINE)
_ARCH_HEADER_RE = re.compile(r"^##\s*아키텍처\s*결정\s*$", re.MULTILINE)
_DEP_HEADER_RE = re.compile(r"^##\s*(?:의존성|Dependencies)\s*(?:변경|Changes)?\s*$", re.MULTILINE)
_NEXT_HEADER_RE = re.compile(r"^##\s+", re.MULTILINE)


def _slice_section(text: str, header_re: re.Pattern[str]) -> str | None:
    m = header_re.search(text)
    if not m:
        return None
    start = m.end()
    rest = text[start:]
    nxt = _NEXT_HEADER_RE.search(rest)
    body = rest[: nxt.start()] if nxt else rest
    return body.strip()


_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$")


def _bullets(body: str) -> list[str]:
    out: list[str] = []
    for line in body.splitlines():
        m = _BULLET_RE.match(line)
        if not m:
            continue
        item = m.group(1).strip()
        if item and item != "(없음)":
            out.append(item)
    return out


def _extract_known_issues(version: str, progress_text: str) -> list[dict[str, Any]]:
    section = _slice_section(progress_text, _ISSUES_HEADER_RE)
    if not section:
        return []
    items = _bullets(section)
    if not items:
        return []
    return [
        {
            "version": version,
            "type": "known_issue",
            "source": f"{version}/PROGRESS.md#발견된-이슈",
            "summary": item[:240],
            "relevance": "같은 영역을 건드리는 task에서 동일 함정 회피",
        }
        for item in items
    ]


def _extract_architecture_decisions(version: str, progress_text: str) -> list[dict[str, Any]]:
    section = _slice_section(progress_text, _ARCH_HEADER_RE)
    if not section:
        return []
    items = _bullets(section)
    if not items:
        return []
    return [
        {
            "version": version,
            "type": "architecture_decision",
            "source": f"{version}/PROGRESS.md#아키텍처-결정",
            "summary": item[:240],
            "relevance": "이미 세워진 디렉토리·경로·패턴을 따른다",
        }
        for item in items
    ]


def _extract_dependency_changes(version: str, progress_text: str) -> list[dict[str, Any]]:
    section = _slice_section(progress_text, _DEP_HEADER_RE)
    if not section:
        return []
    items = _bullets(section)
    if not items:
        return []
    return [
        {
            "version": version,
            "type": "dependency",
            "source": f"{version}/PROGRESS.md#의존성-변경",
            "summary": item[:240],
            "relevance": "추가·제거된 라이브러리·초기화 코드 위치",
        }
        for item in items
    ]


def _scan_version(root: Path, version: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Return (candidates, source_file_hashes) for a single version dir."""
    vdir = root / version
    candidates: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}

    fl_path = vdir / "feature_list.json"
    if fl_path.is_file():
        hashes[f"{version}/feature_list.json"] = _sha256_file(fl_path)
        fl = _read_json(fl_path)
        if isinstance(fl, dict):
            candidates.extend(_extract_blocked_tasks(version, fl))

    pg_path = vdir / "PROGRESS.md"
    if pg_path.is_file():
        hashes[f"{version}/PROGRESS.md"] = _sha256_file(pg_path)
        text = _read_text(pg_path)
        if text:
            candidates.extend(_extract_known_issues(version, text))
            candidates.extend(_extract_architecture_decisions(version, text))
            candidates.extend(_extract_dependency_changes(version, text))

    return candidates, hashes


def _do_scan(root: Path, current: str | None, limit: int | None) -> dict[str, Any]:
    versions = _list_versions(root, current)
    if limit is not None and limit >= 0:
        versions = versions[:limit]
    all_candidates: list[dict[str, Any]] = []
    all_hashes: dict[str, str] = {}
    for v in versions:
        cands, hashes = _scan_version(root, v)
        all_candidates.extend(cands)
        all_hashes.update(hashes)

    for entry in all_candidates:
        t = entry.get("type")
        if t not in ALLOWED_TYPES:
            raise ValueError(f"internal: produced invalid type {t!r}")

    return {
        "schema": "release-impl/previous_context_digest@1",
        "root": str(root),
        "current": current,
        "scanned_versions": versions,
        "limit": limit,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "source_files_sha256": all_hashes,
        "candidates": all_candidates,
    }


def _do_consume(digest_path: Path) -> dict[str, Any]:
    if not digest_path.is_file():
        raise FileNotFoundError(f"digest not found: {digest_path}")
    digest = _read_json(digest_path)
    if not isinstance(digest, dict):
        raise ValueError(f"digest invalid JSON: {digest_path}")
    if digest.get("schema") != "release-impl/previous_context_digest@1":
        raise ValueError(f"digest schema unknown: {digest.get('schema')!r}")
    root = Path(digest.get("root", ""))
    if not root.is_dir():
        raise FileNotFoundError(f"digest.root no longer exists: {root}")

    drift: list[str] = []
    for rel, recorded in (digest.get("source_files_sha256") or {}).items():
        actual_path = root / rel
        if not actual_path.is_file():
            drift.append(f"missing: {rel}")
            continue
        actual = _sha256_file(actual_path)
        if actual != recorded:
            drift.append(f"changed: {rel}")
    if drift:
        return {
            "status": "drift",
            "digest_path": str(digest_path),
            "reasons": drift,
            "candidates": [],
        }
    digest["status"] = "ok"
    digest["digest_path"] = str(digest_path)
    return digest


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="scan_previous_versions.py", add_help=True)
    sub = p.add_subparsers(dest="mode", required=True)

    sp_scan = sub.add_parser("scan", help="emit candidate previous_context to stdout")
    sp_scan.add_argument("root", type=Path)
    sp_scan.add_argument("--current", type=str, default=None)
    sp_scan.add_argument("--limit", type=int, default=None)

    sp_digest = sub.add_parser("digest", help="scan + write digest file")
    sp_digest.add_argument("root", type=Path)
    sp_digest.add_argument("--current", type=str, required=True)
    sp_digest.add_argument("--limit", type=int, default=None)
    sp_digest.add_argument("--out", type=Path, default=None)

    sp_consume = sub.add_parser("consume", help="read a digest file (verify drift)")
    sp_consume.add_argument("digest_path", type=Path)

    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    try:
        args = _parse_args(argv[1:])
    except SystemExit as exc:
        return int(getattr(exc, "code", 2) or 2)

    try:
        if args.mode == "scan":
            payload = _do_scan(args.root, args.current, args.limit)
        elif args.mode == "digest":
            current = args.current
            if VERSION_RE.match(current) is None:
                print(f"--current must match ^v\\d+\\.\\d+\\.\\d+$ (got {current!r})", file=sys.stderr)
                return 1
            payload = _do_scan(args.root, current, args.limit)
            out = args.out or (args.root / current / "previous_context_digest.json")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            payload = {**payload, "written_to": str(out)}
        elif args.mode == "consume":
            payload = _do_consume(args.digest_path)
        else:
            print(f"unknown mode: {args.mode}", file=sys.stderr)
            return 2
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
