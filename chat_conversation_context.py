from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Iterable

try:
    from .model_catalog import catalog_model_metadata
except ImportError:
    from model_catalog import catalog_model_metadata


DEFAULT_CONTEXT_WINDOW_TOKENS = 32_768


@dataclass(frozen=True)
class ConversationContextPlan:
    context_window_tokens: int
    input_budget_tokens: int
    fixed_tokens: int
    history_budget_tokens: int
    history_tokens: int
    summary_reserve_tokens: int
    recent_history: list[dict[str, str]]
    compacted_history: list[dict[str, str]]


def estimate_text_tokens(value: object) -> int:
    """Conservative local estimate that keeps Thai text from being undercounted."""
    text = str(value or "")
    if not text.strip():
        return 0
    thai = sum(1 for char in text if "\u0e00" <= char <= "\u0e7f")
    other = sum(1 for char in text if not char.isspace()) - thai
    return max(1, math.ceil(thai / 1.6) + math.ceil(max(0, other) / 4))


def estimate_message_tokens(message: dict[str, Any]) -> int:
    return 4 + estimate_text_tokens(_message_content_text(message.get("content")))


def history_fingerprint(history: Iterable[dict[str, str]]) -> str:
    payload = [
        {"role": str(item.get("role") or ""), "content": str(item.get("content") or "")}
        for item in history
    ]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def plan_conversation_context(
    history: list[dict[str, str]],
    *,
    model_id: str,
    fixed_messages: list[dict[str, Any]],
    output_tokens: int,
    context_window_tokens: int | None = None,
) -> ConversationContextPlan:
    """Fit complete recent turns into the selected model's usable input window."""
    window = int(context_window_tokens or _catalog_context_window(model_id) or DEFAULT_CONTEXT_WINDOW_TOKENS)
    window = max(1_024, window)
    safety_margin = max(128, math.ceil(window * 0.04))
    input_budget = max(0, window - max(0, int(output_tokens)) - safety_margin)
    fixed_tokens = sum(estimate_message_tokens(message) for message in fixed_messages)
    history_budget = max(0, input_budget - fixed_tokens)
    normalized_history = _normalize_history(history)
    recent_history, compacted_history = _select_recent_turns(normalized_history, history_budget)
    summary_reserve = 0
    if compacted_history:
        summary_reserve = min(2_048, max(128, history_budget // 4))
        recent_history, compacted_history = _select_recent_turns(
            normalized_history,
            max(0, history_budget - summary_reserve),
        )
    return ConversationContextPlan(
        context_window_tokens=window,
        input_budget_tokens=input_budget,
        fixed_tokens=fixed_tokens,
        history_budget_tokens=history_budget,
        history_tokens=sum(estimate_message_tokens(message) for message in recent_history),
        summary_reserve_tokens=summary_reserve,
        recent_history=recent_history,
        compacted_history=compacted_history,
    )


def _catalog_context_window(model_id: str) -> int:
    metadata = catalog_model_metadata(str(model_id or ""))
    try:
        return int(metadata.get("context_window_tokens") or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


def _message_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_message_content_text(item) for item in content)
    if isinstance(content, dict):
        if content.get("type") == "image_url":
            return "[image attachment]"
        return "\n".join(_message_content_text(value) for value in content.values())
    return str(content or "")


def _normalize_history(history: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in history:
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            normalized.append({"role": role, "content": content})
    return normalized


def _select_recent_turns(history: list[dict[str, str]], budget: int) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    units = _history_units(history)
    selected: list[list[dict[str, str]]] = []
    used = 0
    for unit in reversed(units):
        cost = sum(estimate_message_tokens(message) for message in unit)
        if selected and used + cost > budget:
            break
        if not selected and cost > budget:
            break
        selected.append(unit)
        used += cost
    selected.reverse()
    recent = [message for unit in selected for message in unit]
    compacted_count = max(0, len(history) - len(recent))
    return recent, history[:compacted_count]


def _history_units(history: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    units: list[list[dict[str, str]]] = []
    index = 0
    while index < len(history):
        message = history[index]
        if message["role"] == "user" and index + 1 < len(history) and history[index + 1]["role"] == "assistant":
            units.append([message, history[index + 1]])
            index += 2
        else:
            units.append([message])
            index += 1
    return units
