#!/usr/bin/env bash
# 마켓플레이스 정합성 검사.
#   - marketplace.json / plugin.json JSON 파싱
#   - plugins[].source 경로 존재 + plugin.json name·version 일치
#   - 모든 SKILL.md frontmatter name 이 디렉토리명과 일치
#   - 스크립트 경로가 ${CLAUDE_PLUGIN_ROOT} 로 하드닝되어 있고 접두사 중복이 없음
#   - 플러그인 스킬 호출이 <plugin>:<skill> 로 네임스페이스화되어 있음
# 사용: bash scripts/validate-marketplace.sh
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail + 1)); }

# 플러그인 목록은 marketplace.json 에서 읽는다. 하드코딩하면 신규 플러그인이 검사 4·5 를
# 조용히 빠져나간다 — 실패가 아니라 미수행이므로 통과처럼 보인다.
PLUGINS=$(python3 -c "
import json
d = json.load(open('.claude-plugin/marketplace.json'))
print(' '.join(p['name'] for p in d['plugins']))
")
[ -n "$PLUGINS" ] || { printf '  \033[31m✗\033[0m marketplace.json 에서 플러그인 목록을 읽지 못했습니다.\n'; exit 1; }

echo "== 1. JSON 파싱 =="
while IFS= read -r f; do
  if python3 -c "import json,sys;json.load(open(sys.argv[1]))" "$f" 2>/dev/null; then
    ok "$f"
  else
    bad "$f — JSON 파싱 실패"
  fi
done < <(find .claude-plugin plugins -name '*.json' -path '*.claude-plugin*' | sort)

echo "== 2. marketplace.json ↔ plugin.json 정합 =="
while IFS='|' read -r name src; do
  [ -d "$src" ] || { bad "$name — source 경로 없음: $src"; continue; }
  man="$src/.claude-plugin/plugin.json"
  [ -f "$man" ] || { bad "$name — plugin.json 없음: $man"; continue; }
  pname=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['name'])" "$man")
  if [ "$pname" = "$name" ]; then ok "$name ↔ $man"; else
    bad "$name — plugin.json name 불일치: '$pname'"
  fi
done < <(python3 -c "
import json
d = json.load(open('.claude-plugin/marketplace.json'))
for p in d['plugins']:
    print('%s|%s' % (p['name'], p['source'].lstrip('./')))
")

echo "== 3. SKILL.md frontmatter name ↔ 디렉토리명 =="
while IFS= read -r f; do
  d=$(basename "$(dirname "$f")")
  n=$(grep -m1 '^name:' "$f" | sed 's/^name: *//; s/"//g; s/[[:space:]]*$//')
  if [ "$d" = "$n" ]; then ok "$d"; else bad "$f — name='$n' vs dir='$d'"; fi
done < <(find plugins -name SKILL.md | sort)

echo "== 4. 스크립트 경로 하드닝 =="
bare=$(grep -rnE '(^|[^}A-Za-z0-9_-])(\{skill_root\}/|skills/[a-z0-9-]+/|\./)?scripts/[a-zA-Z0-9_./-]+\.(py|sh)' \
        --include='*.md' --include='evals.json' --include='install_hooks.sh' plugins 2>/dev/null \
        | grep -v 'CLAUDE_PLUGIN_ROOT' | wc -l | tr -d ' ')
[ "$bare" = "0" ] && ok "상대 경로 스크립트 호출 0건" \
                  || bad "상대 경로 스크립트 호출 $bare 건 잔존"

dup=$(grep -rF 'CLAUDE_PLUGIN_ROOT}/${CLAUDE_PLUGIN_ROOT' plugins 2>/dev/null | wc -l | tr -d ' ')
[ "$dup" = "0" ] && ok "접두사 중복 0건" || bad "\${CLAUDE_PLUGIN_ROOT} 중복 $dup 건"

# 참조된 스크립트가 어느 플러그인에도 없으면 보고한다. 이전 구현은 "찾은 것"만 출력하고
# 그것의 존재를 다시 확인해 항상 통과했다 — dangling 참조가 검출되지 않았다.
dangling=0
while IFS='|' read -r found ref; do
  if [ "$found" != "1" ]; then
    bad "참조된 스크립트를 어느 플러그인에서도 찾을 수 없음: $ref"
    dangling=$((dangling + 1))
  fi
# 문자 클래스에 '.' 을 남겨두는 이유: scripts/schemas/*.schema.json 같은 참조도 검사 대상이다.
# 대신 문장 끝 마침표가 경로에 붙어 오므로(`...install_hooks.sh.`) 후행 구두점을 떼어낸다.
done < <(grep -rhoE '\$\{CLAUDE_PLUGIN_ROOT\}/skills/[a-z0-9-]+/scripts/[a-zA-Z0-9_./-]+' plugins \
         | sed 's|\${CLAUDE_PLUGIN_ROOT}/||; s|[.,;:]*$||' | sort -u \
         | while read -r r; do
             hit=0
             for p in $PLUGINS; do
               if [ -f "plugins/$p/$r" ]; then hit=1; break; fi
             done
             echo "$hit|$r"
           done)
[ "$dangling" = "0" ] && ok "참조 스크립트 실체 확인 완료 (dangling 0건)"

echo "== 5. 스킬 호출 네임스페이스 =="
for p in $PLUGINS; do
  skills=$(find "plugins/$p/skills" -maxdepth 1 -mindepth 1 -type d -exec basename {} \; | paste -sd'|' -)
  n=$(grep -rhoE "(^|[[:space:]\`(\"'])/($skills)([^A-Za-z0-9_:-]|$)" "plugins/$p" 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" = "0" ] && ok "$p — 네임스페이스 없는 호출 0건" \
                 || bad "$p — 네임스페이스 없는 호출 $n 건"
done

echo
if [ "$fail" -eq 0 ]; then
  echo "모든 검사 통과."
else
  echo "실패 $fail 건."
  exit 1
fi
