#!/usr/bin/env python3
"""확정된 TC 의 `command` 를 실행해 TC 마다 로그를, 실행마다 요약을 남긴다.

사용:
    run_tc.py <epic_dir> --feature <FID>          # 증거: logs/<FID>/<n>.log + summary.json
    run_tc.py <epic_dir> --regression <FID>       # 직접 의존 기능의 TC + PLAN `test` 1회
                                                  #   → logs/_regression/<FID>/
    run_tc.py <epic_dir> (--feature <FID> | --all) --out _<이름>
                                                  # 증거가 아닌 실행 → logs/_<이름>/<TC-id>.log
    공통: [--cwd <프로젝트 루트>] [--timeout 300] [--budget-seconds 540] [--resume]

출력: stdout JSON { ok, complete, total, passed, failed[], remaining, summary, logs[] }
종료코드: 0 = 전부 통과, 1 = 실패 있음, 2 = 미완 (--resume 으로 이어 간다),
          3 = 입력 오류 · TC 잠금 불일치

왜 코드인가. 명령을 하나씩 실행하고 출력을 로그로 옮겨 적는 일에는 판단이 없다. 모델이 하면
TC 수만큼 턴이 들고, 옮겨 적는 동안 요약하거나 빠뜨릴 수 있다. 여기서 실행하면 로그는 실제
출력 그대로이고, evaluator 는 테스트가 기대 결과를 정말 검증하는지 보는 데 시간을 쓴다.

증거가 아닌 실행의 로그는 `logs/_…/` 아래에만 쓴다 — 제약 11 이 `logs/<FID>/` 접두를 증거로
인정하므로, 회귀나 generator 의 자가 점검 로그가 증거로 쓰일 수 없게 이름공간을 가른다.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "..", "..", "hooks"))
from _feature_list_rules import RUN_SUMMARY_NAME  # noqa: E402
from validate_harness_doc import (  # noqa: E402
    digest,
    fail,
    parse_tcs,
    read,
    read_feature_list,
    read_json,
    read_text,
    run_keys,
    tc_command,
    tc_lock_ok,
)

TAIL_LINES = 100
TAIL_BYTES = 256 * 1024
OUT_NAME = re.compile(r"_[A-Za-z0-9_-]*(/[A-Za-z0-9_-]+)*")


class Interrupted(Exception):
    """SIGTERM — Bash 도구가 제한 시간에 걸려 끊었다. 지금까지를 남기고 미완으로 끝낸다."""


def parse_args(argv) -> dict:
    opts = {"feature": None, "all": False, "regression": None, "out": None, "cwd": os.getcwd(),
            "timeout": 300.0, "budget": 540.0, "resume": False}
    if not argv or argv[0].startswith("--"):
        fail("사용: run_tc.py <epic_dir> --feature <FID> | --regression <FID> | "
             "(--feature <FID> | --all) --out _<이름>")
    opts["epic_dir"] = os.path.abspath(argv[0])
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg in ("--all", "--resume"):
            opts[arg[2:]] = True
            i += 1
            continue
        if arg not in ("--feature", "--regression", "--out", "--cwd", "--timeout",
                       "--budget-seconds"):
            fail(f"알 수 없는 인자: {arg}")
        if i + 1 >= len(argv):
            fail(f"{arg} 뒤에 값이 필요합니다.")
        key = "budget" if arg == "--budget-seconds" else arg[2:]
        try:
            opts[key] = float(argv[i + 1]) if key in ("timeout", "budget") else argv[i + 1]
        except ValueError:
            fail(f"{arg} 는 숫자여야 합니다.")
        i += 2
    return opts


def select(opts: dict, tcs: list) -> tuple:
    """(선택 이름, 로그 디렉토리 상대 경로, [(id, 명령, 로그 파일 이름)])."""
    epic_dir, fid = opts["epic_dir"], opts["feature"]
    if sum((bool(fid), opts["all"], bool(opts["regression"]))) != 1:
        fail("--feature · --all · --regression 중 하나만 준다.")

    def items(chosen, name_key="id"):
        return [(tc["id"], tc_command(tc), f"{tc[name_key]}.log") for tc in chosen]

    if opts["regression"]:
        if opts["out"]:
            fail("--regression 은 --out 을 받지 않는다.")
        fid = opts["regression"]
        listed = read_feature_list(os.path.join(epic_dir, "feature_list.json")).get("features", [])
        feature = next((f for f in listed if isinstance(f, dict) and f.get("id") == fid), None)
        if feature is None:
            fail(f"feature_list 에 {fid} 가 없다.")
        deps = set(feature.get("dependencies") or [])
        chosen = items([tc for tc in tcs if tc["fid"] in deps])
        suite = run_keys(read_text(os.path.join(epic_dir, "..", "..", "PLAN.md"))).get("test")
        if suite:
            chosen.append(("PLAN-test", suite, "PLAN-test.log"))
        return f"regression:{fid}", f"logs/_regression/{fid}", chosen

    chosen = tcs if opts["all"] else [tc for tc in tcs if tc["fid"] == fid]
    if not chosen:
        fail(f"TC 가 없는 기능: {fid}" if fid else "TC 가 하나도 없다.")
    name = "all" if opts["all"] else f"feature:{fid}"
    if opts["out"]:
        if not OUT_NAME.fullmatch(opts["out"]):
            fail("--out 은 `_` 로 시작하는 이름이어야 한다 (예: _epic, _self/F001). "
                 "`logs/<FID>/` 는 증거 자리다.")
        return name, f"logs/{opts['out']}", items(chosen)
    if opts["all"]:
        fail("증거 실행은 기능 하나만 받는다. --all 은 --out _<이름> 이 필요하다.")
    return name, f"logs/{fid}", items(chosen, "n")


def tail(path: str) -> str:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - TAIL_BYTES))
            data = fh.read()
    except OSError:
        return ""
    return "\n".join(data.decode("utf-8", errors="replace").splitlines()[-TAIL_LINES:])


def kill_group(proc) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def run_one(tc_id: str, command: str, log_path: str, cwd: str, timeout: float) -> dict:
    """명령 하나를 실행하고 로그를 쓴다.

    출력은 파이프가 아니라 파일로 받는다 — 명령이 남긴 백그라운드 자식이 파이프를 쥐고 있으면
    본 명령이 끝나도 읽기가 끝나지 않는다. 끝나면 프로세스 그룹을 통째로 정리해, TC 가 남긴
    고아 프로세스가 다음 TC 의 포트를 잡고 있지 않게 한다.
    """
    raw_path = log_path + ".out"
    started = time.monotonic()
    timed_out = False
    with open(raw_path, "wb") as raw:
        proc = subprocess.Popen(["bash", "-c", command], cwd=cwd, stdout=raw,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                start_new_session=True)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out, code = True, 124
        except Interrupted:
            os.remove(raw_path)
            raise
        finally:
            kill_group(proc)
            proc.wait()
    seconds = round(time.monotonic() - started, 1)
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write(f"TC: {tc_id}\ncommand: {command}\nexit: {code}\nseconds: {seconds}\n"
                 f"timed_out: {str(timed_out).lower()}\n"
                 f"--- output (last {TAIL_LINES} lines) ---\n{tail(raw_path)}\n")
    os.remove(raw_path)
    return {"id": tc_id, "exit": code, "seconds": seconds, "timed_out": timed_out}


def write_summary(path: str, summary: dict, total: int) -> list:
    """지금까지의 결과로 요약을 다시 쓰고 실패한 TC id 를 돌려준다. TC 하나가 끝날 때마다
    부른다 — 호출이 중간에 끊겨도 디스크의 요약이 그 시점까지는 맞아야 `--resume` 이 이어 간다."""
    results = summary["results"]
    failed = [r["id"] for r in results if r.get("exit") != 0]
    summary.update(total=total, complete=len(results) == total, failed=len(failed))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return failed


def on_sigterm(signum, frame):
    raise Interrupted()


def main(argv) -> int:
    opts = parse_args(argv)
    epic_dir = opts["epic_dir"]
    tc_path = os.path.join(epic_dir, "TC.md")
    if not os.path.isfile(tc_path):
        fail("TC.md 가 없다 — 레거시 레이아웃은 러너를 쓰지 않는다.")
    if tc_lock_ok(tc_path) is not True:
        fail("TC 잠금이 없거나 TC.md 가 잠금 이후 바뀌었다 — 확정된 TC 만 실행한다.")
    sha = digest(tc_path)

    selection, rel_dir, items = select(opts, parse_tcs(read(tc_path)))
    out_dir = os.path.join(epic_dir, rel_dir)
    summary_path = os.path.join(out_dir, RUN_SUMMARY_NAME)
    summary = {"selection": selection, "tc_sha256": sha, "results": []}

    if opts["resume"]:
        previous = read_json(summary_path)
        if not isinstance(previous, dict) or previous.get("complete") is not False \
                or previous.get("selection") != selection or previous.get("tc_sha256") != sha:
            fail("이어 갈 실행이 없다 (요약이 없거나, 이미 끝났거나, 선택·TC 가 다르다).")
        summary["results"] = [r for r in previous.get("results", []) if isinstance(r, dict)]
    else:
        os.makedirs(out_dir, exist_ok=True)
        for _, _, log_name in items:  # 지난 실행의 로그가 이번 결과처럼 읽히지 않게 한다
            try:
                os.remove(os.path.join(out_dir, log_name))
            except OSError:
                pass

    done = {r.get("id") for r in summary["results"]}
    signal.signal(signal.SIGTERM, on_sigterm)
    started = time.monotonic()
    ran = 0
    try:
        for tc_id, command, log_name in items:
            if tc_id in done:
                continue
            # 이 호출의 첫 TC 는 무조건 돈다. 그다음부터는 timeout 만큼 예산이 남았을 때만 시작한다.
            if ran and time.monotonic() - started + opts["timeout"] > opts["budget"]:
                break
            result = run_one(tc_id, command, os.path.join(out_dir, log_name),
                             opts["cwd"], opts["timeout"])
            result["log"] = f"{rel_dir}/{log_name}"
            summary["results"].append(result)
            ran += 1
            write_summary(summary_path, summary, len(items))
    except Interrupted:
        pass
    signal.signal(signal.SIGTERM, signal.SIG_IGN)  # 요약을 쓰는 동안 다시 끊기지 않게

    failed = write_summary(summary_path, summary, len(items))
    results = summary["results"]
    json.dump({"ok": summary["complete"] and not failed, "complete": summary["complete"],
               "total": len(items), "passed": len(results) - len(failed), "failed": failed,
               "remaining": len(items) - len(results),
               "summary": f"{rel_dir}/{RUN_SUMMARY_NAME}",
               "logs": [r["log"] for r in results if "log" in r]},
              sys.stdout, ensure_ascii=False)
    if not summary["complete"]:
        return 2
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
