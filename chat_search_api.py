from __future__ import annotations

from typing import Protocol
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_SEARCH_API_TIMEOUT_SECONDS = 8.0
BRAVE_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class SearchProvider(Protocol):
    def search(self, query: str, *, count: int) -> list[dict]:
        """Return normalized search results with title, url, and snippet keys."""


class BraveSearchProvider:
    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: float = DEFAULT_SEARCH_API_TIMEOUT_SECONDS,
        fetcher=None,
    ):
        self._api_key = str(api_key or "").strip()
        self._timeout_seconds = float(timeout_seconds or DEFAULT_SEARCH_API_TIMEOUT_SECONDS)
        self._fetcher = fetcher or _fetch_json

    def search(self, query: str, *, count: int) -> list[dict]:
        if not self._api_key:
            raise RuntimeError("Brave Search API key is not configured.")
        clean_query = str(query or "").strip()
        if not clean_query:
            return []
        limit = max(1, min(int(count or 5), 10))
        url = f"{BRAVE_SEARCH_ENDPOINT}?{urlencode({'q': clean_query, 'count': limit})}"
        payload = self._fetcher(
            url,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self._api_key,
            },
            timeout=self._timeout_seconds,
        )
        results = payload.get("web", {}).get("results", []) if isinstance(payload, dict) else []
        normalized: list[dict] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            snippet = str(item.get("description") or item.get("snippet") or "").strip()
            if not title or not url:
                continue
            normalized.append({"title": title, "url": url, "snippet": snippet})
        return normalized


def get_search_provider(config) -> SearchProvider | None:
    enabled = bool(getattr(config, "search_api_enabled", False))
    provider_name = str(getattr(config, "search_api_provider", "brave") or "brave").strip().casefold()
    api_key = str(getattr(config, "search_api_key", "") or "").strip()
    if not enabled or not api_key:
        return None
    if provider_name == "brave":
        return BraveSearchProvider(api_key)
    return None


def _fetch_json(url: str, *, headers: dict[str, str], timeout: float) -> dict:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8", errors="replace"))
