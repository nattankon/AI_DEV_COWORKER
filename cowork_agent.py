from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol

try:
    from .agent_config import build_cowork_system_prompt, load_cowork_memory_context
    from .agent_state import AgentRunState
    from .local_ai import create_local_ai_client, local_model_id
    from .session_store import finish_cowork_session, record_cowork_event, start_cowork_session
    from .tool_loop import LoopHooks, run_tool_loop
    from .workspace_tools import WorkspaceTools
except ImportError:
    from agent_config import build_cowork_system_prompt, load_cowork_memory_context
    from agent_state import AgentRunState
    from local_ai import create_local_ai_client, local_model_id
    from session_store import finish_cowork_session, record_cowork_event, start_cowork_session
    from tool_loop import LoopHooks, run_tool_loop
    from workspace_tools import WorkspaceTools


class ChatModel(Protocol):
    def complete(self, messages: list[dict], tools: list[dict], generation: dict | None = None) -> dict: ...


class SessionRecorder(Protocol):
    def start(self, model: str, workspace: Path) -> None: ...

    def record(self, event_type: str, payload: dict) -> None: ...

    def finish(self, status: str, summary: str) -> None: ...


class JsonlSessionRecorder:
    def start(self, model: str, workspace: Path) -> None:
        start_cowork_session(model, str(workspace))

    def record(self, event_type: str, payload: dict) -> None:
        record_cowork_event(event_type, payload)

    def finish(self, status: str, summary: str) -> None:
        finish_cowork_session(status, summary)


class OpenAIChatModel:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        extra_body: dict | None = None,
        timeout: float = 45.0,
    ):
        self.client = create_local_ai_client(base_url, api_key, timeout=timeout)
        self.model = _provider_model_id(model)
        self.extra_body = dict(extra_body or {})

    def complete(self, messages: list[dict], tools: list[dict], generation: dict | None = None) -> dict:
        request = self._request_payload(messages, tools, generation)
        response = self.client.chat.completions.create(**request)
        message = response.choices[0].message
        return {
            "content": _normalize_content(message.content),
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "name": getattr(tool_call.function, "name", ""),
                    "arguments": getattr(tool_call.function, "arguments", "{}") or "{}",
                }
                for tool_call in (message.tool_calls or [])
            ],
        }

    def stream_complete(
        self,
        messages: list[dict],
        tools: list[dict],
        generation: dict | None = None,
        on_delta: Callable[[str], None] | None = None,
    ) -> dict:
        request = self._request_payload(messages, tools, generation)
        request["stream"] = True
        chunks = self.client.chat.completions.create(**request)
        content_parts: list[str] = []
        tool_calls_by_index: dict[int, dict[str, Any]] = {}
        for chunk in chunks:
            choices = getattr(chunk, "choices", []) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            if delta is None:
                continue
            content = _normalize_content(getattr(delta, "content", ""))
            if content:
                content_parts.append(content)
                if on_delta:
                    on_delta(content)
            for tool_call in getattr(delta, "tool_calls", None) or []:
                index = int(getattr(tool_call, "index", 0) or 0)
                current = tool_calls_by_index.setdefault(
                    index,
                    {"id": "", "name": "", "arguments": ""},
                )
                call_id = getattr(tool_call, "id", "") or ""
                if call_id:
                    current["id"] += call_id
                function = getattr(tool_call, "function", None)
                if function is not None:
                    name = getattr(function, "name", "") or ""
                    arguments = getattr(function, "arguments", "") or ""
                    if name:
                        current["name"] += name
                    if arguments:
                        current["arguments"] += arguments
        return {
            "content": "".join(content_parts),
            "tool_calls": [
                {
                    "id": call.get("id", ""),
                    "name": call.get("name", ""),
                    "arguments": call.get("arguments", "{}") or "{}",
                }
                for _index, call in sorted(tool_calls_by_index.items())
            ],
        }

    def stream(self, messages: list[dict], tools: list[dict], generation: dict | None = None):
        deltas: list[str] = []
        self.stream_complete(messages, tools, generation, deltas.append)
        yield from deltas

    def _request_payload(self, messages: list[dict], tools: list[dict], generation: dict | None = None) -> dict:
        generation_settings = dict(generation or {})
        request = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "temperature": generation_settings.get("temperature", 0),
            "max_tokens": generation_settings.get("max_tokens", 8192),
        }
        if self.extra_body:
            request["extra_body"] = self.extra_body
        return request


_STAGE_STATUS = {
    "inspect": "Inspecting the project…",
    "plan": "Planning the change…",
    "act": "Working…",
    "verify": "Running verification…",
    "report": "Writing response…",
}


def _tool_status_text(tool_name: str, arguments: dict) -> str:
    name = str(tool_name or "")
    args = arguments if isinstance(arguments, dict) else {}
    path = str(args.get("path") or args.get("relative_path") or "").strip()
    if name in {"write_file", "edit_file"}:
        return f"Editing {path}…" if path else "Editing a file…"
    if name == "read_file":
        return f"Reading {path}…" if path else "Reading a file…"
    if name == "run_verification":
        preset = str(args.get("name") or "").strip()
        return f"Running {preset}…" if preset else "Running verification…"
    if name in {"list_directory", "search_files"}:
        return "Searching the project…"
    return f"Using {name}…" if name else "Working…"


class CoworkAgent:
    def __init__(
        self,
        model: ChatModel,
        model_name: str,
        workspace: str | Path,
        tools: WorkspaceTools,
        recorder: SessionRecorder | None = None,
        max_iterations: int = 20,
        event_sink: Callable[[str, dict], None] | None = None,
    ):
        self.model = model
        self.model_name = model_name
        self.workspace = Path(workspace).resolve()
        self.tools = tools
        self.recorder = recorder or JsonlSessionRecorder()
        self.max_iterations = max_iterations
        self.event_sink = event_sink or (lambda _event_type, _payload: None)
        self._history: list[dict] = []

    def clear_history(self) -> None:
        self._history.clear()

    def run(
        self,
        prompt: str,
        initial_run_state: AgentRunState | dict | None = None,
        on_delta: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_stream_reset: Callable[[], None] | None = None,
        on_evidence: Callable[[dict], None] | None = None,
        user_content: Any | None = None,
    ) -> str:
        normalized_prompt = str(prompt or "").strip()
        if not normalized_prompt:
            raise ValueError("Prompt cannot be empty.")
        request_content = user_content if user_content is not None else normalized_prompt

        def emit_status(text: str) -> None:
            if on_status and text:
                on_status(text)

        def record_stage(stage: str) -> None:
            self._record_stage(run_state, stage)
            emit_status(_STAGE_STATUS.get(stage, ""))

        memory_context = load_cowork_memory_context(
            prompt="",
            base_dir=str(self.workspace),
            shared_state={"output_dir": str(self.workspace)},
        )
        messages = [
            {"role": "system", "content": build_cowork_system_prompt(memory_context)},
            *self._history,
            {"role": "user", "content": request_content},
        ]
        self.recorder.start(self.model_name, self.workspace)
        self.recorder.record("message_user", {"content": normalized_prompt})
        run_state = _coerce_run_state(initial_run_state)
        self._record_state_snapshot(run_state)
        record_stage("inspect")
        record_stage("plan")

        try:
            def on_loop_event(event_type: str, payload: dict) -> None:
                self.recorder.record(event_type, payload)
                if event_type == "tool_execution":
                    self.event_sink(event_type, payload)
                    emit_status(_tool_status_text(payload.get("tool_name", ""), payload.get("arguments") or {}))

            def on_tool_result(tool_name: str, _arguments: dict, result: str) -> None:
                stage = "verify" if tool_name == "run_verification" else "act"
                record_stage(stage)
                run_state.observe_tool_result(tool_name, result)
                self._record_state_snapshot(run_state)

            def before_finalize(_content: str) -> str | None:
                if run_state.requires_verification_before_report():
                    self.recorder.record("verification_required_before_report", run_state.completion_evidence())
                    self._record_state_snapshot(run_state)
                    return (
                        "You changed files with write_file. Do not report implementation success yet. "
                        "Call run_verification with an available named preset, inspect the result, "
                        "and only then return a final answer with the evidence."
                    )
                return None

            outcome = run_tool_loop(
                model=self.model,
                messages=messages,
                tools=self.tools,
                max_iterations=self.max_iterations,
                on_event=on_loop_event,
                on_final_delta=on_delta,
                on_stream_reset=on_stream_reset,
                hooks=LoopHooks(before_finalize=before_finalize, on_tool_result=on_tool_result),
                force_final_answer=True,
            )
            content = outcome.answer
            record_stage("report")
            evidence = run_state.completion_evidence()
            self.recorder.record("completion_evidence", evidence)
            if on_evidence:
                on_evidence(evidence)
            self._record_state_snapshot(run_state)
            self._history.extend(
                [
                    {"role": "user", "content": normalized_prompt},
                    {"role": "assistant", "content": content},
                ]
            )
            self.recorder.record("message_assistant", {"content": content})
            self.recorder.finish("completed", content)
            return content
        except Exception as exc:
            self.recorder.finish("error", str(exc))
            raise

    def _record_stage(self, run_state: AgentRunState, stage: str) -> None:
        event = run_state.record_stage(stage)
        if event:
            self.recorder.record("agent_stage", event)

    def _record_state_snapshot(self, run_state: AgentRunState) -> None:
        self.recorder.record("agent_state_snapshot", run_state.to_snapshot())


def _normalize_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(getattr(item, "text", None), str):
                parts.append(item.text)
        return "".join(parts)
    return "" if content is None else str(content)


def _provider_model_id(model: str) -> str:
    normalized = str(model or "").strip()
    if ":" in normalized:
        return normalized.split(":", 1)[1]
    return local_model_id(normalized)


def _coerce_run_state(value: AgentRunState | dict | None) -> AgentRunState:
    if value is None:
        return AgentRunState()
    if isinstance(value, AgentRunState):
        return value
    return AgentRunState.from_snapshot(value)
