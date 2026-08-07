from __future__ import annotations

from typing import Any
from datetime import date
import re

try:
    from .chat_answer_guard import validate_answer
except ImportError:
    from chat_answer_guard import validate_answer


def quality_eval_cases() -> list[dict[str, Any]]:
    return [
        {
            "category": "general",
            "prompt": "Explain what a local-first AI coworker app is in practical terms.",
            "checks": ["answers directly", "does not claim workspace access", "uses clear examples"],
        },
        {
            "category": "web",
            # A web case must have ONE well-defined, currently-true, citeable answer,
            # or it cannot measure search quality. The old "a current API model"
            # prompt was ambiguous (which model?), so a good assistant either asked
            # to clarify or honestly reported no relevant results (2026-08-05 run) -
            # both scored as fail through no fault of the model. This asks for a
            # single fact that lives on one authoritative page.
            "prompt": "What is the latest stable release version of Python 3? Search the web, then cite the source you used.",
            "checks": ["searches and fetches a source", "cites the source", "grounds the version in fetched evidence"],
        },
        {
            "category": "thai",
            "prompt": "อธิบายเป็นภาษาไทยว่า Chat, Cowork และ Code ในโปรแกรมนี้ควรแยกหน้าที่กันอย่างไร พร้อมตัวอย่างการใช้งาน 3 ข้อ",
            "checks": ["keeps Thai answer language", "answers the requested comparison", "gives concrete examples"],
        },
        {
            "category": "attachment",
            "prompt": "Summarize this attached note and cite the attachment label.",
            "checks": ["uses explicit attachment only", "cites attachment label", "does not browse workspace"],
        },
        {
            "category": "coding",
            "prompt": "Generate a small Lua module example and explain how it works.",
            "checks": ["produces runnable-looking code", "explains tradeoffs", "does not mutate files"],
        },
        {
            "category": "memory",
            "prompt": "Do you remember my preferred answer style?",
            "checks": ["uses Chat memory if present", "states uncertainty if absent", "does not infer project facts"],
        },
        {
            "category": "mcp",
            "prompt": "Check whether the Roblox MCP connector is available and list its tools.",
            "checks": ["uses read-only MCP diagnostics", "does not pretend if missing", "does not call side-effecting tools"],
            # An MCP answer produced without entering the tool loop is a pretend
            # answer — the 2026-07-03 gated run exposed this (mcp cells "passed"
            # with Loop=False). The runner enables the mcp toggle for this case.
            "requires_tool_loop": True,
            "web_settings": {"mcp": "on"},
        },
    ]


def quality_eval_cases_for_category(category: str = "") -> list[dict[str, Any]]:
    return [
        {
            "category": str(item.get("category") or ""),
            "prompt": str(item.get("prompt") or ""),
            "checks": list(item.get("checks") or []),
        }
        for item in quality_eval_cases()
        if not category or str(item.get("category") or "") == category
    ]


def run_quality_eval_snapshot(results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Score supplied answers against fixture cases without calling a live model."""
    supplied = {
        str(item.get("category") or ""): item
        for item in (results if isinstance(results, list) else [])
        if isinstance(item, dict)
    }
    evaluations: list[dict[str, Any]] = []
    for case in quality_eval_cases():
        category = str(case.get("category") or "")
        payload = supplied.get(category, {})
        evaluations.append(
            {
                "prompt": case.get("prompt", ""),
                **evaluate_case_result(
                    case,
                    answer=str(payload.get("answer") or ""),
                    sources=payload.get("sources") if isinstance(payload.get("sources"), list) else None,
                    evidence=str(payload.get("evidence") or ""),
                    latency_ms=payload.get("latency_ms"),
                ),
            }
        )
    passed = sum(1 for item in evaluations if item.get("status") == "pass")
    return {
        "count": len(evaluations),
        "passed": passed,
        "failed": len(evaluations) - passed,
        "status": "pass" if passed == len(evaluations) else "fail",
        "results": evaluations,
    }


def _has_thai(text: str) -> bool:
    return bool(re.search(r"[\u0e00-\u0e7f]", str(text or "")))


def evaluate_case_result(
    case: dict[str, Any],
    *,
    answer: str,
    sources: list[dict[str, Any]] | None = None,
    evidence: str = "",
    latency_ms: int | float | None = None,
    entered_tool_loop: bool | None = None,
) -> dict[str, Any]:
    category = str(case.get("category") or "general")
    answer_text = str(answer or "").strip()
    source_items = sources if isinstance(sources, list) else []
    findings: list[str] = []
    score = 0
    if case.get("requires_tool_loop") and entered_tool_loop is False:
        findings.append("answered without entering the tool loop although this case requires tools")
    hallucinated = False
    direct = not _looks_indirect_non_answer(answer_text)
    source_quality_ok = True

    if answer_text:
        score += 1
    else:
        findings.append("empty answer")

    if answer_text and not direct:
        findings.append("not direct: asks for more context instead of answering")

    if category == "web":
        has_source_marker = "[web:" in answer_text or "sources" in answer_text.casefold()
        if source_items and has_source_marker:
            score += 2
        else:
            findings.append("missing sources")
        source_quality_ok = _web_source_quality_ok(source_items)
        if source_items and not source_quality_ok:
            findings.append("low source quality: no explicit high-quality source metadata")
    elif category == "thai":
        if _has_thai(answer_text):
            score += 2
        else:
            findings.append("answer is not Thai")
    elif category == "attachment":
        if any(marker in answer_text.casefold() for marker in ("attached", "attachment", "source", "ไฟล์", "แนบ")):
            score += 2
        else:
            findings.append("attachment label not referenced")
    elif category == "mcp":
        if any(marker in answer_text.casefold() for marker in ("mcp", "connector", "tool", "ไม่พบ", "available")):
            score += 2
        else:
            findings.append("connector status not addressed")
    else:
        if len(answer_text) >= 40:
            score += 2
        else:
            findings.append("answer is too short")

    if latency_ms is not None:
        try:
            latency_value = float(latency_ms)
        except (TypeError, ValueError):
            latency_value = -1
        if 0 <= latency_value <= 30000:
            score += 1
        else:
            findings.append("latency outside target")

    guard = validate_answer(
        answer_text,
        evidence_corpus=str(evidence or ""),
        sources=_sources_with_indices(source_items),
        allow=_guard_allow_values(str(case.get("prompt") or "")),
    )
    if not guard.ok:
        hallucinated = True
        findings.append("hallucinated: " + "; ".join(guard.violations))

    hard_failures = {
        "empty answer",
        "missing sources",
        "answered without entering the tool loop although this case requires tools",
    }
    has_hard_failure = any(item in findings for item in hard_failures) or not direct or not source_quality_ok
    status = "pass" if score >= 3 and not hallucinated and not has_hard_failure else "fail"
    return {
        "category": category,
        "score": score,
        "status": status,
        "findings": findings,
        "hallucinated": hallucinated,
        "direct": direct,
        "source_quality_ok": source_quality_ok,
        "checks": list(case.get("checks") or []),
    }


def _looks_indirect_non_answer(text: str) -> bool:
    normalized = " ".join(str(text or "").casefold().split())
    if not normalized:
        return False
    markers = (
        "could not find specific information",
        "could not find specific current information",
        "cannot find specific information",
        "cannot find specific current information",
        "unable to find specific information",
        "unable to find specific current information",
        "cannot provide a practical",
        "cannot provide a specific",
        "please provide more context",
        "please provide additional context",
        "please specify",
        "need more information",
        "need additional information",
        "if you have a specific",
        "กรุณาระบุหัวข้อ",
        "โปรดระบุหัวข้อ",
        "กรุณาระบุข้อมูล",
        "โปรดระบุข้อมูล",
        "ข้อมูลเฉพาะที่คุณต้องการ",
        "ต้องการข้อมูลอะไร",
    )
    return any(marker in normalized for marker in markers)


def _web_source_quality_ok(sources: list[dict[str, Any]]) -> bool:
    metadata_sources = [
        source
        for source in sources
        if isinstance(source, dict) and ("source_type" in source or "quality_score" in source)
    ]
    if not metadata_sources:
        return True
    trusted_types = {
        "official",
        "official-docs",
        "pricing",
        "status",
        "repository",
        "news",
        "fetched-data",
        "source-adapter",
        # A page the model actually OPENED and grounded on is a real source - the
        # canonical good case, stronger than a search snippet. The 2026-08-06 run
        # proved the gap: both models cited a fetched python.org page (correct,
        # grounded, 0 hallucination) yet scored "low source quality" because
        # "fetched-page" was excluded here while adapter "fetched-data" was trusted.
        "fetched-page",
        "playwright-page",
    }
    for source in metadata_sources:
        source_type = str(source.get("source_type") or "").casefold()
        try:
            quality_score = int(source.get("quality_score") or 0)
        except (TypeError, ValueError):
            quality_score = 0
        if source_type in trusted_types or quality_score >= 2:
            return True
    return False


def _sources_with_indices(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            continue
        next_source = dict(source)
        next_source.setdefault("index", index)
        normalized.append(next_source)
    return normalized


def _guard_allow_values(prompt: str) -> tuple[str, ...]:
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
