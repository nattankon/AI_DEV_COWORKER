from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx


PROFILE_FILENAME = "custom_anthropic_provider.json"
PROVIDER_ID = "anthropic_compatible"
MODEL_PREFIX = "anthropic-compatible:"

PROTOCOL_ANTHROPIC = "anthropic_messages"
PROTOCOL_OPENAI = "openai_chat_completions"
AUTH_BEARER = "bearer"
AUTH_X_API_KEY = "x_api_key"

_PROTOCOLS = {PROTOCOL_ANTHROPIC, PROTOCOL_OPENAI}
_AUTH_SCHEMES = {AUTH_BEARER, AUTH_X_API_KEY}

def provider_presets() -> list[dict[str, str]]:
    return [dict(item) for item in _load_provider_presets()]


def normalize_base_url(value: str) -> str:
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Base URL must be an HTTP or HTTPS endpoint.")
    if parsed.username or parsed.password:
        raise ValueError("Base URL must not contain credentials.")
    path = parsed.path.rstrip("/")
    if not path.casefold().endswith("/v1") and not path.casefold().endswith("/v1/openai"):
        path = f"{path}/v1"
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc, path, "", ""))


def load_profile(app_root: str | Path) -> dict[str, Any]:
    empty = _profile_payload()
    path = Path(app_root) / PROFILE_FILENAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return empty
    if not isinstance(payload, dict):
        return empty
    try:
        base_url = normalize_base_url(str(payload.get("base_url") or ""))
    except ValueError:
        base_url = ""
    return _profile_payload(
        preset_id=str(payload.get("preset_id") or "custom"),
        base_url=base_url,
        protocol=str(payload.get("protocol") or PROTOCOL_ANTHROPIC),
        auth_scheme=str(payload.get("auth_scheme") or AUTH_X_API_KEY),
        models_auth_scheme=str(payload.get("models_auth_scheme") or AUTH_BEARER),
        models=payload.get("models"),
    )


def save_profile(
    app_root: str | Path,
    base_url: str,
    models: list[str] | tuple[str, ...] | None = None,
    *,
    preset_id: str = "custom",
    protocol: str = PROTOCOL_ANTHROPIC,
    auth_scheme: str = AUTH_X_API_KEY,
    models_auth_scheme: str = AUTH_BEARER,
) -> dict[str, Any]:
    root = Path(app_root)
    root.mkdir(parents=True, exist_ok=True)
    previous = load_profile(root)
    profile = _profile_payload(
        preset_id=preset_id,
        base_url=normalize_base_url(base_url),
        protocol=protocol,
        auth_scheme=auth_scheme,
        models_auth_scheme=models_auth_scheme,
        models=previous["models"] if models is None else models,
    )
    destination = root / PROFILE_FILENAME
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return profile


def import_models(
    base_url: str,
    api_key: str,
    *,
    timeout: float = 15.0,
    auth_scheme: str = AUTH_BEARER,
) -> list[str]:
    clean_key = str(api_key or "").strip()
    if not clean_key:
        raise ValueError("API key is required to import models.")
    endpoint = f"{normalize_base_url(base_url)}/models"
    try:
        response = httpx.request(
            "GET",
            endpoint,
            headers={"Accept": "application/json", **_auth_headers(clean_key, auth_scheme)},
            timeout=max(1.0, float(timeout)),
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        detail = _response_detail(exc.response)
        raise RuntimeError(f"Model import failed ({exc.response.status_code}): {detail}") from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError("Model import timed out.") from exc
    except (httpx.RequestError, ValueError) as exc:
        raise RuntimeError(f"Model import connection failed: {exc}") from exc
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
        "strengths": ["Compatible API", "Custom endpoint"],
        "context_window_tokens": 200_000,
        "vision": any(token in raw.casefold() for token in ("claude", "vision", "vl")),
        "custom": True,
    }


def provider_status(app_root: str | Path, *, configured: bool = False) -> dict[str, Any]:
    profile = load_profile(app_root)
    return {
        "id": PROVIDER_ID,
        "label": "Compatible API provider",
        "configured": bool(configured and profile["base_url"]),
        **{key: profile[key] for key in ("preset_id", "base_url", "protocol", "auth_scheme", "models_auth_scheme")},
        "models": [model_metadata(model) for model in profile["models"]],
        "presets": provider_presets(),
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


def _profile_payload(
    *,
    preset_id: str = "custom",
    base_url: str = "",
    protocol: str = PROTOCOL_ANTHROPIC,
    auth_scheme: str = AUTH_X_API_KEY,
    models_auth_scheme: str = AUTH_BEARER,
    models: Any = None,
) -> dict[str, Any]:
    known_presets = {item["id"] for item in provider_presets()}
    clean_preset = str(preset_id or "custom").strip().casefold()
    clean_protocol = _choice(protocol, _PROTOCOLS, "protocol")
    clean_auth_scheme = _choice(auth_scheme, _AUTH_SCHEMES, "request authentication")
    if clean_protocol == PROTOCOL_OPENAI and clean_auth_scheme != AUTH_BEARER:
        raise ValueError("OpenAI-compatible requests require Bearer token authentication.")
    return {
        "preset_id": clean_preset if clean_preset in known_presets else "custom",
        "base_url": str(base_url or ""),
        "protocol": clean_protocol,
        "auth_scheme": clean_auth_scheme,
        "models_auth_scheme": _choice(models_auth_scheme, _AUTH_SCHEMES, "model-list authentication"),
        "models": _clean_models(models),
    }


def _choice(value: str, allowed: set[str], label: str) -> str:
    clean = str(value or "").strip().casefold()
    if clean not in allowed:
        raise ValueError(f"Unsupported {label}: {value}")
    return clean


@lru_cache(maxsize=1)
def _load_provider_presets() -> tuple[dict[str, str], ...]:
    path = Path(__file__).with_name("compatible_provider_presets.json")
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeError(f"Compatible provider preset registry could not be loaded: {exc}") from exc
    if not isinstance(rows, list):
        raise RuntimeError("Compatible provider preset registry must contain a list.")
    presets: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            raise RuntimeError("Compatible provider preset entries must be objects.")
        item = {key: str(raw.get(key) or "").strip() for key in ("id", "label", "base_url", "protocol", "auth_scheme", "models_auth_scheme")}
        if not item["id"] or item["id"] in seen:
            raise RuntimeError("Compatible provider preset IDs must be unique and non-empty.")
        _choice(item["protocol"], _PROTOCOLS, "preset protocol")
        _choice(item["auth_scheme"], _AUTH_SCHEMES, "preset request authentication")
        _choice(item["models_auth_scheme"], _AUTH_SCHEMES, "preset model-list authentication")
        if item["base_url"]:
            item["base_url"] = normalize_base_url(item["base_url"])
        seen.add(item["id"])
        presets.append(item)
    if "custom" not in seen:
        raise RuntimeError("Compatible provider preset registry must include a custom entry.")
    return tuple(presets)


def _auth_headers(api_key: str, scheme: str) -> dict[str, str]:
    clean_scheme = _choice(scheme, _AUTH_SCHEMES, "authentication")
    if clean_scheme == AUTH_X_API_KEY:
        return {"x-api-key": api_key}
    return {"Authorization": f"Bearer {api_key}"}


def _response_detail(response: httpx.Response) -> str:
    text = str(response.text or "").strip()
    return text[:600] or response.reason_phrase or "HTTP request failed"


def _clean_models(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    return sorted({str(value or "").strip() for value in values if str(value or "").strip()})
