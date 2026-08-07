# Chat Capability Roadmap — from chatbot to assistant (Items 1–5)

> Handoff spec for Codex. English throughout; Thai strings are literal data. Self-contained.
> Companions: `CONCEPT_COMPLETE_UPGRADE_PLAN.md`, `LOOP_INTELLIGENCE_UPGRADE.md`,
> `work_logs/track-a-review-log.md`.

## Vision

The Chat foundation is strong (model-driven web research, deterministic guard, streaming, source
cards, status, effort-tied loop). These 5 items turn it from a "chatbot that answers" into an
"assistant that DOES things" and feels frontier-grade. Build each as its OWN commit + Definition of
Done (test → Claude review → log → STOP); the security-sensitive ones (1 MCP writes, 3 code exec, 4
HTML artifacts) must not be rushed.

## Cross-cutting constraints (apply to every item)

- **Reuse the existing tool architecture.** `run_tool_loop` (`tool_loop.py`) already drives any tool
  provider exposing `.schemas` (OpenAI function schemas) and `.dispatch(name, args) -> JSON string`
  (see `workspace_tools.py` and `chat_web_tools.py`). New "action" capabilities (MCP, code exec) are
  NEW TOOL PROVIDERS, not new loops.
- **Combine providers cleanly.** Chat currently uses web-only tools. To add MCP/code tools, introduce a
  `CompositeToolProvider` that merges multiple providers' `.schemas` and routes `.dispatch` by tool name
  (with a name-collision guard). Keep web-only as the default when no other provider is enabled.
- **Approval gate for side effects.** Any tool that WRITES/acts (MCP write tools, code execution) must
  require user approval before running. Reuse the existing approval mechanism (`ipc_sidecar.py`
  `cowork_interactive_question` / `_pending_approvals` / the `approve_command`/`approve_write` pattern in
  `workspace_tools.py`). Read-only tools may run without approval.
- **Opt-in + behavior-preserving.** Every new capability is OFF by default. With nothing enabled, Chat
  behaves exactly as today. Cowork/Code paths are untouched unless explicitly stated.
- **Optional deps stay optional.** Lazy-import third-party libs (mcp SDK, sandbox runtimes) so the app
  runs and tests pass without them installed.
- **The guard still applies.** Tool results feed evidence; the answer guard (`chat_answer_guard.py`)
  keeps validating. Don't let new tools become a hallucination backdoor.

---

## Item 1 — MCP connectors (the biggest lever)

**Why:** MCP (Model Context Protocol) is an open standard for connecting the assistant to external
tools/data (calendar, email, GitHub, Slack, filesystem, Postgres, Drive, …). The tool loop already
supports pluggable providers, so an MCP client is just another provider — this turns "answer questions"
into "act in real tools".

**Scope:** an MCP client + a tool-provider adapter + an approval gate for write tools + a connector
management UI. Default: no connectors → no change.

**Implement:**
1. `chat_mcp_client.py` — connect to MCP servers over stdio and/or HTTP/SSE transport (use the official
   `mcp` Python SDK; **lazy import**; if absent, the feature is disabled). Support: `initialize`,
   `list_tools`, `call_tool`. Manage connection lifecycle + errors/timeouts.
2. `McpToolProvider` (in `chat_mcp_client.py` or a sibling) — adapts connected servers to the tool
   contract: `.schemas` maps each MCP tool definition → an OpenAI function schema (name namespaced by
   server, e.g. `mcp__<server>__<tool>`); `.dispatch(name, args)` routes to `call_tool` and returns the
   result as a JSON string in the standard `{"status": "ok"|"error", ...}` shape.
3. `CompositeToolProvider` — merges web tools + MCP tools (and later code-exec) for a single Chat run;
   routes dispatch by tool name; guards name collisions.
4. Connector registry/config — a stored list of MCP servers `{name, transport, command|url, env,
   enabled}` (file/config; default empty). Add/edit/remove from the UI.
5. **Approval gate for writes:** classify each MCP tool as read-only vs side-effecting. Prefer the MCP
   tool annotation `readOnlyHint` when present; otherwise treat as side-effecting. Before dispatching a
   side-effecting tool, raise the approval prompt (reuse the Cowork approval flow) showing the tool +
   arguments; only run on approve. Read-only tools run without prompting.
6. UI — a Connectors panel: add/remove/enable MCP servers, view their tools, connection status; plus the
   approval prompt surfaced in Chat when a write tool is called.

**Constraints:** preserves Chat's read-only default (write tools require explicit approval each time);
MCP off when no connectors/SDK; combine cleanly with web tools; never bypass the guard.

**Files:** new `chat_mcp_client.py`; `tool_loop.py`/runner wiring via `CompositeToolProvider`;
`ipc_sidecar.py` (connector commands + approval); `chat_runtime.py` (connector config); frontend
(Connectors panel + approval surface) + `coworkBridge.js`.

**Tests (fake MCP server; no real servers):** tools listed → schemas; dispatch routes to call_tool;
a side-effecting tool → approval required (denied = not run); read-only tool → runs without prompt;
no connectors → Chat unchanged; name-collision handled.

**Acceptance:** with a real MCP server configured (e.g. filesystem or a calendar), the model can call its
tools from Chat; writes are approval-gated; nothing changes when no connector is set.

---

## Item 2 — Table-stakes chat affordances (stop / regenerate / edit & resend / threads)

**Why:** these are baseline expectations of GPT/Claude-grade chat. Missing them makes the app feel like a
prototype regardless of how strong the backend is.

**Scope:** Stop generation, Regenerate, Edit & resend, and multiple chat threads with management. (First,
audit which already exist; implement the gaps.)

**Implement:**
1. **Stop generation:** an IPC `cancel` command that signals the in-flight worker for a session to abort.
   The model call / streaming loop checks a per-session cancel flag and stops cleanly, frees resources,
   and emits a "stopped" state (partial streamed text may remain or be cleared per UX choice). Ties to
   the timeout design — this is the user-initiated version of "stop waiting".
2. **Regenerate:** drop the last assistant message and re-run the last user prompt (same settings).
3. **Edit & resend:** edit a prior user message → truncate history after it → resend; the thread continues
   from the edited point.
4. **Threads:** multiple chat sessions (history is already keyed by `client_session_id` in
   `_chat_histories`). Add a thread list UI: new / switch / rename / delete, with persistence and history
   search.

**Constraints:** cancel must truly interrupt the stream and release the worker (no orphan threads);
Cowork unaffected; per-session isolation preserved.

**Files:** `ipc_sidecar.py` (cancel signal + worker interruption; regenerate/edit handling),
`tool_loop.py`/runner (honor a cancel flag), frontend (message-level actions, thread list) +
`coworkBridge.js`.

**Tests:** cancel mid-stream stops generation and frees the worker; regenerate re-runs the last prompt;
edit truncates history and resends; threads keep histories isolated; rename/delete persist.

**Acceptance:** the user can stop a long answer, regenerate, edit a question and rerun, and keep multiple
named conversations.

---

## Item 3 — Code execution / sandbox

**Why:** lets the assistant COMPUTE (data analysis, math, charts) instead of guessing — GPT Code
Interpreter-style. Slots into the tool loop as another provider; pairs with Artifacts (Item 4).

**Scope:** a sandboxed `run_python` (and optionally `run_js`) tool, approval-gated, returning stdout/
stderr/status and any generated artifacts (files/charts). Off by default.

**Implement:**
1. `chat_code_exec.py` — a `CodeExecutor` running code in an ISOLATED subprocess: a fresh temp working
   dir, a hard timeout, NO network by default, and resource limits (CPU/memory where the OS allows).
   Capture stdout/stderr/exit status; collect files written to the temp dir (e.g. PNG charts) as artifacts.
   **Be explicit that subprocess isolation is a first step; a container/VM sandbox is the production-grade
   path** — note it, don't fake it.
2. Tool provider: `run_python(code) -> {status, stdout, stderr, artifacts:[{name, mime, data|path}]}`.
3. **Approval gate:** code execution is powerful → require approval before each run (reuse the approval
   flow), or a strict allow-flag. Default disabled.
4. Surface artifacts to the UI (charts/files) — integrates with Item 4.

**Constraints:** sandbox safety is the priority — timeout, no-network default, temp-dir isolation,
resource caps, output size limits; approval-gated; flag/opt-in; lazy deps. Never run untrusted code
unsandboxed.

**Files:** new `chat_code_exec.py`; runner/`CompositeToolProvider` wiring; `ipc_sidecar.py` (approval +
artifact emit); `chat_runtime.py` (enable flag); frontend (artifact/result rendering).

**Tests (no real heavy sandbox needed — inject a fake executor + a real bounded subprocess test):**
`run_python` returns computed stdout; a timeout is enforced; an error is captured (not crashed);
approval required before run; network blocked by default; oversized output bounded.

**Acceptance:** with the flag on + approval, the model can run Python to compute/plot, and results/charts
appear; disabled by default with zero change.

---

## Item 4 — Artifacts / Canvas

**Why:** renders generated code/docs/HTML in a separate, persistent, versioned panel (Claude artifacts /
GPT canvas). The frontier differentiator for code and writing. You already render markdown — this is the
next level.

**Scope:** detect artifact-worthy output, render in a side panel with versions, copy/download, and (if
code exec exists) run. HTML artifacts render in a SANDBOXED iframe.

**Implement:**
1. Artifact production — choose ONE: (a) the model emits artifacts via a tool call
   `create_artifact(type, title, content)` (cleanest, explicit), OR (b) heuristic detection of large code
   blocks / full HTML / full documents in the answer with an "open in panel" affordance. Recommend (a) for
   reliability; (b) as a fallback.
2. Frontend Artifacts panel — render by type: code (syntax-highlighted), markdown/doc, and HTML in a
   **sandboxed iframe** (`sandbox` attribute, no app access — security critical). Per-regeneration
   VERSIONING with a version switcher; copy + download.
3. Optional: a "Run" button for code artifacts wired to Item 3 (code exec).

**Constraints:** HTML artifacts MUST be sandboxed (no access to the app, no `rehype-raw` leakage —
consistent with the markdown safety already in place); versioning is per artifact; normal markdown answers
are unaffected.

**Files:** `ipc_sidecar.py`/runner (artifact tool or detection + event), frontend (Artifacts panel,
versioning, sandboxed iframe) + `coworkBridge.js` + reducer (artifact state).

**Tests:** an answer that produces an artifact → panel renders it by type; a second generation → a new
version is tracked; HTML artifact renders inside a sandboxed iframe; plain answers show no panel.

**Acceptance:** generated code/HTML/docs open in a side panel, versioned, copyable/downloadable, and (with
Item 3) runnable.

---

## Item 5 — Memory v2 (semantic) + Model Router

Two related "brain" upgrades. May be split into 5a and 5b commits.

### 5a — Memory v2 (semantic long-term memory)
**Why:** today's memory stores preference strings. v2 remembers FACTS/PROJECTS across sessions and recalls
by relevance — so the assistant actually "knows you". The memory-manager UI (separately in progress) is the
view layer; this is the brain.

**Implement:**
- An embedding-backed memory store: `remember(fact, metadata)` and `recall(query) -> top-k relevant
  memories` injected into the prompt (replacing/augmenting `format_for_prompt`). Use LOCAL embeddings
  (a small local model or library) to stay private/offline; fall back to the current keyword/preference
  memory if embeddings are unavailable.
- Persist with ids/metadata so the memory-manager UI can list/edit/delete v2 entries too.
**Constraints:** local-first/private; opt-in; degrade gracefully to current memory; don't bloat the prompt
(inject only top-k relevant).
**Files:** `chat_memory.py` (v2 store + recall), runner (inject recalled memories), config (enable flag).
**Tests:** recall returns the most relevant stored memory for a query; unrelated memories are not injected;
falls back cleanly with no embeddings; entries are listable/deletable.

### 5b — Model Router (use the metadata you added)
**Why:** you added per-model metadata (badge/strengths/vision/context). The router turns that into
automatic model selection by task — the "smart" layer of a multi-provider system.
**Implement:**
- `route_model(prompt, attachments, available_models) -> model_id` using metadata + signals: image
  attachment + a vision-capable model → that model; code-heavy prompt → a code-strong model; very long
  input/context → a long-context model; else a sensible default. Start heuristic; a tiny classifier model
  is a later refinement.
- **Only acts in "auto" mode.** If the user explicitly pinned a model, always honor it — the router never
  overrides an explicit choice.
**Constraints:** explicit user choice wins; auto-only; transparent (surface "routed to X because Y" if
possible); behavior-preserving when auto is off.
**Files:** new `model_router.py`; `ipc_sidecar.py` (use it when model == "auto"); `model_catalog.py`
(metadata it reads).
**Tests:** image + vision-capable available → routes to vision model; code prompt → code-strong model;
long input → long-context model; explicitly pinned model → router not invoked.

---

## Suggested sequencing (each its own commit + DoD)

1. **Item 1 — MCP connectors** (biggest lever; reuses the loop). Land read-only first, then write+approval.
2. **Item 2 — table-stakes** (stop/regenerate/edit/threads) — cheap, high user-visible value.
3. **Item 3 — code execution** (sandbox-safety first; approval-gated).
4. **Item 4 — artifacts** (pairs with 3; sandboxed HTML).
5. **Item 5 — memory v2 + model router** (the brain; 5a then 5b).

## Definition of Done (every item / sub-item)

Implement → full backend suite + frontend vitest green (and Cowork suite green for any shared-loop
change) → Claude review (CLI or in-session), focused on that item's risk (MCP: approval gate + read-only
default; code exec: sandbox isolation + approval; artifacts: sandboxed iframe; router: explicit-choice
wins) → append a review entry to `work_logs/track-a-review-log.md` → STOP and report. Do not start the
next until confirmed.

## Security checklist (do not skip)

- MCP/code-exec side effects → approval-gated, off by default.
- Code execution → isolated subprocess (timeout, no-network, temp dir, resource caps); container path noted.
- HTML artifacts → sandboxed iframe only; never raw-inject into the app DOM.
- Optional deps (mcp, sandbox, embeddings) → lazy-imported; app + tests pass without them.
- The answer guard keeps validating tool-derived facts.
