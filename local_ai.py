from openai import OpenAI


def is_local_model(model: str) -> bool:
    return str(model or "").strip().lower().startswith("local:")


def local_model_id(model: str) -> str:
    normalized = str(model or "").strip()
    return normalized.split(":", 1)[1] if is_local_model(normalized) else normalized


def create_local_ai_client(base_url: str, api_key: str = "", timeout: float = 45.0) -> OpenAI:
    normalized_base_url = str(base_url or "").strip().rstrip("/")
    if not normalized_base_url:
        raise RuntimeError("LOCAL_AI_BASE_URL is not configured.")
    return OpenAI(
        api_key=str(api_key or "").strip() or "local-ai",
        base_url=normalized_base_url,
        timeout=timeout,
        max_retries=0,
    )


def fetch_local_ai_models(base_url: str, api_key: str = "") -> list[str]:
    try:
        payload = create_local_ai_client(base_url, api_key).models.list()
    except Exception as exc:
        raise RuntimeError(str(exc).strip() or "Local AI model fetch failed.") from exc

    model_ids = {
        str(getattr(item, "id", "")).strip()
        for item in payload
        if str(getattr(item, "id", "")).strip()
    }
    return sorted(
        model_id
        for model_id in model_ids
        if "embedding" not in model_id.lower() and not model_id.lower().startswith("embed-")
    )
