#!/usr/bin/env python3
"""Notion 을 토큰 기반 REST API 로만 다루는 CLI. 이 프로젝트에서 Notion 을 만지는 유일한
합법 경로 — `notion-api-only` 규칙이 설치된 프로젝트는 MCP 도구 호출이 훅으로 막히고, 이
스크립트가 그 대체 경로다.

왜 MCP 가 아니라 이 스크립트인가: MCP 서버 접두사는 환경마다 다르고(`mcp__claude_ai_Notion__`,
`mcp__plugin_Notion_notion__`, …) 응답 스키마도 서버 구현에 좌우돼, 같은 스킬이 사람마다 다른
결과를 낸다. 이 스크립트는 결정적이다 — 같은 입력에 같은 출력, 같은 종료 코드.

설계 원칙:
- stdout 은 파이프 가능하게 깨끗이 유지한다 — 성공 응답의 JSON 만 stdout 에 쓴다. 에러는
  전부 stderr 에 JSON 한 줄로 쓴다 (`{"error": {...}}`).
- 호출자는 종료 코드로만 분기한다. 산문으로 성공/실패를 판단하지 않는다.
- 쓰기 요청(page-create/blocks-append/db-create)의 5xx 는 재시도하지 않는다 — 서버가 부분
  적용했을 가능성이 있어, 재시도하면 중복 레코드가 생길 수 있다. 429/네트워크 오류/읽기
  요청의 5xx 만 지수 backoff 로 재시도한다.
- 토큰 값은 어떤 출력 경로로도 나타나지 않는다. `doctor` 는 출처 이름과 접두 4자만 보고한다.

종료 코드:
    0  성공
    2  사용법 오류 (argparse)
    3  설정/인증 — 토큰을 못 찾음, 401, 403
    4  요청 오류 — 400 validation_error
    5  대상 없음 — 404, resolve 실패
    6  일시 실패 — 429/5xx/네트워크, 재시도 소진
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

NOTION_VERSION = "2026-03-11"
API_BASE = "https://api.notion.com/v1"

MAX_RETRIES = 5
BACKOFF_BASE = 1.0
DEFAULT_PAGE_SIZE = 100
MAX_ALL_PAGES = 20  # --all 상한. 출력이 곧 LLM 입력이므로 무제한 덤프를 막는다.

PROP_TYPES = {
    "title", "rich_text", "select", "multi_select", "status", "checkbox",
    "date", "number", "url",
}


# --------------------------------------------------------------------------
# errors
# --------------------------------------------------------------------------

class CliError(Exception):
    """종료 코드를 실어 나르는 예외. main() 이 잡아 stderr 에 JSON 으로 쓰고 그 코드로 exit."""

    def __init__(self, exit_code: int, code: str, message: str, hint: str = "", status: int = 0):
        super().__init__(message)
        self.exit_code = exit_code
        self.code = code
        self.message = message
        self.hint = hint
        self.status = status

    def payload(self) -> dict:
        d = {"code": self.code, "message": self.message, "exit": self.exit_code}
        if self.status:
            d["status"] = self.status
        if self.hint:
            d["hint"] = self.hint
        return {"error": d}


def config_error(message: str, hint: str = "") -> CliError:
    return CliError(3, "config_error", message, hint)


# --------------------------------------------------------------------------
# token resolution
# --------------------------------------------------------------------------

def find_project_root(start: Path) -> Path:
    """start 부터 상향으로 .git 를 찾는다. 없으면 start 그대로."""
    cur = start.resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / ".git").exists():
            return candidate
    return cur


def parse_env_file(path: Path) -> dict:
    """.env 파서. 이 스크립트가 신뢰하는 유일한 파일 형식 규약:

    빈 줄·`#` 시작 줄 무시 / `export ` 접두 허용 / 첫 `=` 로만 분할 / 값 양끝의 짝맞는
    따옴표 제거 / 따옴표가 없을 때만 뒤따르는 ` #` 이후를 주석으로 절단 / 변수 보간 없음.
    """
    out = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value[:1] in ("'", '"'):
            # 따옴표가 있으면 그 안쪽만 값이다 — 닫는 따옴표 뒤의 ` # ...` 는 통째로 버린다.
            # 주석 절단을 먼저 하면 닫는 따옴표가 잘려 값에 여는 따옴표가 남는 버그가 된다.
            quote = value[0]
            end = value.find(quote, 1)
            value = value[1:end] if end != -1 else value[1:]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if key:
            out[key] = value
    return out


def resolve_token(cwd: Path) -> tuple[str, str]:
    """(token, source) 를 돌려준다. 실패하면 CliError(exit=3) 를 던진다.

    출처는 이 순서로만 찾는다: 환경변수 → 프로젝트 루트 .env → 그 상위 1단계 .env.
    상위를 더 올라가지 않는 것은 의도적이다 — 한 워크스페이스를 여러 프로젝트가 공유하는
    흔한 배치(형제 프로젝트들의 부모 폴더)까지만 커버하고, 그 이상은 명시적 환경변수를
    요구한다.
    """
    env_token = os.environ.get("NOTION_TOKEN", "").strip()
    if env_token:
        return env_token, "env"

    root = find_project_root(cwd)
    candidates = [root / ".env", root.parent / ".env"]
    for env_path in candidates:
        values = parse_env_file(env_path)
        token = values.get("NOTION_TOKEN", "").strip()
        if token:
            return token, str(env_path)

    raise config_error(
        "NOTION_TOKEN 을 찾을 수 없습니다.",
        hint=(
            "환경변수 NOTION_TOKEN 을 설정하거나, "
            f"{root / '.env'} 또는 {root.parent / '.env'} 에 NOTION_TOKEN=ntn_... 을 추가하세요. "
            "온보딩 절차는 .claude/rules/notion-api-only.md 를 참고하세요."
        ),
    )


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def _sleep_backoff(attempt: int, retry_after: str | None) -> None:
    if retry_after:
        try:
            time.sleep(max(0.0, float(retry_after)))
            return
        except ValueError:
            pass
    delay = BACKOFF_BASE * (2 ** attempt)
    jitter = delay * random.uniform(-0.2, 0.2)
    time.sleep(delay + jitter)


def api_request(
    method: str,
    path: str,
    token: str,
    *,
    body: dict | None = None,
    query: dict | None = None,
    is_write: bool = False,
) -> dict:
    """Notion REST 호출 1회(+ 필요시 재시도). 성공하면 파싱된 JSON 을 돌려준다.

    읽기와 쓰기의 재시도 정책을 나눈다: 429 는 둘 다 재시도(서버가 아직 처리하지 않았음이
    분명하므로), 5xx/타임아웃은 읽기만 재시도한다 — 쓰기의 5xx 는 서버가 부분 적용했을 수
    있어 재시도하면 중복 레코드를 만들 위험이 있다.
    """
    url = API_BASE + path
    if query:
        qs = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in query.items() if v is not None)
        if qs:
            url = f"{url}?{qs}"

    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    attempt = 0
    while True:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", "replace")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                err_body = json.loads(raw) if raw else {}
            except ValueError:
                err_body = {}
            status = exc.code
            message = err_body.get("message", raw or exc.reason)

            if status == 429:
                if attempt >= MAX_RETRIES:
                    raise CliError(6, "rate_limited", message, status=status,
                                    hint="재시도 소진. 잠시 후 다시 실행하세요.")
                _sleep_backoff(attempt, exc.headers.get("Retry-After") if exc.headers else None)
                attempt += 1
                continue
            if status in (401,):
                raise CliError(3, "unauthorized", message, status=status,
                                hint="토큰이 유효하지 않습니다. integration 을 재발급하세요.")
            if status in (403,):
                raise CliError(3, "forbidden", message, status=status,
                                hint="권한 없음 — integration 이 이 페이지에 공유되지 않았습니다. "
                                     "Notion 에서 페이지 ⋯ → 연결 → integration 을 추가하세요.")
            if status == 404:
                raise CliError(5, "not_found", message, status=status,
                                hint="찾을 수 없음 — ID 오타이거나 공유되지 않아 보이지 않는 "
                                     "경우입니다. Notion 은 둘을 구분해 주지 않습니다.")
            if status == 400:
                raise CliError(4, "validation_error", message, status=status,
                                hint="대개 속성 이름·타입 불일치입니다. ds-get 으로 실제 스키마를 확인하세요.")
            if status >= 500:
                if is_write:
                    raise CliError(6, "server_error", message, status=status,
                                    hint="쓰기 요청이라 재시도하지 않았습니다. 중복 생성 방지를 "
                                         "위해서입니다 — Notion 상태를 확인한 뒤 다시 실행하세요.")
                if attempt >= MAX_RETRIES:
                    raise CliError(6, "server_error", message, status=status,
                                    hint="재시도 소진.")
                _sleep_backoff(attempt, None)
                attempt += 1
                continue
            raise CliError(6, "http_error", message, status=status)
        except (urllib.error.URLError, TimeoutError) as exc:
            if is_write or attempt >= MAX_RETRIES:
                raise CliError(6, "network_error", str(exc),
                                hint="쓰기 요청은 네트워크 오류를 재시도하지 않습니다." if is_write else "재시도 소진.")
            _sleep_backoff(attempt, None)
            attempt += 1
            continue


def paginate(method: str, path: str, token: str, body: dict | None, *, want_all: bool, limit: int) -> dict:
    """has_more/next_cursor 루프를 흡수해 {"results","count","truncated"} 봉투로 돌려준다.
    호출자(모델)는 커서를 만지지 않는다."""
    results: list = []
    cursor = None
    pages = 0
    truncated = False
    while True:
        req_body = dict(body or {})
        req_body["page_size"] = min(limit, DEFAULT_PAGE_SIZE) if not want_all else DEFAULT_PAGE_SIZE
        if cursor:
            req_body["start_cursor"] = cursor
        resp = api_request(method, path, token, body=req_body)
        results.extend(resp.get("results", []))
        pages += 1
        cursor = resp.get("next_cursor")
        has_more = resp.get("has_more", False)
        if not want_all:
            truncated = bool(has_more) or len(results) > limit
            results = results[:limit]
            break
        if not has_more or not cursor:
            break
        if pages >= MAX_ALL_PAGES:
            truncated = True
            break
    return {"results": results, "count": len(results), "truncated": truncated}


# --------------------------------------------------------------------------
# markdown <-> blocks
# --------------------------------------------------------------------------

_INLINE_RE = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)")


def _inline_rich_text(text: str) -> list:
    """`**bold**` / `` `code` `` / `[text](url)` 3종만 인식. 나머지는 그대로 plain text.
    2000자 청크 분할은 호출자가 담당(rich_text 배열 자체는 여기서 나누지 않는다 — 인라인
    서식이 청크 경계에 걸리는 것을 피하려면 이 단계에서 자르지 않는 편이 안전하다)."""
    parts = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            parts.append({"type": "text", "text": {"content": text[pos:m.start()]}})
        if m.group(1) is not None:
            parts.append({"type": "text", "text": {"content": m.group(1)}, "annotations": {"bold": True}})
        elif m.group(2) is not None:
            parts.append({"type": "text", "text": {"content": m.group(2)}, "annotations": {"code": True}})
        else:
            parts.append({"type": "text", "text": {"content": m.group(3), "link": {"url": m.group(4)}}})
        pos = m.end()
    if pos < len(text):
        parts.append({"type": "text", "text": {"content": text[pos:]}})
    return parts or [{"type": "text", "text": {"content": ""}}]


def _chunk_children(blocks: list) -> list:
    """append 100개 제한에 맞춰 청크로 나눈다."""
    return [blocks[i:i + 100] for i in range(0, len(blocks), 100)] or [[]]


def md_to_blocks(text: str) -> list:
    """마크다운을 Notion 블록 배열로 변환한다. 지원: heading 1-3, bulleted/numbered list,
    code fence, quote, divider, table, paragraph. 그 밖은 paragraph 로 떨어진다."""
    lines = text.splitlines()
    blocks: list = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            blocks.append({"type": "divider", "divider": {}})
            i += 1
            continue

        m = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            key = f"heading_{level}"
            blocks.append({"type": key, key: {"rich_text": _inline_rich_text(m.group(2))}})
            i += 1
            continue

        if stripped.startswith("```"):
            lang = stripped[3:].strip() or "plain text"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            blocks.append({
                "type": "code",
                "code": {"rich_text": [{"type": "text", "text": {"content": "\n".join(code_lines)}}],
                          "language": lang},
            })
            continue

        if stripped.startswith("> "):
            blocks.append({"type": "quote", "quote": {"rich_text": _inline_rich_text(stripped[2:])}})
            i += 1
            continue

        if re.match(r"^[-*]\s+", stripped):
            content = re.sub(r"^[-*]\s+", "", stripped)
            blocks.append({"type": "bulleted_list_item",
                            "bulleted_list_item": {"rich_text": _inline_rich_text(content)}})
            i += 1
            continue

        if re.match(r"^\d+\.\s+", stripped):
            content = re.sub(r"^\d+\.\s+", "", stripped)
            blocks.append({"type": "numbered_list_item",
                            "numbered_list_item": {"rich_text": _inline_rich_text(content)}})
            i += 1
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            # 두 번째 줄이 `|---|---|` 구분선이면 헤더 있는 표
            has_header = len(table_lines) >= 2 and bool(re.match(r"^\|[\s:-]+\|", table_lines[1]))
            body_lines = [table_lines[0]] + table_lines[2:] if has_header else table_lines
            rows = []
            for tl in body_lines:
                cells = [c.strip() for c in tl.strip("|").split("|")]
                rows.append(cells)
            width = max((len(r) for r in rows), default=1)
            table_rows = []
            for r in rows:
                cells = [_inline_rich_text(c) for c in r] + [_inline_rich_text("")] * (width - len(r))
                table_rows.append({"type": "table_row", "table_row": {"cells": cells}})
            blocks.append({
                "type": "table",
                "table": {"table_width": width, "has_column_header": has_header, "has_row_header": False},
                "children": table_rows,
            })
            continue

        # paragraph — 다음 빈 줄까지 이어붙인다
        para_lines = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,3}\s|```|&gt;\s|[-*]\s|\d+\.\s|\|)", lines[i].strip()):
            para_lines.append(lines[i].strip())
            i += 1
        blocks.append({"type": "paragraph", "paragraph": {"rich_text": _inline_rich_text(" ".join(para_lines))}})

    return blocks


def _rich_text_to_plain(rich_text: list) -> str:
    return "".join(rt.get("plain_text", rt.get("text", {}).get("content", "")) for rt in rich_text or [])


def block_to_markdown_line(block: dict) -> str:
    btype = block.get("type", "")
    data = block.get(btype, {})
    text = _rich_text_to_plain(data.get("rich_text", []))
    if btype == "heading_1":
        return f"# {text}"
    if btype == "heading_2":
        return f"## {text}"
    if btype == "heading_3":
        return f"### {text}"
    if btype == "bulleted_list_item":
        return f"- {text}"
    if btype == "numbered_list_item":
        return f"1. {text}"
    if btype == "quote":
        return f"> {text}"
    if btype == "code":
        lang = data.get("language", "")
        return f"```{lang}\n{text}\n```"
    if btype == "divider":
        return "---"
    if btype == "table_row":
        cells = data.get("cells", [])
        return "| " + " | ".join(_rich_text_to_plain(c) for c in cells) + " |"
    if btype == "paragraph":
        return text
    return text  # 미지원 타입은 텍스트만 최대한 뽑는다


# --------------------------------------------------------------------------
# --set property helper
# --------------------------------------------------------------------------

def parse_set_args(sets: list) -> dict:
    """--set '키=타입:값' 목록을 Notion properties 객체로 만든다."""
    properties: dict = {}
    for item in sets or []:
        if "=" not in item:
            raise CliError(2, "usage_error", f"--set 형식 오류(키=타입:값): {item!r}")
        key, rest = item.split("=", 1)
        if ":" not in rest:
            raise CliError(2, "usage_error", f"--set 형식 오류(키=타입:값): {item!r}")
        ptype, value = rest.split(":", 1)
        ptype = ptype.strip()
        key = key.strip()
        if ptype not in PROP_TYPES:
            raise CliError(2, "usage_error", f"지원하지 않는 --set 타입: {ptype!r} (지원: {sorted(PROP_TYPES)})")
        properties[key] = _build_property_value(ptype, value)
    return properties


def _build_property_value(ptype: str, value: str) -> dict:
    if ptype == "title":
        return {"title": [{"type": "text", "text": {"content": value}}]}
    if ptype == "rich_text":
        return {"rich_text": [{"type": "text", "text": {"content": value}}]}
    if ptype == "select":
        return {"select": {"name": value}}
    if ptype == "status":
        return {"status": {"name": value}}
    if ptype == "multi_select":
        names = [v.strip() for v in value.split(",") if v.strip()]
        return {"multi_select": [{"name": n} for n in names]}
    if ptype == "checkbox":
        return {"checkbox": value.strip().lower() in ("true", "1", "yes")}
    if ptype == "date":
        return {"date": {"start": value}}
    if ptype == "number":
        return {"number": float(value) if "." in value else int(value)}
    if ptype == "url":
        return {"url": value}
    raise CliError(2, "usage_error", f"지원하지 않는 --set 타입: {ptype!r}")


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------

def cmd_doctor(args, token: str, source: str) -> dict:
    if args.dry_run:
        return {"ok": True, "token_source": source, "token_prefix": token[:4], "dry_run": True}
    me = api_request("GET", "/users/me", token)
    return {
        "ok": True,
        "token_source": source,
        "token_prefix": token[:4],
        "bot": {"name": me.get("name"), "id": me.get("id")},
    }


def cmd_search(args, token: str, source: str) -> dict:
    body: dict = {}
    if args.query:
        body["query"] = args.query
    if args.type:
        body["filter"] = {"property": "object", "value": args.type}
    return paginate("POST", "/search", token, body, want_all=args.all, limit=args.limit)


def cmd_resolve(args, token: str, source: str) -> dict:
    result: dict = {"page": None, "database": None, "data_source": None}

    page_ref = args.page
    page = None
    if re.fullmatch(r"[0-9a-fA-F-]{32,36}", page_ref):
        try:
            page = api_request("GET", f"/pages/{page_ref}", token)
        except CliError:
            page = None
    if page is None:
        found = paginate("POST", "/search", token,
                          {"query": page_ref, "filter": {"property": "object", "value": "page"}},
                          want_all=False, limit=5)
        candidates = found["results"]
        if not candidates:
            raise CliError(5, "not_found", f"페이지를 찾지 못했습니다: {page_ref!r}",
                            hint="integration 이 이 페이지에 공유돼 있는지 확인하세요.")
        page = candidates[0]
    title = ""
    for prop in (page.get("properties") or {}).values():
        if prop.get("type") == "title":
            title = _rich_text_to_plain(prop.get("title", []))
            break
    result["page"] = {"id": page["id"], "title": title, "url": page.get("url")}

    if args.database:
        children = paginate("GET", f"/blocks/{page['id']}/children", token, None, want_all=True, limit=100)
        db_block = next(
            (c for c in children["results"]
             if c.get("type") == "child_database"
             and args.database.lower() in c.get("child_database", {}).get("title", "").lower()),
            None,
        )
        if db_block is None:
            raise CliError(5, "not_found", f"하위 데이터베이스를 찾지 못했습니다: {args.database!r}")
        db = api_request("GET", f"/databases/{db_block['id']}", token)
        sources = db.get("data_sources") or []
        result["database"] = {"id": db["id"], "title": args.database}
        if sources:
            result["data_source"] = {"id": sources[0]["id"], "name": sources[0].get("name")}

    return result


def cmd_page_get(args, token: str, source: str) -> dict:
    return api_request("GET", f"/pages/{args.page_id}", token)


def _fetch_children(block_id: str, token: str, recursive: bool, max_depth: int, depth: int = 0) -> list:
    resp = paginate("GET", f"/blocks/{block_id}/children", token, None, want_all=True, limit=100)
    blocks = resp["results"]
    if recursive and depth < max_depth:
        for b in blocks:
            if b.get("has_children"):
                b["_children"] = _fetch_children(b["id"], token, recursive, max_depth, depth + 1)
    return blocks


def cmd_page_children(args, token: str, source: str) -> dict:
    blocks = _fetch_children(args.id, token, args.recursive, args.max_depth)
    return {"results": blocks, "count": len(blocks)}


def _blocks_to_markdown(blocks: list, depth: int = 0) -> list:
    lines = []
    for b in blocks:
        indent = "  " * depth
        lines.append(indent + block_to_markdown_line(b))
        if b.get("_children"):
            lines.extend(_blocks_to_markdown(b["_children"], depth + 1))
    return lines


def cmd_page_markdown(args, token: str, source: str) -> dict:
    page = api_request("GET", f"/pages/{args.page_id}", token)
    blocks = _fetch_children(args.page_id, token, True, args.max_depth)
    markdown = "\n\n".join(_blocks_to_markdown(blocks))
    return {"page_id": args.page_id, "url": page.get("url"), "markdown": markdown}


def cmd_page_create(args, token: str, source: str) -> dict:
    if bool(args.parent_page_id) == bool(args.parent_data_source_id):
        raise CliError(2, "usage_error", "--parent-page-id 또는 --parent-data-source-id 중 정확히 하나를 지정하세요.")
    parent = ({"type": "page_id", "page_id": args.parent_page_id} if args.parent_page_id
              else {"type": "data_source_id", "data_source_id": args.parent_data_source_id})

    properties = parse_set_args(args.set)
    if args.title and "title" not in properties:
        # 데이터소스 페이지는 title 속성 이름이 스키마마다 다를 수 있어 --set 이 우선이다.
        # 일반 페이지(부모가 page_id)는 속성 스키마가 없으므로 여기서 title 을 채운다.
        if args.parent_page_id:
            properties["title"] = {"title": [{"type": "text", "text": {"content": args.title}}]}

    body: dict = {"parent": parent, "properties": properties}
    page = api_request("POST", "/pages", token, body=body, is_write=True)

    if args.markdown_file:
        md_text = Path(args.markdown_file).read_text(encoding="utf-8")
        blocks = md_to_blocks(md_text)
        for chunk in _chunk_children(blocks):
            if chunk:
                api_request("PATCH", f"/blocks/{page['id']}/children", token,
                             body={"children": chunk}, is_write=True)
    return page


def cmd_page_update(args, token: str, source: str) -> dict:
    if args.properties_json:
        properties = json.loads(Path(args.properties_json).read_text(encoding="utf-8")) \
            if Path(args.properties_json).is_file() else json.loads(args.properties_json)
    else:
        properties = parse_set_args(args.set)
    if not properties:
        raise CliError(2, "usage_error", "--set 또는 --properties-json 중 하나로 변경할 속성을 지정하세요.")
    return api_request("PATCH", f"/pages/{args.page_id}", token, body={"properties": properties}, is_write=True)


def cmd_blocks_append(args, token: str, source: str) -> dict:
    md_text = Path(args.markdown_file).read_text(encoding="utf-8")
    blocks = md_to_blocks(md_text)
    last = {}
    for chunk in _chunk_children(blocks):
        if chunk:
            last = api_request("PATCH", f"/blocks/{args.block_id}/children", token,
                                body={"children": chunk}, is_write=True)
    return {"block_id": args.block_id, "appended": len(blocks), "last_response": last}


def cmd_db_get(args, token: str, source: str) -> dict:
    return api_request("GET", f"/databases/{args.database_id}", token)


def cmd_db_create(args, token: str, source: str) -> dict:
    schema = json.loads(Path(args.schema_file).read_text(encoding="utf-8"))
    body = {
        "parent": {"type": "page_id", "page_id": args.parent_page_id},
        "title": [{"type": "text", "text": {"content": args.title}}],
        "initial_data_source": {"properties": schema},
    }
    return api_request("POST", "/databases", token, body=body, is_write=True)


def cmd_ds_get(args, token: str, source: str) -> dict:
    return api_request("GET", f"/data_sources/{args.data_source_id}", token)


def cmd_ds_query(args, token: str, source: str) -> dict:
    body: dict = {}
    if args.filter_json:
        body["filter"] = json.loads(args.filter_json)
    if args.sorts_json:
        body["sorts"] = json.loads(args.sorts_json)
    return paginate("POST", f"/data_sources/{args.data_source_id}/query", token, body,
                     want_all=args.all, limit=args.limit)


def cmd_view_create(args, token: str, source: str) -> dict:
    body: dict = {
        "database_id": args.database_id,
        "data_source_id": args.data_source_id,
        "name": args.name,
        "type": args.type,
    }
    if args.group_by:
        body["configuration"] = {
            "type": args.type,
            "group_by": {"type": "select", "property_id": args.group_by},
        }
    return api_request("POST", "/views", token, body=body, is_write=True)


def cmd_md2blocks(args, token: str | None, source: str | None) -> dict:
    md_text = Path(args.markdown_file).read_text(encoding="utf-8")
    return {"children": md_to_blocks(md_text)}


# --------------------------------------------------------------------------
# argparse wiring
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="notion_api.py",
        description="Notion 을 토큰 기반 REST API 로 다루는 CLI. --help 로 서브커맨드를 확인하세요.",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="토큰 해석 확인 (네트워크 접속 없이 --dry-run 가능)")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_doctor, needs_token=True)

    p = sub.add_parser("search", help="POST /v1/search")
    p.add_argument("--query", default="")
    p.add_argument("--type", choices=["page", "data_source"], default=None)
    p.add_argument("--limit", type=int, default=DEFAULT_PAGE_SIZE)
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_search, needs_token=True)

    p = sub.add_parser("resolve", help="페이지(+하위 데이터베이스) 를 이름/ID 로 찾는다")
    p.add_argument("--page", required=True)
    p.add_argument("--database", default=None)
    p.set_defaults(func=cmd_resolve, needs_token=True)

    p = sub.add_parser("page-get", help="GET /v1/pages/{id}")
    p.add_argument("page_id")
    p.set_defaults(func=cmd_page_get, needs_token=True)

    p = sub.add_parser("page-children", help="GET /v1/blocks/{id}/children")
    p.add_argument("id")
    p.add_argument("--recursive", action="store_true")
    p.add_argument("--max-depth", type=int, default=3)
    p.set_defaults(func=cmd_page_children, needs_token=True)

    p = sub.add_parser("page-markdown", help="페이지 본문을 재귀 조회해 마크다운으로 변환")
    p.add_argument("page_id")
    p.add_argument("--max-depth", type=int, default=3)
    p.set_defaults(func=cmd_page_markdown, needs_token=True)

    p = sub.add_parser("page-create", help="POST /v1/pages")
    p.add_argument("--parent-page-id", default=None)
    p.add_argument("--parent-data-source-id", default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--set", action="append", default=[], help="키=타입:값 (반복 가능)")
    p.add_argument("--markdown-file", default=None)
    p.set_defaults(func=cmd_page_create, needs_token=True)

    p = sub.add_parser("page-update", help="PATCH /v1/pages/{id}")
    p.add_argument("page_id")
    p.add_argument("--set", action="append", default=[])
    p.add_argument("--properties-json", default=None)
    p.set_defaults(func=cmd_page_update, needs_token=True)

    p = sub.add_parser("blocks-append", help="PATCH /v1/blocks/{id}/children")
    p.add_argument("block_id")
    p.add_argument("--markdown-file", required=True)
    p.set_defaults(func=cmd_blocks_append, needs_token=True)

    p = sub.add_parser("db-get", help="GET /v1/databases/{id}")
    p.add_argument("database_id")
    p.set_defaults(func=cmd_db_get, needs_token=True)

    p = sub.add_parser("db-create", help="POST /v1/databases")
    p.add_argument("--parent-page-id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--schema-file", required=True, help="properties 객체만 담은 JSON 파일")
    p.set_defaults(func=cmd_db_create, needs_token=True)

    p = sub.add_parser("ds-get", help="GET /v1/data_sources/{id}")
    p.add_argument("data_source_id")
    p.set_defaults(func=cmd_ds_get, needs_token=True)

    p = sub.add_parser("ds-query", help="POST /v1/data_sources/{id}/query")
    p.add_argument("data_source_id")
    p.add_argument("--filter-json", default=None)
    p.add_argument("--sorts-json", default=None)
    p.add_argument("--limit", type=int, default=DEFAULT_PAGE_SIZE)
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_ds_query, needs_token=True)

    p = sub.add_parser("view-create", help="POST /v1/views")
    p.add_argument("--database-id", required=True)
    p.add_argument("--data-source-id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--type", required=True,
                    choices=["table", "board", "list", "calendar", "timeline", "gallery",
                             "form", "chart", "map", "dashboard"])
    p.add_argument("--group-by", default=None, help="board 뷰의 group-by 속성 ID")
    p.set_defaults(func=cmd_view_create, needs_token=True)

    p = sub.add_parser("md2blocks", help="마크다운 → 블록 변환 (네트워크 없음, 단위 검증용)")
    p.add_argument("--markdown-file", required=True)
    p.set_defaults(func=cmd_md2blocks, needs_token=False)

    return ap


def main(argv: list) -> int:
    ap = build_parser()
    args = ap.parse_args(argv[1:])

    token, source = "", ""
    if args.needs_token:
        try:
            token, source = resolve_token(Path.cwd())
        except CliError as exc:
            sys.stderr.write(json.dumps(exc.payload(), ensure_ascii=False) + "\n")
            return exc.exit_code

    try:
        result = args.func(args, token, source)
    except CliError as exc:
        sys.stderr.write(json.dumps(exc.payload(), ensure_ascii=False) + "\n")
        return exc.exit_code
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(json.dumps({"error": {"code": "local_error", "message": str(exc), "exit": 2}},
                                     ensure_ascii=False) + "\n")
        return 2

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
