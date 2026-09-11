# Adaptive Chat Context Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use systematic debugging, test-driven development, and verification-before-completion while implementing this plan task-by-task.

**Goal:** Keep long native Chat conversations reliable by compacting before the provider limit, retrying one transient server failure with a smaller prompt, and displaying Backend-planned context usage.

**Architecture:** Extend the existing token-aware planner with a configurable soft utilization target while preserving fixed system/Role/current-user messages and complete recent turns. The Chat sidecar emits sanitized context diagnostics and retries only retryable context/server failures once with older conversational turns removed before using the existing model fallback chain. React prefers the latest session/model-matched Backend diagnostic and falls back to its local estimate before the first request.

**Tech Stack:** Python 3 dataclasses/unittest, Electron JSONL IPC, React 19, Vitest.

---

### Task 1: Soft Context Target

**Files:**
- Modify: `chat_conversation_context.py`
- Modify: `chat_runtime.py`
- Test: `test/test_chat_conversation_context.py`
- Test: `test/test_chat_runtime.py`

- [x] Write failing tests proving a 65% soft target compacts older complete turns before the advertised hard window while retaining the latest complete turn.
- [x] Run the focused Python tests and confirm failure because no target utilization exists.
- [x] Add a bounded `conversation_context_target_ratio` setting and make the planner reserve against the soft window.
- [x] Run focused tests and confirm they pass.

### Task 2: One Reduced-Context Retry

**Files:**
- Modify: `chat_conversation_context.py`
- Modify: `ipc_sidecar.py`
- Test: `test/test_chat_conversation_context.py`
- Test: `test/test_ipc_sidecar.py`

- [x] Write failing tests proving retry reduction keeps all system messages/current user content, retains recent dialogue, and removes older dialogue.
- [x] Write a failing sidecar test where a Chat model returns HTTP 500 once and succeeds only after receiving a smaller prompt.
- [x] Run focused tests and confirm the missing retry behavior.
- [x] Implement one bounded retry only for context-limit or HTTP 5xx failures, reset any partial stream, emit a compacting status, then preserve the existing fallback order if retry fails.
- [x] Run focused tests and confirm they pass.

### Task 3: Backend Context Indicator

**Files:**
- Modify: `ipc_sidecar.py`
- Modify: `frontend/lib/eel.js`
- Modify: `frontend/adapters/coworkBridge.js`
- Modify: `frontend/CoworkApp.jsx`
- Modify: `frontend/model/contextUsage.js`
- Test: `test/test_ipc_sidecar.py`
- Test: `frontend/tests/contextUsage.test.js`
- Test: `frontend/tests/coworkBridge.test.js`

- [x] Write failing tests for a sanitized `chat_context` event and Backend-plan precedence in the indicator.
- [x] Run focused tests and confirm failure because the event and override are absent.
- [x] Emit only counts/percent/model/session metadata and subscribe to it through the existing bridge.
- [x] Store the latest diagnostic per Chat session and use it only when its model matches the selected model.
- [x] Run focused tests and confirm they pass.

### Task 4: Records And Verification

**Files:**
- Modify: `PROJECT_STATE.md`
- Modify: `work_logs/WORK_LOG.md`

- [x] Run the complete Python suite, complete frontend suite, and production frontend build.
- [x] Inspect the final diff and ensure `TUNER.txt` remains untouched.
- [x] Record behavior, risks, rollback boundary, skills, and fresh verification evidence.
