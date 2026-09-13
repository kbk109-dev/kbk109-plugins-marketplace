#!/usr/bin/env python3
"""
compute_next_versions.py — git 태그와 프로젝트 매니페스트의 버전 목록에서 기준선을 정하고
다음 patch / minor / major 후보 3개를 계산한다.

입력:  stdin JSON (없으면 argv) — 아래 두 형태를 받는다
       {"tags": ["v1.13.0", ...],
        "manifests": [{"file": "package.json", "version": "1.12.0"}, ...]}
       ["v1.13.0", ...]        ← 배열이면 전부 tags 로 간주하고 교차 확인을 하지 않는다
출력:  stdout JSON { baseline, baseline_source, candidates{patch,minor,major},
                     mismatch, mismatch_detail[], warnings[], ignored[] }
종료코드: 0 = 정상, 2 = 유효 버전 없음(초기 릴리스 — 사용자 확인 필요), 3 = 입력 오류

규칙 (fix-plan-impl/scripts/compute_next_patch.py 와 동일하게 맞춘다):
- X.Y.Z 형식만 정상 파싱. 선행 `v`/`V` 는 제거 후 비교.
- pre-release 태그(`-rc1`, `-alpha.2`)가 있는 값은 무시하고 warnings 에 기록.
- build metadata(`+build.5`)는 strip 후 X.Y.Z 로 비교.

기준선은 **모든 소스를 통틀어 최대값**이다. 이미 공개된 버전보다 낮은 값을 제안하지 않기 위함.
어느 단계(patch/minor/major)를 추천할지는 이 스크립트가 정하지 않는다 — 변경 성격 판단은
호출하는 스킬의 몫이고, 여기서는 산술만 결정적으로 처리한다.
"""
import json
import re
import sys

SEMVER_CORE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
SEMVER_EXT = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$")

INITIAL_CANDIDATES = ["0.1.0", "1.0.0"]


def parse(versions, label):
    """버전 문자열 목록 → [((major, minor, patch), raw), ...] + ignored/warnings."""
    valid = []
    ignored = []
    warnings = []
    for raw in versions:
        v = str(raw).strip().lstrip("v").lstrip("V")
        if not v:
            continue
        m_core = SEMVER_CORE.match(v)
        if m_core:
            valid.append((tuple(int(x) for x in m_core.groups()), raw))
            continue
        m_ext = SEMVER_EXT.match(v)
        if m_ext:
            major, minor, patch, pre, _build = m_ext.groups()
            if pre:
                ignored.append(raw)
                warnings.append(f"pre-release 태그 무시 ({label}): {raw}")
                continue
            warnings.append(f"build metadata strip ({label}): {raw} → {major}.{minor}.{patch}")
            valid.append(((int(major), int(minor), int(patch)), raw))
            continue
        ignored.append(raw)
        warnings.append(f"파싱 실패 — 무시 ({label}): {raw}")
    return valid, ignored, warnings


def read_input():
    """stdin JSON 우선, 없으면 argv. (tags, manifests) 를 돌려준다."""
    if not sys.stdin.isatty():
        data = sys.stdin.read().strip()
        payload = json.loads(data) if data else []
    else:
        payload = sys.argv[1:]

    if isinstance(payload, list):
        return payload, []
    if isinstance(payload, dict):
        tags = payload.get("tags", [])
        manifests = payload.get("manifests", [])
        if not isinstance(tags, list) or not isinstance(manifests, list):
            raise ValueError("tags 와 manifests 는 배열이어야 합니다.")
        return tags, manifests
    raise ValueError("입력은 버전 문자열 배열 또는 {tags, manifests} 객체여야 합니다.")


def normalize_manifests(manifests):
    """[{file, version}] → [(file, version)]. 문자열만 온 경우 file 은 미상으로 둔다."""
    pairs = []
    warnings = []
    for entry in manifests:
        if isinstance(entry, dict):
            ver = entry.get("version")
            if ver is None:
                warnings.append(f"version 필드 없음 — 무시: {json.dumps(entry, ensure_ascii=False)}")
                continue
            pairs.append((entry.get("file", "(파일명 미상)"), ver))
        elif isinstance(entry, str):
            pairs.append(("(파일명 미상)", entry))
        else:
            warnings.append(f"매니페스트 항목 형식 오류 — 무시: {entry!r}")
    return pairs, warnings


def fail(message, code):
    json.dump({"error": message}, sys.stdout, ensure_ascii=False)
    sys.exit(code)


def main():
    try:
        tags, manifests = read_input()
    except json.JSONDecodeError as e:
        fail(f"입력 JSON 파싱 실패: {e}", 3)
    except ValueError as e:
        fail(str(e), 3)

    man_pairs, warnings = normalize_manifests(manifests)

    tag_valid, tag_ignored, tag_warnings = parse(tags, "tag")
    man_valid, man_ignored, man_warnings = parse([v for _f, v in man_pairs], "manifest")
    warnings = warnings + tag_warnings + man_warnings
    ignored = tag_ignored + man_ignored

    if not tag_valid and not man_valid:
        json.dump(
            {
                "baseline": None,
                "baseline_source": None,
                "candidates": None,
                "initial_candidates": INITIAL_CANDIDATES,
                "mismatch": False,
                "mismatch_detail": [],
                "warnings": warnings,
                "ignored": ignored,
                "note": "유효 X.Y.Z 버전 없음 — 초기 릴리스로 사용자 확인 필요",
            },
            sys.stdout,
            ensure_ascii=False,
        )
        sys.exit(2)

    tag_max = max(tag_valid, key=lambda t: t[0]) if tag_valid else None
    man_max = max(man_valid, key=lambda t: t[0]) if man_valid else None

    # 동률이면 태그를 기준선 출처로 삼는다 — 태그가 실제 배포된 사실의 기록이기 때문.
    if tag_max and (not man_max or tag_max[0] >= man_max[0]):
        (maj, minor, patch) = tag_max[0]
        baseline_source = f"tag:{tag_max[1]}"
    else:
        (maj, minor, patch) = man_max[0]
        # 최대값을 준 매니페스트 파일명을 찾아 붙인다.
        source_file = next(
            (f for f, v in man_pairs if v == man_max[1]), "(파일명 미상)"
        )
        baseline_source = f"manifest:{source_file}"

    baseline = f"{maj}.{minor}.{patch}"

    # 어긋남의 비교 기준은 태그다 — 태그는 실제 배포된 사실의 기록이므로. 태그가 없으면 기준선과 비교한다.
    # mismatch 를 detail 에서 파생시키는 이유: 매니페스트 하나가 태그와 같고 다른 하나가 다를 때
    # "최대값끼리 비교"로는 false 가 나와, detail 에 경고가 들어 있는데도 소비하는 쪽이 그것을 건너뛴다.
    reference = tag_max[0] if tag_max else (maj, minor, patch)
    reference_label = "최신 태그" if tag_max else "기준선"
    ref_str = f"{reference[0]}.{reference[1]}.{reference[2]}"
    mismatch_detail = []
    for f, v in man_pairs:
        parsed, _ig, _w = parse([v], "manifest")
        if parsed and parsed[0][0] != reference:
            mismatch_detail.append(f"{reference_label} {ref_str} ≠ {f} {v}")
    mismatch = bool(mismatch_detail)

    json.dump(
        {
            "baseline": baseline,
            "baseline_source": baseline_source,
            "candidates": {
                "patch": f"{maj}.{minor}.{patch + 1}",
                "minor": f"{maj}.{minor + 1}.0",
                "major": f"{maj + 1}.0.0",
            },
            "mismatch": mismatch,
            "mismatch_detail": mismatch_detail,
            "warnings": warnings,
            "ignored": ignored,
        },
        sys.stdout,
        ensure_ascii=False,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
