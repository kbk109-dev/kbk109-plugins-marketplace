#!/usr/bin/env python3
"""
compute_next_patch.py — Release Plan DB의 버전 목록에서 최고 버전을 찾아
patch 자리만 +1 증가시킨 새 버전을 계산한다.

입력:  stdin JSON 또는 argv — 버전 문자열 배열
출력:  stdout JSON { latest_version, new_version, warnings[], ignored[] }
종료코드: 0 = 정상, 2 = 유효 버전 없음(사용자 확인 필요), 3 = 입력 오류

규칙:
- X.Y.Z 형식만 정상 파싱.
- pre-release 태그(`-rc1`, `-alpha.2`)가 있는 값은 무시하고 warnings에 기록.
- build metadata(`+build.5`)는 strip 후 X.Y.Z로 비교.
- major/minor는 절대 변경하지 않는다. patch만 +1.
"""
import json
import re
import sys

SEMVER_CORE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
SEMVER_EXT = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$")


def parse(versions):
    valid = []
    ignored = []
    warnings = []
    for raw in versions:
        v = raw.strip().lstrip("v").lstrip("V")
        if not v:
            continue
        m_core = SEMVER_CORE.match(v)
        if m_core:
            valid.append((tuple(int(x) for x in m_core.groups()), raw))
            continue
        m_ext = SEMVER_EXT.match(v)
        if m_ext:
            major, minor, patch, pre, build = m_ext.groups()
            if pre:
                ignored.append(raw)
                warnings.append(f"pre-release 태그 무시: {raw}")
                continue
            # build metadata만 있는 경우 strip 후 반영
            warnings.append(f"build metadata strip: {raw} → {major}.{minor}.{patch}")
            valid.append(((int(major), int(minor), int(patch)), raw))
            continue
        ignored.append(raw)
        warnings.append(f"파싱 실패 — 무시: {raw}")
    return valid, ignored, warnings


def main():
    try:
        if not sys.stdin.isatty():
            data = sys.stdin.read().strip()
            versions = json.loads(data) if data else []
        else:
            versions = sys.argv[1:]
    except json.JSONDecodeError as e:
        json.dump({"error": f"입력 JSON 파싱 실패: {e}"}, sys.stdout, ensure_ascii=False)
        sys.exit(3)

    if not isinstance(versions, list):
        json.dump({"error": "입력은 버전 문자열 배열이어야 합니다."}, sys.stdout, ensure_ascii=False)
        sys.exit(3)

    valid, ignored, warnings = parse(versions)

    if not valid:
        json.dump(
            {
                "latest_version": None,
                "new_version": None,
                "warnings": warnings,
                "ignored": ignored,
                "note": "유효 X.Y.Z 버전 없음 — 사용자 확인 필요",
            },
            sys.stdout,
            ensure_ascii=False,
        )
        sys.exit(2)

    valid.sort(key=lambda t: t[0])
    (maj, minor, patch), latest_raw = valid[-1]
    new_version = f"{maj}.{minor}.{patch + 1}"

    json.dump(
        {
            "latest_version": f"{maj}.{minor}.{patch}",
            "latest_raw": latest_raw,
            "new_version": new_version,
            "warnings": warnings,
            "ignored": ignored,
        },
        sys.stdout,
        ensure_ascii=False,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
