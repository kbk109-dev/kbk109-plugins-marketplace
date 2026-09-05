# Notion 연동 온보딩 — `notion-api-only` 규칙 설치 시 안내할 절차

`install_agent_rules.py --notion-rule on` 을 실행하기 전(또는 실행 직후) 사용자에게 이
절차를 안내한다. 토큰이 없으면 훅이 설치돼도 `notion_api.py` 가 매번 exit 3 로 실패한다.

## 1. Integration 생성

`notion.so/profile/integrations` → **New integration** → **Internal** 선택, 워크스페이스
지정.

## 2. Capabilities — 최소 권한만

**Read content / Update content / Insert content** 만 체크한다. Comment·User 정보 등은
이 스크립트가 쓰지 않으므로 켜지 않는다.

## 3. Secret 복사

발급된 토큰(`ntn_…` 로 시작)을 복사한다. 이 화면을 벗어나면 다시 볼 수 없다.

## 4. 대상 페이지마다 공유 — 가장 자주 놓치는 단계

Notion `POST /v1/search` 는 **integration 에 공유된 페이지·데이터소스만** 반환한다.
integration 을 만들었다고 자동으로 워크스페이스 전체가 보이지 않는다.

각 페이지에서: 페이지 우상단 **⋯** → **연결(Connections)** → 방금 만든 integration 추가.
**부모 페이지에 붙이면 하위 페이지가 상속받는다** — 프로젝트가 다루는 최상위 페이지 하나에만
공유해도 그 아래 전부가 보이게 할 수 있다.

## 5. `.env` 배치

```
NOTION_TOKEN=ntn_...
```

`notion_api.py` 는 이 순서로 토큰을 찾는다: 환경변수 `NOTION_TOKEN` → 프로젝트 루트
`.env` → 그 상위 1단계 폴더 `.env`. 한 워크스페이스를 여러 프로젝트가 공유한다면 상위
폴더 `.env` 에 한 번만 두면 된다.

`.env` 가 `.gitignore` 에 있는지 반드시 확인한다 — 커밋되면 토큰이 유출된다.

## 6. 확인

```bash
python3 .claude/scripts/notion_api.py doctor
```

`{"ok": true, "token_source": "...", ...}` 가 나오면 끝. `exit=3` 이면 위 절차를 다시
확인한다.
