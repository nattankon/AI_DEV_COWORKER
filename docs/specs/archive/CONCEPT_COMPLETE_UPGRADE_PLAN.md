# Concept-Complete Chatbot — Master Spec & Upgrade Plan

> **Purpose:** one self-contained document (readable cold) capturing the full concept of the
> Chat assistant — how the model should *think/operate*, plus everything to ADD / FIX / UPGRADE
> to reach that concept. Hand to Codex for implementation; bring back for a single consolidated
> review. English throughout; Thai strings are literal test data (keep verbatim).
>
> **Companion docs:** `TRACK_A_RESEARCH_FOUNDATION_DESIGN.md` (the foundation, now shipped) and
> `work_logs/track-a-review-log.md` (per-step review trail). This plan is "everything after Track A".

---

## 0. Vision (the "why")

A general-purpose chat assistant matching the **experience of Gemini / ChatGPT / Claude chat**.
Three layers: **(1) Chatbot → (2) Cowork → (3) Code CLI**. Chat is built first because strong
code assistance depends on strong **research/retrieval**; the retrieval capability built here is
the reusable foundation for layers 2-3. Models are pluggable via an **API-model system**
(`zai:` GLM-4.5 for testing, plus `openai:`, `gemini:`, `anthropic:`). **Intelligence comes from
the model; our job is the orchestration** so a capable model performs well and a weaker one
degrades gracefully. Never tune prompts to one model's quirks.

---

## 1. How the LM should THINK & OPERATE (the behavioral concept)

This is the target operating model — implement the system so the model can and must behave this way.

1. **Agentic research loop (model-driven).** For current/external facts the model itself drives:
   decide to search → `web_search` → read results → decide if it has enough → `web_fetch` the most
   promising sources → if still thin, search/fetch again → synthesize. NOT a fixed one-shot
   pipeline. (Already enabled via `tool_loop` + `WebResearchTools`.)
2. **Grounding discipline.** State exact prices/dates/version numbers/table values ONLY when they
   appear in fetched evidence. Never infer from titles, hints, or page structure.
3. **Honesty over confidence (the most important behavior).** If evidence is missing, blocked
   (captcha), or a placeholder/skeleton, SAY SO and name the source to check — never fabricate and
   never present placeholder data as real. "I couldn't extract the real price, check EPPO directly"
   beats a confident wrong number.
4. **Partial-date integrity.** A day+month with no year in evidence stays partial. Never append or
   convert a year (not BE, not CE) unless that exact year is in evidence.
5. **Citations.** Cite `[web:N]` using the index from tool results; end with a Sources list. Every
   citation must map to a real fetched source.
6. **Know when NOT to search.** General/parametric questions are answered directly (no web call,
   no latency). Only reach for the web on current/external/factual-lookup questions.
7. **Separate facts / assumptions / suggestions.** Make uncertainty explicit.

These rules already live partly in `RESEARCH_INSTRUCTIONS` (chat_research_runner.py) and the guard
(chat_answer_guard.py). The upgrades below close the gaps where reality breaks these rules.

---

## 2. Current state (Track A — shipped, 149 tests green)

- `tool_loop.py` — shared agentic loop (Cowork refactored onto it; behavior-preserved).
- `chat_web_tools.py` — `WebResearchTools`: model-driven `web_search` / `web_fetch`, `sources()`
  (the `[web:N]` registry), `evidence_corpus()`.
- `chat_research_runner.py` — `ChatResearchRunner` (web-only, max_iterations=6, generation-aware).
- `chat_answer_guard.py` — deterministic, model-agnostic `validate_answer` (numbers/years/dates
  must be in evidence; citation validity; surgical `corrected_answer`).
- `ipc_sidecar.py` `_run_plain_chat` — provider-gated tool research
  (`ChatRuntimeConfig.tool_research_providers`) with `_legacy_web_chat` fallback when
  `used_tools` is False; telemetry `chat_research` / `chat_answer_guard`.
- `chat_web_connector.py` — generic `_extract_tables`, `_extract_page_evidence`, captcha detection.

**Validated end-to-end:** the architecture works (model grounds + cites + guard passes). The
remaining failures are **data quality**, not the loop/guard.

**Root-cause finding (2026-06-29, verified live):** Thai fuel sources defeat HTTP-only extraction —
`bangchak.co.th/th/oilprice` = Radware captcha; `oil-price.bangchak.co.th` = empty JS table;
`eppo.go.th` ships a placeholder table (caption "Loading....." , every cell "30.00") replaced by
JavaScript. The model faithfully reported the placeholder "30.00" and the guard correctly passed
it (the value WAS in evidence). **The bug is upstream extraction feeding JS skeletons as real data.**

---

## 3. ADD / FIX / UPGRADE (grouped by theme; each: problem → change → files → acceptance)

### Theme A — Data quality & truthfulness (HIGHEST priority; this is what makes answers correct)

**A1. Placeholder/skeleton detection (cheap, do first).**
- Problem: JS placeholder tables ("Loading.....", all-identical cells) are extracted as real data.
- Change: in `chat_web_connector.py` (`_extract_tables` / `_extract_page_evidence`), DROP a table when
  (a) its caption / nearby text contains `loading` / `กำลังโหลด`, OR (b) all numeric data cells are
  identical (uniform-fill). When dropped, the page yields no table evidence → the model must say
  "no real value extracted".
- Files: `chat_web_connector.py`, tests in `test/test_chat_web_connector.py`.
- Acceptance: an EPPO-style "Loading....." / uniform-30.00 table produces NO price evidence; a real
  varied table is unaffected.

**A2. XHR-first real extraction (the proper fix).**
- Problem: real prices live behind JS/XHR JSON endpoints, not in raw HTML.
- Change: add a generic **source data-adapter registry**: `{host -> adapter}` where an adapter knows
  the JSON/API endpoint and maps the JSON to structured `{label: value}` rows. Implement adapters for
  the Bangchak widget and EPPO (inspect their network calls to find the JSON endpoint). `web_fetch`
  consults the registry first; falls back to HTML extraction if no adapter.
- Files: new `chat_source_adapters.py`; wire into `chat_web_tools.py` `web_fetch` and/or
  `chat_web_connector.py`. Tests with captured JSON fixtures (no live network in tests).
- Acceptance: `web_fetch` on the Bangchak/EPPO data endpoint returns real per-type prices that differ
  by fuel type.

**A3. JS-aware fetch (Playwright) — last resort only.**
- Problem: some sources have neither usable HTML nor a discoverable XHR endpoint.
- Change: optional `PlaywrightFetcher` used only when (a) HTML extraction yields < N chars or a
  placeholder, AND (b) no adapter exists. 8s timeout; fall back to HTTP result if slow.
- Files: new `chat_playwright_fetch.py` (lazy import; feature-flagged). Keep out of the default test path.
- Acceptance: a known JS-only page yields real values; disabled flag → no Playwright dependency loaded.

**A4. Blocked/captcha routing.** Already detected; ensure a blocked source makes the model try another
source rather than surfacing the block (already partly handled in `_format_chat_web_context` — keep).

### Theme B — Guard upgrades (truthfulness enforcement)

**B1. Uniform-value suspicion (cross-check).** Even if A1 catches most, the guard should flag an answer
that presents a whole price table of identical values as suspicious (likely placeholder). File:
`chat_answer_guard.py`.

**B2. Partial-date vs allow-set fix (real bug found in smoke test).**
- Problem: the current year is in `allow`, so the model can attach the current year to a year-less
  evidence date and the guard won't catch it (smoke test produced "25 มิถุนายน 2026").
- Change: distinguish a **standalone year mention** (allowed via `allow`) from a **year attached to a
  date that appears year-less in evidence** (still forbidden, even if it's the current year). The
  partial-date check must key off the specific evidence date, independent of `allow`.
- Files: `chat_answer_guard.py` + a regression test.

**B3. (Deeper, optional) Association check.** A claimed `label: value` should map to an extracted
table ROW, not just exist somewhere in the corpus (membership). Hard; note as future hardening.

### Theme C — Smart web routing (when to search)

**C1.** Problem: `chat_router.py` `_WEB_TERMS` is a thin keyword list → under-triggers ("who is the
current PM") and over-triggers ("explain price equilibrium"). Change: for tool-capable providers,
prefer letting the MODEL decide whether to search (offer web tools + an instruction on when to use
them) rather than pre-classifying with keywords; keep the keyword router only as the gate for the
legacy path. Optionally add a tiny LLM intent pre-check. Files: `chat_router.py`, `ipc_sidecar.py`.
Acceptance: a general knowledge question answers with no web call; a current-events question searches.

### Theme D — Generic relevance & de-hardcoding (the oil vertical was a test fixture)

**D1.** Remove oil-specific code from the PRIMARY path: `_is_thai_oil_query`, `_has_oil_relevance`,
oil `_query_variants`, oil `_trusted_source_hints` / `_international_source_hints`, oil terms in
`_relevance_terms` / `_source_quality_score`. In tool-mode the model forms queries and picks sources,
so these are unnecessary. Keep (if anywhere) only behind the legacy path, not extended. Files:
`chat_web_connector.py`. Acceptance: no topic-specific branching in the tool-mode path; a non-oil
query (e.g. weather, a stock) works the same way.

**D2.** Query-derived relevance must tolerate Thai (no word boundaries); in tool-mode this matters
less because the model drives queries.

### Theme E — "Feel like frontier chat" (surface; chat layer only — was Track B)

**E1. Streaming output.** Problem: `OpenAIChatModel.complete()` blocks; one `cowork_log` with the full
answer → user stares at a blank screen. Change: add a streaming path (SSE deltas) emitting
incremental `cowork_log_delta` events to the frontend. Files: `cowork_agent.py` (a `stream()` method),
`ipc_sidecar.py`, `frontend/adapters/coworkBridge.js`, `frontend/components/MessageEntry.jsx`.
Note: streaming + the agentic tool loop interact — stream only the final answer turn, not tool turns.

**E2. Markdown rendering.** Problem: `MessageEntry.jsx` renders raw text (`whitespace-pre-wrap`); no
markdown lib in `frontend/` → code blocks, tables, bold show as raw. Change: add `react-markdown` +
`remark-gfm` + code highlighting. Files: `frontend/components/MessageEntry.jsx`, package deps.

**E3. Source cards UI.** Consume `ChatResearchResult.sources` (the `[web:N]` registry): render source
cards with `source_type` badge (fetched / snippet / blocked / hint), quality, clickable `[web:N]`.
Plumb `sources` through the `cowork_log` event → bridge → `MessageEntry`. Files: `ipc_sidecar.py`,
`frontend/adapters/coworkBridge.js`, `frontend/components/MessageEntry.jsx`.

### Theme F — Provider / model UX

**F1. Billing/credit errors graceful.** Gemini/Anthropic runtimes EXIST but need credit; testing showed
a "please top up credit" error. Ensure such errors surface as a CLEAN readable message, do NOT crash
the session, and do NOT silently fall back to a different model than the user picked. Files:
`ipc_sidecar.py` (wrap the research/completion path), error mapping. Keep providers enabled (do not
hide them). Acceptance: no-credit selection shows a friendly message; session stays usable.

### Theme G — Performance

**G1. Concurrency.** Problem: `ChatWebConnector.search` fetches search-engine HTML per query-variant ×
2 engines, then page fetches — all serial at 8s timeout → slow. Change: parallelize with
`ThreadPoolExecutor` (bounded). Files: `chat_web_connector.py`. Acceptance: multi-source search wall
time drops materially; results unchanged.

---

## 4. Suggested sequencing (incremental, each test-gated)

- **Phase 1 — Truthfulness (cheap, high-impact):** A1 (placeholder detection), B2 (date/allow fix),
  F1 (billing UX). Outcome: answers become honest instead of confidently wrong.
- **Phase 2 — Real data:** A2 (XHR adapters), G1 (concurrency). Outcome: real per-type prices; faster.
- **Phase 3 — Intelligence/generality:** C1 (routing), D1 (de-hardcode oil). Outcome: works for any
  topic, searches at the right times.
- **Phase 4 — Feel:** E1 (streaming), E2 (markdown), E3 (source cards). Outcome: frontier-chat UX.
- **Phase 5 — Last resort:** A3 (Playwright) only for sources with no adapter.

---

## 5. Cross-cutting principles (apply to every change)

- **Model-agnostic:** correctness enforced in code (guard/extraction), not by trusting any one model.
- **Behavior-preserving for Cowork:** anything touching `tool_loop.py` keeps the Cowork suite green.
- **Verify against real extracted evidence before blaming the model/guard** (the 2026-06-29 lesson:
  the "all 30.00" answer was a JS placeholder in evidence, not a model hallucination).
- **Each step:** implement → full backend suite green → Claude CLI review → log to
  `work_logs/track-a-review-log.md` → resolve blocking → proceed.
- **English** for code/docs; Thai strings are literal data.

---

## 6. Acceptance smoke tests (the concept, end-to-end)

1. **"ราคาน้ำมันล่าสุดของประเทศไทย"** → either real per-type prices that DIFFER by fuel type (via XHR
   adapter), OR an honest "couldn't extract real prices, check EPPO directly" — NEVER a uniform
   placeholder like all-30.00.
2. **Partial date** in evidence ("26 มิ.ย." no year) → answer keeps it partial; no year added even if
   it's the current year.
3. **General knowledge question** ("explain X concept") → answered with NO web call (no latency).
4. **Current-events question** ("who is the current PM of Thailand") → triggers a web search.
5. **No-credit provider** selected → clean "top up credit" message; session stays usable.
6. **Streaming**: tokens appear incrementally; **markdown**: code/tables/bold render; **source cards**:
   `[web:N]` show with source-type badges.

---

## 7. Open questions for the reviewer (decide before/with implementation)

- C1: full LLM-router vs enriched keyword signals — which, given latency budget?
- A2: confirm the actual JSON endpoints for Bangchak widget and EPPO (network inspection needed).
- E1: streaming with the tool loop — confirm only the final answer turn streams.
- B3: is association-level guard checking worth the complexity now, or defer?
