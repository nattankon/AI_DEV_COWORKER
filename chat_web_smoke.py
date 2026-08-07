from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

try:
    from .chat_playwright_fetch import PlaywrightFetcher
    from .chat_runtime import ChatRuntimeConfig
    from .chat_search_api import get_search_provider
    from .chat_source_adapters import fetch_source_tables, has_source_adapter
    from .chat_web_connector import _extract_page_evidence, _extract_tables, _fetch_text, _is_blocked_page, _source_quality_score
except ImportError:
    from chat_playwright_fetch import PlaywrightFetcher
    from chat_runtime import ChatRuntimeConfig
    from chat_search_api import get_search_provider
    from chat_source_adapters import fetch_source_tables, has_source_adapter
    from chat_web_connector import _extract_page_evidence, _extract_tables, _fetch_text, _is_blocked_page, _source_quality_score


Fetcher = Callable[[str, float], str]


SOURCE_PROFILE_FILENAME = "chat-web-source-profile.json"


HARD_SMOKE_URLS = (
    "https://www.eppo.go.th/data-energy-statistic/energy-price-th/ราคาขายปลีกน้ำมัน/",
    "https://www.bangchak.co.th/th/oilprice",
    "https://oil-price.bangchak.co.th/BcpOilPrice2/th",
    "https://www.globalpetrolprices.com/Thailand/gasoline_prices/",
)


def run_web_smoke(
    urls: list[str] | tuple[str, ...],
    *,
    playwright: bool = False,
    fetcher: Fetcher | None = None,
    playwright_fetcher: Callable[[str], str | None] | None = None,
    timeout_seconds: float = 8.0,
    query: str = "current data table",
) -> dict[str, Any]:
    active_fetcher = fetcher or _fetch_text
    provider = get_search_provider(ChatRuntimeConfig())
    results = [
        _smoke_one_url(
            str(url),
            fetcher=active_fetcher,
            playwright=playwright,
            playwright_fetcher=playwright_fetcher,
            timeout_seconds=timeout_seconds,
            query=query,
        )
        for url in urls
        if str(url).strip()
    ]
    return {
        "status": "ok",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "search_provider": "brave_api" if provider is not None else "not_checked",
        "playwright_enabled": bool(playwright),
        "results": results,
    }


def save_web_smoke_report(report: dict[str, Any], *, output_dir: str | Path = "work_logs") -> dict[str, str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    json_path = root / f"chat-web-smoke-{stamp}.json"
    md_path = root / f"chat-web-smoke-{stamp}.md"
    profile_path = root / SOURCE_PROFILE_FILENAME
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    profile = build_source_smoke_profile(report, existing=_load_source_smoke_profile(profile_path))
    profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path), "source_profile": str(profile_path)}


def build_source_smoke_profile(report: dict[str, Any], *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = _normalize_source_smoke_profile(existing)
    run_stamp = str(report.get("generated_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    profile["updated_at"] = run_stamp
    profile["runs"] = int(profile.get("runs") or 0) + 1

    for item in report.get("results", []):
        if not isinstance(item, dict):
            continue
        domain = _domain_from_url(str(item.get("url") or ""))
        if not domain:
            continue
        row = profile["domains"].setdefault(domain, _empty_domain_profile(domain))
        layer = str(item.get("layer_used") or "empty")
        evidence_len = int(item.get("evidence_len") or 0)
        quality_score = int(item.get("quality_score") or 0)
        success = layer in {"adapter", "html", "playwright"} and evidence_len > 0
        blocked = layer == "blocked"

        row["runs"] += 1
        row["successes"] += 1 if success else 0
        row["blocked"] += 1 if blocked else 0
        row["empty"] += 1 if layer == "empty" else 0
        row["tables"] += 1 if item.get("has_tables") else 0
        row["total_evidence_len"] += evidence_len
        row["total_quality_score"] += quality_score
        row["layers"][layer] = int(row["layers"].get(layer) or 0) + 1
        row["last_url"] = str(item.get("url") or "")
        row["last_layer"] = layer
        row["last_source_type"] = str(item.get("source_type") or "")
        row["last_seen_at"] = run_stamp
        row["best_layer"] = _best_layer(row["layers"])
        row["success_rate"] = round(row["successes"] / row["runs"], 4) if row["runs"] else 0.0
        row["blocked_rate"] = round(row["blocked"] / row["runs"], 4) if row["runs"] else 0.0
        row["avg_quality_score"] = round(row["total_quality_score"] / row["runs"], 4) if row["runs"] else 0.0
        row["avg_evidence_len"] = int(row["total_evidence_len"] / row["runs"]) if row["runs"] else 0

    return profile


def _load_source_smoke_profile(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_source_smoke_profile(existing: dict[str, Any] | None) -> dict[str, Any]:
    profile = existing if isinstance(existing, dict) else {}
    domains = profile.get("domains")
    if not isinstance(domains, dict):
        domains = {}
    normalized_domains: dict[str, dict[str, Any]] = {}
    for domain, row in domains.items():
        if isinstance(row, dict):
            normalized_domains[str(domain)] = _normalize_domain_profile(str(domain), row)
    return {
        "schema_version": 1,
        "updated_at": str(profile.get("updated_at") or ""),
        "runs": int(profile.get("runs") or 0),
        "domains": normalized_domains,
    }


def _normalize_domain_profile(domain: str, row: dict[str, Any]) -> dict[str, Any]:
    base = _empty_domain_profile(domain)
    for key in (
        "runs",
        "successes",
        "blocked",
        "empty",
        "tables",
        "total_evidence_len",
        "total_quality_score",
        "avg_evidence_len",
    ):
        base[key] = int(row.get(key) or 0)
    for key in ("success_rate", "blocked_rate", "avg_quality_score"):
        base[key] = float(row.get(key) or 0.0)
    for key in ("last_url", "last_layer", "last_source_type", "last_seen_at", "best_layer"):
        base[key] = str(row.get(key) or "")
    layers = row.get("layers")
    if isinstance(layers, dict):
        base["layers"] = {str(name): int(count or 0) for name, count in layers.items()}
    return base


def _empty_domain_profile(domain: str) -> dict[str, Any]:
    return {
        "domain": domain,
        "runs": 0,
        "successes": 0,
        "blocked": 0,
        "empty": 0,
        "tables": 0,
        "total_evidence_len": 0,
        "total_quality_score": 0,
        "success_rate": 0.0,
        "blocked_rate": 0.0,
        "avg_quality_score": 0.0,
        "avg_evidence_len": 0,
        "layers": {},
        "best_layer": "",
        "last_url": "",
        "last_layer": "",
        "last_source_type": "",
        "last_seen_at": "",
    }


def _domain_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    return (parsed.netloc or "").lower()


def _best_layer(layers: dict[str, int]) -> str:
    priority = {"adapter": 4, "playwright": 3, "html": 2, "blocked": 1, "empty": 0}
    if not layers:
        return ""
    return sorted(layers.items(), key=lambda item: (priority.get(item[0], 0), item[1], item[0]), reverse=True)[0][0]


def _smoke_one_url(
    url: str,
    *,
    fetcher: Fetcher,
    playwright: bool,
    playwright_fetcher: Callable[[str], str | None] | None,
    timeout_seconds: float,
    query: str,
) -> dict[str, Any]:
    layer_used = "empty"
    evidence = ""
    tables: list[dict] = []
    source_type = "empty"

    try:
        if has_source_adapter(url):
            tables = fetch_source_tables(url, fetcher=fetcher, timeout=timeout_seconds)
            evidence = _tables_to_evidence(tables)
            if evidence:
                layer_used = "adapter"
                source_type = "source-adapter"
    except Exception:
        tables = []
        evidence = ""

    html = ""
    if not evidence:
        try:
            html = str(fetcher(url, timeout_seconds) or "")
        except Exception:
            html = ""
        if html and _is_blocked_page(html):
            layer_used = "blocked"
            source_type = "fetch-blocked"
        elif html:
            tables = _extract_tables(html)
            evidence = _extract_page_evidence(html, query=query)
            if evidence:
                layer_used = "html"
                source_type = "fetched-page"

    if not evidence and playwright and layer_used not in {"blocked"}:
        rendered = _fetch_with_playwright(url, playwright_fetcher=playwright_fetcher, timeout_seconds=timeout_seconds)
        if rendered:
            tables = _extract_tables(rendered)
            evidence = _extract_page_evidence(rendered, query=query)
            if evidence:
                layer_used = "playwright"
                source_type = "playwright-page"

    quality_score = _source_quality_score(url, url, evidence) if evidence else 0
    return {
        "url": url,
        "layer_used": layer_used,
        "evidence_len": len(evidence),
        "has_tables": bool(tables),
        "source_type": source_type,
        "quality_score": quality_score,
    }


def _fetch_with_playwright(
    url: str,
    *,
    playwright_fetcher: Callable[[str], str | None] | None,
    timeout_seconds: float,
) -> str:
    if playwright_fetcher is not None:
        return str(playwright_fetcher(url) or "")
    return str(PlaywrightFetcher().fetch(url, timeout=timeout_seconds) or "")


def _tables_to_evidence(tables: list[dict]) -> str:
    lines: list[str] = []
    for table in tables:
        headers = list(table.get("headers") or [])
        for row in list(table.get("rows") or []):
            cells = [str(cell or "").strip() for cell in row]
            if len(cells) < 2 or not cells[0]:
                continue
            if len(headers) == len(cells) and len(cells) > 2:
                values = "; ".join(f"{header} {cell}" for header, cell in zip(headers[1:], cells[1:]))
            else:
                values = " | ".join(cells[1:])
            lines.append(f"{cells[0]}: {values}")
    return " | ".join(lines)


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Chat Web Smoke Report",
        "",
        f"- Search provider: {report.get('search_provider', 'unknown')}",
        f"- Playwright enabled: {bool(report.get('playwright_enabled'))}",
        "",
        "| URL | Layer | Evidence | Tables | Type | Quality |",
        "|---|---|---:|---:|---|---:|",
    ]
    for item in report.get("results", []):
        lines.append(
            f"| {item.get('url', '')} | {item.get('layer_used', '')} | {item.get('evidence_len', 0)} | "
            f"{bool(item.get('has_tables'))} | {item.get('source_type', '')} | {item.get('quality_score', 0)} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run opt-in live web fallback smoke diagnostics.")
    parser.add_argument("--live", action="store_true", help="Required. Confirms live network/browser fetches are allowed.")
    parser.add_argument("--playwright", action="store_true", help="Enable Playwright fallback for pages that static fetch cannot read.")
    parser.add_argument("--url", action="append", default=[], help="URL to smoke test. Can be repeated.")
    parser.add_argument("--output-dir", default="work_logs")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("--live is required so the default test suite never triggers network/browser work.")
    report = run_web_smoke(args.url or list(HARD_SMOKE_URLS), playwright=args.playwright)
    paths = save_web_smoke_report(report, output_dir=args.output_dir)
    _write_json_stdout({"status": "ok", "reports": paths, "summary": report})
    return 0


def _write_json_stdout(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write(text.encode("utf-8"))
        buffer.flush()
        return
    sys.stdout.write(text)


if __name__ == "__main__":
    raise SystemExit(main())
