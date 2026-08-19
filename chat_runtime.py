from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Mapping


CHAT_SYSTEM_PROMPT = (
    "Be a warm, capable conversational assistant. Talk naturally with the user, answer general questions, "
    "help them think, explain ideas clearly, and generate code in-chat when useful. "
    "Use only capabilities that are actually provided in the current request/runtime, and only claim tool access "
    "after those tools are available. If a request depends on missing local project evidence, unavailable file "
    "access, or a side-effecting action, briefly ask for the needed context or handoff only when that boundary "
    "blocks the answer. Use web/search connectors for current facts when available. Keep memory scoped to the "
    "active mode/session, and avoid volunteering mode or boundary explanations in ordinary answers."
)


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().casefold() in {"1", "true", "yes", "on", "enabled"}


def _env_float(name: str, *, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _env_choice(name: str, *, default: str, choices: set[str]) -> str:
    value = str(os.environ.get(name) or default).strip().casefold()
    return value if value in choices else default


@dataclass(frozen=True)
class ChatEffortConfig:
    temperature: float
    max_tokens: int
    history_messages: int
    # Per-model-turn budget. A single shared 90-second request timeout made
    # higher-effort Chat work fail before it could complete a difficult turn.
    model_timeout_seconds: float = 90.0
    research_max_iterations: int = 6
    research_max_fetch: int = 5
    # Effort-scaled steering for the search->open->ground cycle (chat_router.py's
    # web/mixed prompt block). Data only, so the sidecar never needs an if/elif on
    # effort to decide how hard the model should keep searching.
    search_depth_hint: str = ""

    def generation_settings(self) -> dict[str, int | float]:
        return {"temperature": self.temperature, "max_tokens": self.max_tokens}


@dataclass(frozen=True)
class ChatRuntimeConfig:
    system_prompt: str = CHAT_SYSTEM_PROMPT
    efforts: Mapping[str, ChatEffortConfig] = field(
        default_factory=lambda: {
            "Low": ChatEffortConfig(
                temperature=0.3,
                max_tokens=1024,
                history_messages=4,
                model_timeout_seconds=90.0,
                research_max_iterations=4,
                research_max_fetch=3,
                search_depth_hint="Search depth: open at least the single best source before answering.",
            ),
            "Medium": ChatEffortConfig(
                temperature=0.5,
                max_tokens=4096,
                history_messages=12,
                model_timeout_seconds=180.0,
                research_max_iterations=6,
                research_max_fetch=5,
                search_depth_hint="Search depth: open the 2-3 most relevant sources before answering.",
            ),
            "High": ChatEffortConfig(
                temperature=0.6,
                max_tokens=8192,
                history_messages=20,
                model_timeout_seconds=300.0,
                research_max_iterations=12,
                research_max_fetch=8,
                search_depth_hint="Search depth: search more than once if the first results are weak, and open several sources before answering.",
            ),
        }
    )
    default_effort: str = "Medium"
    tool_research_providers: tuple[str, ...] = ("openai", "gemini", "anthropic", "zai", "deepseek")
    # Route categories that enter the tool-research loop. The 2026-07-03 live A/B
    # (work_logs/chat-quality-live-20260703-115752 vs -120123) showed gating raises
    # pass rate (0.786 -> 0.857), directness (0.93 -> 1.0) and cuts general-route
    # latency, so the gated tuple is now the DEFAULT. "memory" stays excluded.
    # None = legacy behavior (every route except "memory"). Note: when the MCP
    # toggle is on for a request, the sidecar bypasses this gate — available tools
    # mean the model must be able to reach them regardless of route.
    tool_research_routes: tuple[str, ...] | None = ("web", "project", "mixed", "mcp")
    playwright_fetch_enabled: bool = field(
        default_factory=lambda: _env_bool("COWORK_CHAT_PLAYWRIGHT_FETCH", default=False)
    )
    model_timeout_seconds: float = field(
        default_factory=lambda: _env_float("COWORK_CHAT_MODEL_TIMEOUT", default=90.0)
    )
    search_api_provider: str = field(
        default_factory=lambda: str(os.environ.get("COWORK_SEARCH_API_PROVIDER") or "brave").strip() or "brave"
    )
    search_api_key: str = field(
        default_factory=lambda: str(os.environ.get("COWORK_SEARCH_API_KEY") or "").strip()
    )
    artifacts_enabled: bool = field(
        default_factory=lambda: _env_bool("COWORK_CHAT_ARTIFACTS", default=True)
    )
    code_execution_enabled: bool = field(
        default_factory=lambda: _env_bool("COWORK_CHAT_CODE_EXEC", default=False)
    )
    code_execution_sandbox: str = field(
        default_factory=lambda: _env_choice(
            "COWORK_CHAT_CODE_EXEC_SANDBOX",
            default="pyodide",
            choices={"pyodide", "legacy_subprocess"},
        )
    )
    mcp_enabled: bool = field(
        default_factory=lambda: _env_bool("COWORK_CHAT_MCP", default=False)
    )
    semantic_memory_enabled: bool = field(
        default_factory=lambda: _env_bool("COWORK_CHAT_SEMANTIC_MEMORY", default=False)
    )

    @property
    def search_api_enabled(self) -> bool:
        return bool(self.search_api_key.strip())

    def normalize_effort(self, value: object) -> str:
        requested = str(value or "").strip()
        return requested if requested in self.efforts else self.default_effort

    def effort_config(self, value: object) -> ChatEffortConfig:
        return self.efforts[self.normalize_effort(value)]

    def model_timeout_for_effort(self, value: object) -> float:
        """Return the per-turn Chat timeout, respecting a longer global override."""
        effort_config = value if isinstance(value, ChatEffortConfig) else self.effort_config(value)
        effort_timeout = float(effort_config.model_timeout_seconds)
        return max(float(self.model_timeout_seconds), effort_timeout)


DEFAULT_CHAT_RUNTIME_CONFIG = ChatRuntimeConfig()
