#!/usr/bin/env bash
# Install a git pre-commit hook that enforces release-impl invariants.
#
# The hook runs on every commit inside a project that has release-impl state
# (docs/skills/release-impl/v*/feature_list.json). It rejects commits that
# would:
#   1. produce an invalid feature_list.json,
#   2. introduce illegal state transitions (pass → other, AC mutation,
#      task deletion, hash drift),
#   3. leave PROGRESS.md header counters out of sync with feature_list.json.
#
# The hook is intentionally a no-op for commits that do not touch any
# release-impl state, so repositories that consume this skill for a single
# release can keep the hook installed across branches without friction.
#
# Usage (run inside the consuming repository):
#     bash ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/install_hooks.sh
#
# Safe to re-run; overwrites the existing release-impl hook block only.

set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [[ -z "${REPO_ROOT}" ]]; then
  echo "error: not inside a git repository" >&2
  exit 2
fi

HOOK_DIR="${REPO_ROOT}/.git/hooks"
HOOK_FILE="${HOOK_DIR}/pre-commit"
MARK_BEGIN="# >>> release-impl hook >>>"
MARK_END="# <<< release-impl hook <<<"

mkdir -p "${HOOK_DIR}"

HOOK_BODY=$(cat <<'EOF'
# >>> release-impl hook >>>
# This block is managed by ${CLAUDE_PLUGIN_ROOT}/skills/release-impl/scripts/install_hooks.sh.
# Do not edit by hand; re-run the installer to regenerate.
set -e

_ri_scripts="$(git rev-parse --show-toplevel)/skills/release-impl/scripts"
if [[ ! -d "${_ri_scripts}" ]]; then
  # The consumer repo may keep scripts at a different path; fallback to env.
  _ri_scripts="${RELEASE_IMPL_SCRIPTS:-}"
fi

# Collect staged feature_list.json paths under docs/skills/release-impl/v*/
mapfile -t _ri_staged < <(git diff --cached --name-only --diff-filter=ACMR \
  | grep -E '^docs/skills/release-impl/v[0-9]+\.[0-9]+\.[0-9]+/feature_list\.json$' || true)

if [[ ${#_ri_staged[@]} -eq 0 ]]; then
  exit 0
fi

if [[ -z "${_ri_scripts}" || ! -f "${_ri_scripts}/validate_feature_list.py" ]]; then
  echo "release-impl hook: scripts not found — set RELEASE_IMPL_SCRIPTS or install the skill locally" >&2
  exit 1
fi

for _ri_path in "${_ri_staged[@]}"; do
  _ri_tmp_new=$(mktemp)
  git show ":${_ri_path}" > "${_ri_tmp_new}"

  if ! python3 "${_ri_scripts}/validate_feature_list.py" "${_ri_tmp_new}"; then
    rm -f "${_ri_tmp_new}"
    echo "release-impl hook: ${_ri_path} failed validation" >&2
    exit 1
  fi

  # Compare against HEAD version if the file existed before.
  if git cat-file -e "HEAD:${_ri_path}" 2>/dev/null; then
    _ri_tmp_old=$(mktemp)
    git show "HEAD:${_ri_path}" > "${_ri_tmp_old}"
    if ! python3 "${_ri_scripts}/check_state_transition.py" "${_ri_tmp_old}" "${_ri_tmp_new}"; then
      rm -f "${_ri_tmp_old}" "${_ri_tmp_new}"
      echo "release-impl hook: illegal state transition in ${_ri_path}" >&2
      exit 1
    fi
    rm -f "${_ri_tmp_old}"
  fi

  _ri_dir=$(dirname "${_ri_path}")
  # If PROGRESS.md also exists, verify header is in sync.
  if [[ -f "${_ri_dir}/PROGRESS.md" ]]; then
    if ! python3 "${_ri_scripts}/sync_progress.py" --check "${_ri_dir}"; then
      rm -f "${_ri_tmp_new}"
      echo "release-impl hook: PROGRESS.md drift in ${_ri_dir} — run sync_progress.py" >&2
      exit 1
    fi
  fi

  rm -f "${_ri_tmp_new}"
done
# <<< release-impl hook <<<
EOF
)

if [[ -f "${HOOK_FILE}" ]]; then
  # Remove previous managed block if present.
  python3 - "${HOOK_FILE}" "${MARK_BEGIN}" "${MARK_END}" <<'PY'
import re, sys
path, begin, end = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8").read()
pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", re.DOTALL)
open(path, "w", encoding="utf-8").write(pattern.sub("", text))
PY
else
  printf '#!/usr/bin/env bash\nset -euo pipefail\n\n' > "${HOOK_FILE}"
fi

printf '\n%s\n' "${HOOK_BODY}" >> "${HOOK_FILE}"
chmod +x "${HOOK_FILE}"
echo "installed release-impl pre-commit hook at ${HOOK_FILE}"
