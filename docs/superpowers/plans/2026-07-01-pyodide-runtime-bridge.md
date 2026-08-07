# Pyodide Runtime Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or inline TDD task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Chat code execution's default `pyodide` sandbox capable of running Python through a local Pyodide/WASM runtime when the npm package is installed, while preserving safe unavailable behavior when it is not.

**Architecture:** Keep `CodeExecutionToolProvider` unchanged at the tool-loop interface. Deepen `chat_pyodide_sandbox.py` so it can either use an injected runtime for tests or a local Node-backed Pyodide runtime discovered from the app root. A small `tools/pyodide_runner.mjs` script owns the JavaScript/WASM execution details and exchanges one JSON payload with Python over stdin/stdout.

**Tech Stack:** Python unittest, Node.js ESM, npm `pyodide`, Electron sidecar config.

---

### Task 1: Node-backed Pyodide runtime seam

**Files:**
- Modify: `chat_pyodide_sandbox.py`
- Create: `tools/pyodide_runner.mjs`
- Modify: `test/test_chat_pyodide_sandbox.py`

- [ ] Step 1: Add failing tests for runtime discovery and runner invocation.
- [ ] Step 2: Implement `NodePyodideRuntime` with JSON stdin/stdout contract, timeout, output limiting, and unavailable/error result handling.
- [ ] Step 3: Add `tools/pyodide_runner.mjs` to load `pyodide`, capture stdout/stderr, run code, and emit JSON.
- [ ] Step 4: Verify targeted Pyodide tests.

### Task 2: Package dependency and sidecar root wiring

**Files:**
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `ipc_sidecar.py`
- Modify: `test/test_ipc_sidecar.py`

- [ ] Step 1: Add/verify `pyodide` npm dependency.
- [ ] Step 2: Pass the runtime root into `PyodideSandbox` from sidecar so the loader can find `node_modules/pyodide` in dev and packaged layouts.
- [ ] Step 3: Add/verify tests that the provider still defaults to Pyodide and exposes Pyodide metadata.

### Task 3: Docs, logs, verification

**Files:**
- Modify: `PROJECT_STATE.md`
- Modify: `work_logs/WORK_LOG.md`

- [ ] Step 1: Update state to say Pyodide runtime bridge is installed/available when npm dependency exists.
- [ ] Step 2: Run targeted tests, full backend suite, frontend suite, build, and Electron syntax checks.
- [ ] Step 3: Restart Electron app if verification passes.
