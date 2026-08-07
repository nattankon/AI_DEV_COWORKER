from __future__ import annotations

import json
from typing import Any


class CompositeToolProvider:
    """Merge multiple tool providers into the shared tool-loop contract."""

    def __init__(self, providers: list[Any] | tuple[Any, ...]):
        self.providers = [provider for provider in providers if provider is not None]
        self._routes: dict[str, Any] = {}
        self.schemas: list[dict[str, Any]] = []
        for provider in self.providers:
            for schema in list(getattr(provider, "schemas", []) or []):
                name = _schema_name(schema)
                if not name:
                    continue
                if name in self._routes:
                    raise ValueError(f"Tool name collision: {name}")
                self._routes[name] = provider
                self.schemas.append(schema)

    def dispatch(self, name: str, arguments: dict[str, Any]) -> str:
        tool_name = str(name or "").strip()
        provider = self._routes.get(tool_name)
        if provider is None:
            return json.dumps({"status": "error", "error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)
        return str(provider.dispatch(tool_name, dict(arguments or {})))

    def reserve_tool_calls(self, calls: list[dict[str, Any]]) -> None:
        by_provider: dict[int, tuple[Any, list[dict[str, Any]]]] = {}
        for call in calls:
            tool_name = str(call.get("tool_name") or "")
            provider = self._routes.get(tool_name)
            if provider is None:
                continue
            key = id(provider)
            if key not in by_provider:
                by_provider[key] = (provider, [])
            by_provider[key][1].append(call)
        for provider, provider_calls in by_provider.values():
            reserve = getattr(provider, "reserve_tool_calls", None)
            if callable(reserve):
                reserve(provider_calls)

    def sources(self) -> list[dict[str, Any]]:
        for provider in self.providers:
            sources = getattr(provider, "sources", None)
            if callable(sources):
                return list(sources())
        return []

    def evidence_corpus(self) -> str:
        parts: list[str] = []
        for provider in self.providers:
            evidence = getattr(provider, "evidence_corpus", None)
            if callable(evidence):
                text = str(evidence() or "").strip()
                if text:
                    parts.append(text)
        return "\n\n".join(parts)

    def freeze(self) -> None:
        for provider in self.providers:
            freeze = getattr(provider, "freeze", None)
            if callable(freeze):
                freeze()


def _schema_name(schema: dict[str, Any]) -> str:
    function = schema.get("function") if isinstance(schema, dict) else None
    if not isinstance(function, dict):
        return ""
    return str(function.get("name") or "").strip()
