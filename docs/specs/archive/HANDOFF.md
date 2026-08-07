# AI Dev Co-worker Handoff

## Working Directory

Use this folder for future Cowork-only development:

`C:\AI_DEV_COWORKER`

No other application checkout is required to develop, install, or run the Cowork CLI.

## Current Status

- Standalone Cowork CLI is the active product milestone.
- It installs as the `cowork` command and runs independently from directories outside the checkout.
- It owns Local AI model discovery, tool calling, workspace constraints, write approvals, and JSONL session records.
- Secret Guard hides and denies environment secrets, private keys, and credential stores before tool access.
- DeveloperTools adds secret-aware Git status/diff and approval-gated verification presets.
- Approved replacement writes retain rollback backups under `.cowork/backups/`.
- `restore_backup` can restore a rollback backup with approval and creates a pre-restore backup of the current file.
- `list_backups` exposes rollback backup metadata without file contents and hides secret-classified targets.
- Workspace writes and verification runs emit structured audit events into active session JSONL records.
- Verification timeout handling performs best-effort process-tree cleanup and has deterministic coverage for Python and npm worker trees.
- Agent runs now record Inspect/Plan/Act/Verify/Report stages, state snapshots, and require a passing verification result before final reporting after file writes.
- `ipc_sidecar.py` is the Cowork-owned Electron JSONL sidecar adapter over the standalone agent interface.
- Live LM Studio text generation and `list_directory` tool calling were verified with `qwen/qwen3.5-9b`.
- UI/Electron work can resume on top of the sidecar contract, but packaging should stay disabled until approval prompts and lifecycle smoke tests are complete.

## Commands

Run from `C:\AI_DEV_COWORKER`:

```powershell
python -m pip install -e .
cowork --list-models
cowork --workspace C:\path\to\project
python -m unittest discover -s test -p "test_*.py" -v
npm.cmd install --cache .\.npm-cache
npm.cmd test
npm.cmd run build
npm.cmd audit --audit-level=critical
```

## Latest Verification

Freshly run from `C:\AI_DEV_COWORKER` on 2026-06-12:

- Python: 61 unittests passed.
- CLI editable install and `cowork` console command passed.
- Live `cowork --list-models`: returned `qwen/qwen3.5-9b` and `qwen2.5-7b-instruct`.
- Live one-shot response: returned `CLI_OK`.
- Live tool-call response: called `list_directory` and returned `README_PRESENT`.
- Live secret smoke: `read_file(.env)` returned `denied`, the model answered `SECRET_DENIED`, and the secret marker did not appear in output.
- Live Git smoke: `git_status` returned structured `unavailable` for this non-Git project root and the model answered `GIT_UNAVAILABLE_OK`.
- Live state-machine smoke: after the state prompt update, `git_status` still returned structured `unavailable` and the model answered `STATE_GIT_UNAVAILABLE_OK`.
- Deterministic restore smoke: write replacement created a backup, `restore_backup` restored the original file, and the pre-restore backup preserved the replaced content.
- Deterministic backup-list smoke: `list_backups` returned rollback metadata without file contents.
- Deterministic process cleanup smoke: timeout cleanup stopped both Python and npm worker-tree heartbeat processes.
- Deterministic IPC smoke: sidecar handled `fetch_available_models` and malformed JSON through JSONL events.
- Electron launch smoke: `node_modules/.bin/electron.cmd .` started an `AI Dev Co-worker` window from the current build.
- Deterministic Git smoke: `.env` and `SMOKE_SECRET_MARKER` were absent from `git_status`/`git_diff`.
- `npm.cmd test`: 9 test files, 22 tests passed.
- `npm.cmd run build`: passed and emitted `dist/index.html`.
- `npm.cmd audit --audit-level=critical`: 0 vulnerabilities.
- Python compilation passed for all standalone CLI modules.
- Runtime/package scan found legacy terms only inside negative regression assertions.

## Important Files

- `README.md`: project overview and dev commands.
- `cowork_agent.py`: independent agent loop.
- `agent_state.py`: Inspect/Plan/Act/Verify/Report run-state tracker.
- `workspace_tools.py`: safe filesystem tool implementation.
- `developer_tools.py`: Git and verification preset implementation.
- `ipc_sidecar.py`: Cowork-owned Electron JSONL sidecar adapter.
- `cli.py`: CLI adapter and approval interaction.
- `PROJECT_STATE.md`: current capability, risks, and next milestone.
- `ARCHITECTURE.md`: backend/frontend/Electron ownership.
- `INSTALL_AND_UPDATE.md`: future `.exe` install and update rules.
- `work_logs/WORK_LOG.md`: append-only development history.
- `frontend/CoworkStandalone.jsx`: standalone app shell.
- `frontend/CoworkApp.jsx`: active Cowork workspace UI.
- `electron/main.js`: standalone Electron shell and sidecar path resolution.
- `session_store.py`: JSONL runtime records, supports `COWORK_USER_DATA_DIR`.

## Next Recommended Work

1. Resume UI/UX using `ipc_sidecar.py`, not the legacy host.
2. Add UI approval prompts before enabling file writes or verification runs through Electron.
3. Display agent stages, completion evidence, and resumable state snapshots.
4. Add backup listing/restore controls over `list_backups` and `restore_backup`.
