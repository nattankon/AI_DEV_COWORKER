# Chat Tool Safety Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Chat action tools honest and safer before enabling code execution or MCP write tools.

**Architecture:** Keep Chat content permissive while tightening tool boundaries. Code execution is relabeled as experimental/best-effort and remains hard-disabled by default; approvals become richer and fail-closed; Pyodide and MCP live support are introduced as optional, lazy foundations that do not change behavior unless explicitly enabled.

**Tech Stack:** Python backend/unittest, Electron IPC, React/Vitest, optional MCP/Pyodide dependencies.

---

### Task 1: Code Exec Relabel And Hard-Disable Guard

**Files:**
- Modify: `chat_code_exec.py`
- Modify: `chat_runtime.py`
- Modify: `ipc_sidecar.py`
- Test: `test/test_chat_code_exec.py`
- Test: `test/test_ipc_sidecar.py`

- [ ] **Step 1: Write tests**
  - Assert `run_python` disabled state reports experimental/best-effort wording.
  - Assert the network string check is labeled best-effort, not guaranteed isolation.
  - Assert Chat code tools are absent unless both config and UI toggle are enabled.
- [ ] **Step 2: Implement minimal code**
  - Rename user-facing text away from “network disabled” guarantees.
  - Add explicit `sandbox_level`/`network_isolation` metadata to proposals/results.
  - Keep code execution off by default.
- [ ] **Step 3: Verify**
  - Run targeted backend tests, then full backend suite.

### Task 2: Approval Flow V2

**Files:**
- Create: `approval_policy.py`
- Modify: `ipc_sidecar.py`
- Modify: `frontend/components/ApprovalPrompt.jsx`
- Test: `test/test_approval_policy.py`
- Test: `test/test_ipc_sidecar.py`
- Test: frontend approval tests

- [ ] **Step 1: Write tests**
  - Risk classification: read/write/destructive/code.
  - Approval timeout fails closed.
  - Approval prompt includes risk level, subject, full details, and allow scopes.
- [ ] **Step 2: Implement minimal policy**
  - Add structured approval payload with `risk_level`, `risk_summary`, `details`, `full_payload`, `default_decision`.
  - Keep only allow/deny execution semantics for now; add scopes as displayed metadata only unless tests require persistence.
- [ ] **Step 3: Verify**
  - Backend and frontend suites pass.

### Task 3: Pyodide/WASM Sandbox Foundation

**Files:**
- Create: `chat_pyodide_sandbox.py`
- Modify: `chat_code_exec.py`
- Test: `test/test_chat_pyodide_sandbox.py`

- [ ] **Step 1: Write tests**
  - Missing Pyodide dependency returns unavailable, not crash.
  - Provider selection prefers Pyodide only when configured.
- [ ] **Step 2: Implement optional lazy foundation**
  - Add capability probe and unavailable result.
  - Do not claim production sandbox unless the runtime is present.

### Task 4: MCP Live Connector Foundation

**Files:**
- Modify: `chat_mcp_client.py`
- Modify: `ipc_sidecar.py`
- Test: `test/test_chat_mcp_client.py`

- [ ] **Step 1: Write tests with fake SDK/client**
  - Enabled connector creates a live provider when SDK factory is supplied.
  - Missing SDK leaves connector disabled with a clear status.
- [ ] **Step 2: Implement lazy connection hooks**
  - Add `create_mcp_clients(...)` with injected factory support and no hard dependency.
  - Keep default behavior unchanged when SDK/config is missing.

### Task 5: Docs And Verification

**Files:**
- Modify: `PROJECT_STATE.md`
- Modify: `work_logs/WORK_LOG.md`

- [ ] **Step 1: Update docs**
  - Record that code exec remains experimental/off-by-default.
  - Record approval v2 and optional sandbox/MCP status.
- [ ] **Step 2: Full verification**
  - `python -m unittest discover -s test -p test_*.py`
  - `npm test`
  - `npm run build`
  - `node --check electron/main.js`
  - `node --check electron/preload.cjs`
