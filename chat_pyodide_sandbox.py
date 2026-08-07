from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable


class PyodideSandbox:
    def __init__(
        self,
        runtime_loader: Callable[[], Any] | None = None,
        *,
        app_root: str | Path | None = None,
        runner_path: str | Path | None = None,
        node_command: str = "node",
        timeout_seconds: float = 10.0,
        output_limit: int = 20_000,
    ):
        self.runtime_loader = runtime_loader or _default_runtime_loader
        self._auto_discover = runtime_loader is None
        self.app_root = Path(app_root or Path(__file__).resolve().parent)
        self.runner_path = Path(runner_path or Path(__file__).resolve().parent / "tools" / "pyodide_runner.mjs")
        self.node_command = node_command
        self.timeout_seconds = timeout_seconds
        self.output_limit = max(1000, int(output_limit))
        self.sandbox_level = "pyodide_wasm"
        self.network_isolation = "wasm_no_host_network_when_available"

    def run_python(self, code: str) -> dict[str, Any]:
        runtime = self.runtime_loader()
        if runtime is None and self._auto_discover:
            runtime = discover_pyodide_runtime(
                app_root=self.app_root,
                runner_path=self.runner_path,
                node_command=self.node_command,
                timeout_seconds=self.timeout_seconds,
                output_limit=self.output_limit,
            )
        if runtime is None:
            return {
                "status": "unavailable",
                "error": "Pyodide runtime is not installed or not configured.",
                "stdout": "",
                "stderr": "",
                "artifacts": [],
                "sandbox_level": "pyodide_wasm_unavailable",
                "network_isolation": "wasm_no_host_network_when_available",
            }
        try:
            result = runtime.run_python(str(code or ""))
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "stdout": "",
                "stderr": "",
                "artifacts": [],
                "sandbox_level": "pyodide_wasm",
                "network_isolation": "wasm_no_host_network_when_available",
            }
        if not isinstance(result, dict):
            result = {"stdout": str(result), "stderr": ""}
        return {
            "status": "ok",
            "stdout": _limit_text(str(result.get("stdout") or ""), self.output_limit),
            "stderr": _limit_text(str(result.get("stderr") or ""), self.output_limit),
            "artifacts": result.get("artifacts") if isinstance(result.get("artifacts"), list) else [],
            "sandbox_level": "pyodide_wasm",
            "network_isolation": "wasm_no_host_network_when_available",
        }


class NodePyodideRuntime:
    def __init__(
        self,
        *,
        runner_path: str | Path,
        node_command: str = "node",
        cwd: str | Path | None = None,
        timeout_seconds: float = 10.0,
        output_limit: int = 20_000,
    ):
        self.runner_path = Path(runner_path)
        self.node_command = node_command
        self.cwd = Path(cwd) if cwd is not None else None
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self.output_limit = max(1000, int(output_limit))

    def run_python(self, code: str) -> dict[str, Any]:
        payload = json.dumps({"code": str(code or "")}, ensure_ascii=False)
        try:
            completed = subprocess.run(
                [self.node_command, str(self.runner_path)],
                input=payload,
                cwd=str(self.cwd) if self.cwd is not None else None,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            return _pyodide_result("unavailable", error=str(exc))
        except subprocess.TimeoutExpired:
            return _pyodide_result("timeout", error=f"Pyodide execution timed out after {self.timeout_seconds:g}s.")
        if completed.returncode != 0:
            return _pyodide_result(
                "error",
                stderr=_limit_text(completed.stderr, self.output_limit),
                error=f"Pyodide runner exited with code {completed.returncode}.",
            )
        try:
            raw = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError:
            return _pyodide_result("error", stdout=_limit_text(completed.stdout, self.output_limit), error="Pyodide runner returned invalid JSON.")
        if not isinstance(raw, dict):
            raw = {}
        status = str(raw.get("status") or "ok")
        return _pyodide_result(
            status,
            stdout=_limit_text(str(raw.get("stdout") or ""), self.output_limit),
            stderr=_limit_text(str(raw.get("stderr") or ""), self.output_limit),
            error=str(raw.get("error") or ""),
            artifacts=raw.get("artifacts") if isinstance(raw.get("artifacts"), list) else [],
        )


def discover_pyodide_runtime(
    *,
    app_root: str | Path,
    runner_path: str | Path,
    node_command: str = "node",
    timeout_seconds: float = 10.0,
    output_limit: int = 20_000,
) -> NodePyodideRuntime | None:
    root = Path(app_root)
    package_json = root / "node_modules" / "pyodide" / "package.json"
    runner = Path(runner_path)
    if not package_json.exists() or not runner.exists():
        return None
    return NodePyodideRuntime(
        runner_path=runner,
        node_command=node_command,
        cwd=root,
        timeout_seconds=timeout_seconds,
        output_limit=output_limit,
    )


def _default_runtime_loader() -> Any | None:
    return None


def _pyodide_result(
    status: str,
    *,
    stdout: str = "",
    stderr: str = "",
    error: str = "",
    artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "stdout": stdout,
        "stderr": stderr,
        "error": error,
        "artifacts": artifacts or [],
        "sandbox_level": "pyodide_wasm",
        "network_isolation": "wasm_no_host_network_when_available",
    }


def _limit_text(text: str, limit: int) -> str:
    clean = str(text or "")
    if len(clean) <= limit:
        return clean
    return clean[:limit] + f"\n[truncated {len(clean) - limit} chars]"
