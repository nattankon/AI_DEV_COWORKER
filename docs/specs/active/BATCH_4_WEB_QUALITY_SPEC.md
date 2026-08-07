# Batch 4 — Web-category quality (spec for the Sonnet 5 implementer)

> Implementer: Sonnet 5. Reviewer: Opus 4.8. Offline-only work (no live/network in the
> default suite). Definition of Done: backend `python -m unittest discover -s test` and
> frontend `npx vitest run` both green → hand back for Opus review → log to
> `work_logs/track-a-review-log.md`.

## Why (the evidence)

The 2026-07-03 live A/B (`work_logs/chat-quality-live-20260703-115752.md` and `-120123.md`)
shows **web is the ONLY consistently failing category** for both models:
- `zai:glm-5.2` web: 1 loop iteration, **0 sources returned**, source_quality fail — it
  answered a current-fact question WITHOUT searching.
- `zai:glm-4.5-flash` web: searched but source_quality fail — low-quality sources.
Also the 2026-07-03 smoke reported `search_provider: "not_checked"` — no Brave key in that
environment, so web search silently ran on the scrape fallback (low quality by nature),
and nothing surfaced that fact.

## Scope — two levers, both offline-testable

### Lever A — Search-persistence steering (web + mixed routes)

Problem: `ChatRoute.to_prompt_block(has_web_context=True)` (`chat_router.py:68-69`) *invites*
citing but does not make "answer a current/external fact without searching" clearly wrong.
A capable model (glm-5.2) skipped searching entirely.

Do:
- Strengthen the `web`/`mixed` branch of `ChatRoute.to_prompt_block` so it REQUIRES the
  search→open→ground cycle before stating any current/external fact: e.g. "Before stating
  any current or external fact, call web_search, then web_fetch the most relevant results,
  and ground every such fact in fetched evidence with a [web:N] citation. If you have not
  fetched evidence for a current fact, say so instead of answering from memory." Keep it
  topic-agnostic (D1 — no domain names).
- Make the push effort-scaled *as data, not code branches*. Add an optional
  `search_depth_hint: str = ""` parameter to `to_prompt_block` (or a small helper) that the
  sidecar fills from effort (Low = "open at least the single best source"; Medium = "open
  the 2-3 most relevant sources"; High = "search more than once if the first results are
  weak, and open several sources"). The mapping lives in `chat_runtime.py`'s effort config
  as data (e.g. a `search_depth_hint` field on `ChatEffortConfig`), NOT as if/elif in the
  sidecar.
- Do NOT touch the answer guard, `validate_answer`, or the forced-final-answer path. This is
  prompt steering only.

### Lever B — Search-provider visibility

Problem: nothing tells the user (or the scorecard) whether web search used the Brave API or
the scrape fallback, so a missing key silently caps web quality.

Do:
- The Chat research diagnostics returned from `_run_plain_chat(return_diagnostics=True)`
  should include `search_provider` = `"brave_api"` when a real Brave provider is active for
  the request, else `"scrape_fallback"`. Derive it from the SAME resolution the request
  uses (`_chat_web_connector` / `get_search_provider`), do not re-read env separately.
- Surface it in the live quality report: add a `search_provider` column to the cells table
  in `chat_quality_runner._matrix_markdown` and carry it on each cell. (`run_chat_once`
  already returns a diagnostics dict — thread the new field through like
  `entered_tool_loop`.)
- Emit it once to the frontend as part of the existing `chat_web_search` telemetry event
  (add a `provider` field) so the UI *can* show "searched via Brave / basic scrape" later —
  no new UI component required this batch, just the data.

## Constraints

- Offline: every test uses fakes; no network, no model calls, no Brave calls in the suite.
- D1: no topic/vendor names in control flow; effort→hint mapping is data.
- Behavior-preserving for non-web routes and for `web_mode="off"`.
- Don't regress the 370 backend / 134 frontend tests.

## Tests to add

- Router: web/mixed prompt block contains the "search before stating current facts"
  requirement; general/memory blocks do NOT.
- Effort→depth-hint mapping is data-driven and appears in the web prompt block at Low vs
  High (assert different hint text).
- Diagnostics: with a fake Brave provider configured → diagnostics `search_provider` is
  `"brave_api"`; with none → `"scrape_fallback"`.
- Runner: the new column/field is populated from the fake `run_chat_once` payload; markdown
  includes the `search_provider` column.
- `chat_web_search` telemetry event carries `provider`.

## Explicit non-goals

- No live re-run (that's the user's call; needs credits/network).
- No change to source-quality SCORING (`_source_quality_score`) — recalibration must be
  done later with the quality panel as referee, not guessed here.
- No new source adapters or extractor changes.
