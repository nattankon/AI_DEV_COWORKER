from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Callable, Any

try:
    from .chat_runtime import CHAT_SYSTEM_PROMPT
    from .chat_web_tools import WebResearchTools
    from .model_fallback import run_with_model_candidates
    from .tool_loop import LoopHooks, ToolLoopOutcome, run_tool_loop
except ImportError:
    from chat_runtime import CHAT_SYSTEM_PROMPT
    from chat_web_tools import WebResearchTools
    from model_fallback import run_with_model_candidates
    from tool_loop import LoopHooks, ToolLoopOutcome, run_tool_loop


RESEARCH_INSTRUCTIONS = (
    "You can use web_search and web_fetch for current or external facts. "
    "Search first, open the most relevant sources, and ground every external fact in fetched evidence. "
    "Cite sources inline using [web:N] where N is the index returned by tool results, and end with a Sources list. "
    "Only state exact dates, prices, version numbers, or table values when they appear in fetched evidence. "
    "Keep partial dates partial; do not add or convert years unless the year appears in evidence. "
    "When MCP connector tools are available and the user asks about the state of a connected app or service, "
    "use the most relevant read-only MCP tool to inspect that state. Do not stop at listing MCP tools when a "
    "specific read-only inspection tool can answer the user's question."
)


@dataclass(frozen=True)
class ChatResearchResult:
    outcome: ToolLoopOutcome
    sources: list[dict]
    used_model: str
    evidence_corpus: str = ""


class ChatResearchRunner:
    def __init__(
        self,
        *,
        model_factory: Callable[[str], Any],
        model_candidates: Callable[[str], list[str]],
        web_tools_factory: Callable[[str], Any] | None = None,
        max_iterations: int = 6,
        force_final_answer: bool = False,
        tool_context_budget_chars: int | None = 12000,
        parallel_tools: bool = True,
        on_fallback: Callable[[str, str, str], None] | None = None,
    ):
        self._model_factory = model_factory
        self._model_candidates = model_candidates
        self._web_tools_factory = web_tools_factory or (lambda query: WebResearchTools(relevance_query=query))
        self._max_iterations = max_iterations
        self._force_final_answer = force_final_answer
        self._tool_context_budget_chars = tool_context_budget_chars
        self._parallel_tools = parallel_tools
        self._on_fallback = on_fallback

    def run(
        self,
        *,
        prompt: str,
        requested_model: str,
        history: list[dict[str, str]] | None = None,
        system_prompt: str = CHAT_SYSTEM_PROMPT,
        generation: dict | None = None,
        user_content: Any | None = None,
        extra_system_messages: list[dict] | None = None,
        before_finalize: Callable[[str, Any], str | None] | None = None,
        on_final_delta: Callable[[str], None] | None = None,
        on_stream_reset: Callable[[], None] | None = None,
        on_event: Callable[[str, dict], None] | None = None,
    ) -> ChatResearchResult:
        normalized_prompt = str(prompt or "").strip()
        if not normalized_prompt:
            raise ValueError("Prompt cannot be empty.")
        candidates = self._model_candidates(requested_model)

        def attempt(model_name: str) -> ChatResearchResult:
            tools = self._web_tools_factory(normalized_prompt)
            model = self._model_factory(model_name)
            messages = [
                {"role": "system", "content": system_prompt},
                *[dict(message) for message in (extra_system_messages or [])],
                {"role": "system", "content": RESEARCH_INSTRUCTIONS},
                *(history or []),
                {"role": "user", "content": user_content if user_content is not None else normalized_prompt},
            ]
            outcome = run_tool_loop(
                model=model,
                messages=messages,
                tools=tools,
                max_iterations=self._max_iterations,
                generation=generation,
                hooks=LoopHooks(
                    before_finalize=(lambda content: before_finalize(content, tools))
                    if before_finalize
                    else None
                ),
                on_final_delta=on_final_delta,
                on_stream_reset=on_stream_reset,
                on_event=on_event,
                force_final_answer=self._force_final_answer,
                unproductive_result_detector=_is_unproductive_web_result,
                tool_context_budget_chars=self._tool_context_budget_chars,
                parallel_tools=self._parallel_tools,
            )
            return ChatResearchResult(
                outcome=outcome,
                sources=list(tools.sources()) if callable(getattr(tools, "sources", None)) else [],
                used_model=model_name,
                evidence_corpus=str(tools.evidence_corpus()) if callable(getattr(tools, "evidence_corpus", None)) else "",
            )

        return run_with_model_candidates(
            candidates=candidates,
            attempt=attempt,
            on_fallback=self._on_fallback,
            no_candidate_error="No chat research model candidate is available.",
        )[0]


def _is_unproductive_web_result(tool_name: str, arguments: dict, result: str) -> bool:
    del arguments
    if tool_name != "web_fetch":
        return False
    try:
        payload = json.loads(result)
    except (TypeError, ValueError):
        return False
    if payload.get("blocked"):
        return True
    if payload.get("status") != "ok":
        return False
    evidence = str(payload.get("evidence") or "").strip()
    tables = list(payload.get("tables") or [])
    return not evidence and not tables
