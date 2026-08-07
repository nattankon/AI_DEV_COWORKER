from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelRoute:
    model_id: str
    reason: str


_CODE_TERMS = (
    "code",
    "coding",
    "program",
    "script",
    "lua",
    "python",
    "javascript",
    "typescript",
    "react",
    "vue",
    "next.js",
    "frontend",
    "backend",
    "api",
    "html",
    "css",
    "node.js",
    "debug",
    "fix bug",
    "โค้ด",
    "โปรแกรม",
    "สคริปต์",
    "บั๊ก",
    "แก้บั๊ก",
)
_RESEARCH_TERMS = ("research", "sources", "compare sources", "current", "latest", "news", "ค้นหา", "ล่าสุด")
_TRANSLATION_TERMS = ("translate", "translation", "แปล", "ภาษา")
_WRITING_TERMS = ("write prose", "draft", "novel", "story", "rewrite", "summarize", "สรุป", "นิยาย")


def route_model(
    prompt: str,
    attachments: list[dict[str, Any]] | None,
    available_models: list[dict[str, Any]],
    *,
    requested_model: str,
    performance_profile: dict[str, Any] | None = None,
) -> ModelRoute:
    requested = str(requested_model or "").strip()
    if requested and requested != "auto":
        return ModelRoute(requested, "explicit")
    models = [dict(item) for item in (available_models or []) if item.get("id")]
    if not models:
        return ModelRoute("", "no-models")
    if any(str(item.get("kind") or "").casefold() == "image" for item in (attachments or [])):
        profile_match = _best_profile_model(models, performance_profile, ("attachment", "general"), required_strengths={"vision", "multimodal"})
        if profile_match:
            return ModelRoute(profile_match["id"], "auto: quality profile for vision attachment")
        match = _best_model(models, {"vision", "multimodal"})
        if match:
            return ModelRoute(match["id"], "auto: vision attachment")
    lowered = str(prompt or "").casefold()
    if any(term in lowered for term in _RESEARCH_TERMS):
        profile_match = _best_profile_model(models, performance_profile, ("web", "general"))
        if profile_match:
            return ModelRoute(profile_match["id"], "auto: quality profile for research task")
        match = _best_model(models, {"research", "long-context", "reasoning"})
        if match:
            return ModelRoute(match["id"], "auto: research task")
    if any(term in lowered for term in _TRANSLATION_TERMS):
        profile_match = _best_profile_model(models, performance_profile, ("thai", "general"))
        if profile_match:
            return ModelRoute(profile_match["id"], "auto: quality profile for translation task")
        match = _best_model(models, {"translation", "writing", "chat"})
        if match:
            return ModelRoute(match["id"], "auto: translation task")
    if any(term in lowered for term in _WRITING_TERMS):
        profile_match = _best_profile_model(models, performance_profile, ("general", "thai"))
        if profile_match:
            return ModelRoute(profile_match["id"], "auto: quality profile for writing task")
        match = _best_model(models, {"writing", "chat", "translation"})
        if match:
            return ModelRoute(match["id"], "auto: writing task")
    if any(term in lowered for term in _CODE_TERMS):
        profile_match = _best_profile_model(models, performance_profile, ("coding", "general"))
        if profile_match:
            return ModelRoute(profile_match["id"], "auto: quality profile for coding task")
        match = _best_model(models, {"coding", "agent", "reasoning"})
        if match:
            return ModelRoute(match["id"], "auto: coding task")
    if len(str(prompt or "")) > 80_000:
        match = max(models, key=lambda item: int(item.get("context_window_tokens") or 0))
        return ModelRoute(match["id"], "auto: long context")
    default = next((item for item in models if item.get("default_model")), None)
    if default:
        return ModelRoute(default["id"], "auto: default")
    profile_match = _best_profile_model(models, performance_profile, ("general",))
    if profile_match:
        return ModelRoute(profile_match["id"], "auto: quality profile for general task")
    recommended = next((item for item in models if item.get("recommended")), None)
    if recommended:
        return ModelRoute(recommended["id"], "auto: recommended")
    return ModelRoute(models[0]["id"], "auto: first available")


def _best_model(models: list[dict[str, Any]], desired: set[str]) -> dict[str, Any] | None:
    ranked = sorted(
        models,
        key=lambda item: (
            len({str(value).casefold() for value in item.get("strengths", [])} & desired),
            int(item.get("context_window_tokens") or 0),
            bool(item.get("recommended")),
        ),
        reverse=True,
    )
    if not ranked:
        return None
    strengths = {str(value).casefold() for value in ranked[0].get("strengths", [])}
    return ranked[0] if strengths & desired else None


def _best_profile_model(
    models: list[dict[str, Any]],
    profile: dict[str, Any] | None,
    categories: tuple[str, ...],
    *,
    required_strengths: set[str] | None = None,
) -> dict[str, Any] | None:
    profile_models = (profile or {}).get("models")
    if not isinstance(profile_models, dict):
        return None
    available_by_id = {str(model.get("id") or ""): model for model in models}
    ranked: list[tuple[float, int, int, dict[str, Any]]] = []
    for model_id, model in available_by_id.items():
        if required_strengths:
            strengths = {str(value).casefold() for value in model.get("strengths", [])}
            if not strengths & required_strengths:
                continue
        model_profile = profile_models.get(model_id)
        categories_payload = model_profile.get("categories") if isinstance(model_profile, dict) else None
        if not isinstance(categories_payload, dict):
            continue
        best_category: dict[str, Any] | None = None
        category_rank = len(categories)
        for index, category in enumerate(categories):
            payload = categories_payload.get(category)
            if isinstance(payload, dict) and int(payload.get("executed") or 0) > 0:
                best_category = payload
                category_rank = index
                break
        if not best_category:
            continue
        ranked.append(
            (
                float(best_category.get("router_score") or 0),
                int(best_category.get("executed") or 0),
                -category_rank,
                model,
            )
        )
    ranked.sort(key=lambda item: item[:3], reverse=True)
    return ranked[0][3] if ranked and ranked[0][0] > 0 else None
