# Standalone Cowork CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Local AI Cowork CLI that runs entirely from `C:\AI_DEV_COWORKER` without importing, spawning, packaging, or reading code from `C:\API-BLENDER`.

**Architecture:** Replace the host-shaped `engine` interface with one deep `CoworkAgent` module. Its interface accepts a prompt and returns a final response; Local AI requests, tool dispatch, workspace validation, mutation approval, and session recording remain inside the implementation. The CLI is the first adapter at this seam; tests use deterministic fake model and approval adapters.

**Tech Stack:** Python 3.14, OpenAI Python client, `argparse`, `unittest`, JSONL session records

**Completed:** 2026-06-12. The implementation uses a future `ipc_sidecar.py` placeholder rather than pointing Electron at `cowork.py`; UI IPC remains intentionally deferred.

---

### Task 1: Define CLI Configuration

**Files:**
- Create: `cli_config.py`
- Create: `test/test_cli_config.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_defaults_to_lm_studio_and_current_workspace():
    config = parse_cli_args(["--prompt", "inspect this repo"])
    assert config.base_url == "http://127.0.0.1:1234/v1"
    assert config.workspace == Path.cwd().resolve()

def test_rejects_missing_workspace():
    with pytest.raises(ValueError):
        parse_cli_args(["--workspace", "missing", "--prompt", "x"])
```

- [ ] **Step 2: Run `python -m unittest test.test_cli_config -v`**

Expected: FAIL because `cli_config` does not exist.

- [ ] **Step 3: Implement immutable `CliConfig` and `parse_cli_args`**

The parser must expose `--workspace`, `--base-url`, `--api-key`, `--model`, `--prompt`, `--yes`, `--max-iterations`, and `--list-models`. It must resolve the workspace and reject non-directories.

- [ ] **Step 4: Re-run the test**

Expected: PASS.

### Task 2: Implement Workspace-Constrained Tools

**Files:**
- Create: `workspace_tools.py`
- Create: `test/test_workspace_tools.py`

- [ ] **Step 1: Write failing tests for read/list/search, traversal denial, and approved writes**

```python
tools = WorkspaceTools(root=temp_root, approve=lambda proposal: True)
assert tools.read_file("src/app.py") == "print('ok')"
with self.assertRaises(WorkspaceAccessError):
    tools.read_file("../secret.txt")
assert tools.write_file("notes.txt", "hello")["status"] == "written"
```

- [ ] **Step 2: Run `python -m unittest test.test_workspace_tools -v`**

Expected: FAIL because `workspace_tools` does not exist.

- [ ] **Step 3: Implement `WorkspaceTools`**

Expose OpenAI tool schemas and dispatch for `list_directory`, `search_files`, `read_file`, and `write_file`. Canonicalize every target against the selected Workspace. `write_file` must call the approval adapter before mutation and return structured JSON.

- [ ] **Step 4: Re-run the test**

Expected: PASS.

### Task 3: Implement The Independent Agent Loop

**Files:**
- Create: `cowork_agent.py`
- Create: `test/test_cowork_agent.py`
- Modify: `agent_config.py`

- [ ] **Step 1: Write a failing fake-model test**

```python
agent = CoworkAgent(model=fake_model, tools=tools, recorder=recorder, max_iterations=4)
reply = agent.run("read README")
assert reply == "Repository inspected."
assert fake_model.requests[1]["messages"][-1]["role"] == "tool"
```

- [ ] **Step 2: Run `python -m unittest test.test_cowork_agent -v`**

Expected: FAIL because `CoworkAgent` does not exist.

- [ ] **Step 3: Implement the loop**

The model adapter interface is `complete(messages, tools) -> assistant message`. The implementation appends assistant tool calls, dispatches tools, appends tool results, stops on final text, records events, and raises after the iteration limit.

- [ ] **Step 4: Add `OpenAIChatModel`**

The Local AI adapter must call `client.chat.completions.create` with the selected model ID, messages, tool schemas, temperature `0`, and one tool-call round at a time.

- [ ] **Step 5: Re-run the test**

Expected: PASS.

### Task 4: Build The CLI Adapter

**Files:**
- Create: `cli.py`
- Create: `cowork.py`
- Create: `test/test_cli.py`
- Create: `pyproject.toml`

- [ ] **Step 1: Write failing tests for one-shot output and model listing**

```python
exit_code = main(["--prompt", "hello"], dependencies=fakes)
assert exit_code == 0
assert stdout.getvalue() == "answer\n"
```

- [ ] **Step 2: Run `python -m unittest test.test_cli -v`**

Expected: FAIL because `cli.main` does not exist.

- [ ] **Step 3: Implement one-shot and interactive modes**

`python cowork.py --prompt "..."` prints one answer. `python cowork.py` enters a prompt loop. `/exit` stops, `/models` lists Local AI models, and `/clear` resets in-memory conversation history.

- [ ] **Step 4: Add installation metadata**

`pyproject.toml` must declare the `openai` dependency and the `cowork` console script.

- [ ] **Step 5: Re-run the test**

Expected: PASS.

### Task 5: Remove Legacy Host Runtime Dependency

**Files:**
- Modify: `electron/main.js`
- Modify: `package.json`
- Modify: `frontend/tests/relocationIntegration.test.js`
- Delete: legacy-host packaging assumptions from standalone configuration

- [ ] **Step 1: Change the regression test to reject `API-BLENDER` references**

```js
expect(JSON.stringify(packageJson)).not.toContain("API-BLENDER");
expect(getPythonEntryCandidates(...)).not.toContain(expect.stringContaining("API-BLENDER"));
```

- [ ] **Step 2: Run the targeted Vitest**

Expected: FAIL while standalone packaging still references the host.

- [ ] **Step 3: Point Electron at `cowork.py` and package only Cowork-owned Python files**

The standalone app must not import or package host source. UI IPC adaptation can follow after the CLI milestone; Electron must fail clearly if its future JSON IPC adapter is unavailable.

- [ ] **Step 4: Re-run the targeted Vitest**

Expected: PASS.

### Task 6: Verify Independence And Record State

**Files:**
- Modify: `README.md`
- Modify: `ARCHITECTURE.md`
- Modify: `PROJECT_STATE.md`
- Modify: `HANDOFF.md`
- Append: `work_logs/WORK_LOG.md`
- Add: `work_logs/sessions/<timestamp>-standalone-cli.jsonl`

- [ ] **Step 1: Run all Python tests**

Run: `python -m unittest discover -s test -p "test_*.py" -v`

Expected: all tests pass.

- [ ] **Step 2: Run standalone frontend regression tests and build**

Run: `npm.cmd test && npm.cmd run build && npm.cmd audit --audit-level=critical`

Expected: all commands exit `0`.

- [ ] **Step 3: Scan for legacy runtime references**

Run: `rg -n "API-BLENDER|app_main.py|cowork_feature" --glob "!work_logs/**" --glob "!docs/**" .`

Expected: no standalone runtime or package reference to the legacy host.

- [ ] **Step 4: Run CLI smoke checks**

Run: `python cowork.py --help` and `python cowork.py --list-models` against LM Studio when available.

Expected: help exits `0`; model listing returns models or a concise connection error without importing host code.

- [ ] **Step 5: Update durable records**

Record commands, results, known risks, and skills used without secrets.
