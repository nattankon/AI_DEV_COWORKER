from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
from typing import Any, Callable


@dataclass(frozen=True)
class ToolLoopOutcome:
    answer: str
    used_tools: bool
    iterations: int
    forced: bool = False


@dataclass(frozen=True)
class LoopHooks:
    before_finalize: Callable[[str], str | None] | None = None
    on_tool_result: Callable[[str, dict, str], None] | None = None


def run_tool_loop(
    *,
    model: Any,
    messages: list[dict],
    tools: Any,
    max_iterations: int,
    on_event: Callable[[str, dict], None] | None = None,
    hooks: LoopHooks | None = None,
    generation: dict | None = None,
    on_final_delta: Callable[[str], None] | None = None,
    on_stream_reset: Callable[[], None] | None = None,
    force_final_answer: bool = False,
    unproductive_result_detector: Callable[[str, dict, str], bool] | None = None,
    unproductive_steering_threshold: int = 2,
    tool_context_budget_chars: int | None = None,
    parallel_tools: bool = False,
) -> ToolLoopOutcome:
    event_sink = on_event or (lambda _event_type, _payload: None)
    loop_hooks = hooks or LoopHooks()
    empty_response_retries = 0
    used_tools = False
    seen_tool_calls: set[tuple[str, str]] = set()
    consecutive_unproductive_results = 0
    unproductive_steering_sent = False

    for iteration in range(max_iterations):
        tool_schemas = _tool_schemas(tools)
        can_stream = bool(on_final_delta and hasattr(model, "stream_complete"))
        response = _complete_model_turn(
            model=model,
            messages=messages,
            tool_schemas=tool_schemas,
            generation=generation,
            on_delta=on_final_delta if can_stream else None,
        )
        content = str(response.get("content") or "").strip()
        tool_calls = list(response.get("tool_calls") or [])

        if tool_calls:
            if force_final_answer and iteration == max_iterations - 1:
                if can_stream and on_stream_reset:
                    on_stream_reset()
                event_sink("force_final_answer", {"max_iterations": max_iterations})
                messages.append({"role": "user", "content": _FORCED_FINAL_ANSWER_PROMPT})
                return _complete_forced_final_answer(
                    model=model,
                    messages=messages,
                    generation=generation,
                    on_delta=on_final_delta if can_stream else None,
                    on_stream_reset=on_stream_reset if can_stream else None,
                    hooks=loop_hooks,
                    used_tools=used_tools,
                    iterations=max_iterations,
                )
            if can_stream and on_stream_reset:
                on_stream_reset()
            used_tools = True
            messages.append(
                {
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": [
                        {
                            "id": call.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": call.get("name", ""),
                                "arguments": call.get("arguments", "{}"),
                            },
                        }
                        for call in tool_calls
                    ],
                }
            )
            tool_results = _dispatch_tool_calls(
                tools=tools,
                tool_calls=tool_calls,
                seen_tool_calls=seen_tool_calls,
                parallel=parallel_tools,
                event_sink=event_sink,
            )
            for call, tool_name, arguments, result in tool_results:
                event_payload = {"tool_name": tool_name, "arguments": arguments, "result": result}
                event_sink("tool_execution", event_payload)
                if loop_hooks.on_tool_result:
                    loop_hooks.on_tool_result(tool_name, arguments, result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(call.get("id") or ""),
                        "content": result,
                    }
                )
                _apply_tool_context_budget(messages, tool_context_budget_chars)
                if unproductive_result_detector and unproductive_steering_threshold > 0:
                    if unproductive_result_detector(tool_name, arguments, result):
                        consecutive_unproductive_results += 1
                    else:
                        consecutive_unproductive_results = 0
            if (
                unproductive_result_detector
                and not unproductive_steering_sent
                and consecutive_unproductive_results >= unproductive_steering_threshold
            ):
                messages.append({"role": "user", "content": _UNPRODUCTIVE_TOOL_STEERING_PROMPT})
                unproductive_steering_sent = True
            continue

        if not content:
            if can_stream and on_stream_reset:
                on_stream_reset()
            if empty_response_retries == 0:
                empty_response_retries += 1
                repair_message = (
                    "Your previous response was empty. Continue the task from the available tool results. "
                    "Use another tool if needed, or return a concise final answer."
                )
                event_sink("model_empty_response", {"retry": empty_response_retries})
                messages.append({"role": "user", "content": repair_message})
                continue
            raise RuntimeError("Local AI returned neither tool calls nor final text after one recovery attempt.")

        if loop_hooks.before_finalize:
            repair_message = loop_hooks.before_finalize(content)
            if repair_message:
                if can_stream and on_stream_reset:
                    on_stream_reset()
                messages.append({"role": "user", "content": repair_message})
                continue

        return ToolLoopOutcome(answer=content, used_tools=used_tools, iterations=iteration + 1)

    raise RuntimeError(f"Agent loop exceeded {max_iterations} iterations.")


_FORCED_FINAL_ANSWER_PROMPT = (
    "You have reached the research limit. Provide your best answer using ONLY the evidence already "
    "gathered. For anything you could not find, say so explicitly; do NOT guess, fabricate, or fill "
    "gaps with invented values or citations."
)

_UNPRODUCTIVE_TOOL_STEERING_PROMPT = (
    "Recent tool results returned no usable data. Try a different source, or give your best answer "
    "from what you have and state what is missing."
)


def _complete_forced_final_answer(
    *,
    model: Any,
    messages: list[dict],
    generation: dict | None,
    on_delta: Callable[[str], None] | None,
    on_stream_reset: Callable[[], None] | None,
    hooks: LoopHooks,
    used_tools: bool,
    iterations: int,
) -> ToolLoopOutcome:
    for repair_attempt in range(2):
        response = _complete_model_turn(
            model=model,
            messages=messages,
            tool_schemas=[],
            generation=generation,
            on_delta=on_delta,
        )
        content = str(response.get("content") or "").strip()
        if not content:
            raise RuntimeError("Forced final answer returned no final text.")
        if hooks.before_finalize:
            repair_message = hooks.before_finalize(content)
            if repair_message:
                if repair_attempt == 1:
                    raise RuntimeError("Forced final answer did not pass finalize validation after one repair turn.")
                if on_stream_reset:
                    on_stream_reset()
                messages.append({"role": "user", "content": repair_message})
                continue
        return ToolLoopOutcome(answer=content, used_tools=used_tools, iterations=iterations, forced=True)
    raise RuntimeError("Forced final answer did not complete.")


def _tool_schemas(tools: Any) -> list[dict]:
    return list(getattr(tools, "schemas", tools))


def _tool_call_key(tool_name: str, arguments: dict) -> tuple[str, str]:
    return (
        tool_name,
        json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
    )


def _dispatch_tool_calls(
    *,
    tools: Any,
    tool_calls: list[dict],
    seen_tool_calls: set[tuple[str, str]],
    parallel: bool,
    event_sink: Callable[[str, dict], None],
) -> list[tuple[dict, str, dict, str]]:
    prepared: list[dict] = []
    jobs: list[tuple[int, str, dict]] = []
    for index, call in enumerate(tool_calls):
        tool_name = str(call.get("name") or "")
        raw_arguments = call.get("arguments", "{}")
        try:
            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else dict(raw_arguments)
            if not isinstance(arguments, dict):
                raise TypeError("Tool arguments must decode to an object.")
            call_key = _tool_call_key(tool_name, arguments)
            if call_key in seen_tool_calls:
                result = json.dumps(
                    {
                        "status": "skipped",
                        "reason": "duplicate call; you already did this, use the prior result or answer",
                    },
                    ensure_ascii=False,
                )
                prepared.append({"call": call, "tool_name": tool_name, "arguments": arguments, "result": result})
            else:
                seen_tool_calls.add(call_key)
                prepared.append({"call": call, "tool_name": tool_name, "arguments": arguments, "result": None})
                jobs.append((index, tool_name, arguments))
        except Exception as exc:
            result = json.dumps(
                {"status": "error", "error": f"Invalid tool arguments: {exc}"},
                ensure_ascii=False,
            )
            prepared.append({"call": call, "tool_name": tool_name, "arguments": {}, "result": result})

    if parallel and len(jobs) > 1:
        reserve = getattr(tools, "reserve_tool_calls", None)
        if callable(reserve):
            reserve(
                [
                    {"tool_name": prepared[index]["tool_name"], "arguments": dict(prepared[index]["arguments"])}
                    for index, _tool_name, _arguments in jobs
                ]
            )
        for index, tool_name, arguments in jobs:
            event_sink("tool_started", {"tool_name": tool_name, "arguments": dict(arguments)})
        with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as executor:
            futures = {
                executor.submit(_dispatch_single_tool, tools, tool_name, arguments): index
                for index, tool_name, arguments in jobs
            }
            for future, index in futures.items():
                prepared[index]["result"] = future.result()
    else:
        for index, tool_name, arguments in jobs:
            event_sink("tool_started", {"tool_name": tool_name, "arguments": dict(arguments)})
            prepared[index]["result"] = _dispatch_single_tool(tools, tool_name, arguments)

    return [
        (item["call"], item["tool_name"], item["arguments"], str(item["result"] or ""))
        for item in prepared
    ]


def _dispatch_single_tool(tools: Any, tool_name: str, arguments: dict) -> str:
    try:
        return str(tools.dispatch(tool_name, arguments))
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)


def _apply_tool_context_budget(messages: list[dict], budget_chars: int | None) -> None:
    if budget_chars is None:
        return
    budget = max(0, int(budget_chars))
    tool_messages = [message for message in messages if message.get("role") == "tool"]
    while sum(len(str(message.get("content") or "")) for message in tool_messages) > budget:
        target = next(
            (
                message
                for message in tool_messages
                if _tool_result_status(message) != "truncated"
            ),
            None,
        )
        if target is None:
            break
        original = str(target.get("content") or "")
        target["content"] = json.dumps(
            {
                "status": "truncated",
                "reason": "older tool result omitted from model context; use available recent tool results",
                "original_chars": len(original),
            },
            ensure_ascii=False,
        )


def _tool_result_status(message: dict) -> str:
    try:
        payload = json.loads(str(message.get("content") or ""))
    except (TypeError, ValueError):
        return ""
    return str(payload.get("status") or "")


def _complete_model_turn(
    *,
    model: Any,
    messages: list[dict],
    tool_schemas: list[dict],
    generation: dict | None,
    on_delta: Callable[[str], None] | None,
) -> dict:
    if on_delta and hasattr(model, "stream_complete"):
        return model.stream_complete(messages, tool_schemas, generation, on_delta)
    if generation is None:
        return model.complete(messages, tool_schemas)
    return model.complete(messages, tool_schemas, generation)
