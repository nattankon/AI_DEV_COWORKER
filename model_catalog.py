from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


CATALOG_SOURCE_DATE = "2026-06-30"

MODEL_PROVIDER_CATALOG: list[dict[str, Any]] = [
    {
        "id": "openai",
        "label": "OpenAI",
        "source": "https://developers.openai.com/api/docs/guides/latest-model",
        "models": [
            {
                "id": "openai:gpt-5.5",
                "label": "GPT-5.5",
                "tier": "main",
                "billing": "paid",
                "badge": "Top / Coding",
                "strengths": ["reasoning", "coding", "planning", "agent", "long-context"],
                "context_window_tokens": 1_050_000,
                "recommended": True,
                "vision": False,
            },
            {
                "id": "openai:gpt-5.4",
                "label": "GPT-5.4",
                "tier": "main",
                "billing": "paid",
                "badge": "Top / Reasoning",
                "strengths": ["reasoning", "coding", "planning", "agent"],
                "context_window_tokens": 1_050_000,
                "vision": False,
            },
            {
                "id": "openai:gpt-5.3-instant",
                "label": "GPT-5.3 Instant",
                "tier": "fast",
                "billing": "paid",
                "badge": "Fast / Chat",
                "strengths": ["chat", "writing", "translation", "fast-response"],
                "context_window_tokens": 1_050_000,
                "vision": False,
            },
            {
                "id": "openai:gpt-4.1",
                "label": "GPT-4.1",
                "tier": "legacy",
                "billing": "paid",
                "badge": "Legacy / Coding",
                "strengths": ["coding", "long-context", "instruction-following"],
                "context_window_tokens": 1_000_000,
                "vision": False,
            },
            {
                "id": "openai:gpt-4.1-mini",
                "label": "GPT-4.1 Mini",
                "tier": "legacy",
                "billing": "paid",
                "badge": "Value / Coding",
                "strengths": ["coding", "chat", "long-context", "value"],
                "context_window_tokens": 1_000_000,
                "vision": False,
            },
            {
                "id": "openai:gpt-4o",
                "label": "GPT-4o",
                "tier": "legacy",
                "billing": "paid",
                "badge": "Legacy / Vision",
                "strengths": ["vision", "chat", "translation", "writing"],
                "context_window_tokens": 128_000,
                "vision": True,
            },
            {
                "id": "openai:gpt-4o-mini",
                "label": "GPT-4o Mini",
                "tier": "legacy",
                "billing": "paid",
                "badge": "Cheap / Chat",
                "strengths": ["chat", "vision", "fast-response", "value"],
                "context_window_tokens": 128_000,
                "vision": True,
            },
        ],
    },
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "source": "https://api-docs.deepseek.com/",
        "models": [
            {
                "id": "deepseek:deepseek-v4-flash",
                "label": "DeepSeek V4 Flash",
                "tier": "fast",
                "billing": "paid-low-cost",
                "badge": "Fast / Coding",
                "strengths": ["coding", "chat", "translation", "writing", "agent"],
                "context_window_tokens": 1_000_000,
                "vision": False,
            },
            {
                "id": "deepseek:deepseek-v4-pro",
                "label": "DeepSeek V4 Pro",
                "tier": "main",
                "billing": "paid-low-cost",
                "badge": "Top / Reasoning",
                "strengths": ["reasoning", "coding", "planning", "agent", "long-context"],
                "context_window_tokens": 1_000_000,
                "vision": False,
            },
            {
                "id": "deepseek:deepseek-chat",
                "label": "DeepSeek Chat",
                "tier": "legacy",
                "billing": "paid-low-cost",
                "badge": "Legacy / Chat",
                "strengths": ["chat", "coding", "writing"],
                "status": "legacy-alias",
                "vision": False,
            },
            {
                "id": "deepseek:deepseek-reasoner",
                "label": "DeepSeek Reasoner",
                "tier": "legacy",
                "billing": "paid-low-cost",
                "badge": "Legacy / Reasoning",
                "strengths": ["reasoning", "coding", "planning"],
                "status": "legacy-alias",
                "vision": False,
            },
        ],
    },
    {
        "id": "zai",
        "label": "Z.ai",
        "source": "https://docs.z.ai/api-reference/llm/chat-completion",
        "models": [
            {
                "id": "zai:glm-5.2",
                "label": "GLM-5.2",
                "tier": "main",
                "billing": "paid",
                "badge": "Top / Coding",
                "strengths": ["coding", "agent", "long-context", "planning", "reasoning"],
                "context_window_tokens": 1_000_000,
                "recommended": True,
                "vision": False,
            },
            {
                "id": "zai:glm-5.1",
                "label": "GLM-5.1",
                "tier": "main",
                "billing": "paid",
                "badge": "Top / Agent",
                "strengths": ["agent", "coding", "planning", "long-horizon"],
                "context_window_tokens": 200_000,
                "vision": False,
            },
            {
                "id": "zai:glm-5-turbo",
                "label": "GLM-5-Turbo",
                "tier": "fast",
                "billing": "paid",
                "badge": "Fast / Agent",
                "strengths": ["agent", "coding", "fast-response", "workflow"],
                "context_window_tokens": 200_000,
                "vision": False,
            },
            {
                "id": "zai:glm-5",
                "label": "GLM-5",
                "tier": "main",
                "billing": "paid",
                "badge": "Top / Agent",
                "strengths": ["agent", "coding", "reasoning", "planning"],
                "context_window_tokens": 200_000,
                "vision": False,
            },
            {"id": "zai:glm-4.7", "label": "GLM-4.7", "tier": "balanced", "billing": "paid", "badge": "Balanced / Coding", "strengths": ["coding", "chat", "reasoning"], "context_window_tokens": 200_000, "vision": False},
            {"id": "zai:glm-4.7-flashx", "label": "GLM-4.7-FlashX", "tier": "fast", "billing": "paid", "badge": "Fast / Coding", "strengths": ["coding", "chat", "agent"], "context_window_tokens": 200_000, "vision": False},
            {
                "id": "zai:glm-4.7-flash",
                "label": "GLM-4.7-Flash",
                "tier": "free",
                "billing": "free",
                "badge": "Free / Limited",
                "strengths": ["coding", "chat"],
                "context_window_tokens": 200_000,
                "availability_status": "free-rate-limited",
                "vision": False,
            },
            {
                "id": "zai:glm-4.5-flash",
                "label": "GLM-4.5-Flash",
                "tier": "free",
                "billing": "free",
                "badge": "Free / Reasoning",
                "strengths": ["reasoning", "chat", "coding"],
                "context_window_tokens": 131072,
                "recommended": True,
                "default_model": True,
                "availability_status": "free-smoke-tested",
                "vision": False,
            },
        ],
    },
    {
        "id": "gemini",
        "label": "Gemini",
        "source": "https://ai.google.dev/gemini-api/docs/models",
        "models": [
            {
                "id": "gemini:gemini-3.5-flash",
                "label": "Gemini 3.5 Flash",
                "tier": "main",
                "billing": "free-tier",
                "badge": "Top / Fast",
                "strengths": ["chat", "coding", "reasoning", "multimodal", "fast-response"],
                "context_window_tokens": 1_000_000,
                "recommended": True,
                "vision": True,
            },
            {
                "id": "gemini:gemini-3.1-pro-preview",
                "label": "Gemini 3.1 Pro Preview",
                "tier": "main",
                "billing": "paid",
                "badge": "Top / Reasoning",
                "strengths": ["reasoning", "coding", "multimodal", "planning", "long-context"],
                "context_window_tokens": 1_000_000,
                "vision": True,
            },
            {
                "id": "gemini:gemini-3-flash-preview",
                "label": "Gemini 3 Flash Preview",
                "tier": "fast",
                "billing": "free-tier",
                "badge": "Fast / Multimodal",
                "strengths": ["chat", "multimodal", "fast-response", "coding"],
                "context_window_tokens": 1_000_000,
                "vision": True,
            },
            {
                "id": "gemini:gemini-3.1-flash-lite",
                "label": "Gemini 3.1 Flash-Lite",
                "tier": "free",
                "billing": "free-tier",
                "badge": "Free / Fast",
                "strengths": ["chat", "fast-response", "translation", "value"],
                "context_window_tokens": 1_000_000,
                "vision": True,
            },
            {
                "id": "gemini:gemini-2.5-flash",
                "label": "Gemini 2.5 Flash",
                "tier": "free",
                "billing": "free-tier",
                "badge": "Free / Balanced",
                "strengths": ["chat", "coding", "multimodal", "long-context", "value"],
                "context_window_tokens": 1_000_000,
                "vision": True,
            },
            {
                "id": "gemini:gemini-2.5-flash-lite",
                "label": "Gemini 2.5 Flash-Lite",
                "tier": "free",
                "billing": "free-tier",
                "badge": "Free / Fast",
                "strengths": ["chat", "fast-response", "translation", "value"],
                "context_window_tokens": 1_000_000,
                "vision": True,
            },
        ],
    },
]

KNOWN_MODEL_PREFIXES = ("local:", "openai:", "deepseek:", "zai:", "gemini:")


@dataclass(frozen=True)
class ProviderKey:
    provider_id: str
    slot: int


def catalog_model_ids() -> list[str]:
    return [
        str(model["id"])
        for provider in MODEL_PROVIDER_CATALOG
        for model in provider.get("models", [])
        if model.get("id")
    ]


def catalog_model_metadata(model_id: str) -> dict[str, Any]:
    requested = str(model_id or "").strip()
    for provider in MODEL_PROVIDER_CATALOG:
        for model in provider.get("models", []):
            if str(model.get("id") or "") == requested:
                return dict(model)
    return {}


def catalog_model_supports_vision(model_id: str) -> bool:
    metadata = catalog_model_metadata(model_id)
    if "vision" in metadata:
        return bool(metadata.get("vision"))
    strengths = {str(item).casefold() for item in metadata.get("strengths", []) if item}
    return "vision" in strengths or "multimodal" in strengths


# The provider-key store. "credentials.txt" is the canonical name; "key.txt" is
# read as a fallback so existing setups keep working until the user migrates.
# Both are blocked from the agent's file tools by secret_guard.
_KEY_FILE_NAMES: tuple[str, ...] = ("credentials.txt", "key.txt")


def _resolve_key_file(app_root: str | Path) -> Path:
    root = Path(app_root).expanduser().resolve()
    for name in _KEY_FILE_NAMES:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return root / _KEY_FILE_NAMES[0]


def detect_provider_keys(app_root: str | Path) -> list[ProviderKey]:
    key_file = _resolve_key_file(app_root)
    if not key_file.is_file():
        return []

    detected: list[ProviderKey] = []
    for index, line in enumerate(key_file.read_text(encoding="utf-8").splitlines(), start=1):
        key, hint = _credential_parts(line)
        if not key or key.startswith("#"):
            continue
        detected.append(ProviderKey(provider_id=_classify_key(key, hint=hint), slot=index))
    return detected


def read_provider_api_key(app_root: str | Path, provider_id: str) -> str:
    requested_provider = str(provider_id or "").strip()
    if not requested_provider:
        return ""
    key_file = _resolve_key_file(app_root)
    if not key_file.is_file():
        return ""

    for line in key_file.read_text(encoding="utf-8").splitlines():
        key, hint = _credential_parts(line)
        if not key or key.startswith("#"):
            continue
        if _classify_key(key, hint=hint) == requested_provider:
            return key
    return ""


def provider_statuses(app_root: str | Path) -> list[dict[str, Any]]:
    detected = detect_provider_keys(app_root)
    slots_by_provider: dict[str, list[int]] = {}
    for item in detected:
        slots_by_provider.setdefault(item.provider_id, []).append(item.slot)

    statuses: list[dict[str, Any]] = []
    for provider in MODEL_PROVIDER_CATALOG:
        provider_id = str(provider["id"])
        statuses.append(
            {
                "id": provider_id,
                "label": provider["label"],
                "configured": bool(slots_by_provider.get(provider_id)),
                "key_slots": slots_by_provider.get(provider_id, []),
                "models": provider["models"],
                "source": provider["source"],
            }
        )
    if slots_by_provider.get("unknown"):
        statuses.append(
            {
                "id": "unknown",
                "label": "Unknown provider",
                "configured": True,
                "key_slots": slots_by_provider["unknown"],
                "models": [],
                "source": "",
            }
        )
    return statuses


def _credential_parts(line: str) -> tuple[str, str]:
    raw = str(line or "").strip()
    if not raw or raw.startswith("#"):
        return "", ""
    parts = raw.split()
    return parts[0].strip(), raw.casefold()


def _classify_key(key: str, *, hint: str = "") -> str:
    lowered_hint = str(hint or "").casefold()
    if "deepseek" in lowered_hint:
        return "deepseek"
    if "openai" in lowered_hint:
        return "openai"
    if "gemini" in lowered_hint or "google" in lowered_hint:
        return "gemini"
    if "z.ai" in lowered_hint or "zai" in lowered_hint:
        return "zai"
    if key.startswith("sk-ant-"):
        return "unknown"
    if key.startswith("sk-proj-"):
        return "openai"
    if key.startswith("sk-") and len(key) == 51:
        return "deepseek"
    if key.startswith("sk-"):
        return "openai"
    if len(key) == 49 and all(char.isalnum() or char == "." for char in key):
        return "zai"
    if key.startswith("AIza"):
        return "gemini"
    return "unknown"
