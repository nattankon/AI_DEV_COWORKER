from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_FEATURE_ROOT = Path(__file__).resolve().parent
_USER_DATA_ROOT = Path(os.environ["COWORK_USER_DATA_DIR"]) if os.environ.get("COWORK_USER_DATA_DIR") else _FEATURE_ROOT
_WORK_LOG_ROOT = _USER_DATA_ROOT / "work_logs"
_SESSION_ROOT = _WORK_LOG_ROOT / "sessions"
_ACTIVE_SESSION = threading.local()
_WRITE_LOCK = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _safe_payload(value: Any, max_chars: int = 100_000) -> Any:
    try:
        serialized = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        serialized = json.dumps(str(value), ensure_ascii=False)
    if len(serialized) <= max_chars:
        return value
    return {
        "truncated": True,
        "original_characters": len(serialized),
        "preview": serialized[:max_chars],
    }


_MAX_SESSION_FILES = 200


def _session_path(session_id: str) -> Path:
    return _SESSION_ROOT / f"{session_id}.jsonl"


def _prune_old_sessions(max_files: int = _MAX_SESSION_FILES) -> None:
    """Keep the most recent session logs so the sessions directory doesn't grow forever."""
    try:
        files = sorted(_SESSION_ROOT.glob("*.jsonl"), key=lambda path: path.stat().st_mtime)
    except OSError:
        return
    for path in files[: max(0, len(files) - max_files)]:
        try:
            path.unlink()
        except OSError:
            pass


def start_cowork_session(model: str, workspace_root: str) -> str:
    _SESSION_ROOT.mkdir(parents=True, exist_ok=True)
    _prune_old_sessions()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    session_id = f"{timestamp}-{uuid.uuid4().hex[:8]}"
    _ACTIVE_SESSION.session_id = session_id
    record_cowork_event(
        "session_started",
        {
            "model": str(model or ""),
            "workspace_root": os.path.abspath(workspace_root),
        },
        session_id=session_id,
    )
    return session_id


def active_cowork_session_id() -> str | None:
    return getattr(_ACTIVE_SESSION, "session_id", None)


def record_cowork_event(event_type: str, payload: Any, session_id: str | None = None) -> None:
    resolved_session_id = session_id or active_cowork_session_id()
    if not resolved_session_id:
        return

    entry = {
        "timestamp": _utc_now(),
        "session_id": resolved_session_id,
        "event_type": str(event_type),
        "payload": _safe_payload(payload),
    }
    path = _session_path(resolved_session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _WRITE_LOCK:
        with path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def record_cowork_ui_event(event_type: str, payload: dict) -> None:
    if event_type.startswith("cowork_"):
        record_cowork_event("ui_event", {"event_type": event_type, **payload})


def record_cowork_tool_event(tool_name: str, arguments: dict, result: str) -> None:
    record_cowork_event(
        "tool_execution",
        {
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
        },
    )


def finish_cowork_session(status: str, summary: str = "") -> None:
    session_id = active_cowork_session_id()
    if not session_id:
        return
    record_cowork_event("session_finished", {"status": status, "summary": summary}, session_id=session_id)
    _ACTIVE_SESSION.session_id = None


def load_recent_conversation_history(max_messages: int = 20) -> list[dict]:
    if not _SESSION_ROOT.exists():
        return []

    messages: list[dict] = []
    for path in sorted(_SESSION_ROOT.glob("*.jsonl"), reverse=True):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("event_type") != "ui_event":
                continue
            payload = entry.get("payload") or {}
            if payload.get("event_type") != "cowork_log":
                continue
            role = str(payload.get("role", "")).upper()
            text = str(payload.get("text", "")).strip()
            if role == "USER" and text:
                messages.append({"role": "user", "content": text})
            elif role == "AI" and text:
                messages.append({"role": "assistant", "content": text})
            if len(messages) >= max_messages:
                return list(reversed(messages))
    return list(reversed(messages))
