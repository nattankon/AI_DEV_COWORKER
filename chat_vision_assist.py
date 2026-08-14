"""Pure selection and prompt helpers for the optional image-analysis assistant."""

from dataclasses import dataclass
from typing import Any, Callable


DEFAULT_VISION_ASSIST_MODEL = "zai:glm-4.6v-flashx"
VISION_ASSIST_MODES = frozenset({"off", "auto", "on"})


@dataclass(frozen=True)
class VisionAssistDecision:
    enabled: bool
    helper_model: str
    mode: str
    reason: str


def normalize_vision_assist_mode(value: Any) -> str:
    normalized = str(value or "off").strip().casefold()
    return normalized if normalized in VISION_ASSIST_MODES else "off"


def select_vision_assist(
    attachments: list[dict[str, Any]],
    settings: dict[str, Any] | None,
    *,
    supports_vision: Callable[[str], bool],
) -> VisionAssistDecision:
    config = settings if isinstance(settings, dict) else {}
    mode = normalize_vision_assist_mode(config.get("visionAssist"))
    helper_model = str(config.get("visionModel") or DEFAULT_VISION_ASSIST_MODEL).strip()
    has_usable_image = any(
        isinstance(attachment, dict)
        and str(attachment.get("kind") or "").casefold() == "image"
        and str(attachment.get("data_url") or attachment.get("dataUrl") or "").startswith("data:image/")
        for attachment in attachments
    )
    if mode == "off":
        return VisionAssistDecision(False, helper_model, mode, "disabled")
    if not has_usable_image:
        return VisionAssistDecision(False, helper_model, mode, "no-usable-image")
    if not helper_model or not supports_vision(helper_model):
        return VisionAssistDecision(False, helper_model, mode, "helper-not-vision-capable")
    return VisionAssistDecision(True, helper_model, mode, "enabled")


def vision_evidence_system_prompt() -> str:
    return (
        "You are a vision evidence assistant. Inspect only visible evidence in the user-provided images. "
        "Report visible text, objects, counts, layout, and state concisely. Mark ambiguity or unreadable "
        "details as uncertain. Do not invent information, do not use outside knowledge, and do not answer "
        "beyond the image evidence."
    )


def build_vision_evidence_message(evidence: str, helper_model: str) -> str:
    clean_evidence = str(evidence or "").strip()
    return (
        "## Vision Evidence\n"
        f"A secondary image analyst ({helper_model}) inspected the user's attached image. "
        "Use only these observations for image-specific claims. If the observations do not answer the "
        "question, say what is not visible rather than infer it.\n\n"
        f"{clean_evidence}"
    )


def vision_assist_unavailable_message() -> str:
    return (
        "## Image Analysis Availability\n"
        "The image-analysis assistant was unavailable for this request. Do not claim to see image details "
        "unless the selected primary model received the image directly. If image details are required and "
        "not available, ask the user to retry or select a vision-capable model."
    )
