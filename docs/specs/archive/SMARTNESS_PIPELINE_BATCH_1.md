# Smartness Pipeline — Batch 1 (implemented by Claude, pending Codex review)

> Role reversal continues: Claude planned + implemented, Codex reviews.
> Driving question from the user: "what makes the program/AI smarter — MCP first, or other
> pipeline work?" Answer implemented here: MCP adds HANDS; perceived intelligence comes from
> latency, evidence quality, and the model itself. This batch ships the highest
> impact-per-effort items that were executable offline, runs the first real web smoke, and
> records the decisions that need the user's input.
>
> Verification (run after all changes): backend `python -m unittest discover -s test` =
> **352/352** (+5 new). Frontend `npx vitest run` = **134/134** (+1 new).
> Live smoke report: `work_logs/chat-web-smoke-20260703-105932.{json,md}`.

## The roadmap this batch executes

| # | Roadmap item | Status in this batch |
|---|---|---|
| 1 | Preset merge + dedupe (Codex review finding) | DONE |
| 2 | Diagnose ~60s general latency | INSTRUMENTED (experiment ready; needs one live scorecard run) |
| 3 | Run web smoke live, drive source quality | RUN + ANALYZED (fix candidates listed, not blind-patched) |
| 4 | Second model in scorecard | DEFERRED — spends credits; user decision |
| 5 | MCP exposed-tools allowlist (context bloat = dumber model) | DONE |
| 6 | Wire real local embedder | DEFERRED — dependency choice; user decision |
| 7 | Persona safeguards (Cowork/Code) | ALREADY DONE in a parallel Codex session — verified present, no change |

## 1. Preset merge + registry dedupe (fixes Codex review finding 1)

**Problem confirmed worse than reported:** `robloxstudio-mcp` (preset) and
`robloxstudio_mcp` (saved) both sanitize to `robloxstudio_mcp` on the backend, but the
frontend compared RAW names → clicking the preset with an existing connector appended a
second entry → registry ends with TWO connectors of the same name (statuses/clients key
collision).

**Changes:**
- `frontend/components/ConnectorsPanel.jsx` — `sanitizedNameKey()` mirrors backend
  `_safe_name`; `addPreset` now MERGES into the existing connector on a sanitized-name
  match: configured transport/command/url/enabled stay untouched, `read_only_overrides`
  are unioned (a preset can only ADD consent, never clobber config).
- `chat_mcp_client.py` — `_dedupe_connectors()` guard inside
  `McpConnectorRegistry.save_connectors`: FIRST entry wins for connection fields,
  consent lists (`read_only_overrides`, `exposed_tools`) unioned from later duplicates.
  Registry-level, so no UI path can create duplicates (architecture over UI).

**Tests:** backend registry dedupe (http config survives a stdio preset re-add; overrides
unioned); frontend sanitized-collision merge (saves ONE entry, http/url preserved, both
override lists present).

## 2. Latency attribution instrumentation (the ~60s "general" finding)

**What I could establish from code:** `_should_run_tool_research` sent EVERY route except
`memory` into the agentic tool loop — including `general`. The scorecard's general cell
(59.9s, no sources) is consistent with a slow model paying loop overhead for nothing, but
code reading alone cannot split "loop overhead" from "model is just slow." Guessing is
how bad fixes happen, so this ships the instrument, not a behavior change:

- `chat_runtime.py` — `ChatRuntimeConfig.tool_research_routes: tuple[str, ...] | None`.
  `None` (default) = behavior unchanged. A tuple (e.g. `("web", "project")`) limits tool
  research to those route categories. Data-driven; no route names in code branches.
- `ipc_sidecar.py` — `_should_run_tool_research` honors the knob; diagnostics
  (`return_diagnostics=True`) now include `entered_tool_loop`, `research_iterations`,
  `research_forced`, `answer_path_ms`.

**The experiment (one live scorecard run, ~minutes, small credit cost — user's call):**
run the quality panel live twice on the same model, once default and once with
`tool_research_routes=("web","project")`; compare the general column's latency and pass
rate. If latency collapses with no pass-rate loss → make the gated tuple the default. The
diagnostics fields land in each cell either way.

**Tests:** default keeps general/web in, memory out; gated tuple excludes general,
keeps web.

## 3. First real web smoke run (roadmap 3) — results

Command: `python -m chat_web_smoke --live` (network fetches only; no model calls).
Report: `work_logs/chat-web-smoke-20260703-105932.md` + `.json` + updated
`chat-web-source-profile.json`.

| URL | Layer | Evidence | Tables | Quality |
|---|---|---:|---|---:|
| eppo.go.th (ราคาขายปลีกน้ำมัน) | **adapter** | 4272 | yes | **5** |
| bangchak.co.th/th/oilprice | html | 1800 | no | 2 |
| oil-price.bangchak.co.th | **adapter** | 654 | yes | 2 |
| globalpetrolprices.com | html | 1631 | yes | 2 |

**Reading:** the fallback chain WORKS — zero `blocked`/`empty` on the curated hard set,
and the EPPO page (the original placeholder-table incident) now comes through the source
adapter at full quality. Remaining source-quality work, in order of value:
1. `bangchak.co.th/th/oilprice` extracts prose but NO tables at quality 2 — either extend
   the bangchak adapter to cover this URL too, or accept the subdomain adapter
   (`oil-price.bangchak.co.th`) as the canonical bangchak source and drop the main page
   from the hint profile.
2. Three sources scoring 2 while producing usable evidence suggests `_source_quality_score`
   calibration is conservative; recalibrate ONLY with the quality panel as the referee
   (change scoring → run web category → compare source_quality_ok), not by eye.
3. `search_provider: "not_checked"` in the report = no Brave key in THIS shell's env. If
   the app process also lacks `COWORK_SEARCH_API_KEY`, web search runs on the scrape
   fallback — plausibly the real driver of the scorecard's failing web source quality.
   **Check where the Brave key is supposed to be configured before touching scoring.**

No extraction/scoring code was changed in this batch — the report is the instrument; the
fixes above need either a product decision (1) or an eval referee (2, 3).

## 5. MCP `exposed_tools` allowlist (the MCP change that actually adds smartness)

**Problem:** with MCP on, every chat message carried ALL of a server's function schemas
(Roblox = 85). Context bloat slows every turn, costs tokens, and measurably degrades tool
CHOICE — more wrong-tool calls on big menus.

**Changes:**
- `chat_mcp_client.py` — `_sanitize_connector` persists `exposed_tools` (same sanitize as
  overrides); `McpToolProvider` builds ROUTES for every tool (manual runner can still
  dispatch anything, approval-gated as before) but registers function SCHEMAS only for
  exposed tools when the list is non-empty. Empty list = expose all (default, no behavior
  change).
- `frontend/components/ConnectorsPanel.jsx` — "Exposed tools" textarea with plain-language
  copy ("model sees only N tools / all tools visible"); `frontend/components/Composer.jsx`
  preserves the field through its mini-editor (same drop-on-save bug class as overrides).

**Tests:** schemas filtered while manual dispatch of an unexposed tool still works;
empty list exposes everything.

**Strictness (added after self-review):** the MODEL-facing provider instance
(`_create_mcp_tool_provider`, used by the chat loop) is constructed with
`restrict_dispatch_to_exposed=True` — a model that guesses an unexposed tool's namespaced
name gets `"MCP tool is not exposed to the model"` instead of execution. The manual-runner
instance keeps the default False so the panel can run any tool (writes still
approval-gated). Test: unexposed dispatch rejected on the restricted instance, tool never
called.

## 7. Persona safeguards — verified done elsewhere

A parallel Codex session already added the "must not reduce approval, verification,
audit, rollback, or transparency requirements" clause to the Cowork/Code
`_ROLE_MODE_META` descriptions, with assertions in `test_chat_memory.py` (store level)
and `test_ipc_sidecar.py:1094` (injected-prompt level). Verified present; nothing changed
here. The same parallel session also addressed the earlier memory review findings
(embedding redaction in public entries, keyword fallback for entries without embeddings,
forget-marker generic-word filtering) — visible in `PROJECT_STATE.md` item 5's updated
completion notes.

## Deferred — decisions that belong to the user

1. **Second model for the scorecard (roadmap 4).** Biggest single smartness lever in a
   pluggable-model system, but it spends real credits. Needs: which provider/model to
   fund (a cheap strong option: Haiku or Gemini Flash), then one live matrix run for a
   real cross-model comparison. Zero code needed — models are already pluggable.
2. **Local embedder library (roadmap 6).** The seam is ready. Candidates: `fastembed`
   (small, ONNX, no torch) vs `sentence-transformers` (heavier, more models). Needs a
   dependency-weight decision before wiring.
3. **Mojibake separators (Codex review item 3).** Source files are clean UTF-8 — grep for
   mojibake byte patterns (`Â·`, `â€`, `à¸`) found nothing across `frontend/`. If it
   reproduces, it is a RENDER-layer encoding issue (webview charset / index.html meta),
   not source text. Needs a screenshot or exact location before any fix.
4. **Roblox workspace prefetch redesign** stays queued behind the exposed-tools +
   quality-panel work: first measure whether the model can drive read-only MCP tools well
   on its own (now that consent + narrow exposure exist) — if yes, DELETE the prefetch
   instead of generalizing it.

## Files touched

| File | Change |
|---|---|
| `chat_mcp_client.py` | `_dedupe_connectors` registry guard; `exposed_tools` sanitize + schema filtering (`_connector_exposed_tools`) |
| `chat_runtime.py` | `tool_research_routes` knob (default None = unchanged) |
| `ipc_sidecar.py` | route-gating in `_should_run_tool_research`; diagnostics: `entered_tool_loop` / `research_iterations` / `research_forced` / `answer_path_ms` |
| `frontend/components/ConnectorsPanel.jsx` | sanitized-name preset merge; Exposed-tools textarea |
| `frontend/components/Composer.jsx` | preserves `exposed_tools` through the mini-editor |
| `PROJECT_STATE.md` | two dated completion bullets under section 9 |
| `test/test_chat_mcp_client.py` | +3: registry dedupe, exposed filtering, expose-all default |
| `test/test_ipc_sidecar.py` | +1: `tool_research_routes` gating |
| `frontend/tests/ConnectorsPanel.test.jsx` | +1: sanitized-collision merge |
| `work_logs/chat-web-smoke-20260703-105932.*` | first real smoke report |

## What Codex should verify hardest

1. The registry dedupe merge policy (first wins, consent unioned) — confirm no UI or IPC
   path expects last-wins semantics.
2. `restrict_dispatch_to_exposed` split — confirm `_create_mcp_tool_provider` (loop) is
   the ONLY restricted instance and `_run_chat_mcp_tool` (manual) intentionally is not;
   confirm no other provider construction path needs the flag.
3. `tool_research_routes` default-None path is byte-for-byte the old behavior.
