from __future__ import annotations

import json
from html.parser import HTMLParser
from threading import RLock
from typing import Any

try:
    from .chat_source_adapters import fetch_source_tables, has_source_adapter
    from .chat_web_connector import (
        ChatWebConnector,
        _extract_page_evidence,
        _extract_tables,
        _is_blocked_page,
    )
except ImportError:
    from chat_source_adapters import fetch_source_tables, has_source_adapter
    from chat_web_connector import (
        ChatWebConnector,
        _extract_page_evidence,
        _extract_tables,
        _is_blocked_page,
    )


DEFAULT_MAX_WEB_FETCHES = 5


class WebResearchTools:
    def __init__(
        self,
        connector: ChatWebConnector | None = None,
        *,
        max_fetch: int = DEFAULT_MAX_WEB_FETCHES,
        relevance_query: str = "",
        playwright_fetch_enabled: bool = False,
        playwright_fetcher: Any | None = None,
    ):
        self._connector = connector or ChatWebConnector()
        self._sources: list[dict] = []
        self._source_by_url: dict[str, dict] = {}
        self._max_fetch = max(0, int(max_fetch))
        self._fetch_count = 0
        self._relevance_query = str(relevance_query or "").strip()
        self._evidence_parts: list[str] = []
        self._frozen = False
        self._playwright_fetch_enabled = bool(playwright_fetch_enabled)
        self._playwright_fetcher = playwright_fetcher
        self._lock = RLock()

    @property
    def schemas(self) -> list[dict]:
        return [
            _tool_schema(
                "web_search",
                "Search the public web and return indexed web sources for later citation.",
                {
                    "query": _string_property("Search query."),
                    "max_results": _nullable_integer_property("Result limit 1..8; null uses the default."),
                },
                ["query", "max_results"],
            ),
            _tool_schema(
                "web_fetch",
                "Fetch a public web page and return extracted prose evidence plus structured tables.",
                {"url": _string_property("Public web URL to fetch.")},
                ["url"],
            ),
        ]

    def dispatch(self, tool_name: str, arguments: dict) -> str:
        try:
            if tool_name == "web_search":
                payload = self.web_search(arguments.get("query", ""), arguments.get("max_results", 5))
            elif tool_name == "web_fetch":
                payload = self.web_fetch(arguments.get("url", ""))
            else:
                payload = {"status": "error", "error": f"Unknown tool: {tool_name}"}
        except Exception as exc:
            payload = {"status": "error", "error": str(exc)}
        return json.dumps(payload, ensure_ascii=False)

    def sources(self) -> list[dict]:
        with self._lock:
            return [dict(source) for source in self._sources]

    def evidence_corpus(self) -> str:
        with self._lock:
            return "\n".join(part for part in self._evidence_parts if part)

    def freeze(self) -> None:
        with self._lock:
            self._frozen = True

    def reserve_tool_calls(self, calls: list[dict]) -> None:
        for call in calls:
            if str(call.get("tool_name") or "") != "web_fetch":
                continue
            arguments = dict(call.get("arguments") or {})
            clean_url = str(arguments.get("url") or "").strip()
            if clean_url:
                self._register_source(url=clean_url, title=clean_url, source_type="pending")

    def web_search(self, query: str, max_results: Any = 5) -> dict:
        with self._lock:
            if self._frozen:
                return {"status": "error", "error": "web research is closed; rewrite from existing fetched evidence"}
        clean_query = str(query or "").strip()
        if not clean_query:
            return {"status": "error", "error": "query is required"}
        limit = _clamp_int(max_results, default=5, minimum=1, maximum=8)
        response = self._connector.search(clean_query, limit)
        if response.error and not response.results:
            return {"status": "error", "error": response.error}
        results = []
        for result in response.results:
            source = self._register_source(
                url=result.url,
                title=result.title,
                source_type=result.source_type,
            )
            results.append(
                {
                    "index": source["index"],
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet,
                    "source_type": result.source_type,
                }
            )
        return {"status": "ok", "results": results}

    def web_fetch(self, url: str) -> dict:
        with self._lock:
            if self._frozen:
                return {"status": "error", "error": "web research is closed; rewrite from existing fetched evidence"}
        clean_url = str(url or "").strip()
        if not clean_url:
            return {"status": "error", "error": "url is required"}
        with self._lock:
            if self._fetch_count >= self._max_fetch:
                return {"status": "error", "error": "fetch limit reached"}
            # Failed fetch attempts still consume a slot so tool use stays latency-bounded.
            self._fetch_count += 1
        adapter_matched = has_source_adapter(clean_url)
        adapter_tables = fetch_source_tables(
            clean_url,
            fetcher=self._connector._fetcher,
            timeout=self._connector._timeout_seconds,
        )
        if adapter_tables:
            source = self._register_source(
                url=clean_url,
                title=clean_url,
                source_type="fetched-data",
            )
            with self._lock:
                self._evidence_parts.extend(_table_evidence_lines(adapter_tables))
            return {
                "status": "ok",
                "index": source["index"],
                "url": clean_url,
                "title": clean_url,
                "source_type": "fetched-data",
                "blocked": False,
                "evidence": "",
                "tables": adapter_tables,
            }
        html = str(self._connector._fetcher(clean_url, self._connector._timeout_seconds) or "")
        html_payload = self._extract_html_payload(clean_url, html)
        if (
            self._playwright_fetch_enabled
            and not adapter_matched
            and _html_payload_needs_render(html_payload)
        ):
            rendered_html = self._fetch_rendered_html(clean_url)
            if rendered_html:
                rendered_payload = self._extract_html_payload(clean_url, rendered_html)
                if not _html_payload_needs_render(rendered_payload):
                    html_payload = rendered_payload

        source = self._register_source(
            url=clean_url,
            title=html_payload["title"] or clean_url,
            source_type="fetch-blocked" if html_payload["blocked"] else "fetched-page",
        )
        if html_payload["blocked"]:
            return {
                "status": "ok",
                "index": source["index"],
                "url": clean_url,
                "title": html_payload["title"],
                "source_type": source["source_type"],
                "blocked": True,
                "evidence": "",
                "tables": [],
            }
        corpus_parts = [html_payload["evidence"], *_table_evidence_lines(html_payload["tables"])]
        with self._lock:
            self._evidence_parts.extend(part for part in corpus_parts if part)
        return {
            "status": "ok",
            "index": source["index"],
            "url": clean_url,
            "title": html_payload["title"],
            "source_type": source["source_type"],
            "blocked": False,
            "evidence": html_payload["evidence"],
            "tables": html_payload["tables"],
        }

    def _extract_html_payload(self, clean_url: str, html: str) -> dict[str, Any]:
        title = _extract_title(html)
        blocked = _is_blocked_page(html)
        if blocked:
            return {
                "title": title,
                "blocked": True,
                "evidence": "",
                "tables": [],
            }
        raw_had_table = "<table" in str(html or "").casefold()
        tables = _extract_tables(html)
        evidence_html = _strip_tables(html) if tables else html
        evidence = _extract_page_evidence(evidence_html, query=self._relevance_query or title or clean_url)
        if raw_had_table and not tables and evidence.strip() == title.strip():
            evidence = ""
        return {
            "title": title,
            "blocked": False,
            "evidence": evidence,
            "tables": tables,
        }

    def _fetch_rendered_html(self, clean_url: str) -> str | None:
        fetcher = self._playwright_fetcher
        if fetcher is None:
            try:
                from .chat_playwright_fetch import PlaywrightFetcher
            except ImportError:
                from chat_playwright_fetch import PlaywrightFetcher
            fetcher = PlaywrightFetcher()
        try:
            return fetcher.fetch(clean_url, timeout=8.0)
        except Exception:
            return None

    def _register_source(self, *, url: str, title: str, source_type: str) -> dict:
        normalized_url = str(url or "").strip()
        with self._lock:
            existing = self._source_by_url.get(normalized_url)
            if existing:
                if title and (not existing.get("title") or existing.get("title") == normalized_url):
                    existing["title"] = title
                if source_type and existing.get("source_type") == "pending":
                    existing["source_type"] = str(source_type or "web").strip() or "web"
                return existing
            source = {
                "index": len(self._sources) + 1,
                "url": normalized_url,
                "title": str(title or "").strip(),
                "source_type": str(source_type or "web").strip() or "web",
            }
            self._sources.append(source)
            self._source_by_url[normalized_url] = source
            return source


class _TitleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.title = _collapse_space(" ".join(self._parts))
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._parts.append(data)


class _TableStripper(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self._table_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table_depth += 1
            return
        if self._table_depth:
            return
        self.parts.append(self.get_starttag_text() or f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._table_depth:
            self._table_depth -= 1
            return
        if self._table_depth:
            return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._table_depth:
            self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if not self._table_depth:
            self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self._table_depth:
            self.parts.append(f"&#{name};")


def _extract_title(html: str) -> str:
    parser = _TitleParser()
    parser.feed(str(html or ""))
    return parser.title


def _strip_tables(html: str) -> str:
    parser = _TableStripper()
    parser.feed(str(html or ""))
    return "".join(parser.parts)


def _table_evidence_lines(tables: list[dict]) -> list[str]:
    lines: list[str] = []
    for table in tables:
        for row in table.get("rows", []):
            cells = [str(cell or "").strip() for cell in row]
            if not cells or not cells[0]:
                continue
            if len(cells) == 1:
                lines.append(cells[0])
                continue
            values = [cell for cell in cells[1:] if cell]
            if values:
                lines.append(f"{cells[0]}: {' | '.join(values)}")
    return lines


def _html_payload_needs_render(payload: dict[str, Any]) -> bool:
    if payload.get("blocked"):
        return True
    evidence = str(payload.get("evidence") or "").strip()
    tables = list(payload.get("tables") or [])
    return not tables and len(evidence) < 80


def _clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(number, maximum))


def _string_property(description: str) -> dict:
    return {"type": "string", "description": description}


def _integer_property(description: str) -> dict:
    return {"type": "integer", "description": description}


def _nullable_integer_property(description: str) -> dict:
    return {"type": ["integer", "null"], "description": description}


def _tool_schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def _collapse_space(value: str) -> str:
    return " ".join(str(value or "").split())
