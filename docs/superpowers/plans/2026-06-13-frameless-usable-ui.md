# Frameless Usable UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the native Electron title bar and make the visible Claude-like first screen controls usable.

**Architecture:** Keep Electron window control IPC in `electron/main.js` and `electron/preload.cjs`, then connect React header buttons to the existing preload bridge. Keep first-screen UI behavior local to `CoworkApp`, with `Composer` accepting controlled focus/prompt seeds and `SessionRail` exposing active mode selection.

**Tech Stack:** Electron BrowserWindow, React, Vitest, Testing Library, Tailwind CSS.

---

### Task 1: Regression Tests

**Files:**
- Modify: `frontend/tests/relocationIntegration.test.js`
- Modify: `frontend/tests/CoworkApp.test.jsx`
- Modify: `frontend/tests/Composer.test.jsx`

- [ ] **Step 1: Add tests for frameless config, titlebar IPC buttons, selectable mode tabs, sidebar state, search focus, and quick-action prompt seeding.**
- [ ] **Step 2: Run focused frontend tests and confirm they fail for missing behavior.**

### Task 2: Electron And Header Wiring

**Files:**
- Modify: `electron/main.js`
- Modify: `frontend/components/AppHeader.jsx`
- Modify: `styles/index.css`

- [ ] **Step 1: Change BrowserWindow to `frame: false` and a white background.**
- [ ] **Step 2: Mark the custom header as a drag region and all buttons/chips as no-drag.**
- [ ] **Step 3: Wire minimize, maximize, and close buttons to `window.electronAPI`.**

### Task 3: First-Screen Interaction Wiring

**Files:**
- Modify: `frontend/CoworkApp.jsx`
- Modify: `frontend/components/SessionRail.jsx`
- Modify: `frontend/components/Composer.jsx`

- [ ] **Step 1: Add active mode state and pass it into `SessionRail`.**
- [ ] **Step 2: Add sidebar toggle, search focus, previous/next session navigation, and quick-action prompt seeding.**
- [ ] **Step 3: Let `Composer` accept a suggested prompt and focus signal.**

### Task 4: Verification And Records

**Files:**
- Modify: `PROJECT_STATE.md`
- Modify: `work_logs/WORK_LOG.md`
- Create: `work_logs/sessions/2026-06-13-frameless-usable-ui.jsonl`

- [ ] **Step 1: Run focused tests, full frontend tests, production build, and critical npm audit.**
- [ ] **Step 2: Relaunch Electron and inspect renderer diagnostics.**
- [ ] **Step 3: Update project state and work logs with evidence and next steps.**
