# Chat — Remaining Work Plan (handoff spec)

> Handoff for Codex. English throughout; Thai strings are literal data. Self-contained.
> Companions: `CHAT_CAPABILITY_ROADMAP.md`, `LIVE_QUALITY_RUNNER_AND_FIXES.md`,
> `work_logs/track-a-review-log.md`. Each item = its own commit + Definition of Done
> (test → Claude review → log → STOP). Anything that calls models / network / a browser is OPT-IN
> and must NEVER run in the default `unittest`/`vitest` suite.

## Cross-cutting constraints (every item)

- Reuse existing seams: tool loop + `.schemas`/`.dispatch` providers, `CompositeToolProvider`,
  approval-flow v2, the answer guard, `ChatRuntimeConfig`. No new loops.
- Opt-in for live/network/browser work (flag or explicit confirm), like `chat_quality_runner --live`.
- Behavior-preserving for Cowork/Code; Chat stays web-only (no filesystem tools).
- Security unchanged: MCP write tools = approval; code-exec stays off until a real sandbox exists.

---

## 1. Web research — real fallback / hard-site smoke tests

**Problem:** the fetch chain exists (source adapter → static HTML extract → placeholder detection →
Playwright fallback → relevance gate), but it is only unit-tested with fixtures. The live scorecard
showed the `web` category failing on SOURCE QUALITY. There is no visibility into how the fallback chain
behaves on genuinely hard pages (JS-rendered, captcha/anti-bot, tables behind JS).

**Scope:** an OPT-IN smoke harness that exercises the real chain against curated hard URLs and reports
which layer succeeded — plus verify the Search API (Brave) path is exercised.

**Implement:**
- New `chat_web_smoke.py` with `run_web_smoke(urls, *, playwright=False) -> report`. For each URL: run
  the real pipeline (adapter → `_fetch_text` + extract → placeholder check → optional Playwright) and
  record per URL: `{url, layer_used: adapter|html|playwright|blocked|empty, evidence_len, has_tables,
  source_type, quality_score}`.
- A curated fixture list of HARD sites (JS-only price/table pages, a known captcha page, a static-but-
  messy page) kept in the repo as URLs (no cached HTML — the point is real fetch).
- CLI-gated: `python -m chat_web_smoke --live [--playwright]`; `--live` required so the default suite
  never hits the network. Save a JSON/markdown report under `work_logs/`.
- While here, confirm the Search API (Brave) provider is selected when a key is present, and record in
  the report whether results came from the API vs the scrape fallback (ties source quality to provider).

**Files:** new `chat_web_smoke.py`; reuse `chat_web_connector.py`, `chat_source_adapters.py`,
`chat_playwright_fetch.py`, `chat_search_api.py`. Unit test the report SHAPE with a fake fetcher
(no network in the default suite).

**Acceptance:** running the smoke harness produces a per-URL layer/quality report that shows exactly
where hard pages fall through the chain — the instrument to drive source-quality fixes.

---

## 2. MCP — from read-only diagnostics to a real connector ecosystem

**Problem:** MCP is a solid FOUNDATION (registry, read-only diagnostics tool, `McpToolProvider` with
approval gate, HTTP/SSE lazy transports, connect/op timeouts) but `_create_sdk_client` needs the SDK
installed and there is no connector-management UI or live tool calls.

**Scope (phased; each phase its own commit):**
- **2a. SDK packaging + live connect.** Add the `mcp` dependency (optional/extra); fully wire
  `_create_sdk_client`/`SdkMcpClient` for stdio + http + sse. Keep the bounded connect (3s) and op
  timeout (10s). **Terminate the underlying stdio subprocess on timeout** (the review flagged that
  `_call_with_timeout` can leave a lingering process — clean it up).
- **2b. Connector Management UI.** A Connectors panel: list/add/edit/enable/disable connectors
  (name, transport, command/url), "Test connection" (runs the read-only diagnostics), and per-connector
  status. Persist via `McpConnectorRegistry`.
- **2c. Read-only tool calls.** Allow the model to call MCP tools whose `readOnlyHint` is true without
  approval; NORMALIZE each MCP `inputSchema` to a strict-mode-safe function schema
  (`additionalProperties:false`, proper `required`) before exposing it — strict providers reject raw
  schemas (this bit us before with `max_results`).
- **2d. Write/action tools via approval.** Tools without `readOnlyHint` (or side-effecting) require
  approval-flow v2 (informed: show server + tool + args; fail-closed).

**Files:** `chat_mcp_client.py`, `ipc_sidecar.py` (connector commands), `approval_policy.py`,
`chat_runtime.py` (mcp enable + connector config), frontend (Connectors panel) + `coworkBridge.js`.

**Constraints:** off when no connectors / SDK; write = approval; read-only default fail-closed
(missing `readOnlyHint` ⇒ treat as write). Tests use a fake MCP client (no real servers/SDK).

**Acceptance:** with a real MCP server configured, the user manages it in the UI, the model uses its
read-only tools without prompting, and write tools require approval.

---

## 3. Memory — deep semantic (embedding-backed) recall

**Problem:** memory recall is keyword/heuristic; personas are separated (good), but there is no semantic
recall, dedupe, summarization, or typed memory.

**Scope:** embedding-backed Memory v2, opt-in, degrading to the current memory when embeddings are
unavailable.

**Implement:**
- An embedding store: `remember(fact, *, kind, metadata)` and `recall(query, top_k) -> ranked` by
  vector similarity. Use LOCAL embeddings (a small local model / library) to stay private/offline;
  lazy-import; fall back to the current keyword recall if unavailable.
- Typed memory kinds: `preference | profile | writing_style | long_term_goal` (personas stay separate
  as today). Dedupe near-duplicates; summarize when the store grows past a cap.
- "Do not remember this" control (a negative/forget marker) surfaced in the Memory Manager.
- Inject only the top-k relevant memories (don't bloat the prompt).

**Files:** `chat_memory.py` (v2 store + recall + summarize/dedupe), `chat_runtime.py` (enable flag),
frontend `MemoryManager.jsx` (kinds + "do not remember"). Tests with a fake/deterministic embedder.

**Constraints:** local-first, opt-in, graceful fallback, prompt stays small (top-k only), personas
unaffected. No network embedding by default.

**Acceptance:** relevant past facts are recalled semantically for a new question; unrelated ones are not
injected; degrades cleanly without embeddings.

---

## 4. Quality panel — live matrix in-app (not just CLI)

**Problem:** `chat_quality_runner` produces a real per-model×category matrix but only via `--live` CLI;
the app shows snapshot/offline scoring only. The measurement loop is not in the user's hands.

**Scope:** surface the scorecard in the app, with the same live-safety.

**Implement:**
- An IPC command `chat_quality_run` that runs the snapshot scorer (offline, safe) OR the LIVE matrix —
  live requires an explicit in-UI confirmation ("this calls the selected models / uses credits") before
  it runs, mirroring the `--live` gate. Reuse `run_quality_eval_live` + the diagnostics return.
- A Quality panel: pick models + categories → run → render the matrix (pass rate, avg latency,
  hallucination rate, source-quality rate, directness) with per-cell status; keep a history of runs
  (the JSON reports under `work_logs/`).
- Bound each live call (reuse the model timeout + the retry/backoff already added); a failing cell is
  recorded, not fatal.

**Files:** `ipc_sidecar.py` (the command + confirm gate), `chat_quality_runner.py` (reuse), frontend
(Quality panel) + `coworkBridge.js`. Tests use a fake pipeline (no live calls in the suite).

**Acceptance:** the user runs a scorecard from the app (offline instantly; live behind a confirm) and
sees the model×category matrix + history — measurement without the terminal.

---

## 5. UI polish — source cards, quality score, router reason

**Problem:** source cards, `quality_score`, and the router's decision exist in data but are not shown
clearly. The user cannot see WHY a model was chosen or how good a source is.

**Implement (frontend only):**
- **Source cards:** compact layout — domain + title, `source_type` badge
  (fetched/snippet/blocked/hint), and a `quality_score` indicator (dots/bar); clickable `[web:N]`.
- **Router reason:** surface `ModelRoute.reason` (e.g. "auto: coding task", "explicit") near the model
  label so the user sees why Auto picked a model. Plumb the reason from the backend route decision
  through to the UI (telemetry/event already carries routing info).
- **Quality/context display:** show model + context-window usage and, when a scorecard exists, a small
  quality badge per model.

**Files:** `frontend/components/MessageEntry.jsx` / a `SourceCards` component, the model selector,
`coworkBridge.js` (carry router reason). Vitest for rendering (badges, reason text, quality dots).

**Constraints:** no backend behavior change; data-only plumbing for the router reason; keep it compact.

**Acceptance:** source cards show type + quality at a glance; Auto shows the routing reason; nothing
regresses.

---

## Suggested sequencing (ROI-first)

1. **5 (UI polish)** — cheap, high-visible, no risk; makes existing data legible.
2. **4 (Quality panel in-app)** — closes the measurement loop so every later change is measurable in-app.
3. **1 (Web smoke harness)** — instruments the fallback chain to drive the source-quality fix the
   scorecard already flagged.
4. **2 (MCP ecosystem)** — the biggest new capability; phase 2a→2d.
5. **3 (Semantic memory)** — valuable upgrade, least urgent.

## Still-open items (carry-forward, not in this file)

- **Latency (~60s general)** from the live scorecard — highest impact on "usable in practice"; diagnose
  whether general routes through the tool loop unnecessarily vs the free model being slow. Worth doing
  alongside item 4.
- **Mode-scoped persona roles** (Chat done; Cowork/Code pending) — add a `mode` field + separate prompt
  blocks; Cowork/Code role prompts must reinforce "cannot relax verification/approval/transparency," and
  add a test proving a role CANNOT weaken the safety gates.
- Code-exec real sandbox (Pyodide/container) before enabling; frontend base64-persistence check.

## Definition of Done (every item)

Implement → full backend + frontend suites green (Cowork suite green for shared changes) → Claude review
(live/network/browser paths opt-in and absent from the default suite; MCP approval + strict-schema norm;
memory local-first + fallback) → append a review entry to `work_logs/track-a-review-log.md` → STOP and
report. Do not start the next until confirmed.
