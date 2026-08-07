# Cowork Development Rules

These rules apply to every file and task under the active project root at `C:\AI_DEV_COWORKER`.

## Source Of Truth

- All Cowork-owned backend, frontend, documentation, tests, prompts, policies, and work records belong in this project root.
- Treat paths in project documentation as relative to `C:\AI_DEV_COWORKER` unless an absolute path is explicitly required.
- Files under the legacy host at `C:\API-BLENDER` may contain only integration bridges required by the host application.
- Do not add new Cowork business logic to `app_main.py`, `frontend/src`, or `frontend/electron` when it can live here.
- Do not hard-code either `C:\API-BLENDER` or `C:\AI_DEV_COWORKER` into runtime logic; runtime paths must resolve from the app folder, `process.resourcesPath`, `COWORK_APP_ROOT`, or `COWORK_USER_DATA_DIR`.

## Required Work Sequence

1. Read this file, `PROJECT_STATE.md`, and the relevant architecture/roadmap section before editing.
2. Inspect existing code and dependencies before proposing or applying changes.
3. Identify risks, permissions, tests, and rollback behavior before enabling new agent powers.
4. Make the smallest reversible change that completes the task.
5. Run fresh verification commands before claiming completion.
6. Append a dated entry to `work_logs/WORK_LOG.md` after every development task.
7. Update `PROJECT_STATE.md` whenever capabilities, architecture, model settings, or known risks change.

## Skill Usage Policy

- Check available Codex skills before substantial work.
- Use a matching skill whenever the task clearly falls within its scope.
- For implementation plans, use `writing-plans`.
- For architecture changes, use `improve-codebase-architecture`.
- For defects, use `systematic-debugging` before applying fixes.
- For new behavior and safety boundaries, use `test-driven-development`.
- Before completion claims, use `verification-before-completion`.
- Before major merges or risky changes, use `requesting-code-review`.
- For Electron/React UI verification, use `webapp-testing` and the Browser plugin.
- Use `find-skills` when a required workflow is not covered by installed skills.
- Record skills used in the work log. If no skill is used, record the reason.

## Persistence And Audit Rules

- Never rely on an online chat thread as the only record of decisions or progress.
- Runtime conversations and tool activity must be written to `work_logs/sessions/*.jsonl`.
- Human-readable development summaries must be appended to `work_logs/WORK_LOG.md`.
- Current architecture, completed milestones, next actions, and blockers must be maintained in `PROJECT_STATE.md`.
- Do not write API keys, passwords, tokens, private keys, or full `.env` contents to logs.
- Large tool results may be truncated, but the event, tool name, arguments, status, and timestamp must remain.

## Safety Rules

- Local-first is the default. Cloud providers require explicit user selection.
- Workspace access must become allowlist-based before arbitrary write or command execution is enabled.
- File writes require approval, diff visibility, and rollback support once Permission Gate is implemented.
- Never report success without fresh test, build, lint, or direct behavior evidence appropriate to the change.
- Preserve unrelated user changes and avoid destructive Git or filesystem operations.
