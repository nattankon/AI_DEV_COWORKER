from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


_SECRET_PATTERN = re.compile(
    r"(api[_ -]?key|secret|password|passwd|token|private[_ -]?key|sk-[a-z0-9_-]{8,}|AIza[0-9A-Za-z_-]{20,})",
    re.IGNORECASE,
)
_PREFERENCE_PATTERNS = (
    re.compile(r"(ผม|ฉัน|เรา)\s*(ชอบ|อยากให้|ต้องการให้|ขอให้).+", re.IGNORECASE),
    re.compile(r"(ตอบ|อธิบาย).*(ภาษาไทย|ละเอียด|สั้น|กระชับ|เป็นกันเอง|ตรงไปตรงมา)", re.IGNORECASE),
    re.compile(r"(เรียกผมว่า|เรียกฉันว่า|ผมชื่อ|ฉันชื่อ).+", re.IGNORECASE),
    re.compile(r"(i prefer|please answer|call me|my name is|i like you to|i want you to).+", re.IGNORECASE),
    re.compile(r"(my long[- ]term goal is|my goal is|i want to build|i want to become).+", re.IGNORECASE),
    re.compile(r"(please write|answer style|writing style|warm detailed|concise thai|detailed thai).+", re.IGNORECASE),
)
_MAX_CONTENT_CHARS = 4000
_ROLE_MODE_META = {
    "Chat": {"authority": "chat_persona"},
    "Cowork": {"authority": "cowork_persona"},
    "Code": {"authority": "code_persona"},
}

# Role is a single global layer that applies to every chat in all modes.
_GLOBAL_ROLE_HEADER = "## Active Role"
_GLOBAL_ROLE_DESCRIPTION = (
    "This is the user's standing role instruction. It applies to every chat across all modes and "
    "is the highest-priority guidance for who you are and how you respond. Follow it directly."
)


def _normalize_mode(mode: str) -> str:
    candidate = str(mode or "").strip()
    return candidate if candidate in _ROLE_MODE_META else "Chat"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _entry_id(content: str, kind: str) -> str:
    normalized = re.sub(r"\s+", " ", content.strip().casefold())
    return f"{kind}:{normalized[:96]}"


class ChatMemoryStore:
    def __init__(self, root: str | Path, *, embedder: Callable[[str], list[float]] | None = None):
        self.root = Path(root)
        self.path = self.root / "chat_memory" / "personal.json"
        self._embedder = embedder

    def load_personal_memories(self) -> list[dict[str, Any]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        entries = raw.get("entries") if isinstance(raw, dict) else []
        if not isinstance(entries, list):
            return []
        return [entry for entry in entries if isinstance(entry, dict)]

    def list_memories(self) -> list[dict[str, Any]]:
        return [self._public_entry(entry) for entry in self.load_personal_memories()]

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        requested = str(memory_id or "").strip()
        if not requested:
            return None
        for entry in self.load_personal_memories():
            if str(entry.get("id") or "") == requested:
                return self._public_entry(entry)
        return None

    def update_memory(self, memory_id: str, text: str) -> dict[str, Any] | None:
        requested = str(memory_id or "").strip()
        content = str(text or "").strip()
        if not requested or not content or _SECRET_PATTERN.search(content):
            return None
        entries = self.load_personal_memories()
        updated: dict[str, Any] | None = None
        now = _utc_now()
        next_entries: list[dict[str, Any]] = []
        for entry in entries:
            if str(entry.get("id") or "") != requested:
                next_entries.append(entry)
                continue
            next_entry = {
                **entry,
                "content": content[:_MAX_CONTENT_CHARS],
                "updated_at": now,
            }
            embedding = self._embedding_for(content)
            if embedding is not None:
                next_entry["embedding"] = embedding
            else:
                next_entry.pop("embedding", None)
            updated = next_entry
            next_entries.append(next_entry)
        if updated is None:
            return None
        self._write_entries(next_entries)
        return self._public_entry(updated)

    def set_memory_enabled(self, memory_id: str, enabled: bool) -> dict[str, Any] | None:
        requested = str(memory_id or "").strip()
        if not requested:
            return None
        entries = self.load_personal_memories()
        updated: dict[str, Any] | None = None
        now = _utc_now()
        next_entries: list[dict[str, Any]] = []
        for entry in entries:
            if str(entry.get("id") or "") != requested:
                next_entries.append(entry)
                continue
            source = dict(entry.get("source") or {})
            source["enabled"] = bool(enabled)
            next_entry = {
                **entry,
                "enabled": bool(enabled),
                "source": source,
                "updated_at": now,
            }
            updated = next_entry
            next_entries.append(next_entry)
        if updated is None:
            return None
        self._write_entries(next_entries)
        return self._public_entry(updated)

    def delete_memory(self, memory_id: str) -> bool:
        requested = str(memory_id or "").strip()
        if not requested:
            return False
        entries = self.load_personal_memories()
        next_entries = [entry for entry in entries if str(entry.get("id") or "") != requested]
        if len(next_entries) == len(entries):
            return False
        self._write_entries(next_entries)
        return True

    def remember_from_user_message(self, message: str, source_session_id: str = "") -> list[dict[str, Any]]:
        content = str(message or "").strip()
        if not content or _SECRET_PATTERN.search(content):
            return []
        if not self._is_memorable(content):
            return []

        now = _utc_now()
        kind = self._kind_for(content)
        entry = {
            "id": _entry_id(content, kind),
            "namespace": "personal",
            "kind": kind,
            "content": content[:_MAX_CONTENT_CHARS],
            "source": {"type": "chat_user_message", "session_id": str(source_session_id or "")},
            "created_at": now,
            "updated_at": now,
        }
        embedding = self._embedding_for(content)
        if embedding is not None:
            entry["embedding"] = embedding
        entries = self.load_personal_memories()
        by_id = {str(existing.get("id") or ""): dict(existing) for existing in entries}
        if entry["id"] in by_id:
            entry["created_at"] = by_id[entry["id"]].get("created_at") or now
        by_id[entry["id"]] = entry
        next_entries = sorted(by_id.values(), key=lambda item: str(item.get("updated_at") or ""))[-50:]
        self._write_entries(next_entries)
        return [entry]

    def recall(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        entries = self._active_memory_entries()
        if not entries:
            return []
        entries = [entry for entry in entries if str(entry.get("kind") or "") not in {"do_not_remember", "role"}]
        query_terms = _terms(query)
        if self._embedder is not None:
            semantic = self._semantic_recall(query, entries, top_k=top_k)
            keyword = self._keyword_recall(entries, query_terms, top_k=top_k) if query_terms else []
            if semantic or keyword:
                return self._dedupe_entries([*keyword, *semantic])[:top_k]
        if not query_terms:
            return entries[-top_k:]
        return self._keyword_recall(entries, query_terms, top_k=top_k)

    def _keyword_recall(self, entries: list[dict[str, Any]], query_terms: set[str], *, top_k: int) -> list[dict[str, Any]]:
        scored: list[tuple[int, str, dict[str, Any]]] = []
        for entry in entries:
            entry_terms = _terms(str(entry.get("content") or ""))
            score = len(query_terms & entry_terms)
            if score > 0:
                scored.append((score, str(entry.get("updated_at") or entry.get("created_at") or ""), entry))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [entry for _score, _timestamp, entry in scored[:top_k]]

    def remember(self, fact: str, metadata: dict[str, Any] | None = None) -> dict[str, Any] | None:
        content = str(fact or "").strip()
        if not content or _SECRET_PATTERN.search(content):
            return None
        now = _utc_now()
        kind = str((metadata or {}).get("kind") or "fact").strip() or "fact"
        embedding = self._embedding_for(content)
        entry_id = _entry_id(content, kind)
        mode = str((metadata or {}).get("mode") or "").strip()
        if kind == "role" and mode:
            entry_id = f"{entry_id}:{mode.casefold()}"
        entries = self.load_personal_memories()
        duplicate = self._semantic_duplicate(entries, content, kind, embedding)
        if duplicate is not None:
            entry_id = str(duplicate.get("id") or entry_id)
        entry = {
            "id": entry_id,
            "namespace": "personal",
            "kind": kind,
            "content": content[:_MAX_CONTENT_CHARS],
            "source": dict(metadata or {}),
            "created_at": now,
            "updated_at": now,
        }
        if embedding is not None:
            entry["embedding"] = embedding
        by_id = {str(existing.get("id") or ""): dict(existing) for existing in entries}
        if entry["id"] in by_id:
            entry["created_at"] = by_id[entry["id"]].get("created_at") or now
        by_id[entry["id"]] = entry
        next_entries = sorted(by_id.values(), key=lambda item: str(item.get("updated_at") or ""))[-100:]
        self._write_entries(next_entries)
        return self._public_entry(entry)

    def remember_manual(self, text: str, *, kind: str = "preference", source_session_id: str = "", mode: str = "Chat", project: str = "") -> dict[str, Any] | None:
        allowed_kinds = {"do_not_remember", "identity", "long_term_goal", "memory", "preference", "profile", "role", "writing_style"}
        normalized_kind = str(kind or "preference").strip()
        if normalized_kind not in allowed_kinds:
            normalized_kind = "preference"
        if normalized_kind == "do_not_remember":
            return self.mark_do_not_remember(text, source_session_id=source_session_id)
        normalized_mode = _normalize_mode(mode)
        metadata = {
            "type": "manual_chat_memory",
            "session_id": str(source_session_id or ""),
            "project": str(project or ""),
            "kind": normalized_kind,
        }
        if normalized_kind == "role":
            # Role is a single global layer; it is not scoped to a mode or session.
            metadata.update({"authority": "global_role", "scope": "global", "enabled": True})
        return self.remember(text, metadata)

    def mark_do_not_remember(self, text: str, *, source_session_id: str = "") -> dict[str, Any] | None:
        content = str(text or "").strip()
        if not content or _SECRET_PATTERN.search(content):
            return None
        return self.remember(
            content,
            {
                "type": "manual_do_not_remember",
                "session_id": str(source_session_id or ""),
                "kind": "do_not_remember",
                "enabled": True,
            },
        )

    def format_for_prompt(
        self,
        max_entries: int = 8,
        query: str = "",
        source_session_id: str = "",
        mode: str = "Chat",
        project: str = "",
        include_personal_memory: bool = True,
    ) -> str:
        source_session = str(source_session_id or "")
        normalized_mode = _normalize_mode(mode)
        project = str(project or "")
        role_entries = self._active_role_entries()
        if query and include_personal_memory:
            recalled = self.recall(query, top_k=max_entries)
            recent = list(reversed(self._active_memory_entries()))[: max(2, min(3, max_entries))]
            candidate = [entry for entry in [*recalled, *recent] if str(entry.get("kind") or "") != "role"]
            entries = self._dedupe_entries(
                [entry for entry in candidate if self._memory_in_scope(entry, source_session, project)]
            )[:max_entries]
        elif include_personal_memory:
            entries = [
                entry
                for entry in self._active_memory_entries()
                if str(entry.get("kind") or "") != "role" and self._memory_in_scope(entry, source_session, project)
            ][-max_entries:]
        else:
            entries = []
        if not entries and not role_entries:
            return ""
        lines = []
        if role_entries:
            lines.extend([_GLOBAL_ROLE_HEADER, _GLOBAL_ROLE_DESCRIPTION])
            for entry in role_entries:
                timestamp = str(entry.get("updated_at") or entry.get("created_at") or "unknown time")
                content = str(entry.get("content") or "").strip()
                if content:
                    lines.append(f"- [role, {timestamp}] {content}")
        if entries:
            if lines:
                lines.append("")
            header = "## Chat Memory" if normalized_mode == "Chat" else "## Session Memory"
            scope_note = " and other chats in the same project" if project else ""
            lines.extend(
                [
                    header,
                    f"User instructions and context for this chat{scope_note}. Follow them for this session.",
                ]
            )
        for entry in entries:
            if str(entry.get("kind") or "") == "do_not_remember":
                continue
            timestamp = str(entry.get("updated_at") or entry.get("created_at") or "unknown time")
            kind = str(entry.get("kind") or "memory")
            content = str(entry.get("content") or "").strip()
            if content:
                lines.append(f"- [{kind}, {timestamp}] {content}")
        return "\n".join(lines)

    def _active_role_entries(self) -> list[dict[str, Any]]:
        """Role is global — every enabled role applies to all chats and modes."""
        roles: list[dict[str, Any]] = []
        for entry in self.load_personal_memories():
            if str(entry.get("kind") or "") != "role":
                continue
            if entry.get("enabled") is False or (entry.get("source") or {}).get("enabled") is False:
                continue
            roles.append(entry)
        return roles[-5:]

    def _memory_in_scope(self, entry: dict[str, Any], source_session: str, project: str) -> bool:
        """A memory applies to its own chat, to any chat in the same project, or globally
        when it has no session (legacy or user-global memory)."""
        source = entry.get("source") or {}
        entry_session = str(source.get("session_id") or "")
        entry_project = str(source.get("project") or "")
        if not entry_session:
            return True
        if source_session and entry_session == source_session:
            return True
        if project and entry_project and entry_project == project:
            return True
        return False

    def _dedupe_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for entry in entries:
            key = str(entry.get("id") or entry.get("content") or "")
            if key in seen:
                continue
            seen.add(key)
            out.append(entry)
        return out

    def _active_memory_entries(self) -> list[dict[str, Any]]:
        entries = [entry for entry in self.load_personal_memories() if entry.get("enabled") is not False and (entry.get("source") or {}).get("enabled") is not False]
        forget_markers = [entry for entry in entries if str(entry.get("kind") or "") == "do_not_remember"]
        if not forget_markers:
            return entries
        return [
            entry
            for entry in entries
            if str(entry.get("kind") or "") == "do_not_remember" or not self._blocked_by_forget_markers(entry, forget_markers)
        ]

    def _blocked_by_forget_markers(self, entry: dict[str, Any], markers: list[dict[str, Any]]) -> bool:
        content_terms = _terms(str(entry.get("content") or ""))
        if not content_terms:
            return False
        for marker in markers:
            marker_terms = _forget_marker_terms(str(marker.get("content") or ""))
            if len(marker_terms) < 2:
                continue
            if marker_terms and marker_terms <= content_terms:
                return True
            if marker_terms and content_terms & marker_terms and len(content_terms & marker_terms) >= min(2, len(marker_terms)):
                return True
        return False

    def _embedding_for(self, text: str) -> list[float] | None:
        if self._embedder is None:
            return None
        try:
            vector = [float(value) for value in list(self._embedder(text) or [])]
        except Exception:
            return None
        return vector if any(value != 0 for value in vector) else None

    def _semantic_duplicate(self, entries: list[dict[str, Any]], content: str, kind: str, embedding: list[float] | None) -> dict[str, Any] | None:
        if embedding is None or kind in {"do_not_remember", "role"}:
            return None
        best: tuple[float, dict[str, Any]] | None = None
        for entry in entries:
            if str(entry.get("kind") or "") != kind:
                continue
            score = _cosine(embedding, _entry_embedding(entry))
            if score >= 0.98 and (best is None or score > best[0]):
                best = (score, entry)
        return best[1] if best else None

    def _semantic_recall(self, query: str, entries: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
        query_embedding = self._embedding_for(query)
        if query_embedding is None:
            return []
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for entry in entries:
            if str(entry.get("kind") or "") in {"do_not_remember", "role"}:
                continue
            score = _cosine(query_embedding, _entry_embedding(entry))
            if score > 0:
                scored.append((score, str(entry.get("updated_at") or entry.get("created_at") or ""), entry))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [entry for score, _timestamp, entry in scored[:top_k] if score >= 0.2]

    def _write_entries(self, entries: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".json.tmp")
        payload = {"schema_version": 1, "entries": entries}
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def _public_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        content = str(entry.get("content") or "").strip()
        public = {key: value for key, value in entry.items() if key != "embedding"}
        return {
            **public,
            **{
                key: entry.get("source", {}).get(key)
                for key in ("authority", "scope", "mode", "enabled")
                if key in entry.get("source", {})
            },
            "text": content,
            "content": content,
        }

    def _is_memorable(self, content: str) -> bool:
        return any(pattern.search(content) for pattern in _PREFERENCE_PATTERNS)

    def _kind_for(self, content: str) -> str:
        lowered = content.casefold()
        if any(marker in lowered for marker in ("long-term goal", "long term goal", "my goal is", "i want to build", "i want to become")):
            return "long_term_goal"
        if any(marker in lowered for marker in ("please answer", "please write", "answer style", "writing style", "warm detailed", "concise thai", "detailed thai")):
            return "writing_style"
        if any(marker in lowered for marker in ("เรียกผมว่า", "เรียกฉันว่า", "ผมชื่อ", "ฉันชื่อ", "call me", "my name is")):
            return "identity"
        return "preference"


def _terms(text: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[A-Za-z0-9_ก-๙]{2,}", str(text or "").casefold())
        if term not in {"the", "and", "for", "with", "this", "that"}
    }


_FORGET_MARKER_STOPWORDS = {
    "do",
    "dont",
    "don't",
    "not",
    "remember",
    "forget",
    "my",
    "this",
    "that",
    "the",
    "a",
    "an",
}


def _forget_marker_terms(text: str) -> set[str]:
    return {term for term in _terms(text) if term not in _FORGET_MARKER_STOPWORDS}


def _entry_embedding(entry: dict[str, Any]) -> list[float] | None:
    raw = entry.get("embedding")
    if not isinstance(raw, list):
        return None
    try:
        vector = [float(value) for value in raw]
    except (TypeError, ValueError):
        return None
    return vector if any(value != 0 for value in vector) else None


def _cosine(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    if size <= 0:
        return 0.0
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = sum(left[index] * left[index] for index in range(size)) ** 0.5
    right_norm = sum(right[index] * right[index] for index in range(size)) ** 0.5
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (left_norm * right_norm)
