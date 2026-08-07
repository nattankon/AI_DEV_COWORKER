# Code/Cowork Workspace Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add usable Code and Cowork workspace panels for safe file browsing, Git inspection, allowlisted verification, and approval-gated backup restoration.

**Architecture:** Extend the existing JSONL sidecar with request-ID workspace actions. Read-only actions run immediately through `WorkspaceTools`; verification and restore actions run on background workers so approval answers can continue through stdin. React uses a focused workspace panel with lazy directory/file loading and separate Changes, Verification, and Backups views.

**Tech Stack:** Python 3 unittest, Electron IPC/preload, React 19, Vitest/Testing Library, Tailwind CSS, lucide-react.

---

### Task 1: Sidecar Workspace Actions

**Files:**
- Modify: `test/test_ipc_sidecar.py`
- Modify: `ipc_sidecar.py`

- [ ] Add failing tests for changing workspace, listing directories, reading a file, Git inspection, verification result events, and restore result events.
- [ ] Run `python -m unittest test.test_ipc_sidecar -v` and confirm failures are caused by missing workspace commands.
- [ ] Add request-ID commands `set_workspace` and `workspace_action`; route reads through `WorkspaceTools` and run approval-gated actions on background workers.
- [ ] Emit `workspace_changed` and `workspace_response` events without exposing secret file content.
- [ ] Re-run the focused Python tests and confirm they pass.

### Task 2: Electron And Renderer Bridge

**Files:**
- Modify: `electron/main.js`
- Modify: `electron/preload.cjs`
- Modify: `frontend/lib/eel.js`
- Modify: `frontend/adapters/coworkBridge.js`
- Modify: `frontend/tests/coworkBridge.test.js`
- Modify: `frontend/tests/relocationIntegration.test.js`

- [ ] Add failing tests requiring the new inbound channels and bridge methods.
- [ ] Run focused Vitest and confirm missing methods/channels fail.
- [ ] Add `set-workspace` and `workspace-action` IPC handlers and expose narrow preload methods.
- [ ] Map workspace events and methods through the renderer bridge.
- [ ] Re-run focused bridge tests.

### Task 3: Code/Cowork Workspace UI

**Files:**
- Create: `frontend/components/WorkspacePanel.jsx`
- Modify: `frontend/CoworkApp.jsx`
- Modify: `frontend/tests/CoworkApp.test.jsx`

- [ ] Add failing UI tests for selecting Code/Cowork, browsing a folder, opening a file, viewing Git changes/diff, starting an allowlisted verification preset, and requesting backup restore.
- [ ] Run the focused CoworkApp test and confirm the panel is absent.
- [ ] Build a dense workspace panel with Files, Changes, Verification, and Backups tabs; use stable split-pane dimensions and accessible buttons.
- [ ] Keep verification presets fixed to `python-tests`, `frontend-tests`, and `frontend-build`; do not accept arbitrary commands.
- [ ] Route restore through the existing approval prompt and refresh backups after completion.
- [ ] Re-run focused frontend tests.

### Task 4: Verification And Records

**Files:**
- Modify: `PROJECT_STATE.md`
- Modify: `ARCHITECTURE.md`
- Modify: `DEVELOPMENT_ROADMAP.md`
- Modify: `work_logs/WORK_LOG.md`
- Create: `work_logs/sessions/2026-06-13-code-cowork-workspace-panel.jsonl`

- [ ] Run the full Python and frontend test suites.
- [ ] Compile changed Python runtime modules and run the production frontend build.
- [ ] Run the critical npm audit.
- [ ] Update architecture, capability, risk, milestone, human work log, and JSONL audit records.
- [ ] Relaunch Electron and verify renderer diagnostics and visible Code/Cowork panel text.
