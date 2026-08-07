# Claude-Like UI Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-skin the standalone Cowork frontend to match the provided Claude-like preview, with chat-first layout and code/cowork affordances deferred.

**Architecture:** Keep the existing React state, bridge, session storage, and composer submission behavior. Change only the frontend shell/components/styles so the first screen becomes a Claude-like app: light sidebar, slim chrome, centered greeting, large composer, quick actions, and status chips.

**Tech Stack:** React 19, Tailwind CSS, Vitest, Testing Library, Vite.

---

### Task 1: Lock The New UI Contract In Tests

**Files:**
- Modify: `frontend/tests/CoworkApp.test.jsx`

- [ ] **Step 1: Write failing UI expectations**

Assert that `CoworkApp` renders `Chat`, `Cowork`, `Code`, `Good afternoon`, `How can I help you today?`, `New chat`, `Recents`, `Ask before write`, and `Server`.

- [ ] **Step 2: Run test to verify RED**

Run: `npm.cmd test -- frontend/tests/CoworkApp.test.jsx`
Expected: FAIL because the existing UI still renders dark dashboard labels.

### Task 2: Build The Claude-Like Shell

**Files:**
- Modify: `frontend/CoworkStandalone.jsx`
- Modify: `frontend/CoworkApp.jsx`
- Modify: `frontend/components/SessionRail.jsx`
- Modify: `frontend/components/AppHeader.jsx`
- Modify: `frontend/components/Composer.jsx`
- Modify: `frontend/components/Timeline.jsx`
- Modify: `styles/index.css`

- [ ] **Step 1: Replace dark app chrome with light Claude-like app shell**

Use a full-screen light background, fixed-height top chrome, 286px sidebar on desktop, centered hero stage when timeline is empty, and a normal timeline view once messages exist.

- [ ] **Step 2: Preserve functional behavior**

Keep session switching, workspace selection, prompt submission, bridge injection, and busy disabled state intact.

- [ ] **Step 3: Run focused frontend tests**

Run: `npm.cmd test -- frontend/tests/CoworkApp.test.jsx`
Expected: PASS.

### Task 3: Verify The Rebuild

**Files:**
- Modify: `work_logs/WORK_LOG.md`
- Modify: `PROJECT_STATE.md`
- Add: `work_logs/sessions/2026-06-12-claude-like-ui-refresh.jsonl`

- [ ] **Step 1: Run full frontend and build verification**

Run: `npm.cmd test`, `npm.cmd run build`, and browser/Playwright visual smoke.

- [ ] **Step 2: Record progress**

Update project state and work logs with the new UI direction, tests run, and remaining code-mode/approval work.
