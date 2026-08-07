from __future__ import annotations

import re
from dataclasses import dataclass


_PROJECT_TERMS = (
    "โปรเจกต์",
    "โปรแกรมนี้",
    "แอปนี้",
    "ระบบนี้",
    "งานนี้",
    "ทำถึงไหน",
    "สถานะ",
    "ไฟล์",
    "โค้ด",
    "workspace",
    "project",
    "repo",
    "repository",
    "codebase",
)
_WEB_TERMS = (
    "ล่าสุด",
    "วันนี้",
    "ปี 2026",
    "2026",
    "current",
    "latest",
    "today",
    "news",
    "pricing",
    "ราคา",
)
_MEMORY_TERMS = (
    "จำ",
    "ความจำ",
    "สไตล์",
    "นิสัย",
    "ผมชอบ",
    "ฉันชอบ",
    "remember",
    "memory",
    "preference",
)
# "mcp" alone is specific enough; "connector(s)" is a common software/hardware
# noun, so it only counts alongside an app-context term — otherwise "which
# connector does HDMI use" would enter the tool loop and pay real search latency.
_MCP_STRONG_PATTERN = re.compile(r"\bmcp\b")
_MCP_WEAK_PATTERN = re.compile(r"\bconnectors?\b")
_MCP_CONTEXT_TERMS = (
    "server",
    "tool",
    "tools",
    "plugin",
    "enable",
    "enabled",
    "available",
    "configured",
    "เชื่อมต่อ",
    "ตั้งค่า",
)


@dataclass(frozen=True)
class ChatRoute:
    category: str
    reasons: tuple[str, ...] = ()
    needs_personal_memory: bool = True
    needs_project_context: bool = False
    needs_web_context: bool = False

    def to_prompt_block(self, *, has_web_context: bool = False, search_depth_hint: str = "") -> str:
        lines = [
            f"## Chat Route: {self.category}",
            "Use this routing decision to choose context. Do not invent missing retrieved facts.",
            "Separate facts, assumptions, and suggestions. Use source labels when available, and say what is missing when evidence is insufficient.",
        ]
        if self.reasons:
            lines.append("Reasons: " + "; ".join(self.reasons))
        if self.category == "general":
            lines.append("Answer from the selected model and relevant personal memory only.")
        if self.needs_project_context:
            lines.append("If project-specific evidence is not attached or otherwise provided, briefly ask for the missing context or a workspace handoff only when that evidence is required.")
        if self.needs_web_context and has_web_context:
            lines.append("Use the Chat Web Context for current or external facts. Cite web source labels inline and end with a Sources section listing the used URLs.")
            lines.append(
                "Before stating any current or external fact, call web_search, then web_fetch the most relevant "
                "results, and ground every such fact in fetched evidence with a [web:N] citation. If you have not "
                "fetched evidence for a current fact, say so instead of answering from memory."
            )
            if search_depth_hint:
                lines.append(search_depth_hint)
        elif self.needs_web_context:
            lines.append("No web connector is available yet. Do not answer current or external facts from stale model memory. If the answer requires current external facts, say that live/source lookup is not available in this app yet and state what source would be needed.")
        if self.category == "mcp":
            lines.append("Use the read-only MCP diagnostics/tools to check real connector state before answering. Never guess whether a connector exists or what tools it has.")
        if self.category == "memory":
            lines.append("Prioritize Chat personal memory and clearly state uncertainty when memory is missing.")
        if self.category == "mixed":
            lines.append("Separate model knowledge, remembered preferences, missing project evidence, and missing web evidence. Do not merge unsupported current facts with model knowledge.")
        return "\n".join(lines)


def classify_chat_prompt(prompt: str) -> ChatRoute:
    text = re.sub(r"\s+", " ", str(prompt or "").strip().casefold())
    has_project = any(term.casefold() in text for term in _PROJECT_TERMS)
    has_web = any(term.casefold() in text for term in _WEB_TERMS)
    has_memory = any(term.casefold() in text for term in _MEMORY_TERMS)
    has_mcp = bool(_MCP_STRONG_PATTERN.search(text)) or (
        bool(_MCP_WEAK_PATTERN.search(text))
        and any(term.casefold() in text for term in _MCP_CONTEXT_TERMS)
    )
    reasons: list[str] = []
    if has_project:
        reasons.append("mentions project/workspace context")
    if has_web:
        reasons.append("asks for current or external facts")
    if has_memory:
        reasons.append("asks about remembered user preferences")
    if has_mcp:
        reasons.append("asks about MCP connectors or external tools")

    if has_project and has_web:
        return ChatRoute("mixed", tuple(reasons), needs_project_context=True, needs_web_context=True)
    if has_project:
        return ChatRoute("project", tuple(reasons), needs_project_context=True)
    if has_web:
        return ChatRoute("web", tuple(reasons), needs_web_context=True)
    if has_mcp:
        # MCP questions need the tool loop (diagnostics/read-only tools live there);
        # this category is part of the default tool_research_routes tuple.
        return ChatRoute("mcp", tuple(reasons))
    if has_memory:
        return ChatRoute("memory", tuple(reasons), needs_personal_memory=True)
    return ChatRoute("general", ("ordinary knowledge question",), needs_personal_memory=True)
