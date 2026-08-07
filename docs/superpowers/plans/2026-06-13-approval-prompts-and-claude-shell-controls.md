# Approval Prompts And Claude Shell Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the visible Claude-style shell interactions from the reference screenshots and enable explicit UI approval prompts for file writes and verification runs.

**Architecture:** Keep privileged actions in the Python sidecar and Electron preload bridge. React owns display state for menus, projects, model/effort choices, and approval prompts, while approval decisions flow back through the existing `answer_question` IPC command.

**Tech Stack:** React, Electron IPC, Python sidecar, Vitest, Python unittest, Tailwind CSS.

---

### Task 1: Approval Prompt Contract

**Files:**
- Modify: `ipc_sidecar.py`
- Modify: `frontend/adapters/coworkBridge.js`
- Test: `tests/test_ipc_sidecar.py`
- Test: `frontend/tests/coworkBridge.test.js`

- [ ] **Step 1: Add a failing sidecar test proving `approve_write` emits a `cowork_interactive_question` payload and waits for `answer_question`.**
- [ ] **Step 2: Add a failing sidecar test proving `approve_command` uses the same queue and resolves deny safely.**
- [ ] **Step 3: Implement a pending approval queue keyed by approval id in `ipc_sidecar.py`.**
- [ ] **Step 4: Normalize approval payloads in the frontend bridge with type, title, diff, command, and risk fields.**

### Task 2: Approval UI

**Files:**
- Create: `frontend/components/ApprovalPrompt.jsx`
- Modify: `frontend/CoworkApp.jsx`
- Test: `frontend/tests/CoworkApp.test.jsx`

- [ ] **Step 1: Add failing React tests for rendering a write approval diff and sending allow/deny via the bridge.**
- [ ] **Step 2: Add failing React tests for rendering a verification approval command summary.**
- [ ] **Step 3: Implement the approval prompt panel with Approve and Deny buttons.**
- [ ] **Step 4: Append `approval.resolved` events to the timeline after a decision.**

### Task 3: Claude-Style Shell Controls

**Files:**
- Create: `frontend/components/ShellMenu.jsx`
- Create: `frontend/components/ProjectsView.jsx`
- Create: `frontend/components/ModelMenu.jsx`
- Modify: `frontend/components/AppHeader.jsx`
- Modify: `frontend/components/Composer.jsx`
- Modify: `frontend/components/SessionRail.jsx`
- Modify: `frontend/CoworkApp.jsx`
- Test: `frontend/tests/CoworkApp.test.jsx`
- Test: `frontend/tests/Composer.test.jsx`

- [ ] **Step 1: Add failing tests for hamburger menu items, recent session context menu, and pin/rename/delete local session actions.**
- [ ] **Step 2: Add failing tests for plus menu items, slash skills suggestions, and model/effort selection.**
- [ ] **Step 3: Add failing tests for Projects view search/new/select-folder behavior.**
- [ ] **Step 4: Implement local state and reusable popover components with accessible labels.**

### Task 4: Verification And Records

**Files:**
- Modify: `PROJECT_STATE.md`
- Modify: `work_logs/WORK_LOG.md`
- Create: `work_logs/sessions/2026-06-13-approval-prompts-shell-controls.jsonl`

- [ ] **Step 1: Run focused frontend and Python tests.**
- [ ] **Step 2: Run full frontend tests, Python unittests, production build, and critical audit.**
- [ ] **Step 3: Relaunch Electron and inspect renderer diagnostics.**
- [ ] **Step 4: Update durable project state and work logs.**
