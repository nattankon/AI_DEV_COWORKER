from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from typing import Callable, Mapping, Any

try:
    from .secret_guard import SecretGuard
except ImportError:
    from secret_guard import SecretGuard


_DEFAULT_MAX_OUTPUT_CHARS = 100_000
_SENSITIVE_ENV_MARKERS = ("API_KEY", "CREDENTIAL", "PASSWORD", "PRIVATE_KEY", "SECRET", "TOKEN")


@dataclass(frozen=True)
class VerificationCommand:
    name: str
    argv: tuple[str, ...]
    timeout_seconds: float


@dataclass(frozen=True)
class CommandProposal:
    name: str
    argv: tuple[str, ...]
    cwd: str
    timeout_seconds: float


def default_verification_commands() -> dict[str, VerificationCommand]:
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or (
        "npm.cmd" if os.name == "nt" else "npm"
    )
    return {
        "python-tests": VerificationCommand(
            name="python-tests",
            argv=(sys.executable, "-m", "unittest", "discover", "-s", "test", "-p", "test_*.py", "-v"),
            timeout_seconds=120,
        ),
        "frontend-tests": VerificationCommand(
            name="frontend-tests",
            argv=(npm, "test"),
            timeout_seconds=180,
        ),
        "frontend-build": VerificationCommand(
            name="frontend-build",
            argv=(npm, "run", "build"),
            timeout_seconds=180,
        ),
    }


def load_project_verification_commands(root: str | Path) -> dict[str, VerificationCommand]:
    """Read optional per-project verification presets from <root>/.cowork/verify.json.

    Format: {"presets": {"<name>": {"argv": ["cmd", "arg", ...], "timeout_seconds": 60}}}.
    Invalid entries are skipped. Every preset still runs through the approval gate.
    """
    config = Path(root).expanduser().resolve() / ".cowork" / "verify.json"
    if not config.is_file():
        return {}
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    presets = data.get("presets") if isinstance(data, dict) else None
    if not isinstance(presets, dict):
        return {}
    commands: dict[str, VerificationCommand] = {}
    for raw_name, spec in presets.items():
        if not isinstance(raw_name, str) or not raw_name.strip() or not isinstance(spec, dict):
            continue
        argv = spec.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(part, str) and part for part in argv):
            continue
        try:
            timeout = float(spec.get("timeout_seconds", 120))
        except (TypeError, ValueError):
            timeout = 120.0
        if timeout <= 0:
            timeout = 120.0
        name = raw_name.strip()
        commands[name] = VerificationCommand(name=name, argv=tuple(argv), timeout_seconds=timeout)
    return commands


class DeveloperTools:
    def __init__(
        self,
        root: str | Path,
        approve_command: Callable[[CommandProposal], bool],
        verification_commands: Mapping[str, VerificationCommand] | None = None,
        secret_guard: SecretGuard | None = None,
        max_output_chars: int = _DEFAULT_MAX_OUTPUT_CHARS,
        process_tree_killer: Callable[[int], None] | None = None,
        audit_sink: Callable[[str, dict], None] | None = None,
    ):
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError(f"Workspace directory does not exist: {self.root}")
        if max_output_chars < 1:
            raise ValueError("max_output_chars must be at least 1.")
        self._approve_command = approve_command
        if verification_commands is None:
            resolved_commands = default_verification_commands()
            resolved_commands.update(load_project_verification_commands(self.root))
            self._verification_commands = resolved_commands
        else:
            self._verification_commands = dict(verification_commands)
        self._secret_guard = secret_guard or SecretGuard()
        self._max_output_chars = max_output_chars
        self._process_tree_killer = process_tree_killer or _terminate_process_tree
        self._audit_sink = audit_sink or (lambda _event_type, _payload: None)

    @property
    def verification_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._verification_commands, key=str.casefold))

    def git_status(self) -> dict:
        unavailable = self._git_unavailable_result()
        if unavailable:
            return unavailable

        branch_result = self._run(("git", "branch", "--show-current"), timeout_seconds=15)
        status_result = self._run(
            ("git", "status", "--porcelain=v1", "-z", "--untracked-files=all"),
            timeout_seconds=30,
        )
        if status_result["status"] != "completed":
            return self._git_error_result(status_result)

        changes = []
        records = status_result["stdout"].split("\0")
        index = 0
        while index < len(records):
            record = records[index]
            index += 1
            if not record:
                continue
            code = record[:2]
            path = record[3:] if len(record) > 3 else ""
            related_paths = [path]
            original_path = None
            if ("R" in code or "C" in code) and index < len(records):
                original_path = records[index]
                index += 1
                related_paths.append(original_path)
            if not path or any(self._is_secret_path(item) for item in related_paths):
                continue
            change = {"code": code, "path": path}
            if original_path:
                change["original_path"] = original_path
            changes.append(change)

        stdout = "\n".join(f"{change['code']} {change['path']}" for change in changes)
        return {
            "status": "ok",
            "branch": branch_result["stdout"].strip() if branch_result["status"] == "completed" else "",
            "changes": changes,
            "changed_files": [change["path"] for change in changes],
            "stdout": stdout,
            "stderr": "",
            "exit_code": 0,
            "duration_ms": branch_result["duration_ms"] + status_result["duration_ms"],
            "truncated": status_result["truncated"],
        }

    def git_diff(self) -> dict:
        unavailable = self._git_unavailable_result()
        if unavailable:
            return unavailable

        names_result = self._run(
            ("git", "diff", "--name-only", "-z", "--no-ext-diff"),
            timeout_seconds=30,
        )
        if names_result["status"] != "completed":
            return self._git_error_result(names_result)
        changed_files = [
            path
            for path in names_result["stdout"].split("\0")
            if path and not self._is_secret_path(path)
        ]
        if not changed_files:
            return {
                "status": "ok",
                "changed_files": [],
                "stdout": "",
                "stderr": "",
                "exit_code": 0,
                "duration_ms": names_result["duration_ms"],
                "truncated": names_result["truncated"],
            }

        diff_result = self._run(
            ("git", "diff", "--no-ext-diff", "--no-color", "--", *changed_files),
            timeout_seconds=30,
        )
        if diff_result["status"] != "completed":
            return self._git_error_result(diff_result)
        return {
            "status": "ok",
            "changed_files": changed_files,
            "stdout": diff_result["stdout"],
            "stderr": diff_result["stderr"],
            "exit_code": diff_result["exit_code"],
            "duration_ms": names_result["duration_ms"] + diff_result["duration_ms"],
            "truncated": names_result["truncated"] or diff_result["truncated"],
        }

    def run_verification(self, name: str) -> dict:
        normalized_name = str(name or "").strip()
        command = self._verification_commands.get(normalized_name)
        if command is None:
            self._audit(
                "verification_rejected",
                {
                    "name": normalized_name,
                    "reason": "not_allowlisted",
                    "allowed": list(self.verification_names),
                },
            )
            return {
                "status": "error",
                "error": f"Verification preset is not allowlisted: {normalized_name or '(empty)'}",
                "allowed": list(self.verification_names),
            }

        proposal = CommandProposal(
            name=command.name,
            argv=command.argv,
            cwd=str(self.root),
            timeout_seconds=command.timeout_seconds,
        )
        self._audit("verification_approval_requested", _proposal_payload(proposal))
        approved = bool(self._approve_command(proposal))
        self._audit("verification_approval_decision", {"name": command.name, "approved": approved})
        if not approved:
            return {"status": "denied", "name": command.name}

        self._audit("verification_started", _proposal_payload(proposal))
        result = self._run(command.argv, timeout_seconds=command.timeout_seconds)
        if result["status"] == "timeout":
            result["name"] = command.name
            self._audit("verification_timeout", _verification_audit_payload(command.name, result))
            return result
        if result["status"] != "completed":
            payload = {
                **result,
                "status": "error",
                "name": command.name,
            }
            self._audit("verification_finished", _verification_audit_payload(command.name, payload))
            return payload
        payload = {
            **result,
            "status": "passed" if result["exit_code"] == 0 else "failed",
            "name": command.name,
        }
        self._audit("verification_finished", _verification_audit_payload(command.name, payload))
        return payload

    def _git_unavailable_result(self) -> dict | None:
        result = self._run(("git", "rev-parse", "--is-inside-work-tree"), timeout_seconds=15)
        if result["status"] == "completed" and result["exit_code"] == 0:
            return None
        return {
            "status": "unavailable",
            "error": "Workspace is not a Git repository or Git is unavailable.",
            "stdout": "",
            "stderr": "",
            "exit_code": result.get("exit_code"),
            "duration_ms": result["duration_ms"],
            "truncated": result["truncated"],
        }

    def _git_error_result(self, result: dict) -> dict:
        return {
            **result,
            "status": "error",
            "error": "Git inspection failed.",
        }

    def _is_secret_path(self, relative_path: str) -> bool:
        return not self._secret_guard.evaluate(Path(relative_path)).allowed

    def _run(self, argv: tuple[str, ...], timeout_seconds: float) -> dict:
        started = time.monotonic()
        process = None
        try:
            popen_kwargs: dict[str, Any] = {}
            if os.name == "nt":
                popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            else:
                popen_kwargs["start_new_session"] = True
            process = subprocess.Popen(
                list(argv),
                cwd=self.root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                env=_sanitized_environment(),
                **popen_kwargs,
            )
            stdout_value, stderr_value = process.communicate(timeout=timeout_seconds)
            stdout, stdout_truncated = self._limit_output(stdout_value)
            stderr, stderr_truncated = self._limit_output(stderr_value)
            return {
                "status": "completed",
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": process.returncode,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "truncated": stdout_truncated or stderr_truncated,
            }
        except subprocess.TimeoutExpired as exc:
            process_tree_terminated = False
            if process is not None:
                try:
                    self._process_tree_killer(process.pid)
                    process_tree_terminated = True
                finally:
                    if process.poll() is None:
                        process.kill()
                    try:
                        process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
            stdout, stdout_truncated = self._limit_output(_coerce_text(exc.stdout))
            stderr, stderr_truncated = self._limit_output(_coerce_text(exc.stderr))
            return {
                "status": "timeout",
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": None,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "truncated": stdout_truncated or stderr_truncated,
                "error": f"Command exceeded {timeout_seconds:g} seconds.",
                "process_tree_terminated": process_tree_terminated,
            }
        except OSError as exc:
            return {
                "status": "unavailable",
                "stdout": "",
                "stderr": "",
                "exit_code": None,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "truncated": False,
                "error": str(exc),
            }

    def _limit_output(self, value: str) -> tuple[str, bool]:
        if len(value) <= self._max_output_chars:
            return value, False
        return value[: self._max_output_chars], True

    def _audit(self, event_type: str, payload: dict[str, Any]) -> None:
        self._audit_sink(event_type, payload)


def _coerce_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _sanitized_environment() -> dict[str, str]:
    environment = {
        name: value
        for name, value in os.environ.items()
        if not any(marker in name.upper() for marker in _SENSITIVE_ENV_MARKERS)
    }
    environment["CI"] = "1"
    environment["NO_COLOR"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def _terminate_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
        return

    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return


def _proposal_payload(proposal: CommandProposal) -> dict[str, Any]:
    return {
        "name": proposal.name,
        "argv": list(proposal.argv),
        "cwd": proposal.cwd,
        "timeout_seconds": proposal.timeout_seconds,
    }


def _verification_audit_payload(name: str, result: dict) -> dict[str, Any]:
    return {
        "name": name,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "duration_ms": result.get("duration_ms"),
        "truncated": bool(result.get("truncated")),
        "stdout_chars": len(str(result.get("stdout") or "")),
        "stderr_chars": len(str(result.get("stderr") or "")),
        "process_tree_terminated": bool(result.get("process_tree_terminated", False)),
    }
