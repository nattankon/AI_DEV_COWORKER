from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any, Callable
import argparse
import inspect
import json
import time
import uuid

try:
    from .chat_quality_eval import evaluate_case_result, quality_eval_cases
    from .chat_runtime import ChatRuntimeConfig
    from .ipc_sidecar import IpcDependencies, IpcSidecar
    from .model_performance import save_model_performance_profile
except ImportError:
    from chat_quality_eval import evaluate_case_result, quality_eval_cases
    from chat_runtime import ChatRuntimeConfig
    from ipc_sidecar import IpcDependencies, IpcSidecar
    from model_performance import save_model_performance_profile


RunChatOnce = Callable[..., dict[str, Any]]

# Sentinel accepted by --tool-research-routes to request the pre-gated behavior
# (tool_research_routes=None: every route except memory enters the loop).
LEGACY_ROUTES: tuple[str, ...] = ("legacy",)


@dataclass(frozen=True)
class LiveRunConfig:
    effort: str = "Medium"
    web_settings: dict[str, str] | None = None


def run_chat_once(
    prompt: str,
    *,
    model: str,
    effort: str = "Medium",
    web_settings: dict[str, str] | None = None,
    app_root: str | Path | None = None,
    workspace: str | Path | None = None,
    tool_research_routes: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Run one Chat prompt through the real sidecar pipeline. Intended for explicit live eval only."""
    root = Path(app_root or Path.cwd()).resolve()
    active_workspace = Path(workspace or root).resolve()
    dependency_kwargs: dict[str, Any] = {
        "workspace": active_workspace,
        "app_root": root,
        "output": StringIO(),
        "model_lister": lambda: [],
    }
    if tool_research_routes == LEGACY_ROUTES:
        # Explicit legacy mode: every non-memory route enters the loop — matches
        # the pre-2026-07-03 default and the archived "default"-labeled reports.
        dependency_kwargs["chat_config"] = ChatRuntimeConfig(tool_research_routes=None)
    elif tool_research_routes is not None:
        dependency_kwargs["chat_config"] = ChatRuntimeConfig(tool_research_routes=tuple(tool_research_routes))
    sidecar = IpcSidecar(
        IpcDependencies(**dependency_kwargs)
    )
    started = time.perf_counter()
    answer, used_model, sources, diagnostics = sidecar._run_plain_chat(
        str(prompt or ""),
        model,
        f"quality-{uuid.uuid4().hex}",
        effort,
        web_settings=web_settings or {"webMode": "auto", "searchProvider": "auto"},
        history_override=[],
        return_diagnostics=True,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    return {
        "answer": answer,
        "sources": sources,
        "evidence_corpus": str(diagnostics.get("evidence_corpus") or ""),
        "latency_ms": latency_ms,
        "used_model": used_model,
        "entered_tool_loop": bool(diagnostics.get("entered_tool_loop")),
        "research_iterations": int(diagnostics.get("research_iterations") or 0),
        "research_forced": bool(diagnostics.get("research_forced")),
        "answer_path_ms": int(diagnostics.get("answer_path_ms") or 0),
        "search_provider": str(diagnostics.get("search_provider") or ""),
    }


def run_quality_eval_live(
    *,
    models: list[str],
    run_chat_once: RunChatOnce,
    categories: list[str] | None = None,
    effort: str = "Medium",
    web_settings: dict[str, str] | None = None,
    retry_attempts: int = 0,
    retry_backoff_seconds: float = 0.0,
    tool_research_routes: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    selected_categories = {str(item) for item in categories or [] if str(item).strip()}
    cases = [
        case
        for case in quality_eval_cases()
        if not selected_categories or str(case.get("category") or "") in selected_categories
    ]
    cells: list[dict[str, Any]] = []
    for model in models:
        for case in cases:
            category = str(case.get("category") or "")
            prompt = str(case.get("prompt") or "")
            try:
                started = time.perf_counter()
                base_settings = dict(web_settings or {"webMode": "auto", "searchProvider": "auto"})
                case_settings = case.get("web_settings") if isinstance(case.get("web_settings"), dict) else {}
                payload, attempts = _run_chat_once_with_retries(
                    run_chat_once,
                    prompt,
                    model=str(model),
                    effort=effort,
                    web_settings={**base_settings, **case_settings},
                    tool_research_routes=tool_research_routes,
                    retry_attempts=retry_attempts,
                    retry_backoff_seconds=retry_backoff_seconds,
                )
                latency_ms = payload.get("latency_ms")
                if latency_ms is None:
                    latency_ms = int((time.perf_counter() - started) * 1000)
                evaluation = evaluate_case_result(
                    case,
                    answer=str(payload.get("answer") or ""),
                    sources=payload.get("sources") if isinstance(payload.get("sources"), list) else None,
                    evidence=str(payload.get("evidence_corpus") or payload.get("evidence") or ""),
                    latency_ms=latency_ms,
                    entered_tool_loop=payload.get("entered_tool_loop") if isinstance(payload.get("entered_tool_loop"), bool) else None,
                )
                cells.append(
                    {
                        "model": str(model),
                        "used_model": str(payload.get("used_model") or model),
                        "category": category,
                        "prompt": prompt,
                        "answer": str(payload.get("answer") or ""),
                        "latency_ms": int(float(latency_ms)),
                        "attempts": attempts,
                        "variant": _route_variant(tool_research_routes),
                        "entered_tool_loop": bool(payload.get("entered_tool_loop")),
                        "research_iterations": int(payload.get("research_iterations") or 0),
                        "research_forced": bool(payload.get("research_forced")),
                        "answer_path_ms": int(payload.get("answer_path_ms") or 0),
                        "search_provider": str(payload.get("search_provider") or ""),
                        "used_source": bool(payload.get("sources")),
                        "thai_ok": _thai_ok(category, str(payload.get("answer") or "")),
                        **evaluation,
                    }
                )
            except Exception as exc:
                skipped = _skip_reason(exc)
                cells.append(
                    {
                        "model": str(model),
                        "used_model": str(model),
                        "category": category,
                        "prompt": prompt,
                        "answer": "",
                        "score": 0,
                        "status": "skipped" if skipped else "failed",
                        **({"skip_reason": skipped} if skipped else {}),
                        "findings": [f"error: {exc}"],
                        "checks": list(case.get("checks") or []),
                        "latency_ms": 0,
                        "attempts": _attempts_from_error(exc),
                        "variant": _route_variant(tool_research_routes),
                        "entered_tool_loop": False,
                        "research_iterations": 0,
                        "research_forced": False,
                        "answer_path_ms": 0,
                        "search_provider": "",
                        "hallucinated": False,
                        "used_source": False,
                        "thai_ok": False,
                        "direct": False,
                        "source_quality_ok": False,
                    }
                )
    return {
        "models": _aggregate_by(cells, key="model"),
        "categories": _aggregate_by(cells, key="category"),
        "summary": {**_summary(cells), "variant": _route_variant(tool_research_routes)},
        "cells": cells,
    }


def save_quality_report(matrix: dict[str, Any], *, output_dir: str | Path = "work_logs") -> dict[str, str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    json_path = root / f"chat-quality-live-{stamp}.json"
    md_path = root / f"chat-quality-live-{stamp}.md"
    json_path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_matrix_markdown(matrix), encoding="utf-8")
    profile_paths = save_model_performance_profile(matrix, output_dir=root)
    return {"json": str(json_path), "markdown": str(md_path), **profile_paths}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run opt-in live Chat quality evaluation.")
    parser.add_argument("--live", action="store_true", help="Required. Confirms live model/API calls are allowed.")
    parser.add_argument("--models", required=True, help="Comma-separated model ids to evaluate.")
    parser.add_argument("--categories", default="", help="Optional comma-separated category filter.")
    parser.add_argument("--effort", default="Medium", choices=("Low", "Medium", "High"))
    parser.add_argument("--retry-attempts", type=int, default=0, help="Retry count for retryable provider errors such as 429.")
    parser.add_argument("--retry-backoff-seconds", type=float, default=0.0, help="Delay between retry attempts.")
    parser.add_argument("--tool-research-routes", default="", help="Optional comma-separated route categories that may enter tool research, e.g. web,project.")
    parser.add_argument("--output-dir", default="work_logs")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("--live is required so the default test suite never triggers model calls.")
    models = [item.strip() for item in args.models.split(",") if item.strip()]
    categories = [item.strip() for item in args.categories.split(",") if item.strip()] or None
    matrix = run_quality_eval_live(
        models=models,
        categories=categories,
        effort=args.effort,
        web_settings={"webMode": "auto", "searchProvider": "auto"},
        retry_attempts=max(0, args.retry_attempts),
        retry_backoff_seconds=max(0.0, args.retry_backoff_seconds),
        tool_research_routes=_parse_routes(args.tool_research_routes),
        run_chat_once=run_chat_once,
    )
    paths = save_quality_report(matrix, output_dir=args.output_dir)
    print(json.dumps({"status": "ok", "reports": paths, "summary": matrix["summary"]}, ensure_ascii=False, indent=2))
    return 0


def _aggregate_by(cells: list[dict[str, Any]], *, key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for cell in cells:
        groups.setdefault(str(cell.get(key) or ""), []).append(cell)
    return {name: _aggregate_cells(items) for name, items in groups.items()}


def _aggregate_cells(cells: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cells)
    if total == 0:
        return {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0, "avg_latency_ms": 0, "hallucination_rate": 0.0, "source_usage_rate": 0.0}
    passed = sum(1 for cell in cells if cell.get("status") == "pass")
    skipped = sum(1 for cell in cells if cell.get("status") == "skipped")
    executed = total - skipped
    failed = sum(1 for cell in cells if cell.get("status") in {"fail", "failed"})
    hallucinated = sum(1 for cell in cells if cell.get("status") != "skipped" and cell.get("hallucinated"))
    source_used = sum(1 for cell in cells if cell.get("status") != "skipped" and cell.get("used_source"))
    direct = sum(1 for cell in cells if cell.get("status") != "skipped" and cell.get("direct", True))
    source_quality_ok = sum(1 for cell in cells if cell.get("status") != "skipped" and cell.get("source_quality_ok", True))
    latencies = [int(cell.get("latency_ms") or 0) for cell in cells if cell.get("status") != "skipped" and int(cell.get("latency_ms") or 0) >= 0]
    return {
        "total": total,
        "executed": executed,
        "skipped": skipped,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / executed, 4) if executed else 0.0,
        "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
        "hallucination_rate": round(hallucinated / executed, 4) if executed else 0.0,
        "source_usage_rate": round(source_used / executed, 4) if executed else 0.0,
        "directness_rate": round(direct / executed, 4) if executed else 0.0,
        "source_quality_rate": round(source_quality_ok / executed, 4) if executed else 0.0,
    }


def _summary(cells: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate = _aggregate_cells(cells)
    return {
        "total_cells": aggregate["total"],
        "executed_cells": aggregate["executed"],
        "skipped_cells": aggregate["skipped"],
        "passed_cells": aggregate["passed"],
        "failed_cells": aggregate["failed"],
        "pass_rate": aggregate["pass_rate"],
        "avg_latency_ms": aggregate["avg_latency_ms"],
        "hallucination_rate": aggregate["hallucination_rate"],
        "source_usage_rate": aggregate["source_usage_rate"],
        "directness_rate": aggregate["directness_rate"],
        "source_quality_rate": aggregate["source_quality_rate"],
    }


def _thai_ok(category: str, answer: str) -> bool:
    if category != "thai":
        return False
    return bool(any("\u0e00" <= char <= "\u0e7f" for char in answer))


def _matrix_markdown(matrix: dict[str, Any]) -> str:
    lines = [
        "# Chat Live Quality Report",
        "",
        "## Summary",
        "",
        f"- Total cells: {matrix.get('summary', {}).get('total_cells', 0)}",
        f"- Skipped cells: {matrix.get('summary', {}).get('skipped_cells', 0)}",
        f"- Pass rate: {matrix.get('summary', {}).get('pass_rate', 0)}",
        f"- Avg latency ms: {matrix.get('summary', {}).get('avg_latency_ms', 0)}",
        f"- Hallucination rate: {matrix.get('summary', {}).get('hallucination_rate', 0)}",
        f"- Directness rate: {matrix.get('summary', {}).get('directness_rate', 0)}",
        f"- Source quality rate: {matrix.get('summary', {}).get('source_quality_rate', 0)}",
        f"- Variant: {matrix.get('summary', {}).get('variant', 'default')}",
        "",
        "## Cells",
        "",
        "| Model | Category | Status | Score | Attempts | Latency ms | Loop | Iters | Path ms | Provider | Direct | Source quality | Hallucinated | Sources |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|",
    ]
    for cell in matrix.get("cells", []):
        lines.append(
            f"| {cell.get('model', '')} | {cell.get('category', '')} | {cell.get('status', '')} | "
            f"{cell.get('score', 0)} | {cell.get('attempts', 1)} | {cell.get('latency_ms', 0)} | "
            f"{bool(cell.get('entered_tool_loop'))} | {int(cell.get('research_iterations') or 0)} | {int(cell.get('answer_path_ms') or 0)} | "
            f"{cell.get('search_provider') or ''} | {bool(cell.get('direct', True))} | {bool(cell.get('source_quality_ok', True))} | "
            f"{bool(cell.get('hallucinated'))} | {bool(cell.get('used_source'))} |"
        )
    return "\n".join(lines) + "\n"


def _run_chat_once_with_retries(
    run_chat_once: RunChatOnce,
    prompt: str,
    *,
    model: str,
    effort: str,
    web_settings: dict[str, str],
    tool_research_routes: tuple[str, ...] | None,
    retry_attempts: int,
    retry_backoff_seconds: float,
) -> tuple[dict[str, Any], int]:
    max_attempts = max(1, int(retry_attempts) + 1)
    attempts = 0
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        try:
            return (
                _call_run_chat_once(
                    run_chat_once,
                    prompt,
                    model=model,
                    effort=effort,
                    web_settings=web_settings,
                    tool_research_routes=tool_research_routes,
                ),
                attempts,
            )
        except Exception as exc:
            last_error = exc
            setattr(exc, "_quality_eval_attempts", attempts)
            if attempt >= max_attempts or not _is_retryable_provider_error(exc):
                raise
            if retry_backoff_seconds > 0:
                time.sleep(retry_backoff_seconds)
    if last_error is not None:
        raise last_error
    raise RuntimeError("quality runner retry loop ended without a result")


def _is_retryable_provider_error(exc: Exception) -> bool:
    text = str(exc).casefold()
    return any(
        marker in text
        for marker in (
            "429",
            "rate limit",
            "rate_limit",
            "temporarily overloaded",
            "overloaded",
            "too many requests",
        )
    )


def _skip_reason(exc: Exception) -> str:
    text = str(exc).casefold()
    if any(marker in text for marker in ("402", "insufficient credit", "billing required", "payment required", "quota exceeded", "no credit")):
        return "billing_required"
    if any(marker in text for marker in ("invalid api key", "unauthorized", "401", "403", "permission denied")):
        return "auth_required"
    return ""


def _attempts_from_error(exc: Exception) -> int:
    try:
        return max(1, int(getattr(exc, "_quality_eval_attempts", 1)))
    except (TypeError, ValueError):
        return 1


def _call_run_chat_once(
    callback: RunChatOnce,
    prompt: str,
    *,
    model: str,
    effort: str,
    web_settings: dict[str, str],
    tool_research_routes: tuple[str, ...] | None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model,
        "effort": effort,
        "web_settings": web_settings,
    }
    if _accepts_keyword(callback, "tool_research_routes"):
        kwargs["tool_research_routes"] = tool_research_routes
    return callback(prompt, **kwargs)


def _accepts_keyword(callback: RunChatOnce, name: str) -> bool:
    try:
        signature = inspect.signature(callback)
    except (TypeError, ValueError):
        return True
    for parameter in signature.parameters.values():
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            return True
    return name in signature.parameters


def _route_variant(tool_research_routes: tuple[str, ...] | None) -> str:
    # "default" in reports before 2026-07-03 meant LEGACY (all routes). After the
    # gated tuple became the config default, an unlabeled run means gated — the
    # label must say so, or A/B comparisons against archived reports silently
    # compare gated-vs-gated.
    if tool_research_routes is None:
        return "default:gated"
    if tool_research_routes == LEGACY_ROUTES:
        return "legacy"
    return "routes:" + ",".join(str(item) for item in tool_research_routes)


def _parse_routes(value: str) -> tuple[str, ...] | None:
    routes = tuple(item.strip() for item in str(value or "").split(",") if item.strip())
    if routes and all(item.casefold() == "legacy" for item in routes):
        return LEGACY_ROUTES
    return routes or None


if __name__ == "__main__":
    raise SystemExit(main())
