from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_CODE_BLOCK_RE = re.compile(r"```(?P<lang>[a-zA-Z0-9_-]*)\s*\n(?P<content>.*?)```", re.DOTALL)


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.path = self.root / "chat_artifacts" / "artifacts.json"

    def list_artifacts(self) -> list[dict[str, Any]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        artifacts = raw.get("artifacts") if isinstance(raw, dict) else []
        return [item for item in artifacts if isinstance(item, dict)]

    def create_artifact(self, artifact_type: str, title: str, content: str, *, session_id: str = "") -> dict[str, Any]:
        clean_type = _artifact_type(artifact_type)
        clean_title = str(title or "").strip()[:120] or f"{clean_type.title()} artifact"
        clean_content = str(content or "")
        artifacts = self.list_artifacts()
        artifact_id = _artifact_id(clean_title, clean_type, session_id)
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        existing = next((item for item in artifacts if item.get("id") == artifact_id), None)
        if existing is None:
            existing = {
                "id": artifact_id,
                "title": clean_title,
                "type": clean_type,
                "session_id": session_id,
                "created_at": now,
                "versions": [],
            }
            artifacts.append(existing)
        versions = list(existing.get("versions") or [])
        version = len(versions) + 1
        entry = {"version": version, "content": clean_content, "created_at": now}
        versions.append(entry)
        existing["versions"] = versions
        existing["updated_at"] = now
        self._write(artifacts)
        return {**existing, "version": version, "content": clean_content}

    def _write(self, artifacts: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".json.tmp")
        temp.write_text(json.dumps({"schema_version": 1, "artifacts": artifacts}, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)


class ArtifactToolProvider:
    def __init__(self, store: ArtifactStore, *, session_id: str = ""):
        self.store = store
        self.session_id = session_id
        self.schemas = [
            {
                "type": "function",
                "function": {
                    "name": "create_artifact",
                    "description": "Create a persistent Chat artifact such as code, markdown, or sandboxed HTML.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["code", "markdown", "html", "text"]},
                            "title": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["type", "title", "content"],
                        "additionalProperties": False,
                    },
                },
            }
        ]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> str:
        if name != "create_artifact":
            return json.dumps({"status": "error", "error": f"Unknown artifact tool: {name}"}, ensure_ascii=False)
        artifact = self.store.create_artifact(
            str(arguments.get("type") or "text"),
            str(arguments.get("title") or ""),
            str(arguments.get("content") or ""),
            session_id=self.session_id,
        )
        return json.dumps({"status": "ok", "artifact": _public_artifact(artifact)}, ensure_ascii=False)


def detect_artifacts(answer: str) -> list[dict[str, str]]:
    artifacts: list[dict[str, str]] = []
    for match in _CODE_BLOCK_RE.finditer(str(answer or "")):
        lang = match.group("lang").casefold()
        content = match.group("content").strip()
        if not content:
            continue
        if lang in {"html", "htm"} or "<html" in content.casefold() or "<!doctype html" in content.casefold():
            artifacts.append({"type": "html", "title": "HTML artifact", "content": content})
        elif len(content) >= 1200:
            artifacts.append({"type": "code", "title": f"{lang or 'Code'} artifact", "content": content})
    return artifacts[:4]


def _artifact_type(value: str) -> str:
    normalized = str(value or "").strip().casefold()
    return normalized if normalized in {"code", "markdown", "html", "text"} else "text"


def _artifact_id(title: str, artifact_type: str, session_id: str) -> str:
    raw = f"{session_id}\0{artifact_type}\0{title}".encode("utf-8")
    return "artifact-" + hashlib.sha1(raw).hexdigest()[:16]


def _public_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": artifact.get("id"),
        "title": artifact.get("title"),
        "type": artifact.get("type"),
        "version": artifact.get("version"),
        "content": artifact.get("content"),
        "updated_at": artifact.get("updated_at"),
    }
