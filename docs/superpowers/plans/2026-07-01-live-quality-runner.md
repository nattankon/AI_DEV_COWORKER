# Live Quality Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use inline execution in this session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement de-hardcoded research strategy, grounding-aware quality scoring, and an opt-in live quality runner.

**Architecture:** Keep query planning generic through a data-driven query-type registry, reuse the existing answer guard for hallucination checks, and add a headless quality runner that accepts an injected Chat pipeline for tests and optional live execution. The default unit test suite never calls live models or network.

**Tech Stack:** Python `unittest`, existing Chat IPC/runtime classes, JSON report files under `work_logs/`.

---

### Task 1: De-Hardcode Research Strategy

**Files:**
- Modify: `chat_research_strategy.py`
- Modify: `test/test_chat_research_strategy.py`

- [ ] Write failing tests proving docs/pricing/github/news resolve via registry, fuel query no longer gets a fuel-specific query, and a dummy profile works through the same path.
- [ ] Implement `_QUERY_TYPE_PROFILES` and `_build_plan_from_profiles`.
- [ ] Remove fuel/oil topic branch from code control flow.

### Task 2: Grounding-Aware Quality Eval

**Files:**
- Modify: `chat_quality_eval.py`
- Modify: `test/test_chat_quality_eval.py`

- [ ] Write failing tests for hallucinated year/price with evidence, grounded values with evidence, and general empty-evidence no-op.
- [ ] Thread `evidence` through `evaluate_case_result` and `run_quality_eval_snapshot`.
- [ ] Reuse `chat_answer_guard.validate_answer` with prompt/today allow values.

### Task 3: Live Quality Runner

**Files:**
- Create: `chat_quality_runner.py`
- Create: `test/test_chat_quality_runner.py`
- Modify: `ipc_sidecar.py`
- Modify: `chat_quality_eval.py`

- [ ] Write fake-pipeline tests for matrix scoring, hallucination cells, per-cell error continuation, and category filtering.
- [ ] Implement `run_quality_eval_live`.
- [ ] Implement `run_chat_once` against `IpcSidecar._run_plain_chat`, returning answer, sources, empty evidence for legacy path unless captured.
- [ ] Add CLI entrypoint gated by explicit arguments and write JSON/Markdown reports under `work_logs/`.

### Task 4: Verification And Docs

**Files:**
- Modify: `PROJECT_STATE.md`
- Modify: `work_logs/WORK_LOG.md`

- [ ] Run targeted tests after each task.
- [ ] Run full backend, frontend, build, and Electron syntax verification.
- [ ] Update project state and work log with exact verification output.
