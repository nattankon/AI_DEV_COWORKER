# Unified Role And Conversation UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Cowork and Code the same persistent system-role authority and left/right conversation presentation as Chat.

**Architecture:** Keep role persistence in `ChatMemoryStore`, but pass its formatted role context separately through `IpcSidecar` into `CoworkAgent.run()` so the agent inserts it as a system message rather than user content. Reuse the existing `MessageEntry` bubble renderer for all three modes and preserve mode-specific labels, Chat-only editing, web sources, attachments, and system-error treatment.

**Tech Stack:** Python 3 unittest backend, React, Tailwind CSS, Vitest/Testing Library, Electron/Vite.

---

### Task 1: Promote Cowork And Code Role Context

**Files:**
- Modify: `test/test_cowork_agent.py`
- Modify: `test/test_ipc_sidecar.py`
- Modify: `cowork_agent.py`
- Modify: `ipc_sidecar.py`

- [x] Add a failing agent test asserting that role context is a system message and the user prompt remains unchanged.
- [x] Update Cowork/Code sidecar tests to require `system_context` instead of role text inside the prompt.
- [x] Run the focused backend tests and confirm they fail for the missing system-context path.
- [x] Add optional `system_context` forwarding to the fallback runner and `CoworkAgent.run()`.
- [x] Run the focused backend tests and confirm they pass.

### Task 2: Unify Conversation Presentation

**Files:**
- Modify: `frontend/tests/Timeline.test.jsx`
- Modify: `frontend/components/Timeline.jsx`
- Modify: `frontend/components/MessageEntry.jsx`

- [x] Add failing UI tests for right-aligned Cowork/Code user bubbles, left-aligned assistant/system bubbles, mode labels, Markdown, and copy controls.
- [x] Run the focused Vitest file and confirm the new assertions fail against the flat timeline.
- [x] Generalize the existing Chat bubble renderer and timeline spacing to all three modes while retaining Chat-only edit and web-source behavior.
- [x] Run the focused Vitest file and confirm it passes.

### Task 3: Verify And Record

**Files:**
- Modify: `PROJECT_STATE.md`
- Modify: `work_logs/WORK_LOG.md`

- [x] Run focused backend and frontend tests.
- [x] Run the complete backend and frontend suites plus the production build.
- [x] Inspect desktop and narrow screenshots for alignment, overflow, and preserved system-error styling.
- [x] Record the capability, verification evidence, risks, and skills used.
- [x] Review the final diff and leave unrelated `TUNER.txt` untouched.
