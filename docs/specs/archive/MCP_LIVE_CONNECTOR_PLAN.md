# MCP Live Connector — Completion Plan (handoff spec)

> Handoff for Codex. English throughout; Thai strings are literal data. Self-contained.
> Companions: `CHAT_REMAINING_WORK_PLAN.md` (item 2), `work_logs/track-a-review-log.md`
> (2026-07-02 entry, FINDINGS 2/3 feed directly into this plan).
> Each item = its own commit + Definition of Done (test → Claude review → log → STOP).
> Anything that talks to a real MCP server is OPT-IN and must NEVER run in the default
> `unittest`/`vitest` suite — tests use fake clients only.

## Context

The MCP foundation is done and reviewed: connector registry (JSON, atomic write),
validate/test/discover IPC commands, read-only diagnostics tools, `McpToolProvider` with a
code-enforced approval callback for non-read-only tools, strict-mode schema normalization,
lazy HTTP/SSE/stdio transports with bounded timeouts, and a connector CRUD + test UI inside
the Composer settings area.

What is missing to make it a *usable live connector experience*:

1. Connection status lies: `create_mcp_clients` reports `"connected"` without any I/O
   (the client is lazy; real connect happens per tool call).
2. The user cannot *drive* a connector: there is no "pick a tool → see its args → run it
   (read-only) → see the result in Chat" flow. Everything goes through the model.
3. The model's MCP calls are invisible in Chat: `emit_chat_status` covers only
   `web_search`/`web_fetch` (`ipc_sidecar.py` ~line 727-746); MCP tool calls show nothing.
4. **Chat mode has no approval UI at all**: `CoworkApp.jsx:323` forces
   `pendingApproval = null` when `activeMode === "Chat"`, and the bottom-panel render is
   also gated `activeView !== "chat"`. So any MCP write tool call in Chat blocks the
   sidecar's `_request_approval` until `approval_timeout_seconds`, then auto-denies.
   Fail-closed (good) but write tools are effectively unusable in Chat (bad UX, confusing
   "Approval timed out" error).
5. Strict-schema normalization makes optional MCP params *mandatory* (no `"null"` type
   widening) and does not recurse into nested object schemas.

## Cross-cutting constraints (every item)

- Approval is enforced in CODE (`McpToolProvider.dispatch` → `approval_callback`), never in
  prompt text. Nothing in this plan may weaken that: missing `readOnlyHint` ⇒ write ⇒
  approval required; `default_decision` stays `"deny"`; timeout stays deny.
- Write/destructive tools keep the HEAVY approval path (informed: server + tool + full
  args; risk badge from `approval_policy.py`; destructive-verb tools get the
  `destructive` risk level). No "always allow" scope in this phase — `allow_scopes`
  stays `["once"]`.
- Manual tool runs (Item 3) follow the SAME gate as model-driven runs: read-only tools run
  without approval; non-read-only tools go through the same `_request_approval` flow.
  A human clicking a button is not a reason to skip the informed-approval screen.
- Chat stays web-only for filesystem: MCP tools reach external servers, never
  `WorkspaceTools`. `CompositeToolProvider` assembly in `ipc_sidecar.py` (~line 768-776)
  must keep excluding filesystem/git tools for Chat.
- Default suites stay offline: every test uses fake MCP clients / fake transports.
  Live-server verification is a manual, documented step (like `chat_quality_runner --live`).
- Frontend events flow through the existing seam: sidecar `_emit` → `eel.js` event map →
  `coworkBridge.js` normalization → reducer/timeline. No new side channels.

## Current-state file map (verified by code read, 2026-07-02)

| Concern | Where |
|---|---|
| Registry / sanitize / validate | `chat_mcp_client.py` — `McpConnectorRegistry`, `_sanitize_connector`, `validate_connector` |
| Client creation + status | `chat_mcp_client.py` — `create_mcp_clients` (lazy; status "connected" without I/O), `SdkMcpClient` (per-call `asyncio.run`, op timeout 10s), `_call_with_timeout` (3s, can leak thread) |
| Tool exposure to model | `chat_mcp_client.py` — `McpToolProvider` (namespacing `mcp__server__tool`, read-only gate, approval callback), `_strict_object_schema` |
| Diagnostics tools | `chat_mcp_client.py` — `McpDiagnosticsToolProvider` (`mcp_diagnose_connector`, `mcp_list_tools`) |
| IPC commands | `ipc_sidecar.py` — `chat_connector_list/save/test/discover` (~line 218-228), `_emit_chat_connectors_state`, `_test_chat_connector`, `_discover_chat_connector` |
| Provider assembly for Chat | `ipc_sidecar.py` `web_tools_factory` (~line 754-776): MCP provider added when `chat_config.mcp_enabled` AND per-request `web_settings` toggle (frontend default `"off"`) |
| Approval plumbing | `ipc_sidecar.py` — `_approve_mcp_tool` → `_request_approval` (emits `cowork_interactive_question`, waits on condition, timeout ⇒ deny) → `_answer_question`; payload built by `approval_policy.build_approval_payload` |
| Approval UI | `frontend/CoworkApp.jsx` — `ApprovalPrompt` component; `pendingApproval` **nulled in Chat mode (line ~323)**; render gated `activeView !== "chat"` (~line 1016) |
| Connector UI | `frontend/components/Composer.jsx` (~line 74-250): CRUD, enable/disable, test, discover; status chips from `chat_connectors_state` |
| Event bridge | `frontend/lib/eel.js` (event map + command dispatch), `frontend/adapters/coworkBridge.js` (normalization) |
| Chat status line | `ipc_sidecar.py` `on_tool_result`/`emit_chat_status` (~line 727-752): web_search/web_fetch only |
| Tests | `test/test_chat_mcp_client.py`, `test/test_ipc_sidecar.py`, `test/test_approval_policy.py`, `frontend/tests/coworkBridge.test.js`, `frontend/tests/Composer.test.jsx` |

---

## Item 1 — Truthful connection lifecycle (fixes review FINDING 2)

**Problem:** `create_mcp_clients` marks a connector `"connected"` after merely constructing
a lazy `SdkMcpClient`. The 3s `connection_timeout_seconds` never bounds a real connection;
a broken command/URL still shows "connected"; errors surface only on the first tool call;
and every call re-launches the stdio subprocess (stateful servers lose all state between
calls). `_has_connected_mcp_clients` (used to pick the code-exec sandbox flavor) also
trusts this fake status.

**Design:**
- Add `SdkMcpClient.probe()` — a real, bounded `initialize()` round-trip (reuse
  `_run_with_session` so the op timeout applies). `create_mcp_clients` calls `probe()`
  inside `_call_with_timeout`; only a successful probe yields status `"connected"`.
  Probe failure ⇒ status `"error"` with the real message; timeout ⇒ `"timeout"`, client
  NOT added (existing fail-closed behavior preserved).
- Cache the probe result per connector (name + transport + command/url hash) for the
  sidecar process lifetime with a short TTL (e.g. 60s), so `web_tools_factory`,
  `_emit_chat_connectors_state`, and diagnostics do not re-probe on every message.
  "Test connection" in the UI bypasses the cache (force re-probe).
- stdio cleanup (carry-forward from the 2026-07-01 review): when a probe or call times
  out, terminate the child process. The `async with stdio_client(...)` context already
  closes on normal unwind; the leak case is `_call_with_timeout`'s abandoned thread.
  Mitigate: run the probe via `asyncio.wait_for` INSIDE the client (async-native timeout
  cancels and unwinds the context manager, killing the subprocess) instead of relying on
  the outer thread timeout; keep the outer `_call_with_timeout` only as a last-resort
  backstop.
- Do NOT build a persistent session pool in this item. Per-call sessions are acceptable
  for read-only tools; note "session reuse for stateful servers" as an explicit
  non-goal / future item so scope stays small.

**Files:** `chat_mcp_client.py` (probe, status, async timeout), `ipc_sidecar.py`
(cache seam — inject a clock for tests).

**Tests (fake clients, no SDK):** fake client whose `probe()` succeeds/fails/times out ⇒
statuses `connected`/`error`/`timeout`; timeout client not in the clients dict; cache hit
avoids second probe within TTL; "test connection" forces re-probe.

**Acceptance:** status shown in the Connectors panel reflects a real handshake; a broken
command shows `error` immediately at save/test time, not on first model call.

---

## Item 2 — Strict-schema hardening (fixes review FINDING 3)

**Problem:** `_strict_object_schema` appends every property to `required` without widening
its `type` to include `"null"`, so genuinely optional MCP params become mandatory under
strict mode (same class as the old `web_search.max_results` bug). Nested object schemas
are not recursively normalized (`additionalProperties:false` is required at every level by
strict providers).

**Design:**
- For each property NOT originally listed in `required`: widen `type` to a union with
  `"null"` (string type ⇒ `[type, "null"]`; list type ⇒ append `"null"` if absent; no
  `type` key ⇒ leave as-is, strict providers accept absent type). Keep the property in
  `required` (strict mode demands it) — nullability is what restores optionality.
- Recurse: normalize any nested `properties`/`items` object schemas the same way
  (`additionalProperties:false` + required/nullable rules), with a depth cap (e.g. 5) to
  avoid pathological schemas.
- Dispatch-side: strip `None` values from arguments before calling the real MCP tool, so
  servers never receive explicit nulls they did not expect (mirror `_clamp_int`-style
  tolerance).

**Files:** `chat_mcp_client.py` (`_strict_object_schema` + a `_strip_null_arguments`
helper used in `McpToolProvider.dispatch`).

**Tests:** optional param becomes nullable+required; originally-required param stays
non-nullable; nested object gets `additionalProperties:false` recursively; depth cap
holds; dispatch drops `None` args before `call_tool`.

**Acceptance:** an MCP tool with optional params is callable by a strict-mode model
without inventing values, and nested-object tools do not get rejected at schema
registration.

---

## Item 3 — MCP Tool Runner UI: pick tool → view args → run → result in Chat

**Problem:** the user can configure and test connectors but cannot exercise a tool
directly. The requested flow: select a tool, see its argument schema, run it (read-only),
and see the result rendered in the Chat conversation.

**Design — backend:**
- New IPC command `chat_mcp_tool_run` with payload
  `{server, tool, arguments, client_session_id}`.
  - Resolve the tool via a (cached, Item 1) client; unknown server/tool ⇒ clean error
    event, no exception.
  - **Same gate as model-driven calls:** if the tool's `readOnlyHint` is not true, route
    through `_request_approval("mcp_tool_call", ...)` — identical payload/risk path as
    `_approve_mcp_tool`. Denied/timeout ⇒ emit a denied result event. Read-only ⇒ run
    immediately.
  - Reuse `McpToolProvider` for dispatch (do NOT duplicate the read-only/approval logic —
    instantiate the provider and call `dispatch` with the namespaced name, so there is
    exactly ONE enforcement point).
  - Emit `chat_mcp_tool_result`:
    `{server, tool, arguments, status: ok|denied|error|timeout, result, duration_ms,
    read_only, client_session_id}`. Truncate `result` for the event (e.g. 20k chars) with
    a `truncated: true` flag.
  - Also append a timeline entry to the Chat conversation: emit the existing `cowork_log`
    with `role: "SYSTEM"`-style MCP payload OR a dedicated event the reducer maps to a
    timeline card (see frontend). The run must appear in the SAME session transcript the
    user is looking at.
- Extend `mcp_list_tools`' data path (or `chat_connectors_state`) so the frontend can get,
  per connector: tool name, description, `read_only`, and the NORMALIZED `input_schema`
  (post Item 2) — this is what drives the args form.

**Design — frontend:**
- In the Connectors panel (Composer settings area), each connected connector gets a
  "Tools" expansion: list of tools with a read-only/write badge (write badge styled as a
  warning). Selecting a tool shows:
  - description,
  - an args form generated from `input_schema.properties` (string/number/boolean/enum
    inputs; JSON textarea fallback for objects/arrays; nullable fields may be left
    blank ⇒ omitted from `arguments`),
  - a "Run tool" button. For write tools the button says "Request approval & run" so the
    user knows the heavy gate is coming.
- On run: send `chat_mcp_tool_run`; render the result as an **MCP result card** in the
  Chat timeline (new event type in `coworkBridge.js` → reducer → a `McpResultCard`
  component next to `MessageEntry`): server/tool header, status chip
  (ok/denied/error/timeout), read-only badge, collapsible args (pretty JSON), collapsible
  result (pretty JSON / text), duration. Denied runs render the denial visibly (audit
  trail, not a silent drop).
- The card is a timeline event (persisted like other events), NOT transient status — the
  user asked for "results shown in Chat".

**Files:** `ipc_sidecar.py` (command + emit), `chat_mcp_client.py` (expose normalized
schema in tool listings), `frontend/lib/eel.js` + `frontend/adapters/coworkBridge.js`
(event + command), `frontend/model/coworkReducer.js` (timeline event),
`frontend/components/Composer.jsx` (tools expansion + args form),
new `frontend/components/McpResultCard.jsx`, `frontend/components/MessageEntry.jsx` or
timeline renderer wiring.

**Tests:** backend — fake client: read-only tool runs without approval; write tool
triggers `_request_approval` (assert the approval callback fired) and deny ⇒
`status: denied`; unknown tool ⇒ error event; result truncation flag. frontend — vitest:
args form renders from a schema fixture (string/enum/boolean/nullable), write badge
shown, result card renders ok/denied/error states, timeline persists the card.

**Acceptance:** user picks a tool on a configured connector, sees its args, runs a
read-only tool with no prompt, sees the result as a card in the Chat conversation; a
write tool always shows the informed approval screen first, and a denial is visible in
the transcript.

---

## Item 4 — Chat-mode approval UI (unblocks write tools in Chat; keeps them heavy)

**Problem:** `CoworkApp.jsx` line ~323 hard-nulls `pendingApproval` in Chat mode and the
overlay render is gated `activeView !== "chat"`. Every write-tool approval request in
Chat (model-driven MCP call, code-exec, and Item 3's manual write runs) silently waits
and then times out to deny. The backend flow is correct and fail-closed; the frontend
simply never shows the question.

**Design:**
- Remove the Chat-mode exclusion: compute `pendingApproval` from the timeline regardless
  of mode, and render `ApprovalPrompt` in the Chat view (inline above the composer is
  fine — mirror the Cowork placement).
- Keep it HEAVY and honest:
  - show `approval_kind`, subject (`server/tool`), risk badge (`write`/`destructive`/
    `code` from `approval_policy`), risk summary, and the full args JSON
    (`proposal.details`) expanded by default for `destructive`, collapsed for `write`;
  - options remain exactly `allow` / `deny`; default focus on **deny**; Escape = deny;
  - while an approval is pending, the chat composer input is disabled with a hint
    ("Waiting for your approval decision…") so the user cannot stack messages behind a
    blocked worker thread.
- `ProcessingIndicator` already accepts `waitingForApproval` — pass it in Chat mode too.
- No behavior change to `_request_approval` itself: timeout ⇒ deny stays.

**Files:** `frontend/CoworkApp.jsx` (un-gate + render), `frontend/components/
ApprovalPrompt.jsx` (risk badge/args display if not already sufficient), vitest.

**Tests:** vitest — approval event in Chat mode renders the prompt; deny/allow dispatches
`answerApproval` with the approval_id; composer disabled while pending; destructive risk
shows expanded args. Reducer test: `approval.requested`/`approval.resolved` unchanged.

**Acceptance:** a write MCP tool called in Chat (by the model or via Item 3) shows the
informed approval prompt in the Chat view; deny blocks the call; allow lets exactly that
one call through; nothing is auto-approved; timeout still denies.

---

## Item 5 — MCP activity visibility in Chat (model-driven calls)

**Problem:** when the MODEL calls an MCP tool mid-loop, the user sees nothing (status
line covers only `web_search`/`web_fetch`). For trust and debuggability the user should
see "Calling <server>/<tool>…" while it runs and a compact record afterward.

**Design:**
- In the Chat tool loop's `on_tool_result` seam (`ipc_sidecar.py` ~line 727), recognize
  `mcp__<server>__<tool>` names: emit `emit_chat_status(f"MCP: {server}/{tool}")` when the
  call starts (transient status, same mechanism as "Reading: domain").
- After the result, emit the SAME `chat_mcp_tool_result` event as Item 3 (mark it
  `origin: "model"` vs `origin: "manual"`), so model-driven calls produce the same
  timeline card. Reuse one card component; keep result truncation.
- Do not log arguments/results into `chat_message_*` telemetry or `_chat_histories`
  (same rule as image data): the card event is the only record.

**Files:** `ipc_sidecar.py` (tool-name recognition + emit), reuse Item 3's frontend card.

**Tests:** backend — fake loop invoking an `mcp__srv__tool` result triggers status +
result event with `origin: "model"`; web tools unaffected. Frontend — card renders for
model-origin events identically.

**Acceptance:** when the model uses an MCP tool in Chat, the user sees a live status line
during the call and a persistent result card in the conversation afterward.

---

## Suggested sequencing

1. **Item 2 (strict schema)** — small, pure-function, unblocks reliable tool listings for
   the UI (Item 3 needs the normalized schema) and reliable model calls.
2. **Item 1 (truthful connect)** — makes every status the UI shows real; Item 3's tool
   listing depends on a client that actually connects.
3. **Item 4 (Chat approval UI)** — REQUIRED BEFORE Item 3's write path and before
   enabling model-driven write tools in Chat; without it every write is a confusing
   timeout-deny.
4. **Item 3 (Tool Runner UI + result cards)** — the main deliverable; lands on top of
   1/2/4.
5. **Item 5 (model-call visibility)** — reuses Item 3's card; cheap once 3 exists.

## Explicit non-goals (this phase)

- Persistent MCP sessions / connection pooling for stateful servers (per-call sessions
  documented as the current model; revisit if a real server needs state).
- "Always allow" / session-scoped approval memory for MCP write tools (approval fatigue
  work is approval-flow v3 territory; every write stays ask-every-time for now).
- OAuth / authenticated remote connectors.
- Any relaxation for destructive-verb tools — they keep the `destructive` risk level and
  the heaviest presentation.

## Live verification (manual, after review — not in any suite)

Documented steps, run by the user: configure one real stdio server (e.g. a filesystem or
echo reference server) + one HTTP server if available; verify: probe status honest for a
good and a broken command; tool list renders with read-only/write badges; read-only
manual run shows a result card with no prompt; write manual run shows the approval screen
(deny leaves a denied card; allow runs); model-driven read-only call shows status + card;
timeout of a hung server yields `timeout` status without a lingering child process
(check the process table). Save findings to `work_logs/` like the quality reports.

## Definition of Done (every item)

Implement → full backend (`python -m unittest`) + frontend (`vitest`) suites green, all
offline → Claude review (approval gate unweakened: missing `readOnlyHint` ⇒ approval;
manual and model paths share ONE dispatch/enforcement point; no MCP args/results leaked
into telemetry/history; default suites make zero network/SDK calls) → append a review
entry to `work_logs/track-a-review-log.md` → STOP and report. Do not start the next item
until confirmed.
