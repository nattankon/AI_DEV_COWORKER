from __future__ import annotations

import json
import concurrent.futures
import asyncio
import shlex
import time
from pathlib import Path
from typing import Any, Callable


class McpConnectorRegistry:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.path = self.root / "chat_mcp_connectors.json"

    def list_connectors(self) -> list[dict[str, Any]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        connectors = raw.get("connectors") if isinstance(raw, dict) else []
        return [item for item in connectors if isinstance(item, dict)]

    def save_connectors(self, connectors: list[dict[str, Any]]) -> None:
        clean = _dedupe_connectors([_sanitize_connector(item) for item in connectors if isinstance(item, dict)])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".json.tmp")
        temp.write_text(json.dumps({"schema_version": 1, "connectors": clean}, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)


class McpToolProvider:
    def __init__(
        self,
        clients: dict[str, Any],
        approval_callback: Callable[[dict[str, Any]], bool],
        *,
        restrict_dispatch_to_exposed: bool = False,
    ):
        self.clients = {str(name): client for name, client in clients.items() if name and client is not None}
        self.approval_callback = approval_callback
        # The MODEL-facing provider instance sets restrict_dispatch_to_exposed=True so a
        # model cannot call an unexposed tool by guessing its name; the manual-runner
        # instance leaves it False because the user may run any tool from the panel.
        self.restrict_dispatch_to_exposed = bool(restrict_dispatch_to_exposed)
        self._unexposed: set[str] = set()
        self._routes: dict[str, tuple[str, str, bool]] = {}
        self.schemas: list[dict[str, Any]] = []
        for server_name, client in self.clients.items():
            exposed = _connector_exposed_tools(client)
            for tool in list(client.list_tools() or []):
                tool_name = str(_tool_get(tool, "name") or "").strip()
                if not tool_name:
                    continue
                namespaced = mcp_tool_name(server_name, tool_name)
                read_only = _is_mcp_tool_read_only(server_name, client, tool)
                # Routes cover EVERY tool so the manual runner can dispatch any of
                # them (still approval-gated). Function schemas are what the MODEL
                # sees; a non-empty exposed_tools list narrows only that, keeping
                # per-message context small on big servers.
                self._routes[namespaced] = (server_name, tool_name, read_only)
                if exposed and tool_name not in exposed:
                    self._unexposed.add(namespaced)
                    continue
                self.schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": namespaced,
                            "description": _truncate_text(
                                str(_tool_get(tool, "description") or f"MCP tool {tool_name}"), 300
                            ),
                            "parameters": _strict_object_schema(_tool_get(tool, "inputSchema")),
                        },
                    }
                )

    def tool_metadata(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for schema in self.schemas:
            function = schema.get("function") if isinstance(schema, dict) else {}
            name = str(function.get("name") or "")
            route = self._routes.get(name)
            if route is None:
                continue
            server_name, tool_name, read_only = route
            out.append(
                {
                    "name": tool_name,
                    "namespaced_name": name,
                    "server": server_name,
                    "description": str(function.get("description") or ""),
                    "read_only": read_only,
                    "input_schema": function.get("parameters") if isinstance(function.get("parameters"), dict) else _strict_object_schema({}),
                }
            )
        return out

    def route_metadata(self, name: str) -> dict[str, Any] | None:
        route = self._routes.get(str(name or ""))
        if route is None:
            return None
        server_name, tool_name, read_only = route
        return {"server": server_name, "tool": tool_name, "read_only": read_only}

    def dispatch(self, name: str, arguments: dict[str, Any]) -> str:
        route = self._routes.get(str(name or ""))
        if route is None:
            return json.dumps({"status": "error", "error": f"Unknown MCP tool: {name}"}, ensure_ascii=False)
        if self.restrict_dispatch_to_exposed and str(name or "") in self._unexposed:
            return json.dumps(
                {"status": "error", "error": f"MCP tool is not exposed to the model: {name}"},
                ensure_ascii=False,
            )
        server_name, tool_name, read_only = route
        if not read_only:
            proposal = {"server": server_name, "tool": tool_name, "arguments": dict(arguments or {})}
            if not self.approval_callback(proposal):
                return json.dumps(
                    {"status": "denied", "server": server_name, "tool": tool_name, "read_only": read_only, "error": "User denied MCP tool call."},
                    ensure_ascii=False,
                )
        try:
            result = self.clients[server_name].call_tool(tool_name, _strip_null_arguments(dict(arguments or {})))
        except Exception as exc:
            return json.dumps({"status": "error", "server": server_name, "tool": tool_name, "read_only": read_only, "error": str(exc)}, ensure_ascii=False)
        return json.dumps(
            {"status": "ok", "server": server_name, "tool": tool_name, "read_only": read_only, "result": _normalize_mcp_result(result)},
            ensure_ascii=False,
        )


class McpDiagnosticsToolProvider:
    def __init__(
        self,
        *,
        connectors: list[dict[str, Any]],
        clients: dict[str, Any],
        statuses: list[dict[str, Any]],
    ):
        self.connectors = [_sanitize_connector(item) for item in connectors if isinstance(item, dict)]
        self.clients = clients
        self.statuses = statuses
        self.schemas = [
            {
                "type": "function",
                "function": {
                    "name": "mcp_diagnose_connector",
                    "description": "Read-only diagnostic for configured MCP connectors by name, such as Roblox MCP. Reports whether a configured connector exists and its connection status.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mcp_list_tools",
                    "description": (
                        "Read-only browser for tools exposed by configured MCP connectors. Does not call the tools. "
                        "Returns a compact listing (name, read_only, short description). Pass `tool` with one tool "
                        "name to get that tool's full input schema."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "tool": {"type": ["string", "null"]},
                        },
                        "required": ["query", "tool"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> str:
        if name == "mcp_list_tools":
            return json.dumps(
                {
                    "status": "ok",
                    "servers": self._tool_browser(
                        str((arguments or {}).get("query") or ""),
                        tool_filter=str((arguments or {}).get("tool") or "").strip(),
                    ),
                },
                ensure_ascii=False,
            )
        if name != "mcp_diagnose_connector":
            return json.dumps({"status": "error", "error": f"Unknown MCP diagnostics tool: {name}"}, ensure_ascii=False)
        query = str((arguments or {}).get("query") or "").strip()
        matches = self._matches(query)
        if not matches:
            return json.dumps(
                {
                    "status": "ok",
                    "found": False,
                    "query": query,
                    "matches": [],
                    "message": f"No MCP connector matched {query!r}. Ask the user to install or enable a matching connector/plugin if they want Chat to use it.",
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "status": "ok",
                "found": True,
                "query": query,
                "matches": matches,
                "message": "Configured MCP connector status.",
            },
            ensure_ascii=False,
        )

    def _matches(self, query: str) -> list[dict[str, Any]]:
        terms = _diagnostic_match_terms(query)
        statuses_by_name = {str(item.get("name") or ""): item for item in self.statuses if isinstance(item, dict)}
        out: list[dict[str, Any]] = []
        for connector in self.connectors:
            name = connector["name"]
            haystack = " ".join(str(connector.get(key) or "") for key in ("name", "command", "url")).casefold()
            if terms and not any(term in haystack for term in terms):
                continue
            status = statuses_by_name.get(name, {"name": name, "status": "unknown"})
            out.append(
                {
                    "name": name,
                    "transport": connector.get("transport"),
                    "enabled": bool(connector.get("enabled")),
                    "status": str(status.get("status") or "unknown"),
                    "error": str(status.get("error") or ""),
                    "tools": _client_tool_names(self.clients.get(name)),
                }
            )
        return out

    def _tool_browser(self, query: str, *, tool_filter: str = "") -> list[dict[str, Any]]:
        matches = self._matches(query)
        out: list[dict[str, Any]] = []
        for match in matches:
            client = self.clients.get(match["name"])
            tools: list[dict[str, Any]] = []
            try:
                raw_tools = list(client.list_tools() or []) if client is not None else []
            except Exception:
                raw_tools = []
            for tool in raw_tools:
                tool_name = str(_tool_get(tool, "name") or "")
                if tool_filter:
                    if tool_name.casefold() != tool_filter.casefold():
                        continue
                    tools.append(
                        {
                            "name": tool_name,
                            "description": str(_tool_get(tool, "description") or ""),
                            "read_only": _is_mcp_tool_read_only(match["name"], client, tool),
                            "input_schema": _strict_object_schema(_tool_get(tool, "inputSchema")),
                        }
                    )
                    continue
                # Compact listing: no schemas, so big servers (85+ tools) stay inside
                # the tool-result context budget. Full schema is served per tool via
                # the `tool` argument.
                tools.append(
                    {
                        "name": tool_name,
                        "description": _truncate_text(str(_tool_get(tool, "description") or ""), 100),
                        "read_only": _is_mcp_tool_read_only(match["name"], client, tool),
                    }
                )
            out.append({**match, "tools": tools})
        return out


def mcp_sdk_available() -> bool:
    try:
        import mcp  # noqa: F401
    except Exception:
        return False
    return True


def create_mcp_clients(
    connectors: list[dict[str, Any]],
    *,
    client_factory: Callable[[dict[str, Any]], Any] | None = None,
    sdk_available: Callable[[], bool] = mcp_sdk_available,
    connection_timeout_seconds: float = 3.0,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    clients: dict[str, Any] = {}
    statuses: list[dict[str, Any]] = []
    for raw_connector in connectors:
        connector = _sanitize_connector(raw_connector)
        name = connector["name"]
        if not connector.get("enabled"):
            statuses.append({"name": name, "status": "disabled"})
            continue
        if client_factory is None and not sdk_available():
            statuses.append(
                {
                    "name": name,
                    "status": "unavailable",
                    "error": "MCP SDK is not installed.",
                }
            )
            continue
        try:
            client = _call_with_timeout(
                lambda: client_factory(connector)
                if client_factory
                else _create_sdk_client(connector, probe_timeout_seconds=connection_timeout_seconds),
                timeout_seconds=connection_timeout_seconds,
            )
        except TimeoutError:
            statuses.append({"name": name, "status": "timeout", "error": _connector_timeout_message(connector, connection_timeout_seconds)})
            continue
        except Exception as exc:
            statuses.append({"name": name, "status": "error", "error": _connector_error_message(connector, exc)})
            continue
        if client is None:
            statuses.append({"name": name, "status": "unavailable", "error": "MCP client could not be created."})
            continue
        try:
            tool_summary = _call_with_timeout(lambda: _probe_mcp_client(name, client), timeout_seconds=connection_timeout_seconds)
        except TimeoutError:
            statuses.append({"name": name, "status": "timeout", "error": _connector_timeout_message(connector, connection_timeout_seconds)})
            continue
        except Exception as exc:
            statuses.append({"name": name, "status": "error", "error": _connector_error_message(connector, exc)})
            continue
        clients[name] = client
        statuses.append({"name": name, "status": "connected", **tool_summary})
    return clients, statuses


def validate_connector(item: dict[str, Any]) -> dict[str, Any]:
    connector = _sanitize_connector(item)
    errors: list[str] = []
    if not connector["name"]:
        errors.append("Connector name is required.")
    if connector["transport"] == "stdio" and not connector["command"].strip():
        errors.append("stdio connectors require a command.")
    if connector["transport"] in {"http", "sse"} and not connector["url"].strip():
        errors.append(f"{connector['transport']} connectors require a url.")
    return {"status": "ok" if not errors else "error", "connector": connector, "errors": errors}


def _connector_error_message(connector: dict[str, Any], exc: BaseException) -> str:
    raw = str(exc) or exc.__class__.__name__
    lowered = raw.casefold()
    if any(marker in lowered for marker in ("all connection attempts failed", "unable to connect", "connection refused", "session terminated")):
        target = connector.get("url") or connector.get("command") or connector.get("name")
        message = f"MCP server is not reachable at {target}. Make sure the external MCP server or plugin is running and connected."
        if connector.get("transport") in {"http", "sse"}:
            message += " For HTTP/SSE connectors, use the full MCP endpoint, for example http://localhost:58741/mcp."
        haystack = " ".join(str(connector.get(key) or "") for key in ("name", "command", "url")).casefold()
        if "roblox" in haystack:
            message += " In Roblox Studio, the MCP Server panel should show Connected before testing it here."
        return message
    return raw


def _connector_timeout_message(connector: dict[str, Any], timeout_seconds: float) -> str:
    message = f"MCP connection timed out after {timeout_seconds:g}s."
    if connector.get("transport") in {"http", "sse"}:
        message += " Make sure the external MCP server/plugin is reachable and that the URL points to the full MCP endpoint, for example http://localhost:58741/mcp."
    haystack = " ".join(str(connector.get(key) or "") for key in ("name", "command", "url")).casefold()
    if "roblox" in haystack:
        message += " In Roblox Studio, the MCP Server panel should show Connected before testing it here."
    return message


def _sanitize_connector(item: dict[str, Any]) -> dict[str, Any]:
    name = _safe_name(str(item.get("name") or "connector"))
    transport = str(item.get("transport") or "stdio").strip().casefold()
    return {
        "name": name,
        "transport": transport if transport in {"stdio", "http", "sse"} else "stdio",
        "command": str(item.get("command") or "")[:500],
        "url": str(item.get("url") or "")[:500],
        "enabled": bool(item.get("enabled")),
        "read_only_overrides": _sanitize_read_only_overrides(item.get("read_only_overrides")),
        "exposed_tools": _sanitize_read_only_overrides(item.get("exposed_tools")),
    }


def _dedupe_connectors(connectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Sanitized names collide (e.g. "robloxstudio-mcp" and "robloxstudio_mcp" both
    # sanitize to robloxstudio_mcp). Registry-level guard: the FIRST entry (the
    # user's existing config) wins for connection fields; consent lists from later
    # duplicates are unioned so a preset re-apply can only ADD read-only consent,
    # never clobber a configured transport/command/url.
    by_name: dict[str, dict[str, Any]] = {}
    for connector in connectors:
        key = str(connector.get("name") or "").casefold()
        existing = by_name.get(key)
        if existing is None:
            by_name[key] = dict(connector)
            continue
        for field in ("read_only_overrides", "exposed_tools"):
            merged = list(existing.get(field) or [])
            for item in connector.get(field) or []:
                if item not in merged:
                    merged.append(item)
            if merged:
                existing[field] = merged
    return list(by_name.values())


def _sanitize_read_only_overrides(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        name = str(item or "").strip()[:128]
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out[:200]


def _create_sdk_client(_connector: dict[str, Any], *, probe_timeout_seconds: float = 3.0) -> Any:
    connector = _sanitize_connector(_connector)
    validation = validate_connector(connector)
    if validation["errors"]:
        raise RuntimeError("; ".join(validation["errors"]))
    return SdkMcpClient(connector, probe_timeout_seconds=probe_timeout_seconds)


class SdkMcpClient:
    def __init__(
        self,
        connector: dict[str, Any],
        *,
        operation_timeout_seconds: float = 10.0,
        probe_timeout_seconds: float = 3.0,
        tools_cache_ttl_seconds: float = 60.0,
    ):
        self.connector = _sanitize_connector(connector)
        self.operation_timeout_seconds = max(1.0, float(operation_timeout_seconds))
        self.probe_timeout_seconds = max(0.5, float(probe_timeout_seconds))
        self.tools_cache_ttl_seconds = max(0.0, float(tools_cache_ttl_seconds))
        self._tools_cache: list[Any] | None = None
        self._tools_cache_at = 0.0

    def list_tools(self) -> list[Any]:
        if self._tools_cache is not None and (time.monotonic() - self._tools_cache_at) < self.tools_cache_ttl_seconds:
            return list(self._tools_cache)
        return self._refresh_tools(self.operation_timeout_seconds)

    def probe(self) -> list[Any]:
        # A probe is the bounded connect handshake: always hits the server (no cache)
        # and must finish within the connect budget, not the longer operation budget.
        return self._refresh_tools(self.probe_timeout_seconds)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return asyncio.run(self._run_with_session(lambda session: session.call_tool(name, arguments or {})))

    def _refresh_tools(self, timeout_seconds: float) -> list[Any]:
        tools = list(self._fetch_tool_list(timeout_seconds) or [])
        self._tools_cache = tools
        self._tools_cache_at = time.monotonic()
        return list(tools)

    def _fetch_tool_list(self, timeout_seconds: float) -> list[Any]:
        return asyncio.run(self._run_with_session(lambda session: session.list_tools(), timeout_seconds=timeout_seconds))

    async def _run_with_session(self, operation: Callable[[Any], Any], *, timeout_seconds: float | None = None) -> Any:
        timeout = self.operation_timeout_seconds if timeout_seconds is None else max(0.5, float(timeout_seconds))
        try:
            return await asyncio.wait_for(self._run_with_session_unbounded(operation), timeout=timeout)
        except TimeoutError as exc:
            raise RuntimeError(f"MCP SDK operation timed out after {timeout:g}s.") from exc
        except RuntimeError as exc:
            message = str(exc)
            if message.startswith("MCP SDK") or message.startswith("Unsupported MCP transport"):
                raise
            raise RuntimeError(f"MCP SDK connection failed: {message}") from exc
        except Exception as exc:
            raise RuntimeError(f"MCP SDK connection failed: {_exception_summary(exc)}") from exc

    async def _run_with_session_unbounded(self, operation: Callable[[Any], Any]) -> Any:
        transport = self.connector["transport"]
        if transport == "stdio":
            return await self._run_stdio(operation)
        if transport == "http":
            return await self._run_streamable_http(operation)
        if transport == "sse":
            return await self._run_sse(operation)
        raise RuntimeError(f"Unsupported MCP transport: {transport}")

    async def _run_stdio(self, operation: Callable[[Any], Any]) -> Any:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except Exception as exc:
            raise RuntimeError("MCP SDK is not installed.") from exc
        command_parts = _split_command(self.connector["command"])
        if not command_parts:
            raise RuntimeError("stdio connectors require a command.")
        params = StdioServerParameters(command=command_parts[0], args=command_parts[1:])
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = operation(session)
                if hasattr(result, "__await__"):
                    result = await result
                return _normalize_mcp_sdk_payload(result)

    async def _run_streamable_http(self, operation: Callable[[Any], Any]) -> Any:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except Exception as exc:
            raise RuntimeError("MCP SDK streamable HTTP transport is not installed.") from exc
        url = str(self.connector.get("url") or "").strip()
        if not url:
            raise RuntimeError("http connectors require a url.")
        async with streamablehttp_client(url) as streams:
            read_stream, write_stream = _unpack_transport_streams(streams)
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = operation(session)
                if hasattr(result, "__await__"):
                    result = await result
                return _normalize_mcp_sdk_payload(result)

    async def _run_sse(self, operation: Callable[[Any], Any]) -> Any:
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
        except Exception as exc:
            raise RuntimeError("MCP SDK SSE transport is not installed.") from exc
        url = str(self.connector.get("url") or "").strip()
        if not url:
            raise RuntimeError("sse connectors require a url.")
        async with sse_client(url) as streams:
            read_stream, write_stream = _unpack_transport_streams(streams)
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = operation(session)
                if hasattr(result, "__await__"):
                    result = await result
                return _normalize_mcp_sdk_payload(result)


def _safe_name(value: str) -> str:
    clean = "".join(char if char.isalnum() or char == "_" else "_" for char in str(value or "").strip())
    return clean.strip("_") or "tool"


def _truncate_text(value: str, limit: int) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def mcp_tool_name(server_name: str, tool_name: str) -> str:
    return f"mcp__{_safe_name(server_name)}__{_safe_name(tool_name)}"


def _split_command(command: str) -> list[str]:
    try:
        return shlex.split(str(command or ""), posix=False)
    except ValueError:
        return str(command or "").split()


def _terms(value: str) -> list[str]:
        return [part for part in _safe_name(value).casefold().split("_") if part and len(part) > 1]


_MCP_DIAGNOSTIC_GENERIC_TERMS = {
    "check",
    "connection",
    "connector",
    "connectors",
    "diagnose",
    "diagnostic",
    "mcp",
    "server",
    "status",
    "test",
    "ตรวจสอบ",
    "ทดสอบ",
    "สถานะ",
    "เชื่อมต่อ",
}


def _diagnostic_match_terms(value: str) -> list[str]:
    terms = _terms(value)
    return [term for term in terms if term not in _MCP_DIAGNOSTIC_GENERIC_TERMS]


def _unpack_transport_streams(streams: Any) -> tuple[Any, Any]:
    if not isinstance(streams, tuple) or len(streams) < 2:
        raise RuntimeError("MCP transport did not return readable streams.")
    return streams[0], streams[1]


def _exception_summary(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup):
        parts = [_exception_summary(item) for item in exc.exceptions[:3]]
        return "; ".join(part for part in parts if part) or str(exc)
    return str(exc) or exc.__class__.__name__


def _client_tool_names(client: Any) -> list[str]:
    if client is None:
        return []
    try:
        tools = list(client.list_tools() or [])
    except Exception:
        return []
    return [str(_tool_get(tool, "name") or "").strip() for tool in tools if str(_tool_get(tool, "name") or "").strip()]


def _call_with_timeout(callback: Callable[[], Any], *, timeout_seconds: float) -> Any:
    timeout = max(0.1, float(timeout_seconds))
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(callback)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise TimeoutError(str(exc)) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _probe_mcp_client(server_name: str, client: Any) -> dict[str, int]:
    probe = getattr(client, "probe", None)
    if callable(probe):
        tools = list(probe() or [])
    elif hasattr(client, "list_tools"):
        tools = list(client.list_tools() or [])
    else:
        return {"tool_count": 0, "read_only_tool_count": 0, "write_tool_count": 0, "tools": []}
    read_only = 0
    for tool in tools:
        if _is_mcp_tool_read_only(server_name, client, tool):
            read_only += 1
    return {
        "tool_count": len(tools),
        "read_only_tool_count": read_only,
        "write_tool_count": max(0, len(tools) - read_only),
        "tools": _mcp_tool_metadata_from_tools(server_name, client, tools),
    }


def _mcp_tool_metadata_from_tools(server_name: str, client: Any, tools: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tool in tools:
        tool_name = str(_tool_get(tool, "name") or "").strip()
        if not tool_name:
            continue
        out.append(
            {
                "name": tool_name,
                "description": str(_tool_get(tool, "description") or ""),
                "read_only": _is_mcp_tool_read_only(server_name, client, tool),
                "input_schema": _strict_object_schema(_tool_get(tool, "inputSchema")),
            }
        )
    return out


def _connector_exposed_tools(client: Any) -> set[str]:
    connector = getattr(client, "connector", None) if client is not None else None
    exposed = connector.get("exposed_tools") if isinstance(connector, dict) else None
    if not isinstance(exposed, (list, tuple)):
        return set()
    return {str(item or "").strip() for item in exposed if str(item or "").strip()}


def _is_mcp_tool_read_only(server_name: str, client: Any, tool: Any) -> bool:
    annotations = _tool_get(tool, "annotations") or {}
    if bool(annotations.get("readOnlyHint")):
        return True
    tool_name = str(_tool_get(tool, "name") or "").strip()
    if not tool_name:
        return False
    connector = getattr(client, "connector", None) if client is not None else None
    overrides = connector.get("read_only_overrides") if isinstance(connector, dict) else None
    if not isinstance(overrides, (list, tuple)):
        return False
    return tool_name in {str(item or "").strip() for item in overrides}


def _tool_get(tool: Any, key: str) -> Any:
    if isinstance(tool, dict):
        return tool.get(key)
    return getattr(tool, key, None)


def _normalize_mcp_result(result: Any) -> Any:
    if isinstance(result, dict):
        return {str(key): _normalize_mcp_result(value) for key, value in result.items()}
    if isinstance(result, (list, tuple)):
        return [_normalize_mcp_result(item) for item in result]
    if isinstance(result, (str, int, float, bool)) or result is None:
        return result
    model_dump = getattr(result, "model_dump", None)
    if callable(model_dump):
        try:
            return _normalize_mcp_result(model_dump())
        except Exception:
            pass
    if hasattr(result, "type") and hasattr(result, "text"):
        return {
            "type": str(getattr(result, "type", "")),
            "text": str(getattr(result, "text", "")),
        }
    if hasattr(result, "__dict__"):
        public = {
            str(key): value
            for key, value in vars(result).items()
            if not str(key).startswith("_")
        }
        if public:
            return _normalize_mcp_result(public)
    return str(result)


def _normalize_mcp_sdk_payload(result: Any) -> Any:
    if hasattr(result, "tools"):
        return list(getattr(result, "tools") or [])
    if hasattr(result, "content"):
        return {"content": getattr(result, "content")}
    return result


def _strict_object_schema(schema: Any) -> dict[str, Any]:
    normalized = _normalize_strict_schema(schema, depth=0)
    if normalized.get("type") != "object":
        normalized["type"] = "object"
    if not isinstance(normalized.get("properties"), dict):
        normalized["properties"] = {}
    normalized["required"] = [str(name) for name in normalized.get("required", []) if str(name) in normalized["properties"]]
    for name in normalized["properties"]:
        if name not in normalized["required"]:
            normalized["required"].append(name)
    normalized["additionalProperties"] = False
    return normalized


def _normalize_strict_schema(schema: Any, *, depth: int) -> dict[str, Any]:
    if not isinstance(schema, dict):
        schema = {}
    if depth > 5:
        return dict(schema)
    normalized = dict(schema)
    raw_properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    if normalized.get("type") == "object" or raw_properties:
        required = schema.get("required") if isinstance(schema.get("required"), list) else []
        original_required = {str(item) for item in required if str(item) in raw_properties}
        properties: dict[str, Any] = {}
        for name, value in raw_properties.items():
            prop_name = str(name)
            prop_schema = _normalize_strict_schema(value, depth=depth + 1)
            if prop_name not in original_required:
                prop_schema = _nullable_schema(prop_schema)
            properties[prop_name] = prop_schema
        required_names = [str(item) for item in required if str(item) in properties]
        for name in properties:
            if name not in required_names:
                required_names.append(str(name))
        normalized["type"] = "object"
        normalized["properties"] = properties
        normalized["required"] = required_names
        normalized["additionalProperties"] = False
    if isinstance(normalized.get("items"), dict):
        normalized["items"] = _normalize_strict_schema(normalized["items"], depth=depth + 1)
    return normalized


def _nullable_schema(schema: dict[str, Any]) -> dict[str, Any]:
    next_schema = dict(schema)
    schema_type = next_schema.get("type")
    if isinstance(schema_type, list):
        if "null" not in schema_type:
            next_schema["type"] = [*schema_type, "null"]
        return next_schema
    if isinstance(schema_type, str):
        if schema_type != "null":
            next_schema["type"] = [schema_type, "null"]
        return next_schema
    if "anyOf" in next_schema and isinstance(next_schema["anyOf"], list):
        if not any(isinstance(item, dict) and item.get("type") == "null" for item in next_schema["anyOf"]):
            next_schema["anyOf"] = [*next_schema["anyOf"], {"type": "null"}]
        return next_schema
    next_schema["anyOf"] = [dict(next_schema), {"type": "null"}]
    return next_schema


def _strip_null_arguments(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_null_arguments(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_strip_null_arguments(item) for item in value if item is not None]
    return value
