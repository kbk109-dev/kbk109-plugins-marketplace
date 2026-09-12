#!/usr/bin/env bash
# 마켓플레이스 정합성 검사.
#   - marketplace.json / plugin.json / hooks.json JSON 파싱
#   - plugins[].source 경로 존재 + plugin.json name·version 일치
#   - 모든 SKILL.md(plugins/ + .claude/skills/) frontmatter name 이 디렉토리명과 일치
#   - 스크립트 경로가 ${CLAUDE_PLUGIN_ROOT} 로 하드닝되어 있고 접두사 중복이 없음
#   - 플러그인 스킬 호출이 <plugin>:<skill> 로 네임스페이스화되어 있음
#   - SKILL.md description 길이·한글 길이·평균 예산 (상시 컨텍스트 고정비)
#   - SKILL.md 파일 줄 수 500 이하 (지시 희석 방지)
#   - README 트리거 예 문구가 description 에 실재 (언더트리거 회귀 감시)
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
# 매니페스트뿐 아니라 plugins/*/hooks/*.json 도 대상이다. 훅 설정은 파싱에 실패해도 에러를
# 띄우지 않고 그냥 등록되지 않으므로, 검사 밖에 두면 훅이 조용히 죽은 채 배포된다.
while IFS= read -r f; do
  if python3 -c "import json,sys;json.load(open(sys.argv[1]))" "$f" 2>/dev/null; then
    ok "$f"
  else
    bad "$f — JSON 파싱 실패"
  fi
done < <({ find .claude-plugin plugins -name '*.json' -path '*.claude-plugin*';
           find plugins -name '*.json' -path '*/hooks/*'; } | sort -u)

echo "== 2. marketplace.json ↔ plugin.json 정합 =="
# name 뿐 아니라 version 도 비교한다. 두 곳이 어긋나면 마켓플레이스 목록에는 새 버전이 뜨는데
# 설치되는 실체는 옛 버전이라 사용자 쪽에서 "업데이트했는데 그대로"로 나타난다 — 에러가 안 난다.
# metadata.version 은 여기 대상이 아니다. 플러그인과 1:1 대응이 없어 비교할 짝이 없다.
while IFS='|' read -r name src mver; do
  [ -d "$src" ] || { bad "$name — source 경로 없음: $src"; continue; }
  man="$src/.claude-plugin/plugin.json"
  [ -f "$man" ] || { bad "$name — plugin.json 없음: $man"; continue; }
  IFS='|' read -r pname pver < <(python3 -c "
import json,sys
d = json.load(open(sys.argv[1]))
print('%s|%s' % (d['name'], d.get('version', '<없음>')))
" "$man")
  if [ "$pname" != "$name" ]; then
    bad "$name — plugin.json name 불일치: '$pname'"
  elif [ "$pver" != "$mver" ]; then
    bad "$name — version 불일치: marketplace='$mver' vs plugin.json='$pver'"
  else
    ok "$name ↔ $man (v$pver)"
  fi
done < <(python3 -c "
import json
d = json.load(open('.claude-plugin/marketplace.json'))
for p in d['plugins']:
    print('%s|%s|%s' % (p['name'], p['source'].lstrip('./'), p.get('version', '<없음>')))
")

echo "== 3. SKILL.md frontmatter name ↔ 디렉토리명 =="
while IFS= read -r f; do
  d=$(basename "$(dirname "$f")")
  n=$(grep -m1 '^name:' "$f" | sed 's/^name: *//; s/"//g; s/[[:space:]]*$//')
  if [ "$d" = "$n" ]; then ok "$d"; else bad "$f — name='$n' vs dir='$d'"; fi
# .claude/skills/** 도 대상이다. 배포되지는 않지만 이 저장소에서 작업할 때는 똑같이 로드되고,
# name 이 디렉토리명과 어긋나면 호출이 조용히 실패한다 — 플러그인 스킬과 실패 양상이 같다.
done < <({ find plugins -name SKILL.md; find .claude/skills -name SKILL.md 2>/dev/null; } | sort)

echo "== 4. 스크립트 경로 하드닝 =="
# `.claude/scripts/...` · `.claude/hooks/...` 는 이 검사의 대상이 아니다 — 플러그인이
# 번들한 스크립트가 아니라 init-agent-rules 가 **대상 프로젝트에 설치하는** 파일의 고정
# 경로다. 그 경로는 언제나 프로젝트 루트 기준이라 ${CLAUDE_PLUGIN_ROOT} 로 하드닝할 대상
# 자체가 없다(정본은 AGENTS.md/CLAUDE.md 처럼 이미 project-root-relative 로 문서화한다).
bare=$(grep -rnE '(^|[^}A-Za-z0-9_-])(\{skill_root\}/|skills/[a-z0-9-]+/|\./)?scripts/[a-zA-Z0-9_./-]+\.(py|sh)' \
        --include='*.md' --include='evals.json' --include='install_hooks.sh' plugins 2>/dev/null \
        | grep -v 'CLAUDE_PLUGIN_ROOT' | grep -v '\.claude/\(scripts\|hooks\)/' | wc -l | tr -d ' ')
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
# hooks/ 를 함께 보는 이유: 훅 명령이 없는 파일을 가리켜도 하네스가 조용히 실패할 뿐이다.
done < <(grep -rhoE '\$\{CLAUDE_PLUGIN_ROOT\}/(skills/[a-z0-9-]+/scripts|hooks)/[a-zA-Z0-9_./-]+' plugins \
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

echo "== 6. SKILL.md description 예산 =="
# description 은 **모든 세션의 컨텍스트에 항상 로드**된다 — 본문은 스킬이 호출될 때만 읽히지만
# description 은 전체가 상시 과금된다. 그래서 길이가 취향이 아니라 예산이다.
# 공식 상한(description+when_to_use 합계 1,536자)은 soft 라 넘겨도 거부되지 않고 목록에서
# 잘릴 뿐이다. 여기 상한은 잘림 방지가 아니라 **상시 고정비 절감**이 목적이라 훨씬 좁다.
# 한글에 별도 상한을 두는 이유: 한글 ≈1.5 tok/자, ASCII ≈0.25 tok/자로 6배 비싸다. 굴절 변형
# ('구현해줘'/'적용해줘'/'넣어줘') 나열이 이 저장소 description 비용의 대부분이었다.
# 규격·트리거 선정 기준은 AGENTS.md 'description 작성 규격'.
while IFS='|' read -r st msg; do
  [ "$st" = "ok" ] && ok "$msg" || bad "$msg"
done < <(python3 -c "
import glob, os, re

DESC_MAX     = 550   # 스킬 1개 description+when_to_use 합계 상한
DESC_KOR_MAX = 60    # 그중 한글 상한. 굴절 변형을 막는 실질 레버.
DESC_AVG_MAX = 450   # plugins/ 평균 상한. 총량을 스킬 수에 비례시켜 신규 스킬마다 손대지 않게 한다.
KOR = re.compile('[가-힣]')

def val(fm, key):
    m = re.search('^' + key + r':\s*(.*?)(?=\n[A-Za-z_-]+:|\Z)', fm, re.S | re.M)
    return m.group(1).strip() if m else ''

tot = kor_tot = n = 0
for f in sorted(glob.glob('plugins/*/skills/*/SKILL.md')) + sorted(glob.glob('.claude/skills/*/SKILL.md')):
    t = open(f, encoding='utf-8').read()
    m = re.match(r'^---\n(.*?)\n---\n', t, re.S)
    if not m:
        print('bad|%s — frontmatter 없음' % f); continue
    # 공식 상한이 두 키의 **합**에 걸리므로 예산도 합으로 센다.
    # when_to_use 로 옮기는 것은 절감이 아니라 잘림 순서 제어일 뿐이다.
    s = (val(m.group(1), 'description') + ' ' + val(m.group(1), 'when_to_use')).strip()
    k = len(KOR.findall(s))
    name = os.path.basename(os.path.dirname(f))
    if len(s) > DESC_MAX:
        print('bad|%s — %d자 (상한 %d) — 저신호 트리거부터 지운다' % (name, len(s), DESC_MAX))
    elif k > DESC_KOR_MAX:
        print('bad|%s — 한글 %d자 (상한 %d) — 굴절 변형을 합치고 고유 앵커만 남긴다' % (name, k, DESC_KOR_MAX))
    else:
        print('ok|%s — %d자 (한글 %d)' % (name, len(s), k))
    if f.startswith('plugins/'):
        tot += len(s); kor_tot += k; n += 1

avg = tot // max(n, 1)
tokens = round(kor_tot * 1.5 + (tot - kor_tot) * 0.25)
line = 'plugins/ %d개 합계 %d자(한글 %d) ≈ %d토큰 / 평균 %d자' % (n, tot, kor_tot, tokens, avg)
print(('ok|' + line) if avg <= DESC_AVG_MAX else ('bad|평균 상한 %d 초과 — ' % DESC_AVG_MAX) + line)
")

echo "== 7. SKILL.md 줄 수 예산 =="
# 본문은 호출될 때만 로드되므로 상시 비용이 아니다. 그래도 상한을 두는 이유는 토큰이 아니라
# **지시 희석**이다 — 한 파일이 길어지면 모델이 뒷부분 규칙을 흘린다. 넘치면 references/ 로
# 빼서 점진적 정보 공개로 바꾼다(가장 먼저 덜어낼 것은 특정 Phase 에서만 쓰는 산출 문서 템플릿).
# 숫자는 AGENTS.md '본문 500줄 이하' 와 같은 셈법이다 — 프론트매터를 포함한 파일 전체 줄 수.
# 현재 dev-monitor 가 정확히 500줄이라 여유가 0이다. 거기에 한 줄만 더 붙어도 여기서 잡힌다.
# wc -l 이 아니라 grep -c '' 를 쓰는 이유: 마지막 줄에 개행이 없으면 wc -l 은 그 줄을 안 센다.
LINE_MAX=500
while IFS= read -r f; do
  n=$(grep -c '' "$f")
  if [ "$n" -le "$LINE_MAX" ]; then ok "$(basename "$(dirname "$f")") — ${n}줄"
  else bad "$f — ${n}줄 (상한 ${LINE_MAX}) — references/ 로 분리한다"; fi
done < <({ find plugins -name SKILL.md; find .claude/skills -name SKILL.md 2>/dev/null; } | sort)

echo "== 8. README 트리거 예 ↔ description 실재 =="
# README '스킬 전체 목록' 표의 "트리거 예" 는 사용자에게 한 약속이다. description 을 줄이다가
# 그 문구를 지우면 문서는 그대로인데 스킬이 안 뜬다 — 언더트리거가 조용히 생긴다.
# 그래서 README 에 적은 문구를 **반드시 살아남는 집합**으로 삼고 여기서 실재를 확인한다.
# 이 검사가 있으면 리라이트 때 "무엇을 지워도 되는가"가 자동으로 정해진다 — 표에 없는 것만 지운다.
while IFS='|' read -r st msg; do
  [ "$st" = "ok" ] && ok "$msg" || bad "$msg"
done < <(python3 - <<'PY'
import re, glob, os
# 여기만 heredoc 을 쓴다. 패턴에 ASCII 큰따옴표가 들어가 python3 -c "..." 로는 이스케이프가
# 중첩돼 조용히 빗나간다(빗나가면 0건 매칭 → 항상 통과하는 가짜 검사가 된다).
desc = {}
for f in glob.glob('plugins/*/skills/*/SKILL.md'):
    t = open(f, encoding='utf-8').read()
    m = re.match(r'^---\n(.*?)\n---\n', t, re.S)
    d = re.search(r'^description:\s*(.*?)(?=\n[A-Za-z_-]+:|\Z)', m.group(1), re.S | re.M) if m else None
    desc[os.path.basename(os.path.dirname(f))] = d.group(1) if d else ''

miss = checked = 0
for line in open('README.md', encoding='utf-8'):
    row = re.match(r'^\| `([a-z0-9-]+)` \|(.*?)\|', line)
    if not row or row.group(1) not in desc:
        continue
    for phrase in re.findall(r'"([^"]+)"', row.group(2)):
        checked += 1
        if phrase not in desc[row.group(1)]:
            print('bad|README 트리거 "%s" 가 %s description 에 없음' % (phrase, row.group(1)))
            miss += 1
print('ok|README 트리거 예 %d건 전부 description 에 실재' % checked if miss == 0
      else 'bad|README 트리거 %d/%d 건 누락' % (miss, checked))
PY
)

echo
if [ "$fail" -eq 0 ]; then
  echo "모든 검사 통과."
else
  echo "실패 $fail 건."
  exit 1
fi
