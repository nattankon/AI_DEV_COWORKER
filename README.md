# AI Dev Co-worker

Standalone local-first AI coding coworker.

The CLI is the primary product milestone. It owns its Local AI connection, agent loop, workspace tools, write approvals, conversation history, and JSONL session records. It does not import, spawn, package, or read application code from the legacy Blender program.

Active development root: `C:\AI_DEV_COWORKER`.

- `cowork.py`: direct CLI entrypoint.
- `cli.py`: one-shot and interactive command adapter.
- `cowork_agent.py`: independent Local AI tool-calling loop.
- `workspace_tools.py`: workspace-constrained read, list, search, and approved atomic writes.
- `secret_guard.py`: blocks environment secrets, private keys, and credential stores before tool access.
- `agent_config.py`: workspace memory, system prompt, and iteration limits.
- `local_ai.py`: Local AI model namespace and OpenAI-compatible client helpers.
- `session_store.py`: append-only local conversation and tool-event persistence.
- `frontend/` and `electron/`: paused UI prototype retained for the later UI/UX milestone.
- `AGENTS.md`: mandatory development, skill, verification, and logging rules.
- `PROJECT_STATE.md`: current capability, risks, and next milestone.
- `docs/`: all other documentation — see `docs/INDEX.md` for the map (reference docs, active specs, archived specs).
- `work_logs/`: human-readable work history, review log, quality/smoke reports, and test-run logs.
- `package-lock.json`: standalone npm dependency lockfile for this app.

## CLI Setup

Run these from `C:\AI_DEV_COWORKER`:

- `python -m pip install -e .`
- `cowork --list-models`
- `cowork --workspace C:\path\to\project`
- `cowork --workspace C:\path\to\project --prompt "Inspect this repository"`

Defaults:

- Endpoint: `http://127.0.0.1:1234/v1`
- Model: `local:qwen/qwen3.5-9b`
- Workspace: current directory
- Writes: require an interactive diff approval
- Secret paths: hidden from list/search and denied for read/write

Use `--yes` only when every proposed write in that process may be approved automatically.

Interactive commands: `/models`, `/clear`, `/exit`.

## Verification Commands

- `python -m unittest discover -s test -p "test_*.py" -v`
- `npm.cmd install --cache .\.npm-cache`
- `npm.cmd test`
- `npm.cmd run build`
- `npm.cmd audit --audit-level=critical`

Set `COWORK_USER_DATA_DIR` to move JSONL session records outside the checkout. Electron packaging is intentionally deferred until a Cowork-owned IPC adapter exists.
