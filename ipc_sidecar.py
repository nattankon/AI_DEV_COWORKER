from __future__ import annotations

import base64
from dataclasses import dataclass, field, replace
import inspect
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import uuid
from datetime import date
from typing import Callable, TextIO, Any
from urllib.parse import urlparse

try:
    from .cli_config import DEFAULT_LOCAL_AI_BASE_URL, DEFAULT_LOCAL_AI_MODEL
    from .model_catalog import CATALOG_SOURCE_DATE, catalog_model_ids, provider_statuses, read_provider_api_key, save_provider_key, catalog_model_supports_vision, catalog_model_metadata
except ImportError:
    try:
        from cli_config import DEFAULT_LOCAL_AI_BASE_URL, DEFAULT_LOCAL_AI_MODEL
        from model_catalog import CATALOG_SOURCE_DATE, catalog_model_ids, provider_statuses, read_provider_api_key, save_provider_key, catalog_model_supports_vision, catalog_model_metadata
    except ImportError:
        DEFAULT_LOCAL_AI_BASE_URL = "http://127.0.0.1:1234/v1"
        DEFAULT_LOCAL_AI_MODEL = "local:qwen/qwen3.5-9b"
        CATALOG_SOURCE_DATE = "2026-06-28"

        def catalog_model_ids() -> list[str]:
            return []

        def provider_statuses(_app_root) -> list[dict[str, Any]]:
            return []

        def read_provider_api_key(_app_root, _provider_id) -> str:
            return ""

        def save_provider_key(_app_root, _provider_id, _key) -> bool:
            return False

        def catalog_model_supports_vision(_model_id: str) -> bool:
            return False

        def catalog_model_metadata(_model_id: str) -> dict[str, Any]:
            return {}

DEFAULT_FALLBACK_MODELS = ("local:qwen2.5-7b-instruct",)
MAX_CHAT_ATTACHMENTS = 6
MAX_CHAT_ATTACHMENT_CHARS = 12_000
MAX_CHAT_IMAGE_BYTES = 2_000_000

try:
    from .approval_policy import build_approval_payload
    from .chat_artifacts import ArtifactStore, ArtifactToolProvider, detect_artifacts
    from .chat_code_exec import CodeExecutionToolProvider, CodeExecutor
    from .chat_memory import ChatMemoryStore
    from .chat_mcp_client import McpConnectorRegistry, McpDiagnosticsToolProvider, McpToolProvider, create_mcp_clients, mcp_sdk_available, mcp_tool_name, validate_connector
    from .chat_pyodide_sandbox import PyodideSandbox
    from .chat_quality_eval import quality_eval_cases, run_quality_eval_snapshot
    from .chat_text_diagnostics import build_mojibake_diagnostics
    from .chat_vision_assist import (
        build_vision_evidence_message,
        select_vision_assist,
        vision_assist_unavailable_message,
        vision_evidence_system_prompt,
    )
    from .chat_answer_guard import GuardResult, validate_answer
    from .chat_research_runner import ChatResearchRunner
    from .chat_research_strategy import build_research_plan
    from .chat_router import classify_chat_prompt
    from .chat_runtime import DEFAULT_CHAT_RUNTIME_CONFIG, ChatRuntimeConfig
    from .chat_search_api import get_search_provider
    from .chat_tool_provider import CompositeToolProvider
    from .chat_web_connector import ChatWebConnector, DEFAULT_WEB_SEARCH_MAX_RESULTS, WebSearchResponse
    from .chat_web_smoke import SOURCE_PROFILE_FILENAME
    from .chat_web_tools import WebResearchTools
    from .cowork_agent import CoworkAgent, JsonlSessionRecorder, OpenAIChatModel
    from .local_ai import fetch_local_ai_models
    from .model_fallback import run_with_model_candidates
    from .model_performance import PROFILE_FILENAME, load_model_performance_profile
    from .model_router import route_model
    from .session_store import record_cowork_event
    from .workspace_tools import WorkspaceTools
except ImportError:
    from approval_policy import build_approval_payload
    from chat_artifacts import ArtifactStore, ArtifactToolProvider, detect_artifacts
    from chat_code_exec import CodeExecutionToolProvider, CodeExecutor
    from chat_memory import ChatMemoryStore
    from chat_mcp_client import McpConnectorRegistry, McpDiagnosticsToolProvider, McpToolProvider, create_mcp_clients, mcp_sdk_available, mcp_tool_name, validate_connector
    from chat_pyodide_sandbox import PyodideSandbox
    from chat_quality_eval import quality_eval_cases, run_quality_eval_snapshot
    from chat_text_diagnostics import build_mojibake_diagnostics
    from chat_vision_assist import (
        build_vision_evidence_message,
        select_vision_assist,
        vision_assist_unavailable_message,
        vision_evidence_system_prompt,
    )
    from chat_answer_guard import GuardResult, validate_answer
    from chat_research_runner import ChatResearchRunner
    from chat_research_strategy import build_research_plan
    from chat_router import classify_chat_prompt
    from chat_runtime import DEFAULT_CHAT_RUNTIME_CONFIG, ChatRuntimeConfig
    from chat_search_api import get_search_provider
    from chat_tool_provider import CompositeToolProvider
    from chat_web_connector import ChatWebConnector, DEFAULT_WEB_SEARCH_MAX_RESULTS, WebSearchResponse
    from chat_web_smoke import SOURCE_PROFILE_FILENAME
    from chat_web_tools import WebResearchTools
    from cowork_agent import CoworkAgent, JsonlSessionRecorder, OpenAIChatModel
    from local_ai import fetch_local_ai_models
    from model_fallback import run_with_model_candidates
    from model_performance import PROFILE_FILENAME, load_model_performance_profile
    from model_router import route_model
    from session_store import record_cowork_event
    from workspace_tools import WorkspaceTools


@dataclass
class IpcDependencies:
    workspace: Path = field(default_factory=lambda: Path(os.environ.get("COWORK_WORKSPACE", os.getcwd())).resolve())
    app_root: Path = field(default_factory=lambda: Path(os.environ.get("COWORK_APP_ROOT", Path(__file__).resolve().parent)).resolve())
    output: TextIO = field(default_factory=lambda: sys.stdout)
    input_stream: TextIO = field(default_factory=lambda: sys.stdin)
    base_url: str = field(default_factory=lambda: os.environ.get("LOCAL_AI_BASE_URL", DEFAULT_LOCAL_AI_BASE_URL).rstrip("/"))
    api_key: str = field(default_factory=lambda: os.environ.get("LOCAL_AI_API_KEY", ""))
    default_model: str = field(default_factory=lambda: os.environ.get("LOCAL_AI_MODEL", DEFAULT_LOCAL_AI_MODEL))
    fallback_models: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            item.strip()
            for item in os.environ.get("COWORK_FALLBACK_MODELS", ",".join(DEFAULT_FALLBACK_MODELS)).split(",")
            if item.strip()
        )
    )
    approval_timeout_seconds: float = 300
    agent_factory: Callable[[str], Any] | None = None
    chat_model_factory: Callable[..., Any] | None = None
    model_lister: Callable[[], list[str]] | None = None
    workspace_tools_factory: Callable[[Path], Any] | None = None
    chat_web_tools_factory: Callable[..., Any] | None = None
    chat_config: ChatRuntimeConfig = field(default_factory=lambda: DEFAULT_CHAT_RUNTIME_CONFIG)
    chat_memory_root: Path | None = None
    chat_memory_embedder_factory: Callable[..., Callable[[str], list[float]] | None] | None = None
    web_searcher: Callable[..., WebSearchResponse] | None = None
    chat_quality_live_runner: Callable[..., dict[str, Any]] | None = None
    chat_quality_report_writer: Callable[..., dict[str, str]] | None = None


class _RequestCancelled(RuntimeError):
    pass


def _default_model_timeout() -> float:
    """Per-request model timeout in seconds. Long code generations need more than a
    short default; overridable via COWORK_MODEL_TIMEOUT."""
    try:
        value = float(os.environ.get("COWORK_MODEL_TIMEOUT") or 0)
    except (TypeError, ValueError):
        value = 0.0
    return value if value > 0 else 300.0


class IpcSidecar:
    def __init__(self, dependencies: IpcDependencies | None = None):
        self.dependencies = dependencies or IpcDependencies()
        self._approval_condition = threading.Condition()
        self._pending_approvals: dict[str, str | None] = {}
        self._workers: list[threading.Thread] = []
        self._emit_lock = threading.Lock()
        self._worker_context = threading.local()
        self._auto_approve = False
        self._chat_histories: dict[str, list[dict[str, str]]] = {}
        self._cancelled_sessions: set[str] = set()
        self._cancel_lock = threading.Lock()
        self._mcp_client_cache: dict[str, tuple[float, dict[str, Any], list[dict[str, Any]]]] = {}
        self._chat_memory_embedder: Callable[[str], list[float]] | None = None
        self._chat_memory_embedder_initialized = False

    def serve(self) -> None:
        for line in self.dependencies.input_stream:
            self.handle_line(line)

    def handle_line(self, line: str) -> None:
        raw_line = str(line or "").strip()
        if not raw_line:
            return
        try:
            payload = json.loads(raw_line)
            if not isinstance(payload, dict):
                raise ValueError("IPC command must be a JSON object.")
        except (json.JSONDecodeError, ValueError) as exc:
            self._emit_backend_error(f"Invalid IPC JSON: {exc}")
            return

        command = str(payload.get("command") or "").strip()
        try:
            if command == "send_cowork":
                self._send_cowork(payload)
            elif command == "cancel_cowork":
                self._cancel_cowork(payload)
            elif command == "fetch_available_models":
                self._fetch_available_models()
            elif command == "fetch_registered_skills":
                self._emit("registered_skills", {"skills": []})
            elif command == "load_api_keys":
                self._emit_api_keys_loaded()
            elif command == "set_provider_key":
                # The key value flows straight to the key store; never echo it back.
                saved = save_provider_key(
                    self._runtime_root(),
                    str(payload.get("provider") or ""),
                    str(payload.get("key") or ""),
                )
                self._emit_api_keys_loaded(saved=saved, provider=str(payload.get("provider") or ""))
            elif command == "set_api_keys":
                self._emit("api_keys_loaded", {"saved": False, "reason": "not_persisted_by_sidecar"})
            elif command == "set_auto_approve":
                self._auto_approve = bool(payload.get("enabled"))
                self._emit("auto_approve_state", {"enabled": self._auto_approve})
            elif command == "chat_memory_list":
                self._emit_chat_memory_state()
            elif command == "chat_memory_create":
                store = self._chat_memory_store()
                store.remember_manual(
                    str(payload.get("text") or ""),
                    kind=str(payload.get("kind") or "preference"),
                    source_session_id=str(payload.get("client_session_id") or payload.get("clientSessionId") or ""),
                    mode=self._normalize_mode(payload.get("mode") or "Chat"),
                    project=self._active_project(),
                )
                self._emit_chat_memory_state()
            elif command == "chat_memory_update":
                store = self._chat_memory_store()
                store.update_memory(str(payload.get("id") or ""), str(payload.get("text") or ""))
                self._emit_chat_memory_state()
            elif command == "chat_memory_set_enabled":
                store = self._chat_memory_store()
                store.set_memory_enabled(str(payload.get("id") or ""), bool(payload.get("enabled")))
                self._emit_chat_memory_state()
            elif command == "chat_memory_delete":
                store = self._chat_memory_store()
                store.delete_memory(str(payload.get("id") or ""))
                self._emit_chat_memory_state()
            elif command == "chat_artifact_list":
                self._emit_chat_artifacts_state()
            elif command == "chat_quality_eval_list":
                self._emit_chat_quality_eval_state()
            elif command == "chat_quality_eval_run":
                self._emit_chat_quality_eval_state(results=payload.get("results") if isinstance(payload, dict) else None)
            elif command == "chat_quality_run":
                self._run_chat_quality(payload)
            elif command == "chat_connector_list":
                self._emit_chat_connectors_state()
            elif command == "chat_connector_save":
                connectors = payload.get("connectors")
                if isinstance(connectors, list):
                    self._mcp_connector_registry().save_connectors(connectors)
                self._emit_chat_connectors_state()
            elif command == "chat_connector_test":
                self._test_chat_connector(payload)
            elif command == "chat_connector_discover":
                self._discover_chat_connector(payload)
            elif command == "chat_mcp_tool_run":
                self._run_chat_mcp_tool_async(payload)
            elif command == "answer_question":
                self._answer_question(payload)
            elif command == "set_workspace":
                self._set_workspace(payload)
            elif command == "workspace_action":
                self._workspace_action(payload)
            else:
                self._emit_backend_error(f"Unknown IPC command: {command or '(empty)'}")
        except Exception as exc:
            self._emit_backend_error(str(exc).strip() or "IPC command failed.")

    def _send_cowork(self, payload: dict) -> None:
        worker = threading.Thread(target=self._send_cowork_worker, args=(payload,), daemon=True)
        self._workers.append(worker)
        worker.start()

    def _cancel_cowork(self, payload: dict) -> None:
        client_session_id = str(payload.get("client_session_id") or payload.get("clientSessionId") or "").strip()
        mode = self._normalize_mode(payload.get("mode"))
        if client_session_id:
            with self._cancel_lock:
                self._cancelled_sessions.add(client_session_id)
        self._emit(
            "cowork_log",
            {
                "role": "SYSTEM",
                "text": "Stopped.",
                "client_session_id": client_session_id,
                "mode": mode,
            },
        )
        self._emit("cowork_ui_state", {"state": "idle", "client_session_id": client_session_id, "mode": mode})

    def _start_worker(self, target: Callable[..., None], *args: Any) -> None:
        worker = threading.Thread(target=target, args=args, daemon=True)
        self._workers.append(worker)
        worker.start()

    def _send_cowork_worker(self, payload: dict) -> None:
        client_session_id = str(payload.get("client_session_id") or "").strip()
        mode = self._normalize_mode(payload.get("mode"))
        model = ""
        self._clear_cancelled(client_session_id)
        self._worker_context.client_session_id = client_session_id
        self._worker_context.mode = mode
        self._emit("cowork_ui_state", {"state": "busy", "client_session_id": client_session_id, "mode": mode})
        try:
            prompt = str(payload.get("prompt") or "").strip()
            if not prompt:
                self._emit_backend_error("Cowork prompt cannot be empty.")
                return
            model = self._normalize_model_name(str(payload.get("model") or "").strip() or self.dependencies.default_model)
            effort = self.dependencies.chat_config.normalize_effort(payload.get("effort"))
            route = classify_chat_prompt(prompt).category if mode == "Chat" else ""
            self._emit(
                "cowork_log",
                {
                    "role": "USER",
                    "text": prompt,
                    "client_session_id": client_session_id,
                    "mode": mode,
                    **({"route": route} if route else {}),
                },
            )
            attachments = self._normalize_chat_attachments(payload.get("attachments"))
            vision_settings = payload.get("vision_settings") or payload.get("visionSettings")
            if mode == "Chat":
                web_settings = self._normalize_chat_web_settings(payload.get("web_settings") or payload.get("webSettings"))
                def on_chat_delta(delta: str) -> None:
                    self._raise_if_cancelled(client_session_id)
                    if delta:
                        self._emit(
                            "cowork_log_delta",
                            {
                                "client_session_id": client_session_id,
                                "mode": "Chat",
                                "delta": delta,
                            },
                        )

                def on_chat_reset() -> None:
                    self._raise_if_cancelled(client_session_id)
                    self._emit(
                        "cowork_log_delta",
                        {
                            "client_session_id": client_session_id,
                            "mode": "Chat",
                            "delta": "",
                            "reset": True,
                        },
                    )

                answer, used_model, web_sources = self._run_plain_chat(
                    prompt,
                    model,
                    client_session_id,
                    effort,
                    attachments,
                    history_override=self._normalize_chat_history_override(payload.get("history")),
                    web_settings=web_settings,
                    vision_settings=vision_settings,
                    on_delta=on_chat_delta,
                    on_reset=on_chat_reset,
                )
            else:
                self._raise_if_cancelled(client_session_id)
                role_prompt = self._format_mode_role_prompt(prompt, client_session_id, mode)
                vision_assist = self._run_vision_assist(
                    prompt=prompt,
                    attachments=attachments,
                    primary_model=model,
                    settings=vision_settings,
                    client_session_id=client_session_id,
                    mode=mode,
                )

                def cowork_user_content(candidate_model: str) -> Any:
                    attachment_prompt = self._format_chat_attachments(
                        attachments,
                        vision_assist["attachment_model"],
                        context_name=mode,
                    )
                    content_prompt = role_prompt
                    if attachment_prompt:
                        content_prompt = f"{role_prompt}\n\n{attachment_prompt}"
                    evidence_message = str(vision_assist.get("evidence_message") or "").strip()
                    if evidence_message:
                        content_prompt = f"{content_prompt}\n\n{evidence_message}"
                    return self._build_chat_user_content(
                        content_prompt,
                        attachments if vision_assist["send_images_to_primary"] else [],
                        candidate_model,
                    )

                def on_cowork_delta(delta: str) -> None:
                    self._raise_if_cancelled(client_session_id)
                    if delta:
                        self._emit(
                            "cowork_log_delta",
                            {"client_session_id": client_session_id, "mode": mode, "delta": delta},
                        )

                def on_cowork_status(text: str) -> None:
                    self._raise_if_cancelled(client_session_id)
                    clean = str(text or "").strip()
                    if clean:
                        self._emit(
                            "cowork_status",
                            {"client_session_id": client_session_id, "mode": mode, "text": clean},
                        )

                def on_cowork_reset() -> None:
                    self._raise_if_cancelled(client_session_id)
                    self._emit(
                        "cowork_log_delta",
                        {"client_session_id": client_session_id, "mode": mode, "delta": "", "reset": True},
                    )

                def on_cowork_evidence(evidence: dict) -> None:
                    payload = evidence if isinstance(evidence, dict) else {}
                    self._emit(
                        "cowork_completion",
                        {
                            "client_session_id": client_session_id,
                            "mode": mode,
                            "writes_performed": bool(payload.get("writes_performed")),
                            "verification_observed": bool(payload.get("verification_observed")),
                            "verification_passed": bool(payload.get("verification_passed")),
                            "verification_statuses": list(payload.get("verification_statuses") or []),
                            "verification_runs": list(payload.get("verification_runs") or []),
                            "test_files_modified": list(payload.get("test_files_modified") or []),
                        },
                    )

                answer, used_model = self._run_with_fallback(
                    role_prompt,
                    model,
                    client_session_id,
                    mode,
                    on_delta=on_cowork_delta,
                    on_status=on_cowork_status,
                    on_stream_reset=on_cowork_reset,
                    on_evidence=on_cowork_evidence,
                    user_content_factory=cowork_user_content if attachments else None,
                )
                web_sources = []
            self._raise_if_cancelled(client_session_id)
            assistant_payload = {
                "role": "AI",
                "text": answer,
                "client_session_id": client_session_id,
                "model": used_model,
                "mode": mode,
                **({"route": route} if route else {}),
            }
            if web_sources:
                assistant_payload["web_sources"] = web_sources
            self._emit(
                "cowork_log",
                assistant_payload,
            )
        except _RequestCancelled:
            pass
        except Exception as exc:
            message = str(exc).strip() or "Cowork request failed."
            if mode == "Chat":
                message = _friendly_chat_error_message(message, model)
            self._emit_backend_error(message)
        finally:
            self._emit("cowork_ui_state", {"state": "idle", "client_session_id": client_session_id, "mode": mode})
            self._worker_context.client_session_id = ""
            self._worker_context.mode = ""
            self._clear_cancelled(client_session_id)

    def wait_for_idle(self, timeout: float | None = None) -> bool:
        for worker in list(self._workers):
            worker.join(timeout=timeout)
            if worker.is_alive():
                return False
        self._workers = [worker for worker in self._workers if worker.is_alive()]
        return True

    def _clear_cancelled(self, client_session_id: str) -> None:
        if not client_session_id:
            return
        with self._cancel_lock:
            self._cancelled_sessions.discard(client_session_id)

    def _is_cancelled(self, client_session_id: str) -> bool:
        if not client_session_id:
            return False
        with self._cancel_lock:
            return client_session_id in self._cancelled_sessions

    def _raise_if_cancelled(self, client_session_id: str) -> None:
        if self._is_cancelled(client_session_id):
            raise _RequestCancelled()

    def _normalize_chat_history_override(self, raw_history: Any) -> list[dict[str, str]] | None:
        if raw_history is None:
            return None
        if not isinstance(raw_history, list):
            return []
        normalized: list[dict[str, str]] = []
        for item in raw_history:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip().lower()
            content = str(item.get("content") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            normalized.append({"role": role, "content": content})
        return normalized[-40:]

    def _fetch_available_models(self) -> None:
        model_lister = self.dependencies.model_lister or self._default_model_lister
        local_models_error = ""
        try:
            local_models = [self._normalize_model_name(model) for model in model_lister()]
        except Exception as exc:
            local_models = []
            local_models_error = str(exc).strip() or "Local model list failed."
        models = [*local_models, *catalog_model_ids()]
        payload = {
            "models": models,
            "providers": provider_statuses(self._runtime_root()),
            "catalog_source_date": CATALOG_SOURCE_DATE,
        }
        if local_models_error:
            payload["local_models_error"] = local_models_error
        self._emit("available_models", payload)

    def _run_with_fallback(
        self,
        prompt: str,
        requested_model: str,
        client_session_id: str,
        mode: str = "Cowork",
        on_delta: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_stream_reset: Callable[[], None] | None = None,
        on_evidence: Callable[[dict], None] | None = None,
        user_content_factory: Callable[[str], Any] | None = None,
    ) -> tuple[str, str]:
        candidates = self._model_candidates(requested_model)
        failures: list[str] = []
        for index, model in enumerate(candidates):
            try:
                agent = self._create_agent(model)
                return str(
                    agent.run(
                        prompt,
                        on_delta=on_delta,
                        on_status=on_status,
                        on_stream_reset=on_stream_reset,
                        on_evidence=on_evidence,
                        **({"user_content": user_content_factory(model)} if user_content_factory else {}),
                    )
                ), model
            except Exception as exc:
                message = str(exc).strip() or "model request failed"
                failures.append(f"{model}: {message}")
                if index < len(candidates) - 1:
                    next_model = candidates[index + 1]
                    self._emit(
                        "cowork_log",
                        {
                            "role": "SYSTEM",
                            "text": f"Model {model} failed ({message}). Trying fallback {next_model}.",
                            "client_session_id": client_session_id,
                            "model": model,
                            "fallback_model": next_model,
                            "mode": mode,
                        },
                    )
                    continue
                raise RuntimeError("; ".join(failures)) from exc
        raise RuntimeError("No local model candidate is available.")

    def _active_project(self) -> str:
        workspace = getattr(self.dependencies, "workspace", None)
        return str(workspace) if workspace else ""

    def _format_mode_role_prompt(self, prompt: str, client_session_id: str, mode: str) -> str:
        role_prompt = self._chat_memory_store().format_for_prompt(
            query=prompt,
            source_session_id=client_session_id,
            mode=mode,
            project=self._active_project(),
            include_personal_memory=True,
        )
        if not role_prompt.strip():
            return prompt
        return f"{role_prompt}\n\n## User Request\n{prompt}"

    def _run_plain_chat(
        self,
        prompt: str,
        requested_model: str,
        client_session_id: str,
        effort: str,
        attachments: list[dict[str, Any]] | None = None,
        history_override: list[dict[str, str]] | None = None,
        web_settings: dict[str, str] | None = None,
        vision_settings: dict[str, Any] | None = None,
        on_delta: Callable[[str], None] | None = None,
        on_reset: Callable[[], None] | None = None,
        return_diagnostics: bool = False,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        model = self._normalize_model_name(requested_model)
        effort_name = self.dependencies.chat_config.normalize_effort(effort)
        effort_config = self.dependencies.chat_config.effort_config(effort_name)
        history_limit = max(0, effort_config.history_messages)
        history_key = client_session_id or "__default_chat__"
        history = history_override if history_override is not None else self._chat_histories.get(history_key, [])
        recent_history = history[-history_limit:] if history_limit else []
        route = classify_chat_prompt(prompt)
        memory_store = self._chat_memory_store()
        stored_memories = memory_store.remember_from_user_message(prompt, source_session_id=client_session_id)
        memory_prompt = memory_store.format_for_prompt(query=prompt, source_session_id=client_session_id, mode="Chat", project=self._active_project())
        memory_messages = [{"role": "system", "content": memory_prompt}] if memory_prompt else []
        normalized_attachments = attachments or []
        model = self._route_chat_model_if_auto(model, prompt, normalized_attachments)
        vision_assist = self._run_vision_assist(
            prompt=prompt,
            attachments=normalized_attachments,
            primary_model=model,
            settings=vision_settings,
            client_session_id=client_session_id,
            mode="Chat",
        )
        attachment_prompt = self._format_chat_attachments(normalized_attachments, vision_assist["attachment_model"])
        attachment_messages = [{"role": "system", "content": attachment_prompt}] if attachment_prompt else []
        vision_message = str(vision_assist.get("evidence_message") or "").strip()
        vision_messages = [{"role": "system", "content": vision_message}] if vision_message else []
        mcp_context_prompt = self._format_chat_mcp_live_context(
            prompt,
            web_settings,
            client_session_id=client_session_id,
        )
        mcp_context_messages = [{"role": "system", "content": mcp_context_prompt}] if mcp_context_prompt else []
        user_content = self._build_chat_user_content(
            prompt,
            normalized_attachments if vision_assist["send_images_to_primary"] else [],
            model,
        )
        web_response: WebSearchResponse | None = None
        research_result = None
        guard_result: GuardResult | None = None
        used_tool_research = False
        answer_path_started = time.perf_counter()
        tool_loop_attempted = self._should_run_tool_research(route, model, web_settings)
        if tool_loop_attempted:
            try:
                answer, used_model, research_result, guard_result = self._run_tool_research_chat(
                    prompt=prompt,
                    requested_model=model,
                    client_session_id=client_session_id,
                    route=route,
                    effort_config=effort_config,
                    memory_messages=memory_messages,
                    attachment_messages=attachment_messages,
                    vision_messages=vision_messages,
                    mcp_context_messages=mcp_context_messages,
                    recent_history=recent_history,
                    user_content=user_content,
                    web_settings=web_settings,
                    on_delta=on_delta,
                    on_reset=on_reset,
                )
                if not str(answer or "").strip():
                    raise RuntimeError("Chat research model returned an empty response.")
                used_tool_research = bool(research_result and research_result.outcome.used_tools)
            except Exception as exc:
                if _is_provider_access_error(str(exc)):
                    raise
                answer, used_model, web_response = self._legacy_web_chat(
                    prompt=prompt,
                    requested_model=model,
                    client_session_id=client_session_id,
                    route=route,
                    effort_name=effort_name,
                    effort_config=effort_config,
                    memory_messages=memory_messages,
                    attachment_messages=attachment_messages,
                    vision_messages=vision_messages,
                    mcp_context_messages=mcp_context_messages,
                    recent_history=recent_history,
                    user_content=user_content,
                    web_settings=web_settings,
                )
        else:
            answer, used_model, web_response = self._legacy_web_chat(
                prompt=prompt,
                requested_model=model,
                client_session_id=client_session_id,
                route=route,
                effort_name=effort_name,
                effort_config=effort_config,
                memory_messages=memory_messages,
                attachment_messages=attachment_messages,
                vision_messages=vision_messages,
                mcp_context_messages=mcp_context_messages,
                recent_history=recent_history,
                user_content=user_content,
                web_settings=web_settings,
            )
        web_source_count = (
            len(research_result.sources)
            if used_tool_research and research_result
            else len(web_response.results) if web_response else 0
        )
        web_sources = self._chat_web_sources(
            research_sources=research_result.sources if used_tool_research and research_result else None,
            web_response=web_response,
        )
        evidence_corpus = ""
        if used_tool_research and research_result:
            evidence_corpus = str(research_result.evidence_corpus or "")
        elif web_response:
            evidence_corpus = "\n\n".join(
                str(getattr(result, "evidence", "") or "")
                for result in web_response.results
                if str(getattr(result, "evidence", "") or "").strip()
            )
        record_cowork_event("chat_route", {"client_session_id": client_session_id, "mode": "Chat", "route": route.category, "reasons": list(route.reasons), "web_sources": web_source_count})
        record_cowork_event("chat_message_user", {"client_session_id": client_session_id, "model": model, "mode": "Chat", "effort": effort_name, "route": route.category, "web_sources": web_source_count, "content": prompt})
        if attachments:
            record_cowork_event(
                "chat_attachments",
                {
                    "client_session_id": client_session_id,
                    "mode": "Chat",
                    "count": len(attachments),
                    "labels": [attachment["label"] for attachment in attachments],
                    "sources": [attachment["source"] for attachment in attachments],
                },
            )
        if stored_memories:
            record_cowork_event("chat_memory_updated", {"client_session_id": client_session_id, "mode": "Chat", "stored": len(stored_memories)})
        if web_response:
            record_cowork_event(
                "chat_web_search",
                {
                    "client_session_id": client_session_id,
                    "mode": "Chat",
                    "query": web_response.query,
                    "result_count": len(web_response.results),
                    "error": web_response.error,
                    "urls": [result.url for result in web_response.results],
                    "provider": self._resolve_search_provider_label(web_settings),
                },
            )
        if research_result:
            record_cowork_event(
                "chat_research",
                {
                    "client_session_id": client_session_id,
                    "mode": "Chat",
                    "used_tools": research_result.outcome.used_tools,
                    "iterations": research_result.outcome.iterations,
                    "forced": research_result.outcome.forced,
                    "source_count": len(research_result.sources),
                    "used_model": research_result.used_model,
                },
            )
        if guard_result:
            record_cowork_event(
                "chat_answer_guard",
                {
                    "client_session_id": client_session_id,
                    "mode": "Chat",
                    "ok": guard_result.ok,
                    "violation_count": len(guard_result.violations),
                },
            )
        artifacts = self._capture_chat_artifacts(answer, client_session_id, web_settings)
        if artifacts:
            record_cowork_event(
                "chat_artifacts_created",
                {
                    "client_session_id": client_session_id,
                    "mode": "Chat",
                    "count": len(artifacts),
                    "ids": [artifact.get("id") for artifact in artifacts],
                },
            )
        next_history = [
            *history,
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ]
        self._chat_histories[history_key] = next_history[-history_limit:] if history_limit else []
        record_cowork_event("chat_message_assistant", {"client_session_id": client_session_id, "model": used_model, "mode": "Chat", "effort": effort_name, "route": route.category, "web_sources": len(web_sources), "content": answer})
        if return_diagnostics:
            return answer, used_model, web_sources, {
                "route": route.category,
                "used_tool_research": used_tool_research,
                "evidence_corpus": evidence_corpus,
                "web_source_count": len(web_sources),
                # Where the time went: whether this prompt entered the tool loop at
                # all, how many loop iterations ran, and the wall time of the whole
                # answer path — the data needed to attribute the ~60s "general"
                # latency to routing vs raw model speed.
                "entered_tool_loop": research_result is not None,
                # attempted=True with entered=False means the loop CRASHED into the
                # legacy fallback — without this flag that case is indistinguishable
                # from "routing skipped the loop", which misleads eval hard-fails.
                "tool_loop_attempted": tool_loop_attempted,
                "research_iterations": int(research_result.outcome.iterations) if research_result else 0,
                "research_forced": bool(research_result.outcome.forced) if research_result else False,
                "answer_path_ms": int(max(0, (time.perf_counter() - answer_path_started) * 1000)),
                # "brave_api" vs "scrape_fallback" — resolved the same way the
                # request's own web connector resolves it, so a missing key is
                # visible instead of silently capping web quality.
                "search_provider": self._resolve_search_provider_label(web_settings),
            }
        return answer, used_model, web_sources

    def _chat_web_sources(
        self,
        *,
        research_sources: list[dict] | None = None,
        web_response: WebSearchResponse | None = None,
    ) -> list[dict[str, Any]]:
        raw_sources: list[Any] = []
        if research_sources:
            raw_sources = list(research_sources)
        elif web_response:
            raw_sources = [
                {
                    "index": index,
                    "url": result.url,
                    "title": result.title,
                    "source_type": getattr(result, "source_type", "search-result"),
                }
                for index, result in enumerate(web_response.results, start=1)
            ]
        sources: list[dict[str, Any]] = []
        for fallback_index, source in enumerate(raw_sources, start=1):
            if isinstance(source, dict):
                url = str(source.get("url") or "").strip()
                title = str(source.get("title") or url or "Web source").strip()
                source_type = str(source.get("source_type") or "search-result").strip()
                index = source.get("index", fallback_index)
            else:
                url = str(getattr(source, "url", "") or "").strip()
                title = str(getattr(source, "title", "") or url or "Web source").strip()
                source_type = str(getattr(source, "source_type", "search-result") or "search-result").strip()
                index = fallback_index
            if not url:
                continue
            try:
                source_index = int(index)
            except (TypeError, ValueError):
                source_index = fallback_index
            domain = urlparse(url).netloc or urlparse(f"//{url}").netloc or url
            sources.append(
                {
                    "index": source_index,
                    "url": url,
                    "title": title,
                    "source_type": source_type,
                    "domain": domain,
                }
            )
        return sources

    def _run_tool_research_chat(
        self,
        *,
        prompt: str,
        requested_model: str,
        client_session_id: str,
        route: Any,
        effort_config: Any,
        memory_messages: list[dict[str, str]],
        attachment_messages: list[dict[str, str]],
        vision_messages: list[dict[str, str]],
        mcp_context_messages: list[dict[str, str]],
        recent_history: list[dict[str, str]],
        user_content: Any,
        web_settings: dict[str, str] | None = None,
        on_delta: Callable[[str], None] | None = None,
        on_reset: Callable[[], None] | None = None,
    ):
        repair_used = False
        latest_guard: GuardResult | None = None
        allow = self._guard_allow_values(prompt)
        writing_status_emitted = False
        research_activity_seen = False

        def emit_chat_status(text: str) -> None:
            clean_text = str(text or "").strip()
            if not clean_text:
                return
            self._emit(
                "cowork_status",
                {
                    "client_session_id": client_session_id,
                    "mode": "Chat",
                    "text": clean_text,
                },
            )

        def emit_writing_status() -> None:
            nonlocal writing_status_emitted
            if writing_status_emitted or not research_activity_seen:
                return
            writing_status_emitted = True
            emit_chat_status("Writing...")

        def on_research_event(event_type: str, payload: dict) -> None:
            nonlocal research_activity_seen
            if event_type != "tool_execution":
                return
            tool_name = str(payload.get("tool_name") or "")
            arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
            if tool_name == "web_search":
                research_activity_seen = True
                query = str(arguments.get("query") or "").strip()
                if query:
                    emit_chat_status(f"Searching: {query}")
            elif tool_name == "web_fetch":
                research_activity_seen = True
                raw_url = str(arguments.get("url") or "").strip()
                parsed = urlparse(raw_url)
                domain = parsed.netloc or urlparse(f"//{raw_url}").netloc or raw_url
                if domain:
                    emit_chat_status(f"Reading: {domain}")
            elif tool_name.startswith("mcp__"):
                research_activity_seen = True
                server_name, mcp_tool = _parse_mcp_tool_name(tool_name)
                emit_chat_status(f"MCP: {server_name}/{mcp_tool}")
                result_text = str(payload.get("result") or "")
                try:
                    result_payload = json.loads(result_text)
                except json.JSONDecodeError:
                    result_payload = {"status": "error", "error": result_text}
                self._emit_chat_mcp_tool_result(
                    {
                        "client_session_id": client_session_id,
                        "mode": "Chat",
                        "origin": "model",
                        "server": str(result_payload.get("server") or server_name),
                        "tool": str(result_payload.get("tool") or mcp_tool),
                        "arguments": arguments,
                        "read_only": bool(result_payload.get("read_only")),
                        "status": str(result_payload.get("status") or "error"),
                        "result": _compact_mcp_result(result_payload.get("result")),
                        "error": str(result_payload.get("error") or ""),
                        "duration_ms": 0,
                    }
                )

        def on_final_delta(delta: str) -> None:
            if delta:
                emit_writing_status()
            if on_delta:
                on_delta(delta)

        def web_tools_factory(query: str):
            if self.dependencies.chat_web_tools_factory:
                web_tools = _call_chat_web_tools_factory(
                    self.dependencies.chat_web_tools_factory,
                    query,
                    max_fetch=effort_config.research_max_fetch,
                )
            else:
                web_tools = WebResearchTools(
                    self._chat_web_connector(web_settings),
                    max_fetch=effort_config.research_max_fetch,
                    relevance_query=query,
                    playwright_fetch_enabled=self.dependencies.chat_config.playwright_fetch_enabled,
                )
            providers: list[Any] = [web_tools]
            providers.append(self._create_mcp_diagnostics_tool_provider())
            if self.dependencies.chat_config.artifacts_enabled and self._chat_tool_enabled(web_settings, "artifacts", default=True):
                providers.append(ArtifactToolProvider(self._artifact_store(), session_id=client_session_id))
            if self.dependencies.chat_config.code_execution_enabled and self._chat_tool_enabled(web_settings, "code_execution"):
                providers.append(self._create_chat_code_tool_provider())
            if self.dependencies.chat_config.mcp_enabled and self._chat_tool_enabled(web_settings, "mcp"):
                providers.append(self._create_mcp_tool_provider())
            return CompositeToolProvider(providers)

        def on_fallback(model: str, message: str, next_model: str) -> None:
            self._emit(
                "cowork_log",
                {
                    "role": "SYSTEM",
                    "text": f"Model {model} failed ({message}). Trying fallback {next_model}.",
                    "client_session_id": client_session_id,
                    "model": model,
                    "fallback_model": next_model,
                    "mode": "Chat",
                },
            )

        def before_finalize(content: str, tools: Any) -> str | None:
            nonlocal repair_used, latest_guard
            emit_writing_status()
            evidence_corpus = tools.evidence_corpus()
            if not evidence_corpus.strip():
                return None
            guard = validate_answer(
                content,
                evidence_corpus=evidence_corpus,
                sources=tools.sources(),
                allow=allow,
            )
            latest_guard = guard
            if guard.ok or repair_used:
                return None
            repair_used = True
            tools.freeze()
            return (
                "Your answer used values/citations not in the fetched evidence: "
                + "; ".join(guard.violations)
                + ". Rewrite using only fetched evidence already provided in tool results; "
                "keep partial dates partial; fix or remove invalid citations. Do not call web_search or web_fetch again."
            )

        runner = ChatResearchRunner(
            model_factory=lambda model: self._create_chat_model(
                model,
                timeout=self.dependencies.chat_config.model_timeout_seconds,
            ),
            model_candidates=self._model_candidates,
            web_tools_factory=web_tools_factory,
            max_iterations=effort_config.research_max_iterations,
            force_final_answer=True,
            on_fallback=on_fallback,
        )
        result = runner.run(
            prompt=prompt,
            requested_model=requested_model,
            history=recent_history,
            system_prompt=self.dependencies.chat_config.system_prompt,
            generation=effort_config.generation_settings(),
            user_content=user_content,
            extra_system_messages=[
                {
                    "role": "system",
                    "content": route.to_prompt_block(
                        has_web_context=True,
                        search_depth_hint=effort_config.search_depth_hint,
                    ),
                },
                *memory_messages,
                *attachment_messages,
                *vision_messages,
                *mcp_context_messages,
            ],
            before_finalize=before_finalize,
            on_final_delta=on_final_delta,
            on_stream_reset=on_reset,
            on_event=on_research_event,
        )
        if not result.outcome.used_tools:
            return result.outcome.answer, result.used_model, result, latest_guard
        final_guard = validate_answer(
            result.outcome.answer,
            evidence_corpus=result.evidence_corpus,
            sources=result.sources,
            allow=allow,
        )
        latest_guard = final_guard
        answer = (
            final_guard.corrected_answer
            if not final_guard.ok and final_guard.corrected_answer
            else result.outcome.answer
        )
        return answer, result.used_model, result, latest_guard

    def _legacy_web_chat(
        self,
        *,
        prompt: str,
        requested_model: str,
        client_session_id: str,
        route: Any,
        effort_name: str,
        effort_config: Any,
        memory_messages: list[dict[str, str]],
        attachment_messages: list[dict[str, str]],
        vision_messages: list[dict[str, str]],
        mcp_context_messages: list[dict[str, str]],
        recent_history: list[dict[str, str]],
        user_content: Any,
        web_settings: dict[str, str] | None = None,
    ) -> tuple[str, str, WebSearchResponse | None]:
        web_response = self._search_web_for_chat(prompt, route.category, route.needs_web_context, effort_name, web_settings)
        web_prompt = self._format_chat_web_context(web_response)
        web_messages = [{"role": "system", "content": web_prompt}] if web_prompt else []
        messages = [
            {"role": "system", "content": self.dependencies.chat_config.system_prompt},
            {"role": "system", "content": route.to_prompt_block(has_web_context=bool(web_response and web_response.results))},
            *memory_messages,
            *attachment_messages,
            *vision_messages,
            *mcp_context_messages,
            *web_messages,
            *recent_history,
            {"role": "user", "content": user_content},
        ]
        answer, used_model = self._complete_plain_chat_with_fallback(
            messages=messages,
            requested_model=requested_model,
            client_session_id=client_session_id,
            effort_config=effort_config,
        )
        return answer, used_model, web_response

    def _tool_research_enabled(self, model: str) -> bool:
        provider = str(model or "").split(":", 1)[0].casefold()
        enabled = {item.casefold() for item in self.dependencies.chat_config.tool_research_providers}
        return provider in enabled

    def _route_chat_model_if_auto(self, model: str, prompt: str, attachments: list[dict[str, Any]]) -> str:
        if str(model or "").strip() != "auto":
            return model
        local_models = [
            {"id": item, "strengths": ["chat"], "context_window_tokens": 0}
            for item in self._available_model_names()
        ]
        catalog_models = [
            metadata
            for metadata in (catalog_model_metadata(item) for item in catalog_model_ids())
            if metadata
        ]
        routed = route_model(
            prompt,
            attachments,
            [*local_models, *catalog_models],
            requested_model="auto",
            performance_profile=self._load_model_performance_profile(),
        )
        selected = routed.model_id or self._normalize_model_name(self.dependencies.default_model)
        route_payload = {
            "client_session_id": str(getattr(self._worker_context, "client_session_id", "") or ""),
            "mode": "Chat",
            "model": selected,
            "reason": routed.reason,
        }
        self._emit("chat_model_route", route_payload)
        self._emit(
            "cowork_log",
            {
                "role": "SYSTEM",
                "text": f"Auto model routed to {selected} ({routed.reason}).",
                "client_session_id": route_payload["client_session_id"],
                "model": selected,
                "mode": "Chat",
            },
        )
        return selected

    def _load_model_performance_profile(self) -> dict[str, Any]:
        roots = [
            Path(os.environ.get("COWORK_USER_DATA_DIR") or self.dependencies.app_root) / "work_logs" / PROFILE_FILENAME,
            self.dependencies.app_root / "work_logs" / PROFILE_FILENAME,
        ]
        for path in roots:
            profile = load_model_performance_profile(path)
            if profile.get("models"):
                return profile
        return {"schema_version": 1, "models": {}}

    def _guard_allow_values(self, prompt: str) -> tuple[str, ...]:
        today = date.today()
        values = {
            str(today.year),
            str(today.year + 543),
            str(today.day),
            f"{today.day:02d}",
            str(today.month),
            f"{today.month:02d}",
            today.isoformat(),
        }
        values.update(match.group(0) for match in re.finditer(r"(?<![\d.])\d[\d,]*(?:\.\d+)?(?![\d.])", str(prompt or "")))
        return tuple(sorted(values))

    def _search_web_for_chat(self, prompt: str, route_category: str, needs_web_context: bool, effort_name: str, web_settings: dict[str, str] | None = None) -> WebSearchResponse | None:
        if self._web_mode(web_settings) == "off":
            return None
        if not needs_web_context:
            return None
        max_results_by_effort = {"Low": 2, "Medium": 4, "High": DEFAULT_WEB_SEARCH_MAX_RESULTS}
        max_results = max_results_by_effort.get(effort_name, 4)
        search_provider_override = self._search_provider(web_settings)
        searcher = self.dependencies.web_searcher if search_provider_override == "auto" else None
        if searcher is None:
            searcher = self._chat_web_connector(web_settings).search
        try:
            return searcher(prompt, max_results=max_results)
        except TypeError:
            return searcher(prompt)
        except Exception as exc:
            return WebSearchResponse(query=prompt, results=[], error=str(exc).strip() or "Web search failed.")

    def _format_chat_web_context(self, response: WebSearchResponse | None) -> str:
        if response is None:
            return ""
        usable_results = [result for result in response.results if getattr(result, "source_type", "") != "fetch-blocked"]
        display_results = usable_results if usable_results else response.results
        lines = [
            "## Chat Web Context",
            f"Search query: {response.query}",
            "Use these web results only for relevant current or external facts. First analyze the evidence across sources, then synthesize a direct answer. Cite labels like [web:1] inline and end with a Sources section listing each used URL.",
            "For Thai prompts, the search connector may use English/international query variants; answer in Thai unless the user asks otherwise, while preserving original source terms when useful.",
            "Only state exact dates, prices, version numbers, or table values when they appear in extracted evidence. Do not infer missing values from page titles, source hints, or page structure.",
            "Partial dates with only a day and month may be repeated as partial dates, but do not add a year or convert between BE/CE unless that year appears in extracted evidence.",
            "Do not mention unusable sources to the user when at least one usable source exists; answer from usable sources and say only what exact values were or were not extracted.",
            "If searched sources identify where the answer should be but extracted evidence lacks the exact value, say the exact value was not extracted and name the source to check.",
        ]
        source_preferences = build_research_plan(response.query).source_preferences
        if source_preferences:
            lines.append("")
            lines.append("### Source Strategy")
            lines.append("Prefer sources that match the question type; do not treat source hints as evidence unless extracted evidence is present.")
            for preference in source_preferences:
                source_type = str(preference.get("source_type") or "source").strip()
                hint = str(preference.get("hint") or "").strip()
                lines.append(f"- {source_type}: {hint}" if hint else f"- {source_type}")
        if response.analysis and len(display_results) == len(response.results):
            lines.append("")
            lines.append("### Source Analysis")
            lines.append(response.analysis)
        if response.error:
            lines.append(f"Search error: {response.error}")
            lines.append("If current facts are required, explain that live/source lookup failed and say what source is needed.")
        if not display_results:
            return "\n".join(lines) if response.error else ""
        for index, result in enumerate(display_results, start=1):
            lines.append("")
            lines.append(f"[web:{index}] {result.title}")
            lines.append(f"URL: {result.url}")
            if result.snippet:
                lines.append(f"Snippet: {result.snippet}")
            if getattr(result, "evidence", ""):
                lines.append(f"Extracted evidence: {result.evidence}")
            lines.append(f"Source type: {getattr(result, 'source_type', 'search-result')}; quality score: {getattr(result, 'quality_score', 0)}")
        return "\n".join(lines)

    def _complete_plain_chat_with_fallback(
        self,
        *,
        messages: list[dict[str, str]],
        requested_model: str,
        client_session_id: str,
        effort_config: Any,
        on_delta: Callable[[str], None] | None = None,
    ) -> tuple[str, str]:
        candidates = self._model_candidates(requested_model)

        def attempt(model: str) -> str:
            chat_model = self._create_chat_model(
                model,
                timeout=self.dependencies.chat_config.model_timeout_seconds,
            )
            if on_delta and hasattr(chat_model, "stream_complete"):
                response = chat_model.stream_complete(
                    messages,
                    tools=[],
                    generation=effort_config.generation_settings(),
                    on_delta=on_delta,
                )
            else:
                response = chat_model.complete(messages, tools=[], generation=effort_config.generation_settings())
            answer = str(response.get("content") or "").strip()
            if not answer:
                raise RuntimeError("Chat model returned an empty response.")
            return answer

        def on_fallback(model: str, message: str, next_model: str) -> None:
            self._emit(
                "cowork_log",
                {
                    "role": "SYSTEM",
                    "text": f"Model {model} failed ({message}). Trying fallback {next_model}.",
                    "client_session_id": client_session_id,
                    "model": model,
                    "fallback_model": next_model,
                    "mode": "Chat",
                },
            )

        return run_with_model_candidates(
            candidates=candidates,
            attempt=attempt,
            on_fallback=on_fallback,
            no_candidate_error="No chat model candidate is available.",
        )

    def _normalize_chat_attachments(self, raw_attachments: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_attachments, list):
            return []
        attachments: list[dict[str, Any]] = []
        for item in raw_attachments[:MAX_CHAT_ATTACHMENTS]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("name") or "attached-context").strip()[:160]
            source = str(item.get("source") or "user-attached").strip()[:80]
            kind = str(item.get("kind") or "text").strip()[:40] or "text"
            mime = str(item.get("mime") or item.get("type") or "").strip()[:120]
            content = str(item.get("content") or "").strip()
            attachment: dict[str, Any] = {
                "label": label or "attached-context",
                "source": source or "user-attached",
                "kind": kind,
                "content": content[:MAX_CHAT_ATTACHMENT_CHARS],
            }
            data_url = str(item.get("data_url") or item.get("dataUrl") or "").strip()
            is_image = kind.casefold() == "image" or mime.casefold().startswith("image/")
            if is_image:
                attachment["kind"] = "image"
                attachment["mime"] = mime if mime.casefold().startswith("image/") else "image/png"
                normalized_data_url, image_size = self._normalize_image_data_url(data_url, attachment["mime"])
                attachment["size"] = image_size
                if normalized_data_url:
                    attachment["data_url"] = normalized_data_url
                else:
                    attachment["image_error"] = "Image is too large or missing readable image data."
                if not attachment["content"]:
                    attachment["content"] = (
                        f"Image file {attachment['label']} is attached. "
                        f"Type: {attachment['mime']}; size: {image_size} bytes."
                    )
            if not attachment["content"] and not attachment.get("data_url"):
                continue
            attachments.append(attachment)
        return attachments

    def _format_chat_attachments(
        self,
        attachments: list[dict[str, Any]],
        model: str = "",
        *,
        context_name: str = "Chat",
    ) -> str:
        if not attachments:
            return ""
        vision_enabled = self._model_can_receive_images(model)
        lines = [
            f"## {context_name} Attached Context",
            f"The user explicitly attached the following context to this {context_name} conversation. Use it only when relevant, cite source labels like [1], and say when the attached context is insufficient.",
            "If you use any attached source, cite the exact source label inline. End with a Sources section listing each used label and attachment name, for example: Sources: [1] notes.txt.",
        ]
        for index, attachment in enumerate(attachments, start=1):
            lines.append("")
            lines.append(f"[{index}] {attachment['label']} ({attachment['source']}, {attachment['kind']})")
            if attachment.get("kind") == "image" and attachment.get("data_url") and vision_enabled:
                lines.append("This image is sent to the selected vision-capable model as an image payload.")
                continue
            if attachment.get("kind") == "image" and attachment.get("data_url") and not vision_enabled:
                lines.append("The selected model cannot view images directly; only this metadata is available.")
            if attachment.get("image_error"):
                lines.append(str(attachment["image_error"]))
            lines.append("```text")
            lines.append(attachment["content"])
            lines.append("```")
        return "\n".join(lines)

    def _build_chat_user_content(self, prompt: str, attachments: list[dict[str, Any]], model: str) -> Any:
        image_urls = [
            str(attachment.get("data_url") or "")
            for attachment in attachments
            if attachment.get("kind") == "image" and attachment.get("data_url")
        ]
        if not image_urls or not self._model_can_receive_images(model):
            return prompt
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for data_url in image_urls[:MAX_CHAT_ATTACHMENTS]:
            content.append({"type": "image_url", "image_url": {"url": data_url}})
        return content

    def _run_vision_assist(
        self,
        *,
        prompt: str,
        attachments: list[dict[str, Any]],
        primary_model: str,
        settings: dict[str, Any] | None,
        client_session_id: str,
        mode: str,
    ) -> dict[str, Any]:
        decision = select_vision_assist(
            attachments,
            settings,
            supports_vision=self._model_can_receive_images,
        )
        result: dict[str, Any] = {
            "attempted": False,
            "completed": False,
            "helper_model": decision.helper_model,
            "attachment_model": primary_model,
            "send_images_to_primary": True,
            "evidence_message": "",
        }
        if not decision.enabled:
            return result

        helper_metadata = catalog_model_metadata(decision.helper_model)
        helper_label = str(helper_metadata.get("label") or decision.helper_model)
        self._emit(
            "cowork_status",
            {
                "client_session_id": client_session_id,
                "mode": mode,
                "text": f"Analyzing image with {helper_label}...",
            },
        )
        result["attempted"] = True
        started = time.perf_counter()
        try:
            helper_model = self._create_chat_model(
                decision.helper_model,
                timeout=self.dependencies.chat_config.model_timeout_seconds,
            )
            helper_user_content = self._build_chat_user_content(
                "Analyze the attached image evidence for this user request.\n\n"
                f"User request:\n{prompt}",
                attachments,
                decision.helper_model,
            )
            response = helper_model.complete(
                [
                    {"role": "system", "content": vision_evidence_system_prompt()},
                    {"role": "user", "content": helper_user_content},
                ],
                tools=[],
                generation={"temperature": 0, "max_tokens": 1024},
            )
            evidence = str(response.get("content") or "").strip()
            if not evidence:
                raise RuntimeError("Vision helper returned an empty response.")
            duration_ms = int(max(0, (time.perf_counter() - started) * 1000))
            result.update(
                {
                    "completed": True,
                    "attachment_model": decision.helper_model,
                    "send_images_to_primary": False,
                    "evidence_message": build_vision_evidence_message(evidence, decision.helper_model),
                }
            )
            record_cowork_event(
                "vision_assist",
                {
                    "client_session_id": client_session_id,
                    "mode": mode,
                    "helper_model": decision.helper_model,
                    "status": "completed",
                    "duration_ms": duration_ms,
                },
            )
            self._emit(
                "cowork_status",
                {
                    "client_session_id": client_session_id,
                    "mode": mode,
                    "text": "Writing...",
                },
            )
            return result
        except Exception:
            duration_ms = int(max(0, (time.perf_counter() - started) * 1000))
            primary_can_receive_images = self._model_can_receive_images(primary_model)
            result.update(
                {
                    "attachment_model": primary_model,
                    "send_images_to_primary": primary_can_receive_images,
                    "evidence_message": "" if primary_can_receive_images else vision_assist_unavailable_message(),
                }
            )
            record_cowork_event(
                "vision_assist",
                {
                    "client_session_id": client_session_id,
                    "mode": mode,
                    "helper_model": decision.helper_model,
                    "status": "unavailable",
                    "duration_ms": duration_ms,
                },
            )
            self._emit(
                "cowork_status",
                {
                    "client_session_id": client_session_id,
                    "mode": mode,
                    "text": "Vision assist unavailable. Continuing...",
                },
            )
            return result

    def _model_can_receive_images(self, model: str) -> bool:
        normalized = self._normalize_model_name(model)
        provider = normalized.split(":", 1)[0].casefold()
        if provider not in {"openai", "zai", "deepseek"}:
            return False
        return catalog_model_supports_vision(normalized)

    def _normalize_image_data_url(self, data_url: str, fallback_mime: str) -> tuple[str, int]:
        raw = str(data_url or "").strip()
        if not raw.startswith("data:") or ";base64," not in raw:
            return "", 0
        header, encoded = raw.split(";base64,", 1)
        mime = header[5:].strip() or fallback_mime or "image/png"
        if not mime.casefold().startswith("image/"):
            return "", 0
        compact = re.sub(r"\s+", "", encoded)
        try:
            byte_count = len(base64.b64decode(compact, validate=True))
        except Exception:
            return "", 0
        if byte_count <= 0 or byte_count > MAX_CHAT_IMAGE_BYTES:
            return "", byte_count
        return f"data:{mime};base64,{compact}", byte_count

    def _normalize_chat_web_settings(self, raw_settings: Any) -> dict[str, str]:
        raw = raw_settings if isinstance(raw_settings, dict) else {}
        web_mode = str(raw.get("web_mode") or raw.get("webMode") or "auto").strip().casefold()
        search_provider = str(raw.get("search_provider") or raw.get("searchProvider") or "auto").strip().casefold()
        artifacts = str(raw.get("artifacts") or "on").strip().casefold()
        code_execution = str(raw.get("code_execution") or raw.get("codeExecution") or "off").strip().casefold()
        mcp = str(raw.get("mcp") or "off").strip().casefold()
        return {
            "web_mode": web_mode if web_mode in {"auto", "off"} else "auto",
            "search_provider": search_provider if search_provider in {"auto", "brave", "scrape"} else "auto",
            "artifacts": artifacts if artifacts in {"on", "off"} else "on",
            "code_execution": code_execution if code_execution in {"on", "off"} else "off",
            "mcp": mcp if mcp in {"on", "off"} else "off",
        }

    def _web_mode(self, web_settings: dict[str, str] | None) -> str:
        return self._normalize_chat_web_settings(web_settings).get("web_mode", "auto")

    def _search_provider(self, web_settings: dict[str, str] | None) -> str:
        return self._normalize_chat_web_settings(web_settings).get("search_provider", "auto")

    def _chat_tool_enabled(self, web_settings: dict[str, str] | None, key: str, *, default: bool = False) -> bool:
        settings = self._normalize_chat_web_settings(web_settings)
        fallback = "on" if default else "off"
        return str(settings.get(key, fallback)).casefold() == "on"

    def _format_chat_mcp_live_context(
        self,
        prompt: str,
        web_settings: dict[str, str] | None,
        *,
        client_session_id: str,
    ) -> str:
        del client_session_id
        if not self.dependencies.chat_config.mcp_enabled:
            return ""
        if not self._chat_tool_enabled(web_settings, "mcp"):
            return ""
        if not _looks_like_roblox_workspace_inspection(prompt):
            return ""
        clients, statuses = self._create_mcp_clients_cached(self._mcp_connector_registry().list_connectors())
        connected = {str(item.get("name") or "") for item in statuses if str(item.get("status") or "") == "connected"}
        roblox_server = next(
            (
                name
                for name in clients
                if name in connected
                and ("roblox" in name.casefold() or "robloxstudio" in name.casefold())
            ),
            "",
        )
        if not roblox_server:
            return ""
        provider = McpToolProvider({roblox_server: clients[roblox_server]}, approval_callback=lambda _proposal: False)

        def call_json(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            raw = provider.dispatch(mcp_tool_name(roblox_server, tool_name), arguments)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            if payload.get("status") != "ok":
                return {}
            parsed = _first_json_object_from_mcp_result(payload.get("result"))
            return parsed if isinstance(parsed, dict) else {}

        workspace = call_json("get_instance_children", {"instancePath": "Workspace"})
        children = workspace.get("children") if isinstance(workspace.get("children"), list) else []
        physical_children = [
            child
            for child in children
            if isinstance(child, dict)
            and str(child.get("className") or "") in _ROBLOX_PHYSICAL_WORKSPACE_CLASSES
        ]
        if not children:
            return ""

        lines = [
            "## Live Roblox Workspace Context",
            "This read-only context was fetched from the connected Roblox Studio MCP server before answering. Use it to answer questions about the current Workspace state instead of listing available MCP tools.",
            f"Connector: {roblox_server}",
            f"Workspace direct child count: {len(children)}",
            f"Direct physical object count: {len(physical_children)}",
        ]
        if physical_children:
            lines.append("")
            lines.append("### Direct physical Workspace children")
        for child in physical_children[:12]:
            raw_path = str(child.get("path") or "")
            instance_path = _roblox_instance_path_for_tool(raw_path, str(child.get("name") or ""))
            props_payload = call_json("get_instance_properties", {"instancePath": instance_path, "excludeSource": True})
            props = props_payload.get("properties") if isinstance(props_payload.get("properties"), dict) else {}
            name = str(props.get("Name") or child.get("name") or instance_path)
            class_name = str(props.get("ClassName") or child.get("className") or "")
            details = _format_roblox_property_summary(props)
            lines.append(f"- {name} ({class_name}; path: {instance_path}){details}")
        if len(physical_children) > 12:
            lines.append(f"- ... {len(physical_children) - 12} more direct physical children omitted from context.")
        if children and not physical_children:
            lines.append("")
            lines.append("No direct physical BasePart-like children were found under Workspace.")
        return "\n".join(lines)

    def _chat_web_connector(self, web_settings: dict[str, str] | None = None) -> ChatWebConnector:
        requested_provider = self._search_provider(web_settings)
        if requested_provider == "scrape":
            return ChatWebConnector(search_provider=None)
        config = self.dependencies.chat_config
        if requested_provider == "brave":
            config = replace(config, search_api_provider="brave")
        provider = get_search_provider(config)
        return ChatWebConnector(search_provider=provider)

    def _resolve_search_provider_label(self, web_settings: dict[str, str] | None) -> str:
        # Mirrors _chat_web_connector's own provider resolution exactly (same
        # config replace + get_search_provider call) instead of re-reading env,
        # so diagnostics/telemetry can never disagree with what the request itself
        # would use for a search.
        if self._web_mode(web_settings) == "off":
            # No search runs at all when web is off — don't claim a provider the
            # request will never reach.
            return "off"
        requested_provider = self._search_provider(web_settings)
        if requested_provider == "scrape":
            return "scrape_fallback"
        config = self.dependencies.chat_config
        if requested_provider == "brave":
            config = replace(config, search_api_provider="brave")
        return "brave_api" if get_search_provider(config) is not None else "scrape_fallback"

    def _chat_memory_store(self) -> ChatMemoryStore:
        root = self.dependencies.chat_memory_root
        if root is None:
            root = Path(os.environ.get("COWORK_USER_DATA_DIR") or self.dependencies.app_root)
        return ChatMemoryStore(root, embedder=self._chat_memory_embedder_for_store())

    def _chat_memory_embedder_for_store(self) -> Callable[[str], list[float]] | None:
        if not self.dependencies.chat_config.semantic_memory_enabled:
            return None
        if self._chat_memory_embedder_initialized:
            return self._chat_memory_embedder
        self._chat_memory_embedder_initialized = True
        factory = self.dependencies.chat_memory_embedder_factory
        if factory is None:
            try:
                from .chat_embeddings import create_local_embedder
            except ImportError:
                from chat_embeddings import create_local_embedder

            factory = create_local_embedder
        cache_dir = self._runtime_root() / "chat_memory" / "embeddings"
        try:
            self._chat_memory_embedder = factory(cache_dir=cache_dir)
        except Exception:
            self._chat_memory_embedder = None
        return self._chat_memory_embedder

    def _emit_chat_memory_state(self) -> None:
        self._emit("chat_memory_state", {"entries": self._chat_memory_store().list_memories()})

    def _runtime_root(self) -> Path:
        return Path(os.environ.get("COWORK_USER_DATA_DIR") or self.dependencies.app_root)

    def _artifact_store(self) -> ArtifactStore:
        return ArtifactStore(self._runtime_root())

    def _mcp_connector_registry(self) -> McpConnectorRegistry:
        return McpConnectorRegistry(self._runtime_root())

    def _emit_chat_artifacts_state(self) -> None:
        self._emit("chat_artifacts_state", {"artifacts": self._artifact_store().list_artifacts()})

    def _emit_chat_quality_eval_state(self, results: list[dict[str, Any]] | None = None) -> None:
        cases = quality_eval_cases()
        payload: dict[str, Any] = {
            "cases": cases,
            "count": len(cases),
            "source_profile": self._chat_web_source_profile(),
            "text_diagnostics": build_mojibake_diagnostics(self._runtime_root()),
        }
        if results is not None:
            payload["snapshot"] = run_quality_eval_snapshot(results)
        self._emit("chat_quality_eval_state", payload)

    def _chat_web_source_profile(self) -> dict[str, Any]:
        path = self._runtime_root() / "work_logs" / SOURCE_PROFILE_FILENAME
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"schema_version": 1, "domains": {}}
        if not isinstance(payload, dict) or not isinstance(payload.get("domains"), dict):
            return {"schema_version": 1, "domains": {}}
        return payload

    def _run_chat_quality(self, payload: dict[str, Any]) -> None:
        live = bool(payload.get("live"))
        if not live:
            self._emit_chat_quality_eval_state(results=payload.get("results") if isinstance(payload, dict) else None)
            return
        if not bool(payload.get("confirmed")):
            cases = quality_eval_cases()
            self._emit(
                "chat_quality_eval_state",
                {
                    "cases": cases,
                    "count": len(cases),
                    "requires_confirmation": True,
                    "message": "Live quality evaluation uses credits by calling selected models. Confirm before running.",
                },
            )
            return
        models = [str(item).strip() for item in payload.get("models", []) if str(item).strip()] if isinstance(payload.get("models"), list) else []
        categories = [str(item).strip() for item in payload.get("categories", []) if str(item).strip()] if isinstance(payload.get("categories"), list) else []
        tool_research_routes = None
        if isinstance(payload.get("tool_research_routes"), list):
            parsed_routes = tuple(str(item).strip() for item in payload.get("tool_research_routes", []) if str(item).strip())
            tool_research_routes = parsed_routes or None
        if not models:
            raise ValueError("Live quality evaluation requires at least one model.")
        runner = self.dependencies.chat_quality_live_runner
        report_writer = self.dependencies.chat_quality_report_writer
        if runner is None or report_writer is None:
            try:
                from .chat_quality_runner import run_chat_once, run_quality_eval_live, save_quality_report
            except ImportError:
                from chat_quality_runner import run_chat_once, run_quality_eval_live, save_quality_report

            runner = lambda **kwargs: run_quality_eval_live(run_chat_once=run_chat_once, **kwargs)
            report_writer = save_quality_report
        matrix = runner(
            models=models,
            categories=categories or None,
            effort=self.dependencies.chat_config.normalize_effort(payload.get("effort") or "Medium"),
            web_settings=payload.get("web_settings") if isinstance(payload.get("web_settings"), dict) else {"webMode": "auto", "searchProvider": "auto"},
            tool_research_routes=tool_research_routes,
        )
        reports = report_writer(matrix, output_dir=self._runtime_root() / "work_logs")
        cases = quality_eval_cases()
        self._emit(
            "chat_quality_eval_state",
            {
                "cases": cases,
                "count": len(cases),
                "live_matrix": matrix,
                "reports": reports,
            },
        )

    def _emit_chat_connectors_state(self) -> None:
        connectors = self._mcp_connector_registry().list_connectors()
        _clients, statuses = self._create_mcp_clients_cached(connectors)
        self._emit(
            "chat_connectors_state",
            {
                "connectors": connectors,
                "statuses": statuses,
                "mcp_sdk_available": mcp_sdk_available(),
                "enabled": self.dependencies.chat_config.mcp_enabled,
            },
        )

    def _test_chat_connector(self, payload: dict[str, Any]) -> None:
        raw_connector = payload.get("connector")
        if not isinstance(raw_connector, dict):
            self._emit(
                "chat_connector_test_result",
                {"status": "error", "errors": ["connector payload is required."]},
            )
            return
        validation = validate_connector(raw_connector)
        connector = validation["connector"]
        errors = validation["errors"]
        if errors:
            self._emit(
                "chat_connector_test_result",
                {
                    "status": "error",
                    "connector": connector,
                    "errors": errors,
                    "statuses": [{"name": connector["name"], "status": "error", "error": "; ".join(errors)}],
                    "mcp_sdk_available": mcp_sdk_available(),
                },
            )
            return
        _clients, statuses = self._create_mcp_clients_cached([{**connector, "enabled": True}], force=True)
        first_status = statuses[0] if statuses else {"status": "unknown"}
        self._emit(
            "chat_connector_test_result",
            {
                "status": str(first_status.get("status") or "unknown"),
                "connector": connector,
                "errors": [],
                "statuses": statuses,
                "mcp_sdk_available": mcp_sdk_available(),
            },
        )

    def _discover_chat_connector(self, payload: dict[str, Any]) -> None:
        target = str(payload.get("target") or "").strip().casefold()
        if "roblox" not in target:
            self._emit(
                "chat_connector_discovery_result",
                {
                    "target": target or "unknown",
                    "found": False,
                    "configured": False,
                    "preset": None,
                    "statuses": [],
                    "message": "No connector discovery preset is available for this target.",
                },
            )
            return

        connectors = self._mcp_connector_registry().list_connectors()
        existing = next(
            (
                item
                for item in connectors
                if "roblox" in " ".join(str(item.get(key) or "") for key in ("name", "command", "url")).casefold()
            ),
            None,
        )
        preset = existing or {
            "name": "roblox",
            "transport": "stdio",
            "command": "roblox-mcp",
            "url": "",
            "enabled": False,
        }
        validation = validate_connector(preset)
        statuses: list[dict[str, Any]] = []
        if existing:
            _clients, statuses = self._create_mcp_clients_cached([existing], force=True)
        found = bool(statuses and statuses[0].get("status") == "connected")
        self._emit(
            "chat_connector_discovery_result",
            {
                "target": "roblox",
                "found": found,
                "configured": bool(existing),
                "preset": validation["connector"],
                "errors": validation["errors"],
                "statuses": statuses,
                "mcp_sdk_available": mcp_sdk_available(),
                "message": (
                    "Roblox MCP connector is configured."
                    if existing
                    else "No Roblox MCP connector is configured. Add the disabled preset, then edit the command or url before enabling it."
                ),
            },
        )

    def _run_chat_mcp_tool_async(self, payload: dict[str, Any]) -> None:
        # A manual WRITE tool run blocks inside _request_approval waiting for the
        # user's answer_question line. The stdin loop that delivers that line is
        # single-threaded, so the run MUST happen on a worker thread (same pattern
        # as _send_cowork) or every manual write run deadlocks into timeout-deny.
        worker = threading.Thread(target=self._run_chat_mcp_tool_worker, args=(payload,), daemon=True)
        self._workers.append(worker)
        worker.start()

    def _run_chat_mcp_tool_worker(self, payload: dict[str, Any]) -> None:
        try:
            self._run_chat_mcp_tool(payload)
        except Exception as exc:
            self._emit_backend_error(str(exc).strip() or "MCP tool run failed.")

    def _run_chat_mcp_tool(self, payload: dict[str, Any]) -> None:
        client_session_id = str(payload.get("client_session_id") or payload.get("clientSessionId") or "").strip()
        server_name = str(payload.get("server") or "").strip()
        tool_name = str(payload.get("tool") or "").strip()
        arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
        origin = str(payload.get("origin") or "manual").strip() or "manual"
        if not client_session_id:
            raise ValueError("chat_mcp_tool_run requires client_session_id.")
        if not server_name or not tool_name:
            raise ValueError("chat_mcp_tool_run requires server and tool.")

        old_session = getattr(self._worker_context, "client_session_id", "")
        old_mode = getattr(self._worker_context, "mode", "")
        self._worker_context.client_session_id = client_session_id
        self._worker_context.mode = "Chat"
        started = time.perf_counter()
        try:
            clients, _statuses = self._create_mcp_clients_cached(self._mcp_connector_registry().list_connectors())
            provider = McpToolProvider(clients, approval_callback=self._approve_mcp_tool)
            namespaced = mcp_tool_name(server_name, tool_name)
            metadata = provider.route_metadata(namespaced) or {"server": server_name, "tool": tool_name, "read_only": False}
            raw_result = provider.dispatch(namespaced, arguments)
            try:
                result_payload = json.loads(raw_result)
            except json.JSONDecodeError:
                result_payload = {"status": "error", "error": raw_result}
            status = str(result_payload.get("status") or "error")
            self._emit_chat_mcp_tool_result(
                {
                    "client_session_id": client_session_id,
                    "mode": "Chat",
                    "origin": origin,
                    "server": str(metadata.get("server") or server_name),
                    "tool": str(metadata.get("tool") or tool_name),
                    "arguments": arguments,
                    "read_only": bool(metadata.get("read_only")),
                    "status": status,
                    "result": _compact_mcp_result(result_payload.get("result")),
                    "error": str(result_payload.get("error") or ""),
                    "duration_ms": int(max(0, (time.perf_counter() - started) * 1000)),
                }
            )
        finally:
            self._worker_context.client_session_id = old_session
            self._worker_context.mode = old_mode

    def _emit_chat_mcp_tool_result(self, payload: dict[str, Any]) -> None:
        self._emit("chat_mcp_tool_result", payload)

    def _capture_chat_artifacts(
        self,
        answer: str,
        client_session_id: str,
        web_settings: dict[str, str] | None,
    ) -> list[dict[str, Any]]:
        if not self.dependencies.chat_config.artifacts_enabled:
            return []
        if not self._chat_tool_enabled(web_settings, "artifacts", default=True):
            return []
        store = self._artifact_store()
        created: list[dict[str, Any]] = []
        for candidate in detect_artifacts(answer):
            created.append(
                store.create_artifact(
                    candidate["type"],
                    candidate["title"],
                    candidate["content"],
                    session_id=client_session_id,
                )
            )
        if created:
            self._emit_chat_artifacts_state()
        return created

    def _emit_api_keys_loaded(self, **extra: Any) -> None:
        self._emit(
            "api_keys_loaded",
            {
                "localAiBaseUrl": self.dependencies.base_url,
                "hasLocalAiApiKey": bool(self.dependencies.api_key),
                "providers": provider_statuses(self._runtime_root()),
                "search": self._search_capabilities(),
                "catalog_source_date": CATALOG_SOURCE_DATE,
                **extra,
            },
        )

    def _search_capabilities(self) -> dict[str, Any]:
        has_brave_key = bool(str(self.dependencies.chat_config.search_api_key or "").strip())
        return {
            "web_modes": ["auto", "off"],
            "default_provider": str(self.dependencies.chat_config.search_api_provider or "brave"),
            "api_key_configured": has_brave_key,
            "providers": [
                {"id": "auto", "label": "Auto", "available": True},
                {"id": "brave", "label": "Brave", "available": has_brave_key},
                {"id": "scrape", "label": "Basic scrape", "available": True},
            ],
        }

    def _model_candidates(self, requested_model: str) -> list[str]:
        requested = self._normalize_model_name(requested_model)
        if not requested.startswith("local:"):
            return [requested]
        candidates = [requested]
        available = set(self._available_model_names())
        for fallback_model in self.dependencies.fallback_models:
            normalized = self._normalize_model_name(fallback_model)
            if normalized == requested or normalized in candidates:
                continue
            if available and normalized not in available:
                continue
            candidates.append(normalized)
        return candidates

    def _should_run_tool_research(self, route: Any, model: str, web_settings: dict[str, str] | None = None) -> bool:
        if self._web_mode(web_settings) == "off":
            return False
        if not self._tool_research_enabled(model):
            return False
        category = getattr(route, "category", "")
        if category == "memory":
            return False
        # Toggle bypasses: tools the user explicitly switched ON for this request
        # must stay reachable regardless of route — the router's keyword categories
        # cannot see every intent (e.g. "compute 17!" has no code/mcp keyword). The
        # "mcp" route category catches keyword-y prompts; these bypasses catch the
        # rest. Note: web_mode "off" above still wins — Off means every research
        # tool is off for that request (documented in the composer UI).
        if self.dependencies.chat_config.mcp_enabled and self._chat_tool_enabled(web_settings, "mcp"):
            return True
        if self.dependencies.chat_config.code_execution_enabled and self._chat_tool_enabled(web_settings, "code_execution"):
            return True
        allowed_routes = self.dependencies.chat_config.tool_research_routes
        if allowed_routes is not None:
            return category in allowed_routes
        return True

    def _available_model_names(self) -> list[str]:
        model_lister = self.dependencies.model_lister or self._default_model_lister
        try:
            return [self._normalize_model_name(model) for model in model_lister()]
        except Exception:
            return []

    def _normalize_model_name(self, model: str) -> str:
        normalized = str(model or "").strip()
        if normalized == "auto":
            return "auto"
        return normalized if normalized.startswith(("local:", "openai:", "deepseek:", "zai:", "gemini:")) else f"local:{normalized}"

    def _normalize_mode(self, mode: Any) -> str:
        normalized = str(mode or "").strip()
        return normalized if normalized in {"Chat", "Cowork", "Code"} else "Cowork"

    def _create_agent(self, model: str):
        if self.dependencies.agent_factory:
            return self.dependencies.agent_factory(model)
        workspace = self.dependencies.workspace.resolve()
        chat_model = self._create_chat_model(model)
        tools = self._create_workspace_tools(workspace)
        return CoworkAgent(
            model=chat_model,
            model_name=model,
            workspace=workspace,
            tools=tools,
            recorder=JsonlSessionRecorder(),
        )

    def _create_chat_model(self, model: str, *, timeout: float | None = None):
        timeout = timeout if timeout and timeout > 0 else _default_model_timeout()
        provider = model.split(":", 1)[0] if ":" in model else "local"
        if provider == "local":
            return self._build_chat_model(
                base_url=self.dependencies.base_url,
                api_key=self.dependencies.api_key,
                model=model,
                extra_body=None,
                timeout=timeout,
            )
        if provider == "zai":
            api_key = read_provider_api_key(self._runtime_root(), "zai")
            if not api_key:
                raise RuntimeError("Z.ai API key is not configured.")
            return self._build_chat_model(
                base_url="https://api.z.ai/api/paas/v4",
                api_key=api_key,
                model=model,
                extra_body={"thinking": {"type": "disabled"}},
                timeout=timeout,
            )
        if provider == "openai":
            api_key = read_provider_api_key(self._runtime_root(), "openai")
            if not api_key:
                raise RuntimeError("OpenAI API key is not configured.")
            return self._build_chat_model(
                base_url="https://api.openai.com/v1",
                api_key=api_key,
                model=model,
                extra_body=None,
                timeout=timeout,
            )
        if provider == "deepseek":
            api_key = read_provider_api_key(self._runtime_root(), "deepseek")
            if not api_key:
                raise RuntimeError("DeepSeek API key is not configured.")
            return self._build_chat_model(
                base_url="https://api.deepseek.com",
                api_key=api_key,
                model=model,
                extra_body=None,
                timeout=timeout,
            )
        raise RuntimeError(f"Provider runtime is not implemented for {provider}.")

    def _build_chat_model(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        extra_body: dict[str, Any] | None,
        timeout: float | None = None,
    ):
        timeout = timeout if timeout and timeout > 0 else _default_model_timeout()
        if self.dependencies.chat_model_factory:
            return self.dependencies.chat_model_factory(
                base_url=base_url,
                api_key=api_key,
                model=model,
                extra_body=extra_body,
                timeout=timeout,
            )
        return OpenAIChatModel(base_url, api_key, model, extra_body=extra_body, timeout=timeout)

    def _default_model_lister(self) -> list[str]:
        return fetch_local_ai_models(self.dependencies.base_url, self.dependencies.api_key)

    def _create_workspace_tools(self, workspace: Path | None = None):
        root = (workspace or self.dependencies.workspace).resolve()
        if self.dependencies.workspace_tools_factory:
            return self.dependencies.workspace_tools_factory(root)
        return WorkspaceTools(
            root,
            approve_write=self._approve_write,
            approve_command=self._approve_command,
            audit_sink=record_cowork_event,
        )

    def _set_workspace(self, payload: dict[str, Any]) -> None:
        raw_path = str(payload.get("path") or "").strip()
        workspace = Path(raw_path).expanduser().resolve()
        if not raw_path or not workspace.is_dir():
            raise ValueError(f"Workspace directory does not exist: {raw_path or '(empty)'}")
        self.dependencies.workspace = workspace
        self._emit("workspace_changed", {"path": str(workspace)})

    def _workspace_action(self, payload: dict[str, Any]) -> None:
        request_id = str(payload.get("request_id") or payload.get("requestId") or "").strip()
        action = str(payload.get("action") or "").strip()
        if not request_id:
            raise ValueError("Workspace action is missing request_id.")
        if action in {"run_verification", "restore_backup"}:
            self._start_worker(self._workspace_action_worker, request_id, action, payload)
            return
        self._workspace_action_worker(request_id, action, payload)

    def _workspace_action_worker(self, request_id: str, action: str, payload: dict[str, Any]) -> None:
        try:
            tools = self._create_workspace_tools()
            if action == "list_directory":
                path = str(payload.get("path") or ".")
                result = {"path": path, "entries": tools.list_directory(path)}
            elif action == "read_file":
                path = str(payload.get("path") or "").strip()
                result = {"path": path, "content": tools.read_file(path)}
            elif action == "inspect":
                result = {
                    "git_status": json.loads(tools.dispatch("git_status", {})),
                    "git_diff": json.loads(tools.dispatch("git_diff", {})),
                    "backups": tools.list_backups(),
                }
            elif action == "run_verification":
                result = json.loads(tools.dispatch("run_verification", {"name": str(payload.get("name") or "")}))
            elif action == "restore_backup":
                result = tools.restore_backup(str(payload.get("backup_path") or payload.get("backupPath") or ""))
            else:
                raise ValueError(f"Unknown workspace action: {action or '(empty)'}")
            self._emit("workspace_response", {"request_id": request_id, "action": action, "result": result})
        except Exception as exc:
            self._emit(
                "workspace_response",
                {
                    "request_id": request_id,
                    "action": action,
                    "result": {"status": "error", "error": str(exc).strip() or "Workspace action failed."},
                },
            )

    def _approve_write(self, proposal) -> bool:
        return self._request_approval(
            "write_file",
            f"Approve writing {proposal.relative_path}?",
            {
                "relative_path": proposal.relative_path,
                "diff": proposal.diff,
                "old_bytes": len(str(proposal.old_content).encode("utf-8")),
                "new_bytes": len(str(proposal.new_content).encode("utf-8")),
            },
        )

    def _approve_command(self, proposal) -> bool:
        return self._request_approval(
            "run_verification",
            f"Approve running verification preset {proposal.name}?",
            {
                "name": proposal.name,
                "argv": list(proposal.argv),
                "cwd": proposal.cwd,
                "timeout_seconds": proposal.timeout_seconds,
            },
        )

    def _approve_chat_code(self, proposal: dict[str, Any]) -> bool:
        return self._request_approval(
            "chat_run_python",
            "Approve running Chat Python code?",
            {
                "tool": "run_python",
                "code": str(proposal.get("code") or "")[:4000],
                "full_code": str(proposal.get("full_code") or proposal.get("code") or ""),
                "timeout_seconds": proposal.get("timeout_seconds"),
                "risk_level": proposal.get("risk_level"),
                "risk_summary": proposal.get("risk_summary"),
                "sandbox_level": proposal.get("sandbox_level"),
                "network_isolation": proposal.get("network_isolation"),
            },
        )

    def _approve_mcp_tool(self, proposal: dict[str, Any]) -> bool:
        return self._request_approval(
            "mcp_tool_call",
            f"Approve MCP tool {proposal.get('server')}/{proposal.get('tool')}?",
            {
                "server": str(proposal.get("server") or ""),
                "tool": str(proposal.get("tool") or ""),
                "arguments": proposal.get("arguments") if isinstance(proposal.get("arguments"), dict) else {},
            },
        )

    def _create_chat_code_tool_provider(self) -> CodeExecutionToolProvider:
        sandbox = str(self.dependencies.chat_config.code_execution_sandbox or "pyodide").strip().casefold()
        if sandbox == "legacy_subprocess" and self._has_connected_mcp_clients():
            executor = CodeExecutor(root=self._runtime_root() / "chat_code_exec")
        else:
            executor = PyodideSandbox(app_root=self.dependencies.app_root)
        return CodeExecutionToolProvider(
            executor=executor,
            approval_callback=self._approve_chat_code,
            enabled=True,
        )

    def _has_connected_mcp_clients(self) -> bool:
        if not self.dependencies.chat_config.mcp_enabled:
            return False
        clients, statuses = self._create_mcp_clients_cached(self._mcp_connector_registry().list_connectors())
        return bool(clients) and any(status.get("status") == "connected" for status in statuses)

    def _create_mcp_tool_provider(self) -> McpToolProvider:
        clients, _statuses = self._create_mcp_clients_cached(self._mcp_connector_registry().list_connectors())
        return McpToolProvider(clients, approval_callback=self._approve_mcp_tool, restrict_dispatch_to_exposed=True)

    def _create_mcp_diagnostics_tool_provider(self) -> McpDiagnosticsToolProvider:
        connectors = self._mcp_connector_registry().list_connectors()
        clients, statuses = self._create_mcp_clients_cached(connectors)
        return McpDiagnosticsToolProvider(connectors=connectors, clients=clients, statuses=statuses)

    def _create_mcp_clients_cached(self, connectors: list[dict[str, Any]], *, force: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        cache_key = json.dumps(connectors, ensure_ascii=False, sort_keys=True, default=str)
        now = time.monotonic()
        cached = self._mcp_client_cache.get(cache_key)
        if not force and cached and now - cached[0] < 60:
            clients = dict(cached[1])
            statuses = [dict(item) for item in cached[2]]
            return clients, statuses
        clients, statuses = create_mcp_clients(connectors)
        self._mcp_client_cache[cache_key] = (now, dict(clients), [dict(item) for item in statuses])
        return clients, statuses

    def _request_approval(self, approval_kind: str, question: str, proposal: dict[str, Any]) -> bool:
        if self._auto_approve:
            # Auto-approve mode: skip the prompt but keep an audit trail and surface it.
            record_cowork_event("approval_auto_approved", {"approval_kind": approval_kind, "question": question})
            self._emit(
                "cowork_log",
                {
                    "role": "SYSTEM",
                    "text": f"Auto-approved: {question}",
                    "client_session_id": str(getattr(self._worker_context, "client_session_id", "") or ""),
                    "mode": str(getattr(self._worker_context, "mode", "") or "Cowork"),
                },
            )
            return True
        approval_id = f"approval-{uuid.uuid4().hex}"
        approval_payload = build_approval_payload(approval_kind, question, proposal)
        with self._approval_condition:
            self._pending_approvals[approval_id] = None
        self._emit(
            "cowork_interactive_question",
            {
                "approval_id": approval_id,
                "approval_kind": approval_kind,
                "question": question,
                "proposal": approval_payload,
                "options": ["allow", "deny"],
                "client_session_id": str(getattr(self._worker_context, "client_session_id", "") or ""),
                "mode": str(getattr(self._worker_context, "mode", "") or "Cowork"),
            },
        )
        with self._approval_condition:
            resolved = self._approval_condition.wait_for(
                lambda: self._pending_approvals.get(approval_id) is not None,
                timeout=self.dependencies.approval_timeout_seconds,
            )
            answer = self._pending_approvals.pop(approval_id, None)
        if not resolved:
            self._emit_backend_error(f"Approval timed out: {approval_id}")
            return False
        return _is_approval_allow(answer)

    def _answer_question(self, payload: dict[str, Any]) -> None:
        approval_id = str(payload.get("approval_id") or payload.get("approvalId") or "").strip()
        answer = str(payload.get("answer") or "").strip()
        if not approval_id:
            self._emit_backend_error("Approval answer is missing approval_id.")
            return
        with self._approval_condition:
            if approval_id not in self._pending_approvals:
                self._emit_backend_error(f"Unknown approval_id: {approval_id}")
                return
            self._pending_approvals[approval_id] = answer
            self._approval_condition.notify_all()

    def _emit_backend_error(self, message: str) -> None:
        client_session_id = str(getattr(self._worker_context, "client_session_id", "") or "").strip()
        mode = str(getattr(self._worker_context, "mode", "") or "").strip()
        payload = {"source": "stderr", "message": message}
        if client_session_id:
            payload["client_session_id"] = client_session_id
        if mode:
            payload["mode"] = mode
        self._emit("backend-log", payload)

    def _emit(self, ipc_type: str, payload: dict[str, Any]) -> None:
        event = {"__ipc_type": ipc_type, **payload}
        with self._emit_lock:
            self.dependencies.output.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
            self.dependencies.output.flush()


def _is_approval_allow(answer: str | None) -> bool:
    return str(answer or "").strip().casefold() in {"allow", "approve", "approved", "yes", "y"}


def _compact_mcp_result(value: Any, *, max_chars: int = 6000) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        text = "" if value is None else str(value)
        return text if len(text) <= max_chars else f"{text[:max_chars]}..."
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        text = str(value)
    if len(text) <= max_chars:
        return value
    return {"truncated": True, "text": f"{text[:max_chars]}..."}


def _parse_mcp_tool_name(tool_name: str) -> tuple[str, str]:
    text = str(tool_name or "")
    if not text.startswith("mcp__"):
        return "connector", text or "tool"
    parts = text.split("__", 2)
    if len(parts) != 3:
        return "connector", text.removeprefix("mcp__") or "tool"
    return parts[1] or "connector", parts[2] or "tool"


_ROBLOX_PHYSICAL_WORKSPACE_CLASSES = frozenset(
    {
        "Part",
        "MeshPart",
        "UnionOperation",
        "WedgePart",
        "CornerWedgePart",
        "TrussPart",
        "SpawnLocation",
        "Seat",
        "VehicleSeat",
    }
)


def _looks_like_roblox_workspace_inspection(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    if not text.strip():
        return False
    workspace_terms = ("workspace", "roblox", "studio", "พาร์ท", "part", "parts", "ชิ้น", "ฉาก", "วัตถุ", "ออบเจกต์")
    inspection_terms = ("กี่", "จำนวน", "ลักษณะ", "อะไร", "อยู่", "มี", "count", "how many", "describe", "inspect", "list")
    return any(term in text for term in workspace_terms) and any(term in text for term in inspection_terms)


def _roblox_instance_path_for_tool(raw_path: str, name: str) -> str:
    path = str(raw_path or "").strip()
    if path.startswith("game."):
        path = path.removeprefix("game.")
    if path.startswith("Workspace"):
        return path
    clean_name = str(name or "").strip()
    return f"Workspace.{clean_name}" if clean_name else "Workspace"


def _format_roblox_property_summary(properties: dict[str, Any]) -> str:
    if not properties:
        return ""
    fields = []
    for label in ("Size", "Position", "Material", "Color", "BrickColor", "Anchored", "CanCollide", "Transparency"):
        value = properties.get(label)
        if value is not None and str(value).strip():
            fields.append(f"{label}: {value}")
    return ": " + "; ".join(fields) if fields else ""


def _first_json_object_from_mcp_result(result: Any) -> dict[str, Any] | list[Any] | None:
    for text in _mcp_result_texts(result):
        candidate = text.strip()
        if not candidate:
            continue
        parsed = _loads_json_object(candidate)
        if parsed is not None:
            return parsed
        for extracted in re.findall(r"text='(.*?)'\\s+(?:annotations|meta)=", candidate, flags=re.DOTALL):
            parsed = _loads_json_object(extracted)
            if parsed is not None:
                return parsed
    return None


def _loads_json_object(text: str) -> dict[str, Any] | list[Any] | None:
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


def _mcp_result_texts(value: Any) -> list[str]:
    if isinstance(value, dict):
        if "text" in value:
            return [str(value.get("text") or "")]
        out: list[str] = []
        content = value.get("content")
        if isinstance(content, list):
            for item in content:
                out.extend(_mcp_result_texts(item))
        else:
            for item in value.values():
                out.extend(_mcp_result_texts(item))
        return out
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_mcp_result_texts(item))
        return out
    if isinstance(value, str):
        return [value]
    return []


def _call_chat_web_tools_factory(factory: Callable[..., Any], query: str, *, max_fetch: int) -> Any:
    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):
        return factory(query)
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
        return factory(query, max_fetch=max_fetch)
    if "max_fetch" in signature.parameters:
        return factory(query, max_fetch=max_fetch)
    return factory(query)


def _friendly_chat_error_message(message: str, model: str = "") -> str:
    text = str(message or "").strip()
    model_name = str(model or "").strip()
    lowered = text.casefold()
    display_model = model_name
    if not display_model:
        match = re.match(r"([a-z][a-z0-9_-]*:[^:]+):\s+", text, flags=re.IGNORECASE)
        display_model = match.group(1) if match else "the selected model"

    if any(marker in lowered for marker in ("top up", "credit", "billing", "insufficient quota", "quota_exceeded", "payment required", "error code: 402")):
        return (
            f"{display_model} does not have enough credit or billing access right now. "
            "Please top up or choose another configured model, then try again."
        )
    if "error code: 429" in lowered or "temporarily overloaded" in lowered or "rate limit" in lowered:
        return f"{display_model} is temporarily overloaded or rate-limited. Please try again later or choose another model."
    if _is_timeout_error(text):
        return f"{display_model} model timed out. Try again, or pick a faster model."
    if "provider runtime is not implemented" in lowered:
        return f"{display_model} is listed in the catalog, but this provider runtime is not implemented in the app yet."
    return text


def _is_timeout_error(message: str) -> bool:
    lowered = str(message or "").casefold()
    return any(
        marker in lowered
        for marker in (
            "request timed out",
            "timed out",
            "timeout",
            "readtimeout",
            "apitimeout",
        )
    )


def _is_provider_access_error(message: str) -> bool:
    lowered = str(message or "").casefold()
    return any(
        marker in lowered
        for marker in (
            "top up",
            "credit",
            "billing",
            "insufficient quota",
            "quota_exceeded",
            "payment required",
            "error code: 402",
            "error code: 429",
            "temporarily overloaded",
            "rate limit",
        )
    )


def main() -> int:
    IpcSidecar().serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
