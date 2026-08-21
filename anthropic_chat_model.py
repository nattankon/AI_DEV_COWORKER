from __future__ import annotations

import base64
import json
from collections.abc import Iterable
from typing import Any

import httpx


class AnthropicChatModel:
    """Adapter that lets the shared tool loop use Anthropic's Messages API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout: float = 45.0,
        base_url: str = "https://api.anthropic.com/v1",
        auth_scheme: str = "x_api_key",
    ):
        self.api_key = str(api_key or "")
        self.model = _provider_model_id(model)
        self.timeout = max(1.0, float(timeout))
        self.endpoint = f"{str(base_url or '').rstrip('/')}/messages"
        self.auth_scheme = _normalize_auth_scheme(auth_scheme)

    def complete(self, messages: list[dict], tools: list[dict], generation: dict | None = None) -> dict:
        request_body = self._request_payload(messages, tools, generation)
        headers = {
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
                "Accept": "application/json",
                "User-Agent": "AI-Dev-Coworker/0.1",
        }
        if self.auth_scheme == "bearer":
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            headers["x-api-key"] = self.api_key
        try:
            response = httpx.post(
                self.endpoint,
                json=request_body,
                headers=headers,
                timeout=self.timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            detail = str(exc.response.text or "").strip()[:1_000]
            raise RuntimeError(f"Anthropic API request failed ({exc.response.status_code}): {detail}") from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError("Anthropic API request timed out.") from exc
        except (httpx.RequestError, ValueError) as exc:
            raise RuntimeError(f"Anthropic API connection failed: {exc}") from exc
        return _normalize_response(payload)

    def _request_payload(self, messages: list[dict], tools: list[dict], generation: dict | None) -> dict[str, Any]:
        settings = dict(generation or {})
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max(1, int(settings.get("max_tokens") or 2_048)),
            "messages": _anthropic_messages(messages),
        }
        system = _anthropic_system(messages)
        if system:
            payload["system"] = system
        if "temperature" in settings and settings["temperature"] is not None:
            payload["temperature"] = settings["temperature"]
        normalized_tools = _anthropic_tools(tools)
        if normalized_tools:
            payload["tools"] = normalized_tools
        return payload


def _provider_model_id(model: str) -> str:
    raw = str(model or "").strip()
    for prefix in ("anthropic:", "anthropic-compatible:"):
        if raw.startswith(prefix):
            return raw[len(prefix) :]
    return raw


def _normalize_auth_scheme(value: str) -> str:
    clean = str(value or "").strip().casefold()
    if clean not in {"bearer", "x_api_key"}:
        raise ValueError(f"Unsupported Anthropic-compatible authentication: {value}")
    return clean


def _anthropic_system(messages: Iterable[dict[str, Any]]) -> str:
    parts: list[str] = []
    for message in messages:
        if str(message.get("role") or "") == "system":
            text = _content_as_text(message.get("content"))
            if text:
                parts.append(text)
    return "\n\n".join(parts)


def _anthropic_messages(messages: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for message in messages:
        raw_role = str(message.get("role") or "").strip().lower()
        if raw_role == "system":
            continue
        if raw_role == "tool":
            role, blocks = "user", [_tool_result_block(message)]
        elif raw_role == "assistant":
            role, blocks = "assistant", _assistant_blocks(message)
        elif raw_role == "user":
            role, blocks = "user", _content_blocks(message.get("content"))
        else:
            continue
        if not blocks:
            continue
        if output and output[-1]["role"] == role:
            output[-1]["content"].extend(blocks)
        else:
            output.append({"role": role, "content": blocks})
    if not output:
        return [{"role": "user", "content": [{"type": "text", "text": "Continue."}]}]
    return output


def _assistant_blocks(message: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = _content_blocks(message.get("content"))
    for call in message.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        function = call.get("function") if isinstance(call.get("function"), dict) else call
        name = str(function.get("name") or "").strip()
        if not name:
            continue
        raw_arguments = function.get("arguments") or "{}"
        try:
            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else dict(raw_arguments)
        except (TypeError, ValueError, json.JSONDecodeError):
            arguments = {}
        blocks.append(
            {
                "type": "tool_use",
                "id": str(call.get("id") or "tool_call"),
                "name": name,
                "input": arguments if isinstance(arguments, dict) else {},
            }
        )
    return blocks


def _tool_result_block(message: dict[str, Any]) -> dict[str, Any]:
    content = _content_as_text(message.get("content"))
    return {
        "type": "tool_result",
        "tool_use_id": str(message.get("tool_call_id") or message.get("id") or "tool_call"),
        "content": content or "{}",
    }


def _content_blocks(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}] if content else []
    if not isinstance(content, list):
        text = _content_as_text(content)
        return [{"type": "text", "text": text}] if text else []
    blocks: list[dict[str, Any]] = []
    for item in content:
        if isinstance(item, str):
            if item:
                blocks.append({"type": "text", "text": item})
            continue
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            text = str(item.get("text") or "")
            if text:
                blocks.append({"type": "text", "text": text})
            continue
        image = _image_block(item)
        if image:
            blocks.append(image)
    return blocks


def _image_block(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("type") != "image_url":
        return None
    image_url = item.get("image_url")
    url = image_url.get("url") if isinstance(image_url, dict) else image_url
    raw = str(url or "")
    if not raw.startswith("data:") or ";base64," not in raw:
        return None
    header, data = raw.split(",", 1)
    media_type = header[5:].split(";", 1)[0] or "image/png"
    try:
        base64.b64decode(data, validate=True)
    except (ValueError, TypeError):
        return None
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


def _content_as_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [_content_as_text(item) for item in content]
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        if content.get("type") == "text":
            return str(content.get("text") or "")
        return ""
    return str(content or "")


def _anthropic_tools(tools: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for tool in tools:
        function = tool.get("function") if isinstance(tool, dict) else None
        if not isinstance(function, dict) or not function.get("name"):
            continue
        normalized.append(
            {
                "name": str(function["name"]),
                "description": str(function.get("description") or ""),
                "input_schema": function.get("parameters") if isinstance(function.get("parameters"), dict) else {"type": "object"},
            }
        )
    return normalized


def _normalize_response(payload: dict[str, Any]) -> dict[str, Any]:
    content_parts: list[str] = []
    tool_calls: list[dict[str, str]] = []
    for block in payload.get("content") or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and block.get("text"):
            content_parts.append(str(block["text"]))
        elif block.get("type") == "tool_use":
            tool_calls.append(
                {
                    "id": str(block.get("id") or ""),
                    "name": str(block.get("name") or ""),
                    "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
                }
            )
    return {"content": "".join(content_parts), "tool_calls": tool_calls}
