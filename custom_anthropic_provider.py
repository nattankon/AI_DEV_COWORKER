from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


PROFILE_FILENAME = "custom_anthropic_provider.json"
PROVIDER_ID = "anthropic_compatible"
MODEL_PREFIX = "anthropic-compatible:"


def normalize_base_url(value: str) -> str:
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Base URL must be an HTTP or HTTPS endpoint.")
    if parsed.username or parsed.password:
        raise ValueError("Base URL must not contain credentials.")
    path = parsed.path.rstrip("/")
    if not path.casefold().endswith("/v1"):
        path = f"{path}/v1"
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc, path, "", ""))


def load_profile(app_root: str | Path) -> dict[str, Any]:
    path = Path(app_root) / PROFILE_FILENAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"base_url": "", "models": []}
    if not isinstance(payload, dict):
        return {"base_url": "", "models": []}
    try:
        base_url = normalize_base_url(str(payload.get("base_url") or ""))
    except ValueError:
        base_url = ""
    return {"base_url": base_url, "models": _clean_models(payload.get("models"))}


def save_profile(
    app_root: str | Path,
    base_url: str,
    models: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    root = Path(app_root)
    root.mkdir(parents=True, exist_ok=True)
    previous = load_profile(root)
    profile = {
        "base_url": normalize_base_url(base_url),
        "models": _clean_models(previous["models"] if models is None else models),
    }
    destination = root / PROFILE_FILENAME
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return profile


def import_models(base_url: str, api_key: str, *, timeout: float = 15.0) -> list[str]:
    clean_key = str(api_key or "").strip()
    if not clean_key:
        raise ValueError("API key is required to import models.")
    endpoint = f"{normalize_base_url(base_url)}/models"
    request = Request(
        endpoint,
        headers={"Accept": "application/json", "Authorization": f"Bearer {clean_key}"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=max(1.0, float(timeout))) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:600]
        raise RuntimeError(f"Model import failed ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Model import connection failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Model import timed out.") from exc
    rows = payload.get("data") if isinstance(payload, dict) else []
    models = [row.get("id") for row in rows or [] if isinstance(row, dict)]
    return _clean_models(models)


def model_metadata(raw_model_id: str) -> dict[str, Any]:
    raw = str(raw_model_id or "").strip()
    if raw.startswith(MODEL_PREFIX):
        raw = raw[len(MODEL_PREFIX) :]
    return {
        "id": f"{MODEL_PREFIX}{raw}",
        "label": raw,
        "tier": "custom",
        "billing": "custom",
        "badge": "Custom / Imported",
        "strengths": ["Anthropic-compatible", "Custom endpoint"],
        "context_window_tokens": 200_000,
        "vision": raw.casefold().startswith("claude-"),
        "custom": True,
    }


def provider_status(app_root: str | Path, *, configured: bool = False) -> dict[str, Any]:
    profile = load_profile(app_root)
    return {
        "id": PROVIDER_ID,
        "label": "Custom Anthropic-compatible",
        "configured": bool(configured and profile["base_url"]),
        "base_url": profile["base_url"],
        "models": [model_metadata(model) for model in profile["models"]],
        "custom": True,
        "source": "user-configured",
    }


def custom_model_ids(app_root: str | Path) -> list[str]:
    return [f"{MODEL_PREFIX}{model}" for model in load_profile(app_root)["models"]]


def custom_model_metadata(app_root: str | Path, model_id: str) -> dict[str, Any] | None:
    raw = str(model_id or "").strip()
    if not raw.startswith(MODEL_PREFIX):
        return None
    provider_id = raw[len(MODEL_PREFIX) :]
    if provider_id not in load_profile(app_root)["models"]:
        return None
    return model_metadata(provider_id)


def _clean_models(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    return sorted({str(value or "").strip() for value in values if str(value or "").strip()})
