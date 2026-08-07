from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import difflib
import json
import os
from pathlib import Path
import tempfile
from typing import Callable, Any

try:
    from .developer_tools import CommandProposal, DeveloperTools
    from .secret_guard import SecretAccessError, SecretGuard
except ImportError:
    from developer_tools import CommandProposal, DeveloperTools
    from secret_guard import SecretAccessError, SecretGuard


_SKIPPED_DIRECTORIES = {".git", ".npm-cache", "__pycache__", "dist", "node_modules", "release"}
_MAX_READ_BYTES = 500_000
_MAX_SEARCH_RESULTS = 50


class WorkspaceAccessError(ValueError):
    pass


@dataclass(frozen=True)
class WriteProposal:
    relative_path: str
    old_content: str
    new_content: str
    diff: str


class WorkspaceTools:
    def __init__(
        self,
        root: str | Path,
        approve_write: Callable[[WriteProposal], bool],
        secret_guard: SecretGuard | None = None,
        approve_command: Callable[[CommandProposal], bool] | None = None,
        developer_tools: DeveloperTools | None = None,
        audit_sink: Callable[[str, dict], None] | None = None,
    ):
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError(f"Workspace directory does not exist: {self.root}")
        self._approve_write = approve_write
        self._audit_sink = audit_sink or (lambda _event_type, _payload: None)
        self._secret_guard = secret_guard or SecretGuard()
        self._developer_tools = developer_tools or DeveloperTools(
            self.root,
            approve_command=approve_command or (lambda proposal: False),
            secret_guard=self._secret_guard,
            audit_sink=self._audit_sink,
        )

    @property
    def schemas(self) -> list[dict]:
        return [
            _tool_schema(
                "list_directory",
                "List files and directories inside the selected workspace.",
                {"path": _string_property("Workspace-relative directory path. Use . for the root.")},
                ["path"],
            ),
            _tool_schema(
                "search_files",
                "Search workspace-relative file paths and UTF-8 text contents.",
                {"query": _string_property("Case-insensitive text to search for.")},
                ["query"],
            ),
            _tool_schema(
                "read_file",
                "Read a UTF-8 text file inside the selected workspace.",
                {"path": _string_property("Workspace-relative file path.")},
                ["path"],
            ),
            _tool_schema(
                "write_file",
                "Propose a complete UTF-8 file write. The user must approve before the filesystem changes.",
                {
                    "path": _string_property("Workspace-relative file path."),
                    "content": _string_property("Complete replacement file content."),
                },
                ["path", "content"],
            ),
            _tool_schema(
                "list_backups",
                "List rollback backups available under .cowork/backups without exposing file contents.",
                {},
                [],
            ),
            _tool_schema(
                "restore_backup",
                "Restore a file from a rollback backup path under .cowork/backups. The original target path is inferred from the backup path.",
                {"backup_path": _string_property("Workspace-relative rollback backup path returned by a previous write.")},
                ["backup_path"],
            ),
            _tool_schema(
                "git_status",
                "Inspect the current Git branch and changed files without modifying the repository.",
                {},
                [],
            ),
            _tool_schema(
                "git_diff",
                "Read the unstaged Git diff while excluding secret paths.",
                {},
                [],
            ),
            _tool_schema(
                "run_verification",
                "Run one approval-gated verification preset. Arbitrary commands and arguments are not accepted.",
                {
                    "name": {
                        "type": "string",
                        "description": "Allowlisted verification preset name.",
                        "enum": list(self._developer_tools.verification_names),
                    }
                },
                ["name"],
            ),
        ]

    def _resolve(self, value: str | Path) -> Path:
        raw_path = Path(str(value or ".")).expanduser()
        candidate = raw_path if raw_path.is_absolute() else self.root / raw_path
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(self.root):
            raise WorkspaceAccessError(f"Path is outside the workspace: {value}")
        return resolved

    def _relative(self, path: Path) -> str:
        relative = path.relative_to(self.root).as_posix()
        return relative or "."

    def _require_non_secret(self, path: Path) -> None:
        self._secret_guard.require_allowed(Path(self._relative(path)))

    def _is_secret(self, path: Path) -> bool:
        return not self._secret_guard.evaluate(Path(self._relative(path))).allowed

    def list_directory(self, path: str = ".") -> list[str]:
        directory = self._resolve(path)
        if not directory.is_dir():
            raise FileNotFoundError(f"Directory not found: {self._relative(directory)}")
        entries = []
        for entry in directory.iterdir():
            if self._is_secret(entry):
                continue
            suffix = "/" if entry.is_dir() else ""
            entries.append(f"{entry.name}{suffix}")
        return sorted(entries, key=str.casefold)

    def read_file(self, path: str) -> str:
        target = self._resolve(path)
        self._require_non_secret(target)
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {self._relative(target)}")
        if target.stat().st_size > _MAX_READ_BYTES:
            raise ValueError(f"File exceeds {_MAX_READ_BYTES} bytes: {self._relative(target)}")
        return target.read_text(encoding="utf-8")

    def search_files(self, query: str) -> list[dict]:
        normalized_query = str(query or "").strip().casefold()
        if not normalized_query:
            raise ValueError("Search query cannot be empty.")

        results: list[dict] = []
        for directory, directory_names, file_names in os.walk(self.root):
            current_directory = Path(directory)
            directory_names[:] = sorted(
                (
                    name
                    for name in directory_names
                    if name not in _SKIPPED_DIRECTORIES and not self._is_secret(current_directory / name)
                ),
                key=str.casefold,
            )
            for file_name in sorted(file_names, key=str.casefold):
                path = Path(directory) / file_name
                if self._is_secret(path):
                    continue
                relative_path = self._relative(path)
                path_match = normalized_query in relative_path.casefold()
                snippet = ""
                if path.stat().st_size <= _MAX_READ_BYTES:
                    try:
                        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                            if normalized_query in line.casefold():
                                snippet = f"{line_number}: {line.strip()}"
                                break
                    except (OSError, UnicodeDecodeError):
                        pass
                if path_match or snippet:
                    results.append({"path": relative_path, "snippet": snippet})
                if len(results) >= _MAX_SEARCH_RESULTS:
                    return results
        return results

    def write_file(self, path: str, content: str) -> dict:
        target = self._resolve(path)
        self._require_non_secret(target)
        if target.exists() and not target.is_file():
            raise IsADirectoryError(f"Target is not a file: {self._relative(target)}")

        old_content = target.read_text(encoding="utf-8") if target.exists() else ""
        new_content = str(content)
        relative_path = self._relative(target)
        diff = "".join(
            difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
            )
        )
        proposal = WriteProposal(relative_path, old_content, new_content, diff)
        self._audit(
            "write_approval_requested",
            {
                "path": relative_path,
                "exists": target.exists(),
                "old_bytes": len(old_content.encode("utf-8")),
                "new_bytes": len(new_content.encode("utf-8")),
                **_diff_summary(diff),
            },
        )
        approved = bool(self._approve_write(proposal))
        self._audit("write_approval_decision", {"path": relative_path, "approved": approved})
        if not approved:
            return {"status": "denied", "path": relative_path}

        backup_path = None
        if target.exists() and not relative_path.startswith(".cowork/backups/"):
            backup_path = self._create_rollback_backup(relative_path, old_content)
            self._audit(
                "rollback_backup_created",
                {
                    "path": relative_path,
                    "backup_path": backup_path,
                    "bytes": len(old_content.encode("utf-8")),
                },
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=target.parent,
            delete=False,
        ) as temporary_file:
            temporary_file.write(new_content)
            temporary_path = Path(temporary_file.name)
        try:
            os.replace(temporary_path, target)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        result = {"status": "written", "path": relative_path, "bytes": len(new_content.encode("utf-8"))}
        if backup_path:
            result["backup_path"] = backup_path
        self._audit(
            "file_written",
            {
                "path": relative_path,
                "bytes": result["bytes"],
                "backup_path": backup_path,
            },
        )
        return result

    def list_backups(self) -> list[dict]:
        backup_root = self.root / ".cowork" / "backups"
        if not backup_root.is_dir():
            return []

        backups = []
        for backup in backup_root.rglob("*"):
            if not backup.is_file():
                continue
            relative_backup_path = self._relative(backup)
            try:
                target_relative_path = self._target_path_from_backup(relative_backup_path)
                target = self._resolve(target_relative_path)
                self._require_non_secret(target)
            except (SecretAccessError, WorkspaceAccessError, ValueError):
                continue
            stat = backup.stat()
            backups.append(
                {
                    "backup_path": relative_backup_path,
                    "target_path": target_relative_path,
                    "bytes": stat.st_size,
                    "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="milliseconds"),
                }
            )
        backups.sort(key=lambda item: (item["modified_time"], item["backup_path"]), reverse=True)
        self._audit("backups_listed", {"count": len(backups)})
        return backups

    def restore_backup(self, backup_path: str) -> dict:
        backup = self._resolve(backup_path)
        relative_backup_path = self._relative(backup)
        target_relative_path = self._target_path_from_backup(relative_backup_path)
        target = self._resolve(target_relative_path)
        self._require_non_secret(target)
        if not backup.is_file():
            raise FileNotFoundError(f"Backup file not found: {relative_backup_path}")
        if target.exists() and not target.is_file():
            raise IsADirectoryError(f"Restore target is not a file: {target_relative_path}")

        old_content = target.read_text(encoding="utf-8") if target.exists() else ""
        restored_content = backup.read_text(encoding="utf-8")
        diff = "".join(
            difflib.unified_diff(
                old_content.splitlines(keepends=True),
                restored_content.splitlines(keepends=True),
                fromfile=f"a/{target_relative_path}",
                tofile=f"b/{target_relative_path}",
            )
        )
        proposal = WriteProposal(target_relative_path, old_content, restored_content, diff)
        self._audit(
            "restore_approval_requested",
            {
                "path": target_relative_path,
                "restored_from": relative_backup_path,
                "exists": target.exists(),
                "old_bytes": len(old_content.encode("utf-8")),
                "restored_bytes": len(restored_content.encode("utf-8")),
                **_diff_summary(diff),
            },
        )
        approved = bool(self._approve_write(proposal))
        self._audit("restore_approval_decision", {"path": target_relative_path, "approved": approved})
        if not approved:
            return {"status": "denied", "path": target_relative_path}

        pre_restore_backup_path = None
        if target.exists():
            pre_restore_backup_path = self._create_rollback_backup(target_relative_path, old_content)
            self._audit(
                "restore_current_backup_created",
                {
                    "path": target_relative_path,
                    "backup_path": pre_restore_backup_path,
                    "bytes": len(old_content.encode("utf-8")),
                },
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=target.parent,
            delete=False,
        ) as temporary_file:
            temporary_file.write(restored_content)
            temporary_path = Path(temporary_file.name)
        try:
            os.replace(temporary_path, target)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

        result = {
            "status": "restored",
            "path": target_relative_path,
            "restored_from": relative_backup_path,
            "bytes": len(restored_content.encode("utf-8")),
        }
        if pre_restore_backup_path:
            result["pre_restore_backup_path"] = pre_restore_backup_path
        self._audit(
            "file_restored",
            {
                "path": target_relative_path,
                "restored_from": relative_backup_path,
                "bytes": result["bytes"],
                "pre_restore_backup_path": pre_restore_backup_path,
            },
        )
        return result

    def _create_rollback_backup(self, relative_path: str, old_content: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = self.root / ".cowork" / "backups" / timestamp / Path(relative_path)
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(old_content, encoding="utf-8")
        return self._relative(backup)

    def _target_path_from_backup(self, relative_backup_path: str) -> str:
        parts = Path(relative_backup_path).parts
        if len(parts) < 4 or parts[0] != ".cowork" or parts[1] != "backups":
            raise WorkspaceAccessError("Backup path must be under .cowork/backups/<timestamp>/...")
        return Path(*parts[3:]).as_posix()

    def _audit(self, event_type: str, payload: dict[str, Any]) -> None:
        self._audit_sink(event_type, payload)

    def dispatch(self, tool_name: str, arguments: dict) -> str:
        try:
            if tool_name == "list_directory":
                payload = {"status": "ok", "entries": self.list_directory(arguments.get("path", "."))}
            elif tool_name == "search_files":
                payload = {"status": "ok", "matches": self.search_files(arguments.get("query", ""))}
            elif tool_name == "read_file":
                payload = {"status": "ok", "content": self.read_file(arguments.get("path", ""))}
            elif tool_name == "write_file":
                payload = self.write_file(arguments.get("path", ""), arguments.get("content", ""))
            elif tool_name == "list_backups":
                payload = {"status": "ok", "backups": self.list_backups()}
            elif tool_name == "restore_backup":
                payload = self.restore_backup(arguments.get("backup_path", ""))
            elif tool_name == "git_status":
                payload = self._developer_tools.git_status()
            elif tool_name == "git_diff":
                payload = self._developer_tools.git_diff()
            elif tool_name == "run_verification":
                payload = self._developer_tools.run_verification(arguments.get("name", ""))
            else:
                payload = {"status": "error", "error": f"Unknown tool: {tool_name}"}
        except SecretAccessError as exc:
            payload = {"status": "denied", "error": str(exc)}
        except Exception as exc:
            payload = {"status": "error", "error": str(exc)}
        return json.dumps(payload, ensure_ascii=False)


def _string_property(description: str) -> dict:
    return {"type": "string", "description": description}


def _tool_schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def _diff_summary(diff: str) -> dict[str, int]:
    added = 0
    removed = 0
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return {"diff_added_lines": added, "diff_removed_lines": removed}
