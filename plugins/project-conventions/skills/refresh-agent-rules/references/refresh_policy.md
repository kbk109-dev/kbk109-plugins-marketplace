# refresh 판정 규칙 정본

`SKILL.md` 의 Step 2~5 가 이 문서를 따른다. 대상은 `AGENTS.md` **본문 한 곳**뿐이다.

## 1. 고칠 수 있는 것과 없는 것

| 대상 | 이 스킬 | 이유 |
|---|---|---|
| `AGENTS.md` 본문 | **고친다** | 유일한 갱신 대상 |
| `AGENTS.md` 마커 블록 구간 | 안 고친다 | `init-agent-rules` 소관. 재실행하면 덮어써 편집이 사라진다 |
| `CLAUDE.md` | 안 고친다 | 포인터다. 내용이 들어가면 `check-agent-rules` 검사 3 이 깨지고 Cursor 가 못 읽는다 |
| `.claude/rules/*.md` | 안 고친다 | 규칙 본문은 별도 수명주기. 고치려면 사용자가 직접 + `--sync-mdc` |
| `.cursor/rules/*.mdc` | 안 고친다 | 생성물. 손으로 쓰면 이 플러그인이 막으려는 갈라짐 그 자체다 |
| 프로젝트 소스 | 안 고친다 | 문서가 코드를 따라가는 것이지 반대가 아니다 |

마커 블록 구간은 스캔 결과의 `agents_md.marker_ranges` 가 줄 번호로 알려 준다.
**문장으로 금지하는 대신 범위를 받아서 빼라** — 지켜야 할 것을 눈으로 세지 않게 한다.

## 2. 사실 항목과 산문을 가른다

`AGENTS.md` 에는 성격이 다른 두 종류의 글이 섞여 있다. **둘을 같은 잣대로 보면 안 된다.**

| | 사실 항목 | 사람이 쓴 산문 |
|---|---|---|
| 예 | `npm test`, `src/api/handlers/`, `pnpm 만 쓴다`, 버전·경로 | 설계 근거, 정책, 과거에 깨진 이유, 함정 설명 |
| 대조 | 스캔 결과와 맞춰 본다 | **`facts` 로 반증되지 않는 한 손대지 않는다** |
| 근거 | `facts` 의 어느 키에서 왔는지 댈 수 있다 | 댈 수 없다 |

*"왜 AGENTS.md 가 SSoT 인가"* 같은 단락은 코드를 아무리 스캔해도 참·거짓이 안 나온다.
근거를 못 대는 항목은 **판정 대상이 아니다.** 낡아 보인다는 인상만으로 건드리지 않는다.

## 3. 네 갈래 판정

`git.changed_files` · `git.deleted_files` 가 가리키는 영역을 **먼저** 본다. 기준점이 없거나
(`state.exists == false`) `baseline_valid == false` 이면 우선순위 없이 전체를 훑는다.

| 판정 | 조건 | 근거로 댈 `facts` 키 |
|---|---|---|
| **유지** | 문서와 사실이 일치 | — |
| **수정** | 둘 다 존재하는데 값이 다름 | `command_sources[].commands` · `package_managers` · `typescript_strict` · **`git.renamed_files`** |
| **추가** | 사실에 있는데 문서에 없음 | 위와 같음 · `ci_workflows` · `toolchain_files` |
| **삭제 후보** | 문서가 가리키는 대상이 사라짐 | `git.deleted_files` · `facts.tree` · `command_sources` 의 부재 |

**이동은 삭제가 아니다.** git 은 파일이 옮겨지면 `D`+`A` 가 아니라 `R` 로 보고하므로
옛 경로가 `deleted_files` 에 안 들어온다. 스캐너가 그것을 `renamed_files` 의
`{from, to}` 로 따로 낸다. 문서가 `from` 을 가리키고 있으면 **줄을 지우지 말고 `to` 로 고친다** —
파일이 옮겨졌을 뿐인데 지시를 지우면 지시가 사라진다.

`tree` 는 상위 2단계까지만 담기고 `tree_truncated` 가 참이면 잘린 것이다.
**잘린 목록의 부재를 삭제 근거로 쓰지 않는다** — 안 보이는 것과 없는 것은 다르다.
3단계 아래 경로(`src/api/handlers/`)는 애초에 `tree` 에 없으므로, 그 부재는
`git.deleted_files` 로만 확인한다.

## 4. 삭제는 항목별로 승인받는다

추가·수정은 diff 하나로 일괄 승인받아도 된다. **삭제는 다르다.** 모델이 사람이 쓴 설계 근거를
"낡았다"고 지우는 것이 이 스킬 최대의 손실이고, 긴 diff 안의 삭제 한 줄은 놓치기 쉽다.

| ID | 원문 발췌 (최대 6줄) | 사라졌다고 보는 근거 | 확신 |
|---|---|---|---|
| D1 | `API 핸들러는 src/api/handlers/` | `git.deleted_files` 에 `src/api/handlers/route.ts` 외 4건, `facts.tree` 에 해당 경로 없음 | 높음 |
| D2 | `테스트: yarn test` | `facts.package_managers` 가 `["pnpm"]`, `yarn.lock` 없음 | 높음 |

- **근거는 반드시 `facts`/`git` 의 키를 지목한다.** "더 이상 안 쓰는 것 같다" 는 근거가 아니다
- 확신이 낮으면 삭제 대신 **수정**을 제안한다
- **승인 못 받은 항목은 원문 그대로 남긴다.** 침묵은 거절이 아니라 대기이고, 거절은 유지다
- 삭제가 거절돼 문서가 200줄을 넘은 채로 남아도 그것은 실패가 아니다

## 5. no-op — 아무것도 안 하는 것이 정답인 경우

수정·추가·삭제 후보가 **모두 0건**이면 `AGENTS.md` 를 열지도 않는다. 승인도 묻지 않는다.

```
AGENTS.md 는 현재 프로젝트 상태와 일치합니다. 변경하지 않았습니다.

기준점: {baseline_commit 7자리} 이후 커밋 {N}개 · 변경 파일 {M}건 확인
줄 수: {lines} (목표 200 미만 — {충족|N줄 초과})
```

**상태 파일은 이때도 기록한다** (`--result no-change`). 기준점을 옮기지 않으면 다음 실행이
같은 diff 를 다시 훑고, 같은 결론을 다시 낸다.

"고칠 게 없다" 를 자신 있게 말하려면 무엇을 봤는지 밝혀야 한다. 그래서 no-op 보고에도
확인 범위를 적는다.

## 6. 재작성 규칙은 여기 없다

카파시 4원칙 검출·정본 블록·H1 아래 배치, What/How 분류, 200줄 예산 계산은
[`../../init-agent-rules/references/claude_md_rewrite.md`](../../init-agent-rules/references/claude_md_rewrite.md)
**하나가 정본이다.** 이 문서에 복제하지 않는다.

정본이 둘이면 반드시 갈라지고, 갈라져도 에러가 안 난다 — 이 플러그인이 존재하는 이유가 바로
그 실패다. 자기 자신에게 같은 실수를 하지 않는다.

`refresh` 에서 달라지는 점은 **대상 파일뿐**이다. init 은 이관 직전의 `CLAUDE.md` 를,
refresh 는 이미 이관된 `AGENTS.md` 를 다룬다. 규칙 자체는 같다.

## 7. 상태 파일

`.claude/agent-rules.state.json` — 스크립트가 `--record` 로만 쓴다. 모델이 직접 쓰지 않는다.

```json
{
  "schema": 1,
  "baseline_commit": "ce515b2...",
  "last_refreshed": "2026-08-19",
  "last_result": "no-change"
}
```

**커밋 대상이다.** 팀원이 각자 다른 기준점을 들고 있으면 같은 변경을 몇 번이고 다시 제안하게 된다.

기준점이 rebase 로 사라졌거나 shallow clone 이라 닿지 않으면 스크립트가 `baseline_valid: false`
로 알린다. 이때는 빈 diff 를 "변경 없음" 으로 읽지 말고 **전체 대조로 되돌아간다** — 놓친 갱신을
영원히 못 잡는 쪽이 한 번 더 훑는 쪽보다 나쁘다.
