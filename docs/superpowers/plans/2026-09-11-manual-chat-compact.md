# Manual Chat Compact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use systematic debugging, test-driven development, and verification-before-completion while implementing this plan task-by-task.

**Goal:** Make `/compact` create a durable semantic summary instead of deleting all but eight arbitrary timeline events.

**Architecture:** Add a dedicated Chat-only IPC request and result event. The Python sidecar summarizes older complete dialogue turns with the selected model, preserves recent turns, updates its in-memory history, and returns a bounded summary plus counts; React persists the summary as hidden system context and shows only a concise completion notice in the timeline.

**Tech Stack:** Python 3/unittest, Electron IPC, React 19, Vitest.

---

### Task 1: Backend Manual Compaction

**Files:**
- Modify: `chat_conversation_context.py`
- Modify: `ipc_sidecar.py`
- Test: `test/test_chat_conversation_context.py`
- Test: `test/test_ipc_sidecar.py`

- [x] Write failing tests for splitting older dialogue from recent complete turns and for a `compact_chat` command that emits a semantic summary result.
- [x] Run the focused tests and confirm the feature is absent.
- [x] Implement bounded Chat history splitting, model-backed summarization, in-memory history replacement, result counts, and busy/idle lifecycle events.
- [x] Run the focused tests and confirm they pass.

### Task 2: Durable Frontend Summary

**Files:**
- Modify: `electron/main.js`
- Modify: `electron/preload.cjs`
- Modify: `frontend/lib/eel.js`
- Modify: `frontend/adapters/coworkBridge.js`
- Modify: `frontend/CoworkApp.jsx`
- Modify: `frontend/components/TimelineEntry.jsx`
- Test: `frontend/tests/coworkBridge.test.js`
- Test: `frontend/tests/CoworkApp.test.jsx`
- Test: `frontend/tests/ipcChannelAllowlist.test.js`

- [x] Write failing tests proving `/compact` calls the dedicated bridge, does not call normal Chat generation, persists hidden system context, retains recent messages, and displays completion counts.
- [x] Run the focused tests and confirm the old eight-event trim fails the new behavior.
- [x] Wire the request/result IPC, map hidden summary events into Chat history, hide summary context from the timeline, and scope `/compact` to Chat.
- [x] Run the focused tests and confirm they pass.

### Task 3: Records And Verification

**Files:**
- Modify: `PROJECT_STATE.md`
- Modify: `work_logs/WORK_LOG.md`

- [x] Run complete backend and frontend tests plus the production build.
- [x] Inspect the final diff and confirm `TUNER.txt` remains untouched.
- [x] Record behavior, safety/rollback boundaries, skills, and fresh verification evidence.
