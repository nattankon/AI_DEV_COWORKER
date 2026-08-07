# Agent State Machine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit Inspect/Plan/Act/Verify/Report controller layer to the standalone Cowork agent loop.

**Architecture:** Add a small `agent_state.py` module that tracks stage transitions, write activity, verification results, and completion evidence. `CoworkAgent` records state events through the existing recorder and blocks final reporting after writes until a passing `run_verification` result has been observed.

**Tech Stack:** Python 3.11+, `unittest`, existing Cowork agent/tool abstractions

---

### Task 1: State Tracker

**Files:**
- Create: `agent_state.py`
- Create: `test/test_agent_state.py`

- [ ] **Step 1: Write failing tests**

Add tests that prove a fresh state begins in `inspect`, write tool results require verification, passing `run_verification` satisfies completion evidence, and denied/error verification does not.

- [ ] **Step 2: Run RED**

Run: `python -m unittest test.test_agent_state -v`
Expected: import failure for `agent_state`.

- [ ] **Step 3: Implement tracker**

Create `AgentRunState` with `record_stage`, `observe_tool_result`, `requires_verification_before_report`, and `completion_evidence`.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest test.test_agent_state -v`
Expected: all state tracker tests pass.

### Task 2: Agent Loop Integration

**Files:**
- Modify: `cowork_agent.py`
- Modify: `test/test_cowork_agent.py`
- Modify: `agent_config.py`
- Modify: `test/test_agent_config.py`

- [ ] **Step 1: Write failing integration tests**

Add a test where the model writes a file, then tries to answer final text before verification. Assert the agent sends a repair message requiring `run_verification`, records `agent_stage` events, records `completion_evidence`, and only returns after a passing verification result.

- [ ] **Step 2: Run RED**

Run: `python -m unittest test.test_cowork_agent test.test_agent_config -v`
Expected: missing state events and missing repair behavior.

- [ ] **Step 3: Wire tracker**

Instantiate `AgentRunState` per run, record inspect/plan before the first model call, record act for non-verification tools, record verify for `run_verification`, block report until verification passes after writes, and record evidence before finish.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest test.test_agent_state test.test_cowork_agent test.test_agent_config -v`
Expected: all state integration tests pass.

### Task 3: Verification And Records

**Files:**
- Modify: `PROJECT_STATE.md`
- Modify: `ARCHITECTURE.md`
- Modify: `HANDOFF.md`
- Modify: `DEVELOPMENT_ROADMAP.md`
- Modify: `work_logs/WORK_LOG.md`
- Create: `work_logs/sessions/2026-06-12-agent-state-machine.jsonl`

- [ ] **Step 1: Run fresh verification**

Run full Python tests, Python compilation, frontend tests, frontend build, npm audit, and a live smoke if LM Studio is available.

- [ ] **Step 2: Update records**

Record test evidence, state-machine behavior, remaining risks, and next actions.
