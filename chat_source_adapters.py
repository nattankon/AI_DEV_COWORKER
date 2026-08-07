from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse


Fetcher = Callable[[str, float], str]

BANGCHAK_ENDPOINT = "https://oil-price.bangchak.co.th/apioilprice2/th"
EPPO_ENDPOINT = "https://www.eppo.go.th/wp-json/oil-api/v1/oil-prices"


@dataclass(frozen=True)
class SourceAdapter:
    host_substring: str
    fetch_tables: Callable[[str, Fetcher, float], list[dict]]
    # When non-empty, the URL path must also contain one of these markers. This
    # keeps a broad corporate host (www.bangchak.co.th) from hijacking EVERY page
    # on that domain with a price table — only price-ish paths get the adapter.
    path_substrings: tuple[str, ...] = ()


def fetch_source_tables(url: str, *, fetcher: Fetcher, timeout: float) -> list[dict]:
    adapter = _find_adapter(url)
    if adapter is None:
        return []
    return adapter.fetch_tables(str(url or ""), fetcher, timeout)


def has_source_adapter(url: str) -> bool:
    return _find_adapter(url) is not None


def _find_adapter(url: str) -> SourceAdapter | None:
    parsed = urlparse(str(url or ""))
    host = parsed.netloc.casefold()
    path = parsed.path.casefold()
    for adapter in _ADAPTERS:
        if adapter.host_substring not in host:
            continue
        if adapter.path_substrings and not any(marker in path for marker in adapter.path_substrings):
            continue
        return adapter
    return None


def _fetch_bangchak_tables(url: str, fetcher: Fetcher, timeout: float) -> list[dict]:
    del url
    raw = fetcher(BANGCHAK_ENDPOINT, timeout)
    try:
        payload = json.loads(str(raw or ""))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list) or not payload:
        return []
    record = payload[0] if isinstance(payload[0], dict) else {}
    try:
        oil_list = json.loads(str(record.get("OilList") or "[]"), parse_float=Decimal)
    except json.JSONDecodeError:
        return []
    rows: list[list[str]] = []
    for item in oil_list if isinstance(oil_list, list) else []:
        if not isinstance(item, dict):
            continue
        name = _clean_cell(item.get("OilName"))
        if not name:
            continue
        rows.append(
            [
                name,
                _format_cell(item.get("PriceToday")),
                _format_cell(item.get("PriceTomorrow")),
                _format_cell(item.get("PriceDifTomorrow")),
            ]
        )
    if not rows:
        return []
    date = _clean_cell(record.get("OilDateNow") or record.get("OilPriceDate"))
    caption = "Bangchak oil prices" + (f" ({date})" if date else "")
    return [{"caption": caption, "headers": ["Fuel", "PriceToday", "PriceTomorrow", "PriceDifTomorrow"], "rows": rows}]


def _fetch_eppo_tables(url: str, fetcher: Fetcher, timeout: float) -> list[dict]:
    del url
    raw = fetcher(EPPO_ENDPOINT, timeout)
    try:
        payload = json.loads(str(raw or ""))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict) or payload.get("status") != "success":
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    rows: list[list[str]] = []
    for provider, values in data.items():
        if not isinstance(values, dict):
            continue
        date = _clean_cell(values.get(f"oil_{provider}_date"))
        time = _clean_cell(values.get(f"oil_{provider}_time"))
        for suffix, label in _EPPO_FUEL_LABELS:
            price = _format_cell(values.get(f"oil_{provider}_{suffix}"))
            if not price or price == "-":
                continue
            rows.append([str(provider), label, price, date, time])
    if not rows:
        return []
    updated = _clean_cell(payload.get("last_updated"))
    caption = "EPPO oil prices" + (f" (last updated {updated})" if updated else "")
    return [{"caption": caption, "headers": ["Provider", "Fuel", "Price", "Date", "Time"], "rows": rows}]


_EPPO_FUEL_LABELS: tuple[tuple[str, str], ...] = (
    ("gl95", "Gasoline 95"),
    ("gh95", "Gasohol 95"),
    ("gh91", "Gasohol 91"),
    ("e20", "Gasohol E20"),
    ("e85", "Gasohol E85"),
    ("ds", "Diesel"),
    ("pds", "Premium Diesel"),
    ("dsb20", "Diesel B20"),
    ("dsb10", "Diesel B10"),
    ("gs95p", "Premium Gasohol 95"),
    ("gs99p", "Premium Gasohol 99"),
    ("gl95p", "Premium Gasoline 95"),
)


def _clean_cell(value: object) -> str:
    return " ".join(str("" if value is None else value).split())


def _format_cell(value: object) -> str:
    if value is None:
        return ""
    text = _clean_cell(value)
    if not text or text == "-":
        return text
    try:
        decimal = Decimal(text)
    except (InvalidOperation, ValueError):
        return text
    return f"{decimal.quantize(Decimal('0.00'))}"


_ADAPTERS: tuple[SourceAdapter, ...] = (
    # "bangchak.co.th" matches both www and the oil-price subdomain (same JSON API),
    # but only on price paths: /th/oilprice, /BcpOilPrice2/th, /apioilprice2/th all
    # contain "oilprice". Other corporate pages (investor relations, news) must NOT
    # be hijacked by a fuel-price table.
    SourceAdapter("bangchak.co.th", _fetch_bangchak_tables, path_substrings=("oilprice", "oil-price")),
    SourceAdapter("eppo.go.th", _fetch_eppo_tables),
)
