# CLI Hardening Four Items Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the four remaining CLI-hardening items before returning to UI/UX work: backup discovery, process-tree cleanup validation, resumable agent state, and a Cowork-owned IPC sidecar adapter.

**Architecture:** Keep `CoworkAgent.run(prompt)` as the production interface. Put backup discovery in `WorkspaceTools`, process-tree validation in `DeveloperTools` tests/preset behavior, resumable state in `AgentRunState`, and IPC in a thin `ipc_sidecar.py` adapter that speaks JSONL to Electron without adding business logic to Electron.

**Tech Stack:** Python 3.11+ stdlib, unittest, existing Cowork adapters, Electron JSONL stdin/stdout bridge.

---

### Task 1: Backup Discovery Tool

**Files:**
- Modify: `workspace_tools.py`
- Test: `test/test_workspace_tools.py`

- [ ] **Step 1: Write failing tests**

Add tests that create rollback backups, call `list_backups`, assert newest-first metadata, assert no file content is exposed, assert manually placed secret backup targets are hidden, and assert the tool schema exposes no arbitrary target path.

- [ ] **Step 2: Run focused tests to verify RED**

Run: `python -m unittest test.test_workspace_tools.WorkspaceToolsTests -v`
Expected: FAIL because `list_backups` does not exist and schema/dispatch do not expose it.

- [ ] **Step 3: Implement minimal tool**

Add `list_backups()` to scan `.cowork/backups/<timestamp>/...`, infer each target with existing `_target_path_from_backup`, skip secret targets, and return metadata only: `backup_path`, `target_path`, `bytes`, and `modified_time`.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run: `python -m unittest test.test_workspace_tools.WorkspaceToolsTests -v`
Expected: PASS.

### Task 2: Real Process-Tree Cleanup Validation

**Files:**
- Modify: `test/test_developer_tools.py`
- Modify: `developer_tools.py` only if the real-child test exposes a behavior gap.

- [ ] **Step 1: Write failing/validating test**

Add a verification preset that starts a child Python process which writes a heartbeat file repeatedly, then sleeps long enough for timeout. After `run_verification`, assert `status == "timeout"` and the heartbeat stops changing after cleanup.

- [ ] **Step 2: Run focused tests**

Run: `python -m unittest test.test_developer_tools.DeveloperToolsTests -v`
Expected: PASS if existing cleanup handles real process trees, otherwise FAIL and then patch `developer_tools.py`.

### Task 3: Resumable Agent State

**Files:**
- Modify: `agent_state.py`
- Modify: `cowork_agent.py`
- Test: `test/test_agent_state.py`
- Test: `test/test_cowork_agent.py`

- [ ] **Step 1: Write failing tests**

Add `AgentRunState.to_snapshot()` and `AgentRunState.from_snapshot()` tests covering stages, writes, verification statuses, and invalid snapshots. Add an agent test that starts from a snapshot with a previous write and refuses final reporting until verification passes.

- [ ] **Step 2: Run focused tests to verify RED**

Run: `python -m unittest test.test_agent_state test.test_cowork_agent -v`
Expected: FAIL because snapshot methods and agent resume injection do not exist.

- [ ] **Step 3: Implement minimal resume support**

Add snapshot serialization to `AgentRunState`. Add optional `initial_run_state` to `CoworkAgent.run()` and preserve the completion gate behavior from restored state.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run: `python -m unittest test.test_agent_state test.test_cowork_agent -v`
Expected: PASS.

### Task 4: Cowork-Owned IPC Sidecar Adapter

**Files:**
- Create: `ipc_sidecar.py`
- Modify: `__init__.py`
- Modify: `package.json`
- Test: `test/test_ipc_sidecar.py`

- [ ] **Step 1: Write failing tests**

Add tests for JSONL command handling: `send_cowork` emits `cowork_log` start/done events and uses `CoworkAgent.run`; `fetch_available_models` emits `registered model` payloads; malformed JSON emits backend error without crashing.

- [ ] **Step 2: Run focused tests to verify RED**

Run: `python -m unittest test.test_ipc_sidecar -v`
Expected: FAIL because `ipc_sidecar.py` does not exist.

- [ ] **Step 3: Implement thin sidecar**

Implement `IpcSidecar` that reads JSON lines, dispatches commands, writes one JSON event per line with `__ipc_type`, and constructs Cowork dependencies via factories for testability. Keep secrets out of logs.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run: `python -m unittest test.test_ipc_sidecar -v`
Expected: PASS.

### Final Verification

- [ ] Run full backend tests: `python -m unittest discover -s test -p "test_*.py" -v`
- [ ] Compile Python modules: `python -m py_compile __init__.py agent_config.py agent_state.py cli.py cli_config.py cowork.py cowork_agent.py developer_tools.py ipc_sidecar.py local_ai.py secret_guard.py session_store.py workspace_tools.py`
- [ ] Run frontend tests: `npm.cmd test`
- [ ] Run frontend build: `npm.cmd run build`
- [ ] Run critical audit: `npm.cmd audit --audit-level=critical`
- [ ] Run a sidecar smoke with a fake model or no-model command.
- [ ] Update `PROJECT_STATE.md`, `ARCHITECTURE.md`, `HANDOFF.md`, and `work_logs/WORK_LOG.md`.
