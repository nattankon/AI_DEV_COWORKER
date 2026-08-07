# MCP Fixes — Implemented by Claude, pending Codex review

> Role reversal for this batch: Claude implemented, Codex reviews.
> Source findings: `work_logs/track-a-review-log.md` (2026-07-03 entry, FINDINGS 1-6).
> Scope: MCP only. Verification: backend `python -m unittest discover -s test` = **347/347**,
> frontend `npx vitest run` = **133/133** (both run after the changes; 7 new backend tests,
> 3 new frontend tests).

## What Codex should verify hardest

1. The **deadlock fix** (Fix 1) — confirm the worker-thread pattern matches `_send_cowork`
   and that nothing else in `handle_line` can block on `_request_approval`.
2. The **fail-closed inversion** (Fix 3) — confirm NO code path treats a tool as read-only
   without either `readOnlyHint` or an explicit per-connector `read_only_overrides` entry.
   `grep -n "roblox" chat_mcp_client.py` must return nothing.
3. The **migration consequence** (see "Behavior change" below) is acceptable and surfaced
   in the UI well enough.

---

## Fix 1 (was FINDING 1, BLOCKING) — manual write-tool runs deadlocked

**Problem:** `handle_line` dispatched `chat_mcp_tool_run` synchronously on the single
stdin-reading thread. A write tool blocks in `_request_approval` waiting for the
`answer_question` line — which the same blocked thread must read. Every manual write run
timed out to deny (300s). Model-driven writes were unaffected (they already run on a
`_send_cowork` worker thread).

**Change:** `ipc_sidecar.py`
- `chat_mcp_tool_run` now dispatches to `_run_chat_mcp_tool_async` → daemon worker thread
  (`_run_chat_mcp_tool_worker`, appended to `self._workers` so `wait_for_idle` covers it),
  same pattern as `_send_cowork`. Worker wraps the run in try/except →
  `_emit_backend_error` (previously the sync path relied on `handle_line`'s catch).
- `_worker_context` is `threading.local` (verified), so session/mode scoping is per-thread.

**Tests:** `test_ipc_sidecar.py`
- Existing manual-run test now asserts `wait_for_idle(timeout=5)` (async-aware).
- NEW `test_chat_mcp_manual_write_run_receives_approval_while_command_loop_stays_free`:
  submits a write-tool run, polls for the emitted approval question (proving the command
  loop is NOT blocked), answers `allow` via a second `handle_line`, asserts the run
  completes `ok` and the tool actually executed. This deadlocked before the fix.
- `FakeMcpClient` (sidecar tests) gained a `write_instance` tool (no `readOnlyHint`).

## Fix 2 (was FINDING 2, HIGH) — payload explosion on big servers (85 tools)

**Problem:** three bloat vectors: (a) `mcp_list_tools` returned the FULL normalized
`input_schema` for every tool → one tool result blew through the loop's 12k tool-context
budget → the model told the user the connector message "was cut off" (the live-test
symptom). (b) All 85 function schemas registered per message with untruncated
descriptions. (c) `chat_mcp_tool_result` echoed `connector_statuses` (all tools + schemas)
on every run.

**Change:** `chat_mcp_client.py`, `ipc_sidecar.py`
- `mcp_list_tools` now returns a COMPACT listing per tool: `name`, `read_only`,
  `description` truncated to 100 chars — no schemas. Its function schema gained a
  strict-safe nullable `tool` argument (`required: ["query","tool"]`,
  `"type": ["string","null"]`): pass one tool name to get that single tool's full
  `input_schema` on demand. Tool description updated so the model knows the contract.
- `McpToolProvider` function descriptions truncated to 300 chars (`_truncate_text`).
- `connector_statuses` REMOVED from `chat_mcp_tool_result` events.
- NOT changed (deliberate): probe statuses still carry full tool metadata — that is the
  UI's data source for the args form (`chat_connectors_state` is a UI event, not model
  context). A per-connector "expose to model" allowlist for giant servers remains a
  follow-up (see Open items).

**Tests:** compact listing has no `input_schema` and ≤100-char descriptions;
`tool` filter returns exactly one tool with a strict schema; result event asserts
`connector_statuses` absent.

## Fix 3 (was FINDING 3, HIGH) — hardcoded Roblox read-only allowlist removed

**Problem:** `_ROBLOX_READ_ONLY_TOOL_NAMES` (27 names) + "roblox"-substring sniffing in
`_is_mcp_tool_read_only` flipped name-matched tools to no-approval. Vendor data in generic
control flow (D1) and a direct exception to "missing `readOnlyHint` ⇒ write ⇒ approval" —
trust anchored on a connector NAME.

**Change:**
- `chat_mcp_client.py`: frozenset + name sniffing DELETED. `_is_mcp_tool_read_only` is now:
  `readOnlyHint` → read-only; else tool name ∈ the connector's `read_only_overrides` →
  read-only; else write (fail-closed). Overrides come from `client.connector` (the
  sanitized connector config), i.e. DATA the user saved, never code.
- `_sanitize_connector` persists `read_only_overrides` (trimmed, deduped, ≤128 chars each,
  ≤200 entries) through the registry.
- `frontend/components/ConnectorsPanel.jsx`: the Roblox PRESET now carries the 27
  inspection-tool names as `read_only_overrides` — applying the preset is the user's
  explicit consent. New "Read-only overrides" textarea on every connector shows the count
  ("N tools trusted without approval"), allows editing, and states the risk in plain text.
  `normalizeConnector` carries the field.
- `frontend/components/Composer.jsx`: the mini connector editor now PRESERVES
  `read_only_overrides` on edit/save (it previously rebuilt the object from named fields
  and would have silently dropped them).

**Behavior change / migration note (important):** existing saved connectors have NO
overrides, so all unannotated tools on them (e.g. the user's live HTTP Roblox connector —
all 85 tools) now REQUIRE approval until the user either re-applies the Roblox preset or
pastes the tool names into the overrides textarea. This is the intended fail-closed
default; the UI copy explains it. Also affects the Roblox context prefetch (see Open
items): without overrides the prefetch's deny-all dispatch yields nothing, so the
prefetch silently no-ops until consent is given.

**Tests:** overrides mark unannotated tools read-only; NEW fail-closed regression test
(no overrides ⇒ `denied` + approval requested); status counts flow from config →
factory → classification; sanitize dedupes/trims; frontend preset carries the list
(and NOT `create_object`/`execute_luau`); overrides textarea edit round-trips through
save.

## Fix 4 (was FINDING 4, MEDIUM) — list_tools network round-trip per message

**Problem:** clients were cached (60s) but `McpToolProvider.__init__` called
`client.list_tools()` fresh on every construction = a real round-trip per chat message
with MCP on, plus probe double-fetched at create time.

**Change:** `chat_mcp_client.py` — `SdkMcpClient` now caches the tool list
(`tools_cache_ttl_seconds` = 60): `probe()` always hits the server (it IS the bounded
handshake) and refreshes the cache; `list_tools()` serves the cache within TTL. So the
create-time probe feeds provider construction with zero extra round-trips.

**Tests:** probe-then-list performs exactly ONE fetch, and the probe fetch uses the probe
timeout.

## Fix 5 (was FINDING 5, MEDIUM) — timeout nesting + master-toggle decision

**Problem:** outer create/probe thread-timeout (3s) < inner async op timeout (10s): the
outer fired first and abandoned a thread that kept connecting up to 10 more seconds.

**Change:** `chat_mcp_client.py` — `SdkMcpClient` gained `probe_timeout_seconds`
(default 3.0); `create_mcp_clients` passes its `connection_timeout_seconds` into
`_create_sdk_client(..., probe_timeout_seconds=...)`. `probe()` runs
`asyncio.wait_for(..., probe_timeout)` INSIDE the client, so the async cancellation
unwinds the transport context managers (terminating a stdio child) at the same 3s the
outer backstop fires — the outer thread timeout is now a true backstop, not the primary.
`_run_with_session` accepts an optional `timeout_seconds` override; error messages report
the effective timeout.

**Decision documented (no code change):** manual `chat_mcp_tool_run` intentionally does
NOT check `chat_config.mcp_enabled`. Rationale: the master toggle gates MODEL autonomy
(which tools get registered into the loop); a manual run is an explicit user click in the
connector UI, and writes are still approval-gated. If Codex disagrees, the gate belongs at
the top of `_run_chat_mcp_tool`.

## Fix 6 (was FINDING 6, LOW) — result-card audit trail + leaf-schema noise

**Change:**
- `frontend/components/McpResultCard.jsx`: collapsible "Arguments" section (pretty JSON)
  whenever the run had arguments — denied runs now show exactly what was asked.
  (`coworkBridge.js` already normalized `arguments` through; no bridge change needed.)
- `chat_mcp_client.py` `_normalize_strict_schema`: `properties`/`required`/
  `additionalProperties` are now attached ONLY to object-typed schemas (type == "object"
  or has properties). Leaf property schemas (string/number/bool) no longer get empty
  `properties: {}` / `required: []` decorations. Nullable widening and `items` recursion
  unchanged.

**Tests:** Timeline test renders the Arguments section with the denied run's args; leaf
properties carry no object keywords.

---

## Files touched

| File | Changes |
|---|---|
| `chat_mcp_client.py` | overrides sanitize + classification, frozenset deleted, tools cache, probe timeout, compact/on-demand `mcp_list_tools`, description truncation, leaf-schema cleanup, `_truncate_text` |
| `ipc_sidecar.py` | `chat_mcp_tool_run` → worker thread (`_run_chat_mcp_tool_async`/`_worker`), `connector_statuses` dropped from result event |
| `frontend/components/ConnectorsPanel.jsx` | Roblox preset ships overrides as data, overrides textarea + consent copy, `normalizeOverrides` |
| `frontend/components/Composer.jsx` | connector editor preserves `read_only_overrides` |
| `frontend/components/McpResultCard.jsx` | collapsible Arguments section |
| `test/test_chat_mcp_client.py` | fakes carry `connector`; renamed/updated override tests; NEW: fail-closed, compact listing, schema-on-demand, sanitize, tools-cache, leaf-schema tests |
| `test/test_ipc_sidecar.py` | write tool on fake; async-aware manual-run test; NEW deadlock-regression test; prefetch fake consents via overrides |
| `frontend/tests/ConnectorsPanel.test.jsx` | NEW: preset-overrides + textarea-edit tests |
| `frontend/tests/Timeline.test.jsx` | NEW: Arguments audit-trail test |

## Open items (intentionally NOT fixed here — for the next plan)

1. **Roblox context prefetch is still a hardcoded vertical** (`ipc_sidecar.py`
   `_format_chat_mcp_live_context` + `_looks_like_roblox_workspace_inspection` +
   `_ROBLOX_PHYSICAL_WORKSPACE_CLASSES` + helpers): Roblox keyword detection, tool names,
   arg shapes, and class names live in sidecar control flow. Discovered during this batch
   (it was added alongside the previous batch and was not in the reviewed plan). It now at
   least respects consent (its deny-all dispatch only succeeds for override-listed tools),
   but the D1-correct shape is a data-driven "MCP context profile" (per-connector: trigger
   keywords → read-only tool calls → formatter) or simply letting the model drive via the
   normal loop. Needs its own design decision — do not fold silently into another batch.
2. Per-connector "expose to model" allowlist/cap so an 85-tool server does not register
   85 functions per message (token cost), distinct from read-only consent.
3. Full-status tool metadata in `chat_connectors_state` is heavy (fine for a local UI
   event; revisit if it ever leaves the machine).

## How to verify locally

- Backend: `python -m unittest discover -s test` → 347 tests.
- Frontend: `npx vitest run` → 133 tests.
- Live (manual, optional): re-open the Connectors panel, apply the Roblox preset (or add
  overrides to the existing HTTP connector), then: a read-only tool runs from the panel
  with no prompt; a write tool (`create_object`) shows the approval prompt IN CHAT and
  completes after Allow — before this fix it always timed out to deny after 300s.
