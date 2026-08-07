from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import base64
import re
from html.parser import HTMLParser
from html import unescape
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

try:
    from .chat_runtime import ChatRuntimeConfig
    from .chat_research_strategy import build_research_plan
    from .chat_search_api import get_search_provider
except ImportError:
    from chat_runtime import ChatRuntimeConfig
    from chat_research_strategy import build_research_plan
    from chat_search_api import get_search_provider


DEFAULT_WEB_SEARCH_TIMEOUT_SECONDS = 8.0
DEFAULT_WEB_SEARCH_MAX_RESULTS = 5
_DEFAULT_SEARCH_PROVIDER = object()


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str = ""
    evidence: str = ""
    source_type: str = "search-result"
    quality_score: int = 0


@dataclass(frozen=True)
class WebSearchResponse:
    query: str
    results: list[WebSearchResult] = field(default_factory=list)
    error: str = ""
    analysis: str = ""


_SOURCE_HINT_PROFILES = (
    {
        "keywords": ("น้ำมัน", "ราคาน้ำมัน", "เบนซิน", "ดีเซล", "fuel", "gasoline", "diesel"),
        "hints": (
            {
                "title": "EPPO Thailand oil price API",
                "url": "https://www.eppo.go.th/wp-json/oil-api/v1/oil-prices",
                "snippet": "Official Thai energy policy office oil-price data endpoint.",
                "source_type": "trusted-hint",
                "quality_score": 5,
            },
            {
                "title": "Bangchak oil price API",
                "url": "https://oil-price.bangchak.co.th/apioilprice2/th",
                "snippet": "Bangchak public Thai oil-price data endpoint.",
                "source_type": "trusted-hint",
                "quality_score": 4,
            },
            {
                "title": "GlobalPetrolPrices Thailand gasoline prices",
                "url": "https://www.globalpetrolprices.com/Thailand/gasoline_prices/",
                "snippet": "International fuel-price reference page for Thailand gasoline prices.",
                "source_type": "trusted-hint",
                "quality_score": 3,
            },
        ),
    },
)


class ChatWebConnector:
    def __init__(
        self,
        *,
        fetcher=None,
        timeout_seconds: float = DEFAULT_WEB_SEARCH_TIMEOUT_SECONDS,
        search_provider=_DEFAULT_SEARCH_PROVIDER,
    ):
        self._fetcher = fetcher or _fetch_text
        self._timeout_seconds = timeout_seconds
        self._search_provider = (
            get_search_provider(ChatRuntimeConfig())
            if search_provider is _DEFAULT_SEARCH_PROVIDER
            else search_provider
        )

    def search(self, query: str, max_results: int = DEFAULT_WEB_SEARCH_MAX_RESULTS) -> WebSearchResponse:
        clean_query = _clean_search_query(query)
        limit = max(1, min(int(max_results or DEFAULT_WEB_SEARCH_MAX_RESULTS), 8))
        if not clean_query:
            return WebSearchResponse(query="", results=[], error="Search query is empty.")
        errors: list[str] = []
        api_results = self._search_api_results(clean_query, limit, errors)
        if api_results is not None:
            return self._build_response(clean_query, api_results, errors, limit)
        return self._search_html(clean_query, limit, errors)

    def _search_api_results(
        self,
        clean_query: str,
        limit: int,
        errors: list[str],
    ) -> list[WebSearchResult] | None:
        if self._search_provider is None:
            return None
        try:
            raw_results = self._search_provider.search(clean_query, count=limit)
        except Exception as exc:
            errors.append(f"search_api: {str(exc).strip() or 'failed'}")
            return None
        results: list[WebSearchResult] = []
        for item in raw_results or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            if not title or not url:
                continue
            results.append(WebSearchResult(title=title, url=url, snippet=snippet))
        return results

    def _search_html(
        self,
        clean_query: str,
        limit: int,
        errors: list[str],
    ) -> WebSearchResponse:
        collected: list[WebSearchResult] = []
        search_tasks: list[tuple[str, str]] = []
        for variant in _query_variants(clean_query):
            search_tasks.extend(
                [
                    ("duckduckgo", f"https://duckduckgo.com/html/?q={quote_plus(variant)}"),
                    ("bing", f"https://www.bing.com/search?q={quote_plus(variant)}"),
                ]
            )
        task_results: list[list[WebSearchResult] | None] = [None] * len(search_tasks)
        task_errors: list[str | None] = [None] * len(search_tasks)
        with ThreadPoolExecutor(max_workers=_bounded_worker_count(len(search_tasks))) as executor:
            future_by_index = {
                executor.submit(self._fetch_search_results, engine, url, limit): index
                for index, (engine, url) in enumerate(search_tasks)
            }
            for future in as_completed(future_by_index):
                index = future_by_index[future]
                engine = search_tasks[index][0]
                try:
                    task_results[index] = future.result()
                except Exception as exc:
                    task_errors[index] = f"{engine}: {str(exc).strip() or 'failed'}"
        for result_batch in task_results:
            if result_batch:
                collected.extend(result_batch)
        errors.extend(error for error in task_errors if error)
        return self._build_response(clean_query, collected, errors, limit)

    def _build_response(
        self,
        clean_query: str,
        collected: list[WebSearchResult],
        errors: list[str],
        limit: int,
    ) -> WebSearchResponse:
        collected.extend(_source_hints(clean_query))
        ranked = _rank_results(clean_query, _dedupe_search_results(collected), max_results=limit)
        enriched = self._enrich_results(clean_query, ranked)
        analysis = _build_source_analysis(clean_query, enriched)
        return WebSearchResponse(query=clean_query, results=enriched, error="; ".join(errors) if not enriched else "", analysis=analysis)

    def _enrich_results(self, query: str, results: list[WebSearchResult]) -> list[WebSearchResult]:
        enriched: list[WebSearchResult] = list(results)
        fetch_count = min(3, len(results))
        if fetch_count <= 0:
            return enriched
        with ThreadPoolExecutor(max_workers=_bounded_worker_count(fetch_count)) as executor:
            future_by_index = {
                executor.submit(self._enrich_one_result, query, result): index
                for index, result in enumerate(results[:fetch_count])
            }
            for future in as_completed(future_by_index):
                index = future_by_index[future]
                try:
                    enriched[index] = future.result()
                except Exception:
                    enriched[index] = results[index]
        return enriched

    def _fetch_search_results(self, engine: str, url: str, limit: int) -> list[WebSearchResult]:
        html = self._fetcher(url, self._timeout_seconds)
        if engine == "bing":
            return _parse_bing_html(str(html or ""), max_results=limit)
        return _parse_duckduckgo_html(str(html or ""), max_results=limit)

    def _enrich_one_result(self, query: str, result: WebSearchResult) -> WebSearchResult:
        try:
            html = self._fetcher(result.url, self._timeout_seconds)
            if _is_blocked_page(str(html or "")):
                return WebSearchResult(
                    title=result.title,
                    url=result.url,
                    snippet=result.snippet or "Fetch blocked by anti-bot or captcha page.",
                    evidence="",
                    source_type="fetch-blocked",
                    quality_score=0,
                )
            evidence = _extract_page_evidence(str(html or ""), query=query)
            if evidence:
                return WebSearchResult(
                    title=result.title,
                    url=result.url,
                    snippet=result.snippet,
                    evidence=evidence,
                    source_type="fetched-page",
                    quality_score=_source_quality_score(result.url, result.title, evidence),
                )
        except Exception:
            pass
        return result


class _DuckDuckGoHtmlParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._capture: str = ""
        self._current_href: str = ""
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {name: value or "" for name, value in attrs}
        css_classes = set(attrs_dict.get("class", "").split())
        if tag == "a" and "result__a" in css_classes:
            self._capture = "title"
            self._current_href = attrs_dict.get("href", "")
            self._buffer = []
        elif "result__snippet" in css_classes:
            self._capture = "snippet"
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture == "title" and tag == "a":
            title = _collapse_space(" ".join(self._buffer))
            url = _normalize_result_url(self._current_href)
            if title and url:
                self.results.append({"title": title, "url": url, "snippet": ""})
            self._reset_capture()
        elif self._capture == "snippet" and tag in {"a", "div", "span"}:
            snippet = _collapse_space(" ".join(self._buffer))
            if snippet and self.results and not self.results[-1].get("snippet"):
                self.results[-1]["snippet"] = snippet
            self._reset_capture()

    def _reset_capture(self) -> None:
        self._capture = ""
        self._current_href = ""
        self._buffer = []


class _BingHtmlParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._in_result = False
        self._in_heading = False
        self._capture: str = ""
        self._current_href: str = ""
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {name: value or "" for name, value in attrs}
        css_classes = set(attrs_dict.get("class", "").split())
        if tag == "li" and "b_algo" in css_classes:
            self._in_result = True
            return
        if self._in_result and tag == "h2":
            self._in_heading = True
            return
        if self._in_result and self._in_heading and tag == "a" and not self._capture:
            href = attrs_dict.get("href", "")
            if _normalize_result_url(href):
                self._capture = "title"
                self._current_href = href
                self._buffer = []
                return
        if self._in_result and tag == "p" and self.results and not self.results[-1].get("snippet"):
            self._capture = "snippet"
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture == "title" and tag == "a":
            title = _collapse_space(" ".join(self._buffer))
            url = _normalize_result_url(self._current_href)
            if title and url:
                self.results.append({"title": title, "url": url, "snippet": ""})
            self._reset_capture()
        elif self._capture == "snippet" and tag == "p":
            snippet = _collapse_space(" ".join(self._buffer))
            if snippet and self.results:
                self.results[-1]["snippet"] = snippet
            self._reset_capture()
        elif tag == "li" and self._in_result:
            self._in_result = False
            self._in_heading = False
            self._reset_capture()
        elif tag == "h2" and self._in_heading:
            self._in_heading = False

    def _reset_capture(self) -> None:
        self._capture = ""
        self._current_href = ""
        self._buffer = []


def _parse_duckduckgo_html(html: str, *, max_results: int) -> list[WebSearchResult]:
    parser = _DuckDuckGoHtmlParser()
    parser.feed(html)
    return _dedupe_results(parser.results, max_results=max_results)


def _parse_bing_html(html: str, *, max_results: int) -> list[WebSearchResult]:
    parser = _BingHtmlParser()
    parser.feed(html)
    return _dedupe_results(parser.results, max_results=max_results)


def _extract_page_evidence(html: str, *, query: str, max_chars: int = 1800) -> str:
    parser = _ReadableTextParser()
    parser.feed(html)
    text = _collapse_space(" ".join(parser.parts))
    table_lines = _table_evidence_lines(_extract_tables(html))
    if not text and not table_lines:
        return ""
    terms = _relevance_terms(query)
    if text and len(text) <= max_chars:
        prose = text
    elif text:
        sentences = re.split(r"(?<=[.!?。！？])\s+|\n+", text)
        selected: list[str] = []
        for sentence in sentences:
            clean = _collapse_space(sentence)
            if not clean:
                continue
            if not terms or any(term.casefold() in clean.casefold() for term in terms):
                selected.append(clean)
            if len(" ".join(selected)) >= max_chars:
                break
        if not selected:
            selected = [_collapse_space(text[:max_chars])]
        prose = _collapse_space(" ".join(selected))
    else:
        prose = ""
    table_evidence = " | ".join(table_lines)
    return _collapse_space(" ".join([part for part in [table_evidence, prose] if part]))[:max_chars]


def _is_blocked_page(html: str) -> bool:
    text = str(html or "").casefold()
    blocked_markers = (
        "radware captcha page",
        "captcha page",
        "we apologize for the inconvenience",
        "made us think that you are a bot",
        "access denied",
        "request unblock",
        "verify you are human",
        "unusual traffic",
        "enable cookies",
        "cf-challenge",
    )
    return any(marker in text for marker in blocked_markers)


class _ReadableTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self._table_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "table":
            self._table_depth += 1
            return
        if self._table_depth:
            return
        if tag in {"p", "li", "tr", "h1", "h2", "h3", "th", "td", "br"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._table_depth:
            self._table_depth -= 1
            return
        if self._table_depth:
            return
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append(". ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth or self._table_depth:
            return
        clean = _collapse_space(data)
        if clean:
            self.parts.append(clean)


class _TableExtractor(HTMLParser):
    def __init__(self, *, max_tables: int, max_rows: int):
        super().__init__(convert_charrefs=True)
        self.max_tables = max(0, int(max_tables))
        self.max_rows = max(0, int(max_rows))
        self.tables: list[dict] = []
        self._skip_depth = 0
        self._table_depth = 0
        self._active_table: dict | None = None
        self._current_row: list[str] | None = None
        self._current_row_header_flags: list[bool] = []
        self._current_cell: list[str] | None = None
        self._current_cell_is_header = False
        self._caption_parts: list[str] | None = None
        self._heading_tag = ""
        self._heading_parts: list[str] = []
        self._last_heading = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._table_depth == 0:
            self._heading_tag = tag
            self._heading_parts = []
            return
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1 and len(self.tables) < self.max_tables:
                self._active_table = {"caption": self._last_heading, "headers": [], "rows": []}
                self._last_heading = ""
            return
        if self._table_depth != 1 or self._active_table is None:
            return
        if tag == "caption":
            self._caption_parts = []
        elif tag == "tr":
            self._current_row = []
            self._current_row_header_flags = []
        elif tag in {"th", "td"} and self._current_row is not None:
            self._current_cell = []
            self._current_cell_is_header = tag == "th"

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == self._heading_tag:
            self._last_heading = _collapse_space(" ".join(self._heading_parts))
            self._heading_tag = ""
            self._heading_parts = []
            return
        if tag == "caption" and self._caption_parts is not None and self._active_table is not None:
            caption = _collapse_space(" ".join(self._caption_parts))
            if caption:
                self._active_table["caption"] = caption
            self._caption_parts = None
            return
        if tag in {"th", "td"} and self._table_depth == 1 and self._current_cell is not None and self._current_row is not None:
            self._current_row.append(_collapse_space(" ".join(self._current_cell)))
            self._current_row_header_flags.append(self._current_cell_is_header)
            self._current_cell = None
            self._current_cell_is_header = False
            return
        if tag == "tr" and self._table_depth == 1 and self._active_table is not None and self._current_row is not None:
            row = list(self._current_row)
            if any(row):
                is_header_row = all(self._current_row_header_flags)
                if is_header_row and not self._active_table["headers"]:
                    self._active_table["headers"] = row
                elif len(self._active_table["rows"]) < self.max_rows:
                    self._active_table["rows"].append(row)
            self._current_row = None
            self._current_row_header_flags = []
            return
        if tag == "table" and self._table_depth:
            if self._table_depth == 1 and self._active_table is not None:
                if self._active_table["headers"] or self._active_table["rows"]:
                    self.tables.append(self._active_table)
                self._active_table = None
            self._table_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        clean = _collapse_space(data)
        if not clean:
            return
        if self._table_depth > 1:
            return
        if self._current_cell is not None:
            self._current_cell.append(clean)
        elif self._caption_parts is not None:
            self._caption_parts.append(clean)
        elif self._heading_tag:
            self._heading_parts.append(clean)


def _extract_tables(html: str, *, max_tables: int = 8, max_rows: int = 40) -> list[dict]:
    parser = _TableExtractor(max_tables=max_tables, max_rows=max_rows)
    parser.feed(str(html or ""))
    return [table for table in parser.tables if not _is_placeholder_table(table)]


def _is_placeholder_table(table: dict) -> bool:
    caption = _collapse_space(str(table.get("caption") or "")).casefold()
    if any(marker in caption for marker in ("loading", "please wait")):
        return True

    rows = list(table.get("rows") or [])
    if len(rows) < 2:
        return False

    numeric_values: list[str] = []
    for row in rows:
        for cell in list(row)[1:]:
            normalized = str(cell or "").replace(",", "").strip()
            if re.fullmatch(r"\d+(?:\.\d+)?", normalized):
                numeric_values.append(normalized)

    return len(numeric_values) >= 2 and len(set(numeric_values)) == 1


def _table_evidence_lines(tables: list[dict], *, max_lines: int = 80) -> list[str]:
    lines: list[str] = []
    for table in tables:
        headers = list(table.get("headers") or [])
        for row in list(table.get("rows") or []):
            cells = [_collapse_space(cell) for cell in row]
            if len(cells) < 2:
                continue
            label = cells[0]
            if not label:
                continue
            values = cells[1:]
            value_labels = headers[1:] if len(headers) == len(cells) else []
            if value_labels and len(values) > 1:
                value = "; ".join(f"{header} {cell}" for header, cell in zip(value_labels, values))
            else:
                value = " | ".join(values)
            lines.append(f"{label}: {value}")
            if len(lines) >= max_lines:
                return lines
    return lines


def _dedupe_results(items: list[dict[str, str]], *, max_results: int) -> list[WebSearchResult]:
    results: list[WebSearchResult] = []
    seen_urls: set[str] = set()
    for item in items:
        url = item.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        results.append(
            WebSearchResult(
                title=unescape(item.get("title", "")),
                url=url,
                snippet=unescape(item.get("snippet", "")),
            )
        )
        if len(results) >= max_results:
            break
    return results


def _clean_search_query(query: str) -> str:
    text = _collapse_space(query)
    replacements = (
        ("ขอข้อมูล", ""),
        ("ขอ ข้อมูล", ""),
        ("ขอรายละเอียด", ""),
        ("ช่วยค้นหา", ""),
        ("ช่วยหาข้อมูล", ""),
        ("ช่วยหา", ""),
        ("ของประเทศไทย", "ประเทศไทย"),
        ("ขอ", ""),
        ("คืออะไร", ""),
        ("ให้หน่อย", ""),
        ("หน่อย", ""),
        ("ล่าสุดของ", "ล่าสุด"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    text = re.sub(r"[?？!！]+", " ", text)
    text = _collapse_space(text)
    return text or _collapse_space(query)


def _query_variants(clean_query: str) -> list[str]:
    variants = list(build_research_plan(clean_query).queries) or [clean_query]
    text = clean_query.casefold()
    if "gemini" in text:
        variants.append(f"{clean_query} official documentation")
    if "openai" in text:
        variants.append(f"{clean_query} official documentation")
    return list(dict.fromkeys(_collapse_space(variant) for variant in variants if _collapse_space(variant)))


def _source_hints(clean_query: str) -> list[WebSearchResult]:
    text = str(clean_query or "").casefold()
    hints: list[WebSearchResult] = []
    for profile in _SOURCE_HINT_PROFILES:
        keywords = tuple(str(keyword).casefold() for keyword in profile.get("keywords", ()))
        if not any(keyword and keyword in text for keyword in keywords):
            continue
        for item in profile.get("hints", ()):
            hints.append(WebSearchResult(**item))
    return hints


def _rank_results(query: str, results: list[WebSearchResult], *, max_results: int) -> list[WebSearchResult]:
    concrete_results = [result for result in results if result.source_type != "trusted-hint"]
    trusted_hints = [result for result in results if result.source_type == "trusted-hint"]
    ranked_concrete = _rank_result_group(query, concrete_results)
    ranked_hints = _rank_result_group(query, trusted_hints, gate_zero_overlap=False)
    return (ranked_concrete + ranked_hints)[:max_results]


def _rank_result_group(
    query: str,
    results: list[WebSearchResult],
    *,
    gate_zero_overlap: bool = True,
) -> list[WebSearchResult]:
    terms = _relevance_terms(query)
    if not terms:
        return results
    scored: list[tuple[int, int, WebSearchResult]] = []
    for index, result in enumerate(results):
        searchable = f"{result.title} {result.url} {result.snippet} {result.evidence}".casefold()
        score = sum(1 for term in terms if term.casefold() in searchable)
        scored.append((score, -index, result))
    best_score = max((score for score, _index, _result in scored), default=0)
    if gate_zero_overlap and best_score <= 0:
        return []
    if best_score > 0:
        scored = [item for item in scored if item[0] > 0]
    scored.sort(reverse=True)
    return [result for _score, _index, result in scored]


def _dedupe_search_results(results: list[WebSearchResult]) -> list[WebSearchResult]:
    deduped: list[WebSearchResult] = []
    seen: set[str] = set()
    for result in results:
        if not result.url or result.url in seen:
            continue
        seen.add(result.url)
        deduped.append(result)
    return deduped


def _bounded_worker_count(task_count: int) -> int:
    return max(1, min(6, int(task_count or 1)))


def _source_quality_score(url: str, title: str, evidence: str) -> int:
    score = 1 if evidence else 0
    host = urlparse(url).netloc.casefold()
    if host.endswith(".go.th"):
        score += 3
    elif any(domain in host for domain in ("reuters.com", "google.com", "openai.com", "ai.google.dev")):
        score += 2
    if any(marker in f"{title} {evidence}".casefold() for marker in ("updated", "today", "price")):
        score += 1
    return score


def _build_source_analysis(query: str, results: list[WebSearchResult]) -> str:
    if not results:
        return ""
    lines = [f"Analyzed {len(results)} web sources for query: {query}"]
    fetched = [result for result in results if result.evidence]
    if fetched:
        lines.append(f"Fetched readable page evidence from {len(fetched)} source(s).")
    for index, result in enumerate(results, start=1):
        if result.evidence:
            basis = "page evidence"
        elif result.source_type == "fetch-blocked":
            basis = "fetch blocked; does not contain extracted exact values"
        elif result.source_type == "trusted-hint":
            basis = "source hint only; does not contain extracted exact values"
        else:
            basis = "search snippet only; does not contain extracted exact values"
        lines.append(f"[web:{index}] quality={result.quality_score}; basis={basis}; url={result.url}")
        evidence = result.evidence or result.snippet
        if evidence:
            label = "Evidence" if result.evidence else "Snippet"
            lines.append(f"{label}: {evidence[:500]}")
    return "\n".join(lines)


def _relevance_terms(query: str) -> list[str]:
    text = str(query or "").casefold()
    terms: list[str] = []
    phrase_terms = (
        "gemini",
        "openai",
        "z.ai",
        "glm",
        "python",
        "javascript",
        "roblox",
        "blender",
    )
    for term in phrase_terms:
        if term in text:
            terms.append(term)
    for token in re.findall(r"[a-z0-9][a-z0-9._-]{2,}", text):
        if token not in {"the", "and", "for", "with", "latest", "current", "today", "pricing"}:
            terms.append(token)
    thai_stopwords = {
        "ขอ",
        "ช่วย",
        "ข้อมูล",
        "ล่าสุด",
        "วันนี้",
        "ของ",
        "ให้",
        "หน่อย",
        "ประเทศไทย",
    }
    for token in re.findall(r"[\u0E00-\u0E7F]{2,}", text):
        if token not in thai_stopwords:
            terms.append(token)
            if len(token) >= 5:
                terms.append(token[:4])
            if len(token) >= 7:
                terms.append(token[:6])
    return list(dict.fromkeys(terms))

def _fetch_text(url: str, timeout: float) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "AI-Dev-Coworker/0.1 (+local-chat-web-connector)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _normalize_result_url(href: str) -> str:
    raw = str(href or "").strip()
    if raw.startswith("//"):
        raw = "https:" + raw
    parsed = urlparse(raw)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        raw = unquote(target)
        parsed = urlparse(raw)
    if parsed.netloc.endswith("bing.com") and parsed.path.startswith("/ck/"):
        target = _decode_bing_target(parsed.query)
        if target:
            raw = target
            parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return raw


def _collapse_space(value: str) -> str:
    return " ".join(str(value or "").split())


def _decode_bing_target(query: str) -> str:
    encoded = parse_qs(query).get("u", [""])[0]
    if encoded.startswith("a1"):
        encoded = encoded[2:]
    if not encoded:
        return ""
    padded = encoded + "=" * (-len(encoded) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="replace")
    except Exception:
        return ""

