from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any, Callable

try:
    from .workspace_tools import WorkspaceTools
except ImportError:
    from workspace_tools import WorkspaceTools


_WORKSPACE_TOOL_POLICY = (
    {"name": "list_directory", "read_only": True, "destructive": False},
    {"name": "search_files", "read_only": True, "destructive": False},
    {"name": "read_file", "read_only": True, "destructive": False},
    {"name": "write_file", "read_only": False, "destructive": False},
    {"name": "edit_file", "read_only": False, "destructive": False},
    {"name": "list_backups", "read_only": True, "destructive": False},
    {"name": "restore_backup", "read_only": False, "destructive": True},
    {"name": "git_status", "read_only": True, "destructive": False},
    {"name": "git_diff", "read_only": True, "destructive": False},
    {"name": "run_verification", "read_only": False, "destructive": False},
)
_WORKSPACE_TOOL_NAMES = {item["name"] for item in _WORKSPACE_TOOL_POLICY}
_WORKSPACE_TOOL_POLICIES = {item["name"]: item for item in _WORKSPACE_TOOL_POLICY}
_AUDIT_LOCK = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _default_audit_sink(event_type: str, payload: dict[str, Any]) -> None:
    root = Path(os.environ.get("COWORK_USER_DATA_DIR") or Path(__file__).resolve().parent)
    path = root / "work_logs" / "sessions" / "web-chat-local-gateway.jsonl"
    entry = {"timestamp": _utc_now(), "event_type": str(event_type), "payload": payload}
    path.parent.mkdir(parents=True, exist_ok=True)
    with _AUDIT_LOCK:
        with path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


class WebChatLocalMcpGateway:
    """Local-only tool gateway bound to one Web Chat workspace grant generation.

    Callers present the active grant ID and revision on every dispatch. Remote side
    effects additionally require the exact active tunnel generation and flow through
    the native approval callbacks before WorkspaceTools can mutate local state.
    """

    def __init__(
        self,
        *,
        workspace: str | Path,
        grant_id: str,
        grant_revision: int,
        permission_mode: str,
        workspace_tools_factory: Callable[[Path], Any] | None = None,
        providers: dict[str, Any] | None = None,
        approval_callback: Callable[[str, str, dict[str, Any], dict[str, Any]], bool] | None = None,
        tunnel_invalidated_callback: Callable[[dict[str, Any]], None] | None = None,
        audit_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ):
        self.workspace = Path(workspace).expanduser().resolve(strict=True)
        if not self.workspace.is_dir():
            raise ValueError(f"Workspace directory does not exist: {self.workspace}")
        self.grant_id = str(grant_id or "").strip()
        self.grant_revision = int(grant_revision)
        self.permission_mode = str(permission_mode or "manual").strip().casefold()
        if not self.grant_id:
            raise ValueError("Web Chat gateway requires a grant ID.")
        if self.permission_mode not in {"manual", "trusted", "full"}:
            raise ValueError("Web Chat gateway permission mode is invalid.")
        self._audit_sink = audit_sink or _default_audit_sink
        self._approval_callback = approval_callback or (lambda _kind, _question, _proposal, _context: False)
        self._tunnel_invalidated_callback = tunnel_invalidated_callback or (lambda _context: None)
        self._state_lock = threading.RLock()
        self._dispatch_context = threading.local()
        self._active_tunnel_generation: int | None = None
        self._workspace_tools = (
            workspace_tools_factory(self.workspace)
            if workspace_tools_factory
            else WorkspaceTools(
                self.workspace,
                approve_write=self._approve_workspace_write,
                approve_command=self._approve_workspace_command,
                audit_sink=self._audit_workspace_event,
            )
        )
        self._providers = {
            str(name).strip(): provider
            for name, provider in dict(providers or {}).items()
            if str(name).strip() and provider is not None
        }
        self._routes: dict[str, tuple[str, str]] = {}
        self._route_policies: dict[str, dict[str, Any]] = {}
        self._catalog = self._build_catalog()
        self._audit(
            "web_chat_gateway_bound",
            {"grant_id": self.grant_id, "grant_revision": self.grant_revision, "permission_mode": self.permission_mode, "tool_count": len(self._catalog)},
        )

    def list_tools(self) -> list[dict[str, Any]]:
        return [json.loads(json.dumps(item, ensure_ascii=False)) for item in self._catalog]

    def public_state(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "grant_id": self.grant_id,
            "grant_revision": self.grant_revision,
            "permission_mode": self.permission_mode,
            "workspace_path": str(self.workspace),
            "tools_enabled": True,
            "tunnel_connected": False,
            "tool_count": len(self._catalog),
            "tools": self.list_tools(),
        }

    @property
    def active_tunnel_generation(self) -> int | None:
        with self._state_lock:
            return self._active_tunnel_generation

    def activate_tunnel(self, generation: int) -> None:
        run_generation = int(generation)
        if run_generation <= 0:
            raise ValueError("Web Chat tunnel generation must be positive.")
        with self._state_lock:
            self._active_tunnel_generation = run_generation
        self._audit("web_chat_gateway_tunnel_activated", {"grant_id": self.grant_id, "tunnel_generation": run_generation})

    def deactivate_tunnel(self, generation: int, reason: str = "stopped") -> None:
        run_generation = int(generation)
        with self._state_lock:
            if self._active_tunnel_generation != run_generation:
                return
            self._active_tunnel_generation = None
        context = {
            "origin": "web_chat",
            "grant_id": self.grant_id,
            "grant_revision": self.grant_revision,
            "tunnel_generation": run_generation,
            "reason": str(reason or "stopped"),
        }
        self._tunnel_invalidated_callback(context)
        self._audit("web_chat_gateway_tunnel_deactivated", context)

    def dispatch(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        grant_id: str,
        grant_revision: int,
        tunnel_generation: int | None = None,
    ) -> str:
        name = str(tool_name or "").strip()
        clean_arguments = dict(arguments or {})
        try:
            requested_revision = int(grant_revision)
        except (TypeError, ValueError):
            requested_revision = -1
        if str(grant_id or "").strip() != self.grant_id or requested_revision != self.grant_revision:
            return self._denied(name, "Stale Web Chat workspace grant generation.")
        remote_generation = self._normalize_tunnel_generation(tunnel_generation)
        if tunnel_generation is not None and not self._is_active_tunnel_generation(remote_generation):
            return self._denied(name, "Stale Web Chat tunnel generation.")
        if name in _WORKSPACE_TOOL_NAMES:
            policy = _WORKSPACE_TOOL_POLICIES[name]
            if not policy["read_only"] and not self._is_active_tunnel_generation(remote_generation):
                return self._denied(name, "Web Chat side effects require the active tunnel generation.")
            context = self._tool_context(name, clean_arguments, remote_generation, source="workspace")
            self._dispatch_context.value = context
            try:
                result = self._workspace_tools.dispatch(name, clean_arguments)
            finally:
                self._dispatch_context.value = None
            self._audit_call(name, clean_arguments, result)
            return result
        route = self._routes.get(name)
        if route is None:
            return self._denied(name, "Tool is not exposed by the Web Chat local gateway.")
        provider_name, provider_tool = route
        policy = self._route_policies.get(name, {})
        if not policy.get("read_only", False):
            if not self._is_active_tunnel_generation(remote_generation):
                return self._denied(name, "Web Chat side effects require the active tunnel generation.")
            context = self._tool_context(name, clean_arguments, remote_generation, source=provider_name)
            approved = self._approval_callback(
                "mcp_tool_call",
                f"Approve Web Chat MCP tool {provider_name}/{provider_tool}?",
                {"server": provider_name, "tool": provider_tool, "arguments": clean_arguments},
                context,
            )
            if not approved or not self._is_active_tunnel_generation(remote_generation):
                return self._denied(name, "Web Chat MCP tool was not approved.")
        result = self._normalize_provider_result(
            self._providers[provider_name].dispatch(provider_tool, clean_arguments),
            provider_name=provider_name,
            tool_name=provider_tool,
        )
        self._audit_call(name, arguments, result)
        return result

    def close(self, reason: str = "revoked") -> None:
        generation = self.active_tunnel_generation
        if generation is not None:
            self.deactivate_tunnel(generation, reason)
        self._audit(
            "web_chat_gateway_unbound",
            {"grant_id": self.grant_id, "grant_revision": self.grant_revision, "reason": str(reason or "revoked")},
        )

    def _build_catalog(self) -> list[dict[str, Any]]:
        schemas = {
            str((schema.get("function") or {}).get("name") or ""): schema
            for schema in list(getattr(self._workspace_tools, "schemas", []) or [])
            if isinstance(schema, dict)
        }
        catalog: list[dict[str, Any]] = []
        for policy in _WORKSPACE_TOOL_POLICY:
            schema = schemas.get(policy["name"])
            function = schema.get("function") if isinstance(schema, dict) else None
            if not isinstance(function, dict):
                continue
            catalog.append(self._catalog_tool(
                policy["name"],
                function,
                source="workspace",
                read_only=bool(policy["read_only"]),
                destructive=bool(policy["destructive"]),
            ))

        for provider_name, provider in self._providers.items():
            for schema in list(getattr(provider, "schemas", []) or []):
                function = schema.get("function") if isinstance(schema, dict) else None
                if not isinstance(function, dict):
                    continue
                annotations = function.get("annotations")
                if not isinstance(annotations, dict):
                    continue
                if annotations.get("workspaceBoundHint") is not True:
                    continue
                provider_tool = str(function.get("name") or "").strip()
                if not provider_tool:
                    continue
                public_name = f"{provider_name}__{provider_tool}"
                self._routes[public_name] = (provider_name, provider_tool)
                read_only = annotations.get("readOnlyHint") is True
                destructive = annotations.get("destructiveHint") is True
                self._route_policies[public_name] = {"read_only": read_only, "destructive": destructive}
                catalog.append(self._catalog_tool(
                    public_name,
                    function,
                    source=provider_name,
                    read_only=read_only,
                    destructive=destructive,
                ))
        return catalog

    @staticmethod
    def _catalog_tool(
        name: str,
        function: dict[str, Any],
        *,
        source: str,
        read_only: bool,
        destructive: bool,
    ) -> dict[str, Any]:
        parameters = function.get("parameters") if isinstance(function.get("parameters"), dict) else {
            "type": "object", "properties": {}, "required": [], "additionalProperties": False
        }
        return {
            "name": name,
            "description": str(function.get("description") or "")[:300],
            "inputSchema": parameters,
            "annotations": {
                "readOnlyHint": read_only,
                "destructiveHint": destructive,
                "openWorldHint": False,
                "workspaceBoundHint": True,
            },
            "source": source,
        }

    @staticmethod
    def _normalize_tunnel_generation(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return -1

    def _is_active_tunnel_generation(self, generation: int | None) -> bool:
        with self._state_lock:
            return generation is not None and generation == self._active_tunnel_generation

    def _tool_context(self, tool_name: str, arguments: dict[str, Any], generation: int | None, *, source: str) -> dict[str, Any]:
        return {
            "origin": "web_chat",
            "grant_id": self.grant_id,
            "grant_revision": self.grant_revision,
            "permission_mode": self.permission_mode,
            "workspace_path": str(self.workspace),
            "tunnel_generation": generation,
            "tool": tool_name,
            "source": source,
            "arguments": json.loads(json.dumps(arguments, ensure_ascii=False, default=str)),
        }

    def _current_context(self) -> dict[str, Any]:
        value = getattr(self._dispatch_context, "value", None)
        return dict(value) if isinstance(value, dict) else {}

    def _approve_workspace_write(self, proposal: Any) -> bool:
        context = self._current_context()
        tool_name = str(context.get("tool") or "write_file")
        kind = "restore_backup" if tool_name == "restore_backup" else "write_file"
        question = (
            f"Approve restoring {proposal.relative_path} from Web Chat?"
            if kind == "restore_backup"
            else f"Approve Web Chat writing {proposal.relative_path}?"
        )
        approved = bool(self._approval_callback(
            kind,
            question,
            {
                "relative_path": proposal.relative_path,
                "diff": proposal.diff,
                "old_bytes": len(str(proposal.old_content).encode("utf-8")),
                "new_bytes": len(str(proposal.new_content).encode("utf-8")),
            },
            context,
        ))
        return approved and self._is_active_tunnel_generation(self._normalize_tunnel_generation(context.get("tunnel_generation")))

    def _approve_workspace_command(self, proposal: Any) -> bool:
        context = self._current_context()
        approved = bool(self._approval_callback(
            "run_verification",
            f"Approve Web Chat running verification preset {proposal.name}?",
            {
                "name": proposal.name,
                "argv": list(proposal.argv),
                "cwd": proposal.cwd,
                "timeout_seconds": proposal.timeout_seconds,
            },
            context,
        ))
        return approved and self._is_active_tunnel_generation(self._normalize_tunnel_generation(context.get("tunnel_generation")))

    def _denied(self, tool_name: str, error: str) -> str:
        self._audit("web_chat_gateway_tool_denied", {"grant_id": self.grant_id, "tool": tool_name, "error": error})
        return json.dumps({"status": "denied", "error": error}, ensure_ascii=False)

    def _audit_call(self, tool_name: str, arguments: dict[str, Any], result: str) -> None:
        try:
            status = str(json.loads(result).get("status") or "unknown")
        except (json.JSONDecodeError, AttributeError):
            status = "invalid"
        self._audit(
            "web_chat_gateway_tool_call",
            {"grant_id": self.grant_id, "grant_revision": self.grant_revision, "tool": tool_name, "argument_keys": sorted(str(key) for key in dict(arguments or {})), "status": status},
        )

    @staticmethod
    def _normalize_provider_result(result: Any, *, provider_name: str, tool_name: str) -> str:
        try:
            payload = json.loads(result) if isinstance(result, str) else result
        except json.JSONDecodeError:
            payload = None
        if not isinstance(payload, dict) or not str(payload.get("status") or "").strip():
            payload = {
                "status": "error",
                "error": f"Gateway provider {provider_name}/{tool_name} returned an invalid result contract.",
            }
        return json.dumps(payload, ensure_ascii=False, default=str)

    def _audit_workspace_event(self, event_type: str, payload: dict[str, Any]) -> None:
        self._audit(
            "web_chat_gateway_workspace_event",
            {"grant_id": self.grant_id, "workspace_event": str(event_type), "status": str(payload.get("status") or "")},
        )

    def _audit(self, event_type: str, payload: dict[str, Any]) -> None:
        self._audit_sink(event_type, payload)
