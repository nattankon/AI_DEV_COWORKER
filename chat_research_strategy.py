from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
import re


_THAI_RE = re.compile(r"[\u0E00-\u0E7F]")

_QUERY_TYPE_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "keywords": ("api", "sdk", "documentation", "docs", "openai", "gemini", "deepseek", "z.ai", "zai"),
        "query_templates": ("{q} official documentation",),
        "source_hints": (
            {"source_type": "official-docs", "hint": "Prefer official API/model documentation over blogs."},
        ),
    },
    {
        "keywords": ("price", "pricing", "cost", "quota", "rate limit", "billing", "credit", "subscription"),
        "query_templates": ("{q} official pricing", "{q} official status quota limits"),
        "source_hints": (
            {"source_type": "pricing", "hint": "Prefer official pricing, billing, quota, or status pages for costs and limits."},
            {"source_type": "status", "hint": "Use provider status pages when the question is about availability, outages, or overload."},
        ),
    },
    {
        "keywords": ("github", "repo", "repository", "readme", "release notes", "changelog", "issue", "pull request"),
        "query_templates": ("{q} site:github.com",),
        "source_hints": (
            {"source_type": "repository", "hint": "Prefer the repository README, releases, changelog, issues, or pull requests."},
        ),
    },
    {
        "keywords": ("news", "latest", "today", "current", "ล่าสุด", "วันนี้", "ปัจจุบัน"),
        "query_templates": ("{q} latest news",),
        "source_hints": (
            {"source_type": "news", "hint": "Prefer recent primary sources or reputable news reports for event claims."},
        ),
    },
)


@dataclass(frozen=True)
class ResearchPlan:
    original_query: str
    answer_language: str
    queries: tuple[str, ...]
    source_preferences: tuple[dict[str, str], ...] = field(default_factory=tuple)


def build_research_plan(query: str, *, profiles: Iterable[dict[str, Any]] | None = None) -> ResearchPlan:
    original = _clean_query(query)
    language = "th" if _THAI_RE.search(original) else "en"
    queries = [original] if original else []
    preferences: list[dict[str, str]] = []

    for profile in profiles if profiles is not None else _QUERY_TYPE_PROFILES:
        if not _profile_matches(original, profile):
            continue
        for template in _profile_templates(profile):
            queries.append(template.format(q=original))
        preferences.extend(_profile_hints(profile))

    return ResearchPlan(
        original_query=original,
        answer_language=language,
        queries=tuple(dict.fromkeys(_collapse_space(item) for item in queries if _collapse_space(item))),
        source_preferences=tuple(preferences),
    )


def _profile_matches(query: str, profile: dict[str, Any]) -> bool:
    text = query.casefold()
    return any(keyword and keyword in text for keyword in _profile_keywords(profile))


def _profile_keywords(profile: dict[str, Any]) -> tuple[str, ...]:
    raw = profile.get("keywords", ())
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(str(item).casefold() for item in raw if str(item or "").strip())


def _profile_templates(profile: dict[str, Any]) -> tuple[str, ...]:
    raw = profile.get("query_templates", ())
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(str(item) for item in raw if "{q}" in str(item))


def _profile_hints(profile: dict[str, Any]) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    raw = profile.get("source_hints", ())
    if not isinstance(raw, (list, tuple)):
        return hints
    for item in raw:
        if not isinstance(item, dict):
            continue
        source_type = str(item.get("source_type") or "").strip()
        hint = str(item.get("hint") or "").strip()
        if source_type:
            hints.append({"source_type": source_type, "hint": hint})
    return hints


def _collapse_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _clean_query(value: str) -> str:
    text = _collapse_space(value)
    replacements = (
        ("ช่วยหาข้อมูล", ""),
        ("ช่วยหา", ""),
        ("ขอข้อมูล", ""),
        ("ของประเทศไทย", "ประเทศไทย"),
        ("ขอ", ""),
        ("ให้หน่อย", ""),
        ("หน่อย", ""),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    text = re.sub(r"[?？!！]+", " ", text)
    return _collapse_space(text)
