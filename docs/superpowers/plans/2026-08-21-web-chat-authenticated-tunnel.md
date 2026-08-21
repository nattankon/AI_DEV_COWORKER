# Web Chat Authenticated Tunnel - Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven development and verification-before-completion while implementing this plan task-by-task.

**Goal:** Expose the Phase 3 read-only local MCP gateway through an explicitly started, authenticated, short-lived tunnel without exposing website credentials or tunnel secrets to the renderer.

**Architecture:** A Python tunnel controller owns a loopback-only MCP HTTP transport and an optional remote tunnel adapter. Electron generates the bearer credential, sends it directly to the sidecar, and receives only redacted lifecycle state. The existing grant ID, revision, and canonical workspace path remain the capability generation and are checked before tools are enabled.

**Tech Stack:** Python standard-library HTTP server, JSON-RPC/MCP tool methods, optional `cloudflared` child process, Electron main/preload IPC, React, unittest, Vitest, Electron/CDP smoke testing.

---

### Task 1: Authenticated MCP HTTP transport

**Files:**
- Create: `web_chat_tunnel.py`
- Create: `test/test_web_chat_tunnel.py`

- [ ] Write failing tests for bearer rejection, initialize, tools/list, tools/call, stale grant forwarding, credential redaction, idle expiry, and idempotent stop.
- [ ] Run `python -m unittest test.test_web_chat_tunnel -v` and confirm imports fail because the module does not exist.
- [ ] Implement a loopback-only stateless MCP JSON-RPC endpoint. Accept only `initialize`, `notifications/initialized`, `ping`, `tools/list`, and `tools/call`; return protocol errors for everything else.
- [ ] Keep the bearer credential private. Public state may contain status, provider, public endpoint, auth-required flag, expiry, tool count, and errors, but never the token or authorization header.
- [ ] Add a bounded idle monitor and ensure stop closes the HTTP server and any adapter child process.

### Task 2: Optional remote tunnel adapter

**Files:**
- Modify: `web_chat_tunnel.py`
- Modify: `test/test_web_chat_tunnel.py`

- [ ] Write failing tests for missing `cloudflared`, endpoint discovery, process failure, health, and process-tree stop.
- [ ] Implement an adapter registry with a `cloudflare` adapter. The adapter launches `cloudflared tunnel --no-autoupdate --url <loopback endpoint>`, parses only the generated HTTPS endpoint, and never receives or logs the bearer credential.
- [ ] Keep adapters injectable so a private relay can be added without changing gateway permission logic.

### Task 3: Sidecar and grant-generation lifecycle

**Files:**
- Modify: `ipc_sidecar.py`
- Create: `test/test_ipc_web_chat_tunnel.py`

- [ ] Write failing tests for start/state/stop, no-grant rejection, grant replacement teardown, revoke teardown, and final cleanup when `serve()` reaches EOF.
- [ ] Add `web_chat_tunnel_start`, `web_chat_tunnel_stop`, and `web_chat_tunnel_state` commands.
- [ ] Start asynchronously so sidecar stdin remains responsive. Bind the controller to the current gateway object and generation.
- [ ] Stop the controller before replacing or unbinding its gateway and from `serve()` cleanup.

### Task 4: Electron secret ownership and redacted IPC

**Files:**
- Modify: `electron/main.js`
- Modify: `electron/preload.cjs`
- Modify: `electron/webChatGatewayState.js`
- Modify: `frontend/lib/eel.js`
- Modify: `frontend/adapters/coworkBridge.js`
- Modify: `frontend/CoworkApp.jsx`
- Modify: `frontend/tests/webChatGatewayState.test.js`
- Modify: `frontend/tests/relocationIntegration.test.js`

- [ ] Write failing tests showing stale/mismatched tunnel state cannot enable connectivity and renderer contracts expose start/stop but never a credential.
- [ ] Generate a 256-bit random bearer token in Electron main for each explicit start. Send it only over sidecar stdin with a bounded expiry.
- [ ] Merge redacted tunnel state only when grant ID, revision, and canonical workspace path match. Stop before grant replacement/revoke and on app teardown.

### Task 5: Web Chat tunnel controls

**Files:**
- Modify: `frontend/components/WebChatPanel.jsx`
- Modify: `frontend/tests/WebChatPanel.test.jsx`

- [ ] Write failing tests for explicit connect, starting/connected/error state, disconnect, and disabled connect until the local gateway is ready.
- [ ] Add a compact provider selector and Connect/Disconnect controls inside Workspace access. Display endpoint host and authentication/expiry metadata without the bearer token.
- [ ] Keep wording explicit that Phase 4 exposes only the read-only local catalog and that connector registration remains the next phase.

### Task 6: Verification and records

**Files:**
- Modify: `WEB_CHAT_BRIDGE_PLAN.md`
- Modify: `PROJECT_STATE.md`
- Modify: `work_logs/WORK_LOG.md`
- Create: `tools/web_chat_phase4_smoke.mjs`

- [ ] Run focused red/green suites, full backend, full frontend, production build, syntax/compile checks, and whitespace validation.
- [ ] Run an isolated Electron smoke using an injected/fake tunnel adapter seam so no public network endpoint is created in the default test suite. Verify start state is redacted, matching generation connects, revoke tears down, and no token appears in renderer state or logs.
- [ ] Record Phase 4 as source-only. Do not start Phase 5, publish an installer, or alter either updater path.

## Rollback

Remove the tunnel controller, sidecar commands, Electron start/stop IPC, and panel controls. Phase 3 remains a local-only gateway with the persisted grant format unchanged.
