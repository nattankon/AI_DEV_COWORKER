from __future__ import annotations

from datetime import datetime, timezone
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from typing import Any, Callable
from urllib.parse import urlsplit


MCP_PROTOCOL_VERSION = "2025-06-18"
_CLOUDFLARE_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.IGNORECASE)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class CloudflaredQuickTunnelAdapter:
    """Optional cloudflared adapter; bearer authentication stays at the MCP origin."""

    def __init__(
        self,
        *,
        executable_resolver: Callable[[], str | None] | None = None,
        popen_factory: Callable[..., Any] | None = None,
        process_tree_killer: Callable[[Any], None] | None = None,
        startup_timeout_seconds: float = 20.0,
    ):
        self._executable_resolver = executable_resolver or self._resolve_executable
        self._popen_factory = popen_factory or subprocess.Popen
        self._process_tree_killer = process_tree_killer or self._kill_process_tree
        self._startup_timeout = max(0.05, float(startup_timeout_seconds))
        self._process: Any | None = None

    @staticmethod
    def _resolve_executable() -> str | None:
        configured = str(os.environ.get("COWORK_CLOUDFLARED_PATH") or "").strip()
        if configured and os.path.isfile(configured):
            return configured
        return shutil.which("cloudflared")

    def start(self, local_endpoint: str) -> str:
        executable = self._executable_resolver()
        if not executable:
            raise RuntimeError("cloudflared is not installed. Install it or configure COWORK_CLOUDFLARED_PATH.")
        parsed = urlsplit(local_endpoint)
        local_origin = f"{parsed.scheme}://{parsed.netloc}"
        command = [executable, "tunnel", "--no-autoupdate", "--url", local_origin]
        popen_kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.PIPE,
            "stdin": subprocess.DEVNULL,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._process = self._popen_factory(command, **popen_kwargs)
        lines: queue.Queue[str | None] = queue.Queue()

        def read_stderr() -> None:
            stream = getattr(self._process, "stderr", None)
            if stream is None:
                lines.put(None)
                return
            for line in stream:
                lines.put(str(line))
            lines.put(None)

        threading.Thread(target=read_stderr, name="web-chat-cloudflared-output", daemon=True).start()
        deadline = time.monotonic() + self._startup_timeout
        while time.monotonic() < deadline:
            if self._process.poll() is not None and lines.empty():
                break
            try:
                line = lines.get(timeout=min(0.1, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if line is None:
                break
            match = _CLOUDFLARE_URL.search(line)
            if match:
                return f"{match.group(0).rstrip('/')}/mcp"
        self.stop()
        raise RuntimeError("cloudflared did not produce a public endpoint before the startup timeout.")

    def health(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @staticmethod
    def _kill_process_tree(process: Any) -> None:
        if os.name == "nt" and getattr(process, "pid", None):
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return
        adapter: Any | None = None
        try:
            process.terminate()
            process.wait(timeout=3)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def stop(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        self._process_tree_killer(process)


class StaticTestTunnelAdapter:
    """Explicit smoke-test seam; it never opens a public network connection."""

    def __init__(self, endpoint: str):
        self._endpoint = str(endpoint or "").strip()
        self._active = False

    def start(self, _local_endpoint: str) -> str:
        if not self._endpoint.startswith("https://"):
            raise RuntimeError("COWORK_WEB_CHAT_TEST_TUNNEL_ENDPOINT must be HTTPS.")
        self._active = True
        return self._endpoint

    def health(self) -> bool:
        return self._active

    def stop(self) -> None:
        self._active = False


def _default_adapter_factories() -> dict[str, Callable[[], Any]]:
    test_endpoint = str(os.environ.get("COWORK_WEB_CHAT_TEST_TUNNEL_ENDPOINT") or "").strip()
    if test_endpoint:
        return {"cloudflare": lambda: StaticTestTunnelAdapter(test_endpoint)}
    return {"cloudflare": CloudflaredQuickTunnelAdapter}


class WebChatTunnelController:
    """Owns one authenticated MCP listener and one optional remote tunnel adapter."""

    def __init__(
        self,
        *,
        adapter_factories: dict[str, Callable[[], Any]] | None = None,
        audit_sink: Callable[[str, dict[str, Any]], None] | None = None,
        on_state: Callable[[dict[str, Any]], None] | None = None,
    ):
        self._adapter_factories = adapter_factories or _default_adapter_factories()
        self._audit_sink = audit_sink or (lambda _event, _payload: None)
        self._on_state = on_state or (lambda _state: None)
        self._lock = threading.RLock()
        self._server: ThreadingHTTPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None
        self._adapter: Any | None = None
        self._gateway: Any | None = None
        self._credential = ""
        self._expires_at = 0.0
        self._idle_timeout = 0.0
        self._last_activity = 0.0
        self._stop_event = threading.Event()
        self._generation = 0
        self._state = self._empty_state()

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {
            "status": "off",
            "provider": "",
            "grant_id": "",
            "grant_revision": 0,
            "tunnel_generation": 0,
            "workspace_path": "",
            "endpoint": "",
            "auth_required": False,
            "expires_at": "",
            "tool_count": 0,
            "error": "",
        }

    def start(
        self,
        *,
        gateway: Any,
        provider: str,
        credential: str,
        expires_at: float,
        idle_timeout_seconds: float = 900.0,
    ) -> dict[str, Any]:
        provider_name = str(provider or "").strip().casefold()
        factory = self._adapter_factories.get(provider_name)
        if factory is None:
            raise ValueError(f"Unsupported Web Chat tunnel provider: {provider_name or '(empty)'}")
        token = str(credential or "")
        if not token:
            raise ValueError("Web Chat tunnel requires a bearer credential.")
        expiry = float(expires_at)
        if expiry <= time.time():
            raise ValueError("Web Chat tunnel credential is already expired.")

        self.stop("restarted")
        with self._lock:
            self._generation += 1
            run_generation = self._generation
            self._gateway = gateway
            self._credential = token
            self._expires_at = expiry
            self._idle_timeout = max(0.01, float(idle_timeout_seconds))
            self._last_activity = time.monotonic()
            self._stop_event = threading.Event()
            run_stop_event = self._stop_event
            self._state = {
                **self._empty_state(),
                "status": "starting",
                "provider": provider_name,
                "grant_id": str(gateway.grant_id),
                "grant_revision": int(gateway.grant_revision),
                "tunnel_generation": run_generation,
                "workspace_path": str(gateway.workspace),
                "auth_required": True,
                "expires_at": datetime.fromtimestamp(expiry, timezone.utc).isoformat(timespec="seconds"),
                "tool_count": len(gateway.list_tools()),
            }
            gateway.activate_tunnel(run_generation)
        self._publish_state()

        try:
            handler = self._handler_type()
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            server.daemon_threads = True
            server.controller = self  # type: ignore[attr-defined]
            local_endpoint = f"http://127.0.0.1:{server.server_address[1]}/mcp"
            server_thread = threading.Thread(target=server.serve_forever, name="web-chat-mcp-http", daemon=True)
            adapter = factory()
            with self._lock:
                self._server = server
                self._server_thread = server_thread
                self._adapter = adapter
            server_thread.start()
            public_endpoint = str(adapter.start(local_endpoint) or "").strip()
            if not public_endpoint.startswith("https://"):
                raise RuntimeError("Tunnel provider did not return an HTTPS endpoint.")
            with self._lock:
                stale = run_generation != self._generation or run_stop_event.is_set()
            if stale:
                if adapter is not None:
                    adapter.stop()
                return self.public_state()
            with self._lock:
                self._state = {**self._state, "status": "connected", "endpoint": public_endpoint, "error": ""}
            self._audit("web_chat_tunnel_started", {"provider": provider_name, "grant_id": str(gateway.grant_id)})
            self._publish_state()
            self._monitor_thread = threading.Thread(
                target=self._monitor,
                args=(run_generation, run_stop_event),
                name="web-chat-tunnel-monitor",
                daemon=True,
            )
            self._monitor_thread.start()
            return self.public_state()
        except Exception as exc:
            with self._lock:
                stale = run_generation != self._generation or run_stop_event.is_set()
            if stale:
                try:
                    if adapter is not None:
                        adapter.stop()
                except Exception:
                    pass
                return self.public_state()
            try:
                gateway.deactivate_tunnel(run_generation, "start-error")
            except Exception:
                pass
            self._stop_resources()
            with self._lock:
                self._state = {**self._state, "status": "error", "endpoint": "", "error": str(exc)}
                self._credential = ""
            self._audit("web_chat_tunnel_error", {"provider": provider_name, "error": str(exc)})
            self._publish_state()
            raise

    def stop(self, reason: str = "manual") -> dict[str, Any]:
        with self._lock:
            prior_generation = self._generation
            gateway = self._gateway
            self._generation += 1
        if gateway is not None and prior_generation > 0:
            try:
                gateway.deactivate_tunnel(prior_generation, reason)
            except Exception:
                pass
        had_runtime = self._stop_resources()
        with self._lock:
            prior = dict(self._state)
            self._credential = ""
            self._gateway = None
            self._expires_at = 0.0
            self._state = self._empty_state()
        if had_runtime or prior.get("status") not in {"", "off"}:
            self._audit("web_chat_tunnel_stopped", {"provider": str(prior.get("provider") or ""), "reason": str(reason or "manual")})
            self._publish_state()
        return self.public_state()

    def public_state(self) -> dict[str, Any]:
        with self._lock:
            state = json.loads(json.dumps(self._state))
            adapter = self._adapter
        if state["status"] == "connected" and adapter is not None and not adapter.health():
            self.stop("adapter-exited")
            return self.public_state()
        return state

    def _stop_resources(self) -> bool:
        with self._lock:
            self._stop_event.set()
            server = self._server
            adapter = self._adapter
            self._server = None
            self._server_thread = None
            self._monitor_thread = None
            self._adapter = None
        if adapter is not None:
            adapter.stop()
        if server is not None:
            server.shutdown()
            server.server_close()
        return adapter is not None or server is not None

    def _monitor(self, generation: int, stop_event: threading.Event) -> None:
        while not stop_event.wait(0.02):
            with self._lock:
                if generation != self._generation:
                    return
                expired = time.time() >= self._expires_at
                idle = time.monotonic() - self._last_activity >= self._idle_timeout
            if expired or idle:
                self.stop("credential-expired" if expired else "idle-timeout")
                return

    def _handler_type(self):
        controller = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "CoworkWebChatMCP/1"

            def do_POST(self):  # noqa: N802
                if self.path.rstrip("/") != "/mcp":
                    self.send_error(404)
                    return
                authorization = str(self.headers.get("Authorization") or "")
                with controller._lock:
                    expected = f"Bearer {controller._credential}"
                    expired = time.time() >= controller._expires_at
                if expired or not hmac.compare_digest(authorization, expected):
                    self._json_response(401, {"error": "unauthorized"})
                    return
                try:
                    size = int(self.headers.get("Content-Length") or 0)
                    if size <= 0 or size > 1_000_000:
                        raise ValueError("Invalid MCP request size.")
                    payload = json.loads(self.rfile.read(size).decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise ValueError("MCP request must be an object.")
                except Exception as exc:
                    self._json_response(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}})
                    return
                with controller._lock:
                    controller._last_activity = time.monotonic()
                status, response = controller._mcp_response(payload)
                if response is None:
                    self.send_response(status)
                    self.end_headers()
                else:
                    self._json_response(status, response)

            def do_GET(self):  # noqa: N802
                self.send_error(405)

            def log_message(self, _format, *_args):
                return

            def _json_response(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler

    def _mcp_response(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
        request_id = payload.get("id")
        method = str(payload.get("method") or "")
        params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
        if method == "notifications/initialized" and request_id is None:
            return 202, None
        if method == "initialize":
            result = {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "AI Dev Co-worker Web Chat Gateway", "version": "1.0"},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            with self._lock:
                gateway = self._gateway
            result = {"tools": gateway.list_tools() if gateway is not None else []}
        elif method == "tools/call":
            with self._lock:
                gateway = self._gateway
                tunnel_generation = self._generation
            if gateway is None:
                result = {"content": [{"type": "text", "text": "Gateway is not active."}], "isError": True}
            else:
                raw = gateway.dispatch(
                    str(params.get("name") or ""),
                    params.get("arguments") if isinstance(params.get("arguments"), dict) else {},
                    grant_id=str(gateway.grant_id),
                    grant_revision=int(gateway.grant_revision),
                    tunnel_generation=tunnel_generation,
                )
                try:
                    structured = json.loads(raw)
                except json.JSONDecodeError:
                    structured = {"status": "error", "error": "Gateway returned invalid JSON."}
                is_error = str(structured.get("status") or "").casefold() in {"error", "denied"}
                result = {
                    "content": [{"type": "text", "text": json.dumps(structured, ensure_ascii=False)}],
                    "structuredContent": structured,
                    "isError": is_error,
                }
        else:
            return 200, {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
        return 200, {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _publish_state(self) -> None:
        self._on_state(self.public_state())

    def _audit(self, event_type: str, payload: dict[str, Any]) -> None:
        self._audit_sink(event_type, {"timestamp": _utc_now(), **payload})
