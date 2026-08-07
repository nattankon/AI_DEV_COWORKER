# Git And Verification Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Standalone Cowork read-only Git inspection and approval-gated verification presets without exposing arbitrary shell execution.

**Architecture:** Add a focused `developer_tools.py` adapter that invokes subprocesses with argument arrays, workspace-only working directories, timeouts, output limits, and a named command allowlist. `WorkspaceTools` remains the model-facing schema and dispatch registry, while the CLI supplies one approval callback for both writes and verification execution.

**Tech Stack:** Python 3.11+, `subprocess`, `unittest`, Git CLI, npm CLI

---

### Task 1: Define Git inspection behavior

**Files:**
- Create: `test/test_developer_tools.py`
- Create: `developer_tools.py`

- [ ] **Step 1: Write failing tests**

Add tests that initialize a temporary Git repository, commit a baseline file, modify it, and assert `git_status()` and `git_diff()` return structured data. Add a non-repository test asserting a structured `unavailable` result instead of an exception.

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m unittest test.test_developer_tools -v`

Expected: import failure because `developer_tools.py` does not exist.

- [ ] **Step 3: Implement minimal read-only Git adapter**

Implement `DeveloperTools.git_status()` with `git status --short --branch` and `DeveloperTools.git_diff()` with `git diff --no-ext-diff --no-color`. Invoke Git with `shell=False`, set `cwd` to the selected workspace, enforce a timeout, and return `status`, `stdout`, `stderr`, `exit_code`, `duration_ms`, and `truncated`.

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `python -m unittest test.test_developer_tools -v`

Expected: all Git adapter tests pass.

### Task 2: Add approval-gated verification presets

**Files:**
- Modify: `test/test_developer_tools.py`
- Modify: `developer_tools.py`

- [ ] **Step 1: Write failing tests**

Add tests proving that `run_verification("python-tests")` runs only after approval, denial starts no process, unknown preset names are rejected, arguments cannot be supplied by the model, timeout is reported structurally, and output is truncated at the configured limit.

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m unittest test.test_developer_tools -v`

Expected: failures because verification presets and approval proposals are missing.

- [ ] **Step 3: Implement minimal allowlist runner**

Define immutable `VerificationCommand` and `CommandProposal` records. Allow only `python-tests`, `frontend-tests`, and `frontend-build`; store argument arrays rather than command strings; require approval before `subprocess.run`; enforce per-command timeout; return structured results with no shell interpolation.

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `python -m unittest test.test_developer_tools -v`

Expected: all verification safety tests pass.

### Task 3: Expose tools to the agent and CLI

**Files:**
- Modify: `test/test_workspace_tools.py`
- Modify: `test/test_cli.py`
- Modify: `test/test_agent_config.py`
- Modify: `workspace_tools.py`
- Modify: `cli.py`
- Modify: `agent_config.py`
- Modify: `__init__.py`

- [ ] **Step 1: Write failing integration tests**

Assert schemas include `git_status`, `git_diff`, and `run_verification`; dispatch returns structured JSON; `run_verification` accepts only a preset name; and CLI approval displays the exact argument array before execution.

- [ ] **Step 2: Run integration tests and verify RED**

Run: `python -m unittest test.test_workspace_tools test.test_cli test.test_agent_config -v`

Expected: schema and approval assertions fail because the new tools are not registered.

- [ ] **Step 3: Wire the adapters**

Construct `DeveloperTools` inside `WorkspaceTools`, add strict tool schemas and dispatch branches, add CLI command approval rendering, export public records, and tell the small model to inspect Git and run verification before claiming completion.

- [ ] **Step 4: Run integration tests and verify GREEN**

Run: `python -m unittest test.test_workspace_tools test.test_cli test.test_agent_config -v`

Expected: all integration tests pass.

### Task 4: Verify and document

**Files:**
- Modify: `README.md`
- Modify: `ARCHITECTURE.md`
- Modify: `PROJECT_STATE.md`
- Modify: `DEVELOPMENT_ROADMAP.md`
- Modify: `HANDOFF.md`
- Modify: `work_logs/WORK_LOG.md`
- Create: `work_logs/sessions/2026-06-12-git-verification-tools.jsonl`

- [ ] **Step 1: Run fresh verification**

Run the complete Python unittest suite, Python compile checks, frontend tests, frontend production build, npm audit, a temporary Git repository smoke test, denial smoke test, and one approved `python-tests` preset smoke test.

- [ ] **Step 2: Review requirements and risks**

Confirm no API accepts a raw command string, all subprocess calls use `shell=False`, non-Git workspaces fail gracefully, command approval precedes execution, timeout/output bounds are present, and no rollback claim is made for verification commands.

- [ ] **Step 3: Update durable records**

Document capability ownership, exact presets, verification evidence, test counts, and remaining risks. Record that this project folder itself is not currently a Git repository, so Git behavior was verified in temporary repositories.

