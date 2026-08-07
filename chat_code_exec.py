from __future__ import annotations

import base64
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


_BLOCKED_NETWORK_MARKERS = (
    "import socket",
    "from socket",
    "import requests",
    "from requests",
    "urllib.request",
    "http.client",
)

EXPERIMENTAL_SANDBOX_LEVEL = "subprocess_tempdir_experimental"
BEST_EFFORT_NETWORK_ISOLATION = "best_effort_static_check"


class CodeExecutor:
    def __init__(
        self,
        *,
        python_executable: str | None = None,
        root: str | Path | None = None,
        timeout_seconds: float = 10.0,
        output_limit: int = 20_000,
        artifact_limit_bytes: int = 1_000_000,
    ):
        self.python_executable = python_executable or sys.executable
        self.root = Path(root or tempfile.gettempdir()).resolve()
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self.output_limit = max(1000, int(output_limit))
        self.artifact_limit_bytes = max(0, int(artifact_limit_bytes))
        self.sandbox_level = EXPERIMENTAL_SANDBOX_LEVEL
        self.network_isolation = BEST_EFFORT_NETWORK_ISOLATION

    def run_python(self, code: str) -> dict[str, Any]:
        source = str(code or "")
        if not source.strip():
            return _execution_result("error", "Python code is empty.")
        if _looks_networked(source):
            return _execution_result(
                "error",
                "Chat code execution uses a best-effort static network check only; this snippet matched a blocked network marker.",
            )
        self.root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="chat-code-", dir=str(self.root)) as temp_dir:
            try:
                completed = subprocess.run(
                    [self.python_executable, "-I", "-c", source],
                    cwd=temp_dir,
                    env=_minimal_env(),
                    text=True,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                return {
                    "status": "timeout",
                    "stdout": _limit_text(exc.stdout or "", self.output_limit),
                    "stderr": _limit_text(exc.stderr or "", self.output_limit),
                    "exit_code": None,
                    "artifacts": [],
                    "sandbox_level": EXPERIMENTAL_SANDBOX_LEVEL,
                    "network_isolation": BEST_EFFORT_NETWORK_ISOLATION,
                }
            artifacts = _collect_artifacts(Path(temp_dir), self.artifact_limit_bytes)
            status = "ok" if completed.returncode == 0 else "error"
            return {
                "status": status,
                "stdout": _limit_text(completed.stdout, self.output_limit),
                "stderr": _limit_text(completed.stderr, self.output_limit),
                "exit_code": completed.returncode,
                "artifacts": artifacts,
                "sandbox_level": EXPERIMENTAL_SANDBOX_LEVEL,
                "network_isolation": BEST_EFFORT_NETWORK_ISOLATION,
            }


class CodeExecutionToolProvider:
    def __init__(
        self,
        *,
        executor: CodeExecutor,
        approval_callback: Callable[[dict[str, Any]], bool],
        enabled: bool = False,
    ):
        self.executor = executor
        self.approval_callback = approval_callback
        self.enabled = bool(enabled)
        self.schemas = [
            {
                "type": "function",
                "function": {
                    "name": "run_python",
                    "description": "Run a bounded Python snippet in an isolated temporary directory after user approval.",
                    "parameters": {
                        "type": "object",
                        "properties": {"code": {"type": "string"}},
                        "required": ["code"],
                        "additionalProperties": False,
                    },
                },
            }
        ]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> str:
        if name != "run_python":
            return json.dumps({"status": "error", "error": f"Unknown code tool: {name}"}, ensure_ascii=False)
        if not self.enabled:
            return json.dumps({"status": "disabled", "error": "Chat code execution is disabled."}, ensure_ascii=False)
        code = str((arguments or {}).get("code") or "")
        proposal = {
            "tool": "run_python",
            "code": code[:4000],
            "full_code": code,
            "timeout_seconds": getattr(self.executor, "timeout_seconds", None),
            "risk_level": "code",
            "risk_summary": _risk_summary_for_executor(self.executor),
            "sandbox_level": getattr(self.executor, "sandbox_level", EXPERIMENTAL_SANDBOX_LEVEL),
            "network_isolation": getattr(self.executor, "network_isolation", BEST_EFFORT_NETWORK_ISOLATION),
        }
        if not self.approval_callback(proposal):
            return json.dumps({"status": "denied", "error": "User denied Python execution."}, ensure_ascii=False)
        return json.dumps(self.executor.run_python(code), ensure_ascii=False)


def _looks_networked(code: str) -> bool:
    lowered = code.casefold()
    return any(marker in lowered for marker in _BLOCKED_NETWORK_MARKERS)


def _risk_summary_for_executor(executor: Any) -> str:
    sandbox_level = str(getattr(executor, "sandbox_level", "") or "")
    if sandbox_level == "pyodide_wasm":
        return "Runs Python through the Pyodide/WASM sandbox when that runtime is installed; unavailable otherwise."
    return "Runs Python in an experimental subprocess/temp-dir sandbox. This is not a production network or filesystem boundary."


def _execution_result(status: str, error: str = "") -> dict[str, Any]:
    return {
        "status": status,
        "error": error,
        "stdout": "",
        "stderr": "",
        "exit_code": None,
        "artifacts": [],
        "sandbox_level": EXPERIMENTAL_SANDBOX_LEVEL,
        "network_isolation": BEST_EFFORT_NETWORK_ISOLATION,
    }


def _minimal_env() -> dict[str, str]:
    keep = {"SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP"}
    return {key: value for key, value in os.environ.items() if key.upper() in keep}


def _limit_text(text: str, limit: int) -> str:
    clean = str(text or "")
    if len(clean) <= limit:
        return clean
    return clean[:limit] + f"\n[truncated {len(clean) - limit} chars]"


def _collect_artifacts(root: Path, max_bytes: int) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    if max_bytes <= 0:
        return artifacts
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if not data or len(data) > max_bytes:
            continue
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        artifacts.append(
            {
                "name": path.name,
                "mime": mime,
                "data": base64.b64encode(data).decode("ascii"),
                "size": len(data),
            }
        )
    return artifacts[:12]
