# AI Dev Co-worker Architecture

## Project Scope

- Active Cowork project root: `C:\AI_DEV_COWORKER`.
- Paths below are relative to the active project root unless stated otherwise.
- Standalone runtime code must not import, spawn, package, or read application code outside this project.

## CLI Runtime

- `cli.py` owns one-shot and interactive command behavior.
- `cowork.py` is the direct source-checkout entrypoint.
- `cowork_agent.py` is the deep module whose interface accepts prompts and returns final responses. It can start from a restored `AgentRunState` snapshot and records state snapshots during the run.
- `agent_state.py` owns the lightweight Inspect/Plan/Act/Verify/Report run-state tracker, JSON-safe snapshots, and completion evidence policy.
- `workspace_tools.py` owns canonical workspace validation, tool schemas, dispatch, approval proposals, diffs, atomic writes, rollback backup creation, backup metadata listing, and approval-gated backup restoration.
- `secret_guard.py` owns high-confidence secret-path classification and denial reasons. WorkspaceTools applies it before metadata disclosure, reads, diff generation, or writes.
- `developer_tools.py` owns read-only Git inspection and approval-gated verification presets. It invokes subprocesses with argument arrays, `shell=False`, workspace cwd, timeouts, output limits, sanitized sensitive environment variables, and best-effort process-tree cleanup on timeout.
- `agent_config.py` owns workspace memory, system prompt assembly, and iteration limits.
- `local_ai.py` owns Local AI model namespacing, client creation, and model discovery.
- `session_store.py` owns append-only JSONL runtime records and supports `COWORK_USER_DATA_DIR`.

The production seam is `CoworkAgent.run(prompt, initial_run_state=None)`. The CLI adapter supplies the Local AI adapter, WorkspaceTools adapter, write approval callback, command approval callback, audit sink, SecretGuard policy, DeveloperTools policy, and JSONL recorder. Tests supply fake model and recorder adapters through the same interfaces.

## Frontend

- `frontend/CoworkStandalone.jsx` owns the standalone desktop/web surface.
- `frontend/CoworkApp.jsx` owns the active Cowork workspace, project selection, active approval state, model/effort selection, and session actions.
- `frontend/components/ApprovalPrompt.jsx` owns explicit write and verification approval presentation.
- `frontend/components/ProjectsView.jsx`, `ModelMenu.jsx`, `ShellMenu.jsx`, `Composer.jsx`, and `SessionRail.jsx` own the Claude-like local shell controls.
- `frontend/components/WorkspacePanel.jsx` owns Code/Cowork file browsing, file preview, Git evidence, verification preset controls, and rollback backup controls. It requests data lazily and does not access the filesystem directly.
- `frontend/lib/eel.js` owns the renderer bridge for the standalone app.
- External menu entries remain local UI affordances until provider-specific permission and Secret Guard policies are defined.

## Electron

- `electron/main.js` owns the standalone Electron shell.
- Renderer files load from `dist/index.html` in production.
- Electron looks only for Cowork-owned `ipc_sidecar.py`.
- `ipc_sidecar.py` speaks JSONL over stdin/stdout, dispatches `send_cowork` through `CoworkAgent.run` on background workers, emits renderer events with `__ipc_type`, and lists Local AI models.
- Write and verification callbacks emit `cowork_interactive_question` events with an approval ID and proposal details. The worker waits while the main stdin loop receives `answer_question`, then continues only for an explicit allow response.
- `set_workspace` changes the sidecar root only after Electron main has confirmed the path came from the native folder picker.
- `workspace_action` accepts only `list_directory`, `read_file`, `inspect`, `run_verification`, and `restore_backup`. Responses carry a request ID through `workspace_response`; verification and restore execute on background workers so approval answers remain responsive.
- Approval waits fail closed after a bounded timeout, and worker exceptions are returned as structured backend errors.
- No legacy Python entry is packaged.
- Electron packaging remains disabled until the approval flow and sidecar lifecycle pass packaged smoke verification.

## Persistence

- CLI installs may set `COWORK_USER_DATA_DIR` for runtime records.
- Source-checkout mode falls back to `work_logs/`.

## Local AI

- Local models use the `local:model-id` namespace so they cannot collide with cloud models.
- LM Studio endpoint: `http://127.0.0.1:1234/v1`
- Ollama endpoint: `http://127.0.0.1:11434/v1`
- The model/runtime must support OpenAI-compatible tool calling for filesystem operations.

## Current LM Studio Setup

- Model: `qwen/qwen3.5-9b`, Q4_K_M
- API identifier: `qwen/qwen3.5-9b`
- Endpoint: `http://127.0.0.1:1234/v1`
- Context: 12,288
- Parallel requests: 1
- GPU offload: 85%
- Flash Attention: enabled
