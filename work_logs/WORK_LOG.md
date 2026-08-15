# Cowork Development Work Log

This file is append-only. Runtime conversation details are stored separately in `sessions/*.jsonl`.

## 2026-06-12 - Cowork consolidation and persistence

- Moved the Cowork React implementation into `cowork_feature/frontend/`.
- Kept a compatibility export in the host frontend so existing imports continue to work.
- Added project rules covering source ownership, skills, verification, safety, and mandatory logging.
- Added `PROJECT_STATE.md` as the durable handoff document for future accounts and sessions.
- Added automatic JSONL runtime session logging for messages, UI events, tool calls, status, and errors.
- Added recent local conversation recovery for the backend agent context.
- Added renderer-side conversation persistence so the latest 200 messages return after reopening the app.
- Skills used: `improve-codebase-architecture`, `verification-before-completion`, Browser UI verification workflow.
- Verification planned: Python compile, Vite production build, runtime store smoke test, and UI load check.
- Verification found Vite dependency resolution did not cross the frontend root after consolidation; fixed with explicit workspace access and shared React/Lucide aliases.
- Verification completed: Python compile passed, Vite production build passed, and JSONL session write/read recovery passed.

## 2026-06-12 - New Cowork UX/UI implementation plan

- Confirmed that the current Cowork interface is a disposable prototype.
- Retained only Local AI, agent runtime, IPC, workspace selection, and persistence contracts.
- Defined a new coding workspace inspired by terminal-first agent workflows and approachable desktop assistants without copying either product.
- Planned deterministic event state, durable sessions, timeline, command composer, approvals, diff review, verification evidence, provider settings, responsive behavior, and regression testing.
- Plan saved at `plans/2026-06-12-cowork-ui-rebuild.md`.
- Skill used: `writing-plans`.
- No implementation code was changed in this planning task.

## 2026-06-12 - Cowork UI rebuild Milestone A started

- Added Vitest, Testing Library, jsdom, and a test setup for Cowork frontend files living outside the host frontend root.
- Added Vite test configuration and dependency aliases so `cowork_feature/frontend` can use the host frontend React dependency tree.
- Followed TDD red-green for event contracts, reducer, bridge adapter, session storage, timeline, composer, and `CoworkApp`.
- Added `cowork_feature/frontend/model/coworkEvents.js` for the replayable event envelope.
- Added `cowork_feature/frontend/model/coworkReducer.js` and `coworkSelectors.js` for deterministic state replay and derived UI data.
- Added `cowork_feature/frontend/adapters/coworkBridge.js` and `sessionStorage.js`.
- Added rebuilt UI components: `CoworkApp`, `AppHeader`, `SessionRail`, `ContextInspector`, `Timeline`, `TimelineEntry`, `MessageEntry`, `ToolCallEntry`, and `Composer`.
- Switched the host compatibility export from the disposable `CoworkPanel` prototype to the new `CoworkApp`.
- Verification: `npm.cmd test` passed with 7 test files and 15 tests.
- Verification: `npm.cmd run build` passed.
- Verification: `Invoke-WebRequest http://127.0.0.1:4173` returned HTTP 200.
- Browser plugin visual smoke was attempted but blocked by the current Windows sandbox with `CreateProcessAsUserW failed: 5`; retry when browser automation is available.
- Noted npm reported 3 dependency vulnerabilities after installing test dependencies; no audit remediation was applied in this UI milestone.
- Skills used: `test-driven-development`, `improve-codebase-architecture`, `verification-before-completion`, `webapp-testing` for verification intent.
- Final verification: `npm.cmd test` passed with 7 test files and 15 tests.
- Final verification: `npm.cmd run build` passed.
- Final verification: bundled Python `py_compile` passed for `app_main.py` and Cowork backend modules.

## 2026-06-12 - Browser visual smoke recovery

- Added `?tab=cowork` and local-storage tab persistence so smoke tests can land on the rebuilt Cowork workspace directly.
- Confirmed the browser limitation was environment-specific: the in-app browser runtime failed with `CreateProcessAsUserW failed: 5`.
- Recovered visual smoke using headless Chrome with `--no-sandbox` and software rendering flags.
- Captured Cowork tab screenshots at `cowork_feature/work_logs/cowork-tab-smoke-2.png` after a fresh production build.
- Fresh verification: `npm.cmd test` passed again after the tab-selection change.
- Fresh verification: `npm.cmd run build` passed again before the smoke capture.

## 2026-06-12 - Durable Cowork session navigation wired in

- Wired `cowork_feature/frontend/CoworkApp.jsx` to a versioned session store adapter so session metadata and timeline events persist together.
- Upgraded `cowork_feature/frontend/adapters/sessionStorage.js` to schema v3 with per-session event buckets and legacy v2 migration.
- Added real session selection to `cowork_feature/frontend/components/SessionRail.jsx`.
- Added reducer hydration for replaying stored session events back into the active timeline.
- Extended frontend tests to cover persisted session restoration, session switching, and legacy store migration.
- Fixed Tailwind content scanning so classes inside `cowork_feature/frontend` are included in the production CSS bundle.
- Verification: `npm.cmd test` passed with 7 test files and 18 tests.
- Verification: `npm.cmd run build` passed and generated a larger CSS bundle containing Cowork classes.
- Browser visual smoke: Playwright + local Chrome captured `cowork_feature/work_logs/cowork-tab-smoke-6.png`.
- Browser visual smoke results: Cowork title, Sessions rail, Composer, and Run context were visible; horizontal overflow was false.
- Follow-up HTTP check found no 4xx/5xx responses during the Cowork smoke run.

## 2026-06-12 - Standalone Cowork surface split from main app shell

- Created `cowork_feature/frontend/CoworkStandalone.jsx` as a dedicated AI Dev Co-worker surface that does not render Designer, Builder, the main app sidebar, or the Blender AI Studio shell header.
- Created `cowork_feature/frontend/standalone.jsx` as the standalone React entrypoint that still reuses the existing Cowork runtime bridge and loop.
- Added `frontend/cowork.html` as a separate Vite page for opening Cowork directly without `frontend/src/App.jsx`.
- Added Vite multi-page build input for `index.html` and `cowork.html`; the main app entry remains available.
- Added `CoworkStandalone.test.jsx` to guard that the standalone surface excludes Designer, Builder, and the main shell title.
- Verification: `npm.cmd test` passed with 8 test files and 19 tests.
- Verification: `npm.cmd run build` passed and emitted both `dist/index.html` and `dist/cowork.html`.
- Browser visual smoke: Playwright + local Chrome captured `cowork_feature/work_logs/cowork-standalone-smoke.png`.
- Browser visual smoke results: AI Dev Co-worker, Local coding workspace, Sessions, Composer, and Run context were visible; Designer, Builder, and Blender AI Studio Desktop Shell were absent; horizontal overflow was false; no 4xx/5xx responses were observed.

## 2026-06-12 - AI Dev Co-worker project extracted

- Copied the Cowork source into the new top-level `AI_DEV_COWORKER/` folder to make the standalone app identity explicit.
- Added standalone app files: `index.html`, `package.json`, `vite.config.js`, `tailwind.config.js`, `postcss.config.js`, `styles/index.css`, and Electron `main.js` / `preload.cjs`.
- Added local frontend bridge at `AI_DEV_COWORKER/frontend/lib/eel.js` so the standalone UI no longer imports `frontend/src/lib/eel.js`.
- Updated `AI_DEV_COWORKER/frontend/CoworkApp.jsx` and `standalone.jsx` to use local bridge and local styles.
- Added install/update notes for packaged `.exe` portability and user-data-safe updates.
- Updated legacy bridges so the original app can keep working while Cowork source-of-truth moves to `AI_DEV_COWORKER`.
- Updated `AI_DEV_COWORKER/session_store.py` to write runtime sessions under `COWORK_USER_DATA_DIR` when provided.
- Verification: `npm.cmd test` in `AI_DEV_COWORKER` passed with 8 test files and 19 tests.
- Verification: `npm.cmd run build` in `AI_DEV_COWORKER` passed and emitted `dist/index.html`.
- Verification: `npm.cmd test` and `npm.cmd run build` in `frontend` both passed after compatibility bridge updates.
- Verification: bundled Python `py_compile` passed for `AI_DEV_COWORKER` modules and the legacy `cowork_feature` shim.
- Verification: session-store smoke wrote JSONL records under a custom `COWORK_USER_DATA_DIR`.
- Browser visual smoke: Playwright opened `AI_DEV_COWORKER/dist/index.html` directly and captured `AI_DEV_COWORKER/work_logs/ai-dev-coworker-dist-smoke.png`.
- Browser visual smoke results: AI Dev Co-worker, Sessions, Composer, and Run context were visible; Designer and Builder were absent; horizontal overflow was false; no failed file requests were observed.
- Known warning: the new project currently reuses `frontend/node_modules` through helper scripts, which emits Vite `esbuild` unresolved-import warnings even though test/build exit successfully. Installing dependencies directly in `AI_DEV_COWORKER` should remove this warning later.

## 2026-06-12 - Standalone npm install and lockfile completed

- Ran `npm.cmd install --cache .\.npm-cache` inside `AI_DEV_COWORKER`, creating local `node_modules/` and `package-lock.json`.
- Removed the temporary helper scripts that pointed to `../frontend/node_modules`.
- Updated `package.json`, `vite.config.js`, and `postcss.config.js` to use local dependencies.
- Added `test/setup.js` so Vitest no longer depends on the host frontend test setup file.
- Removed unused `concurrently`, `cross-env`, and `wait-on`; this cleared the critical `shell-quote` audit finding.
- Added `.gitignore` for `node_modules/`, `.npm-cache/`, `dist/`, `release/`, Python cache, and transient preview logs.
- Verification: `npm.cmd test` passed with 8 test files and 19 tests.
- Verification: `npm.cmd run build` passed using local Vite from `AI_DEV_COWORKER/node_modules`.
- Verification: `npm.cmd audit --audit-level=critical` reported 0 vulnerabilities.
- Verification: bundled Python `py_compile` passed for standalone Cowork modules and the legacy `cowork_feature` shim.

## 2026-06-12 - Documentation aligned after manual project relocation

- Confirmed the active Cowork project root is now `C:\AI_DEV_COWORKER` and the old `C:\API-BLENDER\AI_DEV_COWORKER` directory no longer exists.
- Updated `AGENTS.md`, `README.md`, `PROJECT_STATE.md`, `ARCHITECTURE.md`, `DEVELOPMENT_ROADMAP.md`, `HANDOFF.md`, `INSTALL_AND_UPDATE.md`, and the active UI rebuild plan to use project-root-relative paths and the new working directory.
- Recorded the legacy host boundary at `C:\API-BLENDER` and documented relocation-sensitive integration blockers instead of treating compatibility as working.
- Direct integration evidence: `../app_main.py` resolves to missing `C:\app_main.py`; the legacy frontend export resolves to missing `C:\API-BLENDER\AI_DEV_COWORKER\frontend\CoworkApp.jsx`; importing `cowork_feature` from the host fails with `ModuleNotFoundError: No module named 'AI_DEV_COWORKER'`.
- Verification: `npm.cmd test` passed with 8 test files and 19 tests.
- Verification: `npm.cmd run build` passed and emitted `dist/index.html`.
- Verification: `npm.cmd audit --audit-level=critical` reported 0 vulnerabilities.
- Verification: `python -m py_compile __init__.py agent_config.py local_ai.py runtime.py session_store.py` passed.
- Skills used: `systematic-debugging` for relocation root-cause tracing and `verification-before-completion` for fresh evidence. No implementation skill was needed because this task changed documentation and audit records only.

## 2026-06-12 - Relocation integration paths repaired

- Added relocation regression tests for Electron sidecar candidates, package resources, the legacy frontend export, and Python compatibility import.
- Added `electron/pathResolution.js` so Electron path discovery is testable without loading Electron runtime APIs.
- Updated standalone Electron discovery to find the sibling `API-BLENDER/app_main.py` through an app-relative path.
- Updated package resources to source the existing host `app_main.py` and its `cowork_feature` compatibility shim from the sibling host directory.
- Updated the legacy Python shim to resolve Cowork through `COWORK_APP_ROOT`, the former nested location, or the relocated sibling project without hard-coded absolute runtime paths.
- Updated the host frontend export, standalone HTML entry, Tailwind scan, Vite filesystem allowlist, and host Vitest include for the relocated project.
- TDD evidence: relocation Vitest initially failed because `electron/pathResolution.js` did not exist; Python integration initially failed with `ModuleNotFoundError`; the package-shim assertion initially failed while the resource was absent. All targeted tests passed after the minimal fixes.
- Verification: direct host import without `COWORK_APP_ROOT` printed `AI_DEV_COWORKER.runtime`.
- Verification: standalone and host frontend tests each passed with 9 files and 23 tests; both production builds passed, and the host build emitted both `index.html` and `cowork.html`.
- Verification: Python relocation unittest and `py_compile` passed; standalone npm audit reported 0 vulnerabilities; all package resource source paths exist.
- Remaining risk: packaged Electron runtime is not yet validated and still packages the legacy host sidecar instead of a Cowork-owned sidecar.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-12 - Standalone Cowork CLI established

- Made the CLI the primary product milestone before further UI/UX work.
- Added `cli_config.py`, `workspace_tools.py`, `cowork_agent.py`, `cli.py`, `cowork.py`, and `pyproject.toml`.
- Added installable `cowork` command with one-shot and interactive modes plus `/models`, `/clear`, and `/exit`.
- Added Cowork-owned Local AI tool loop with list, search, read, and approved atomic write tools.
- Added canonical Workspace validation that rejects traversal and absolute paths outside the selected root.
- Added unified diff approval before writes; `--yes` is the only explicit process-wide auto-approval mode.
- Removed the host-shaped `runtime.py`, removed legacy host sources from npm package resources, and removed the Electron packaging command until a Cowork-owned IPC adapter exists.
- Changed memory loading so it never creates `.claude/cowork_memory.local.md` outside the write approval flow.
- Added `CONTEXT.md`, the standalone CLI implementation plan, and an architecture report at `C:\Users\user\AppData\Local\Temp\architecture-review-20260612-standalone-cli.html`.
- TDD evidence: configuration, workspace tools, agent loop, CLI, host-independence, memory safety, and installed bootstrap tests all failed for the intended missing or unsafe behavior before implementation.
- Verification: 21 Python unittests passed; Python compilation passed.
- Verification: editable install created `cowork.exe`; non-editable wheel built and imported from a temp directory outside the source checkout.
- Verification: LM Studio listed `qwen/qwen3.5-9b` and `qwen2.5-7b-instruct`.
- Verification: live one-shot returned `CLI_OK`; live tool call invoked `list_directory` and returned `README_PRESENT`.
- Verification: standalone frontend 9 files / 22 tests passed; Vite build passed; npm audit found 0 vulnerabilities.
- Runtime scan found legacy host terms only in negative regression assertions.
- Remaining risks: no secret-file guard, Git/verification tools, rollback backup, explicit agent state machine, or Electron IPC adapter yet.
- Skills used: `writing-plans`, `improve-codebase-architecture`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-12 - Secret Guard enforced across CLI workspace tools

- Added `secret_guard.py` with structured allow/deny decisions and denial reasons.
- Blocked high-confidence environment secrets, private keys/certificates, SSH key names, credential files, and credential-store directories.
- Kept `.env.example`, `.env.sample`, and `.env.template` accessible for repository setup workflows.
- Enforced Secret Guard before directory metadata disclosure, search indexing, reads, diff generation, approval callbacks, and writes.
- Added Windows alternate-data-stream normalization so `.env:backup` and `id_rsa:backup` cannot bypass policy.
- Updated the system prompt so small models know blocked secret paths should not be retried.
- Added one bounded recovery attempt when Local AI returns an empty response after tool use; this was discovered during live Secret Guard verification.
- TDD evidence: Secret Guard module was initially missing; `.env` appeared in listing/search; secret reads returned `ok`; writes reached approval; alternate streams and `.git-credentials` initially bypassed policy; empty model responses initially aborted immediately.
- Verification: 27 Python unittests passed and Python compilation passed.
- Verification: frontend 9 files / 22 tests, Vite build, and npm audit passed with 0 vulnerabilities.
- Live verification: `read_file(.env)` returned a structured `denied`; the model answered `SECRET_DENIED`; the marker `NEVER_EXPOSE_THIS_MARKER` did not appear in CLI output or the session event payload.
- Skills used: `test-driven-development`, `systematic-debugging`, and `verification-before-completion`.

## 2026-06-12 - Git and verification tools added to standalone CLI

- Added `developer_tools.py` with read-only `git_status` and `git_diff` operations plus approval-gated verification presets.
- Filtered Git status and diff output through Secret Guard so `.env`, private keys, and credential paths do not reach model-visible tool results.
- Added `run_verification` with named presets only: `python-tests`, `frontend-tests`, and `frontend-build`; arbitrary shell commands and model-supplied arguments are not accepted.
- Updated CLI approval prompts to show preset name, working directory, exact argument array rendering, and timeout before executing a verification preset.
- Sanitized sensitive environment variable names for verification subprocesses and added output length limits and structured timeout/error results.
- TDD evidence: developer tools module was initially missing; workspace schemas lacked Git/verification tools; CLI command approval helper was missing; system prompt lacked Git/verification guidance.
- Verification: 35 Python unittests passed and Python compilation passed.
- Verification: frontend 9 files / 22 tests, Vite build, and npm audit passed with 0 vulnerabilities.
- Verification: `DeveloperTools.run_verification` successfully executed all three default presets in-process.
- Deterministic smoke: temporary Git repository changed `app.py` and `.env`; `git_status`/`git_diff` exposed `app.py` while hiding `.env` and `SMOKE_SECRET_MARKER`.
- Live smoke: LM Studio called `git_status` and returned `GIT_UNAVAILABLE_OK` for the current non-Git project root.
- Remaining risks: approved npm scripts execute repository-defined code, timeout does not yet harden Windows process-tree cleanup, rollback backups and richer approval audit events are still pending.
- Skills used: `writing-plans`, `test-driven-development`, `verification-before-completion`, and `requesting-code-review` with self-review fallback because subagent spawning is only allowed on explicit user request.

## 2026-06-12 - Rollback backups retained for approved replacements

- Added rollback backup creation for approved writes that replace an existing file.
- Backups are written under `.cowork/backups/<timestamp>/...` inside the selected workspace and the write result now includes `backup_path`.
- Denied writes and new-file writes do not create rollback backup directories.
- TDD evidence: replacement write initially returned only `status`, `path`, and `bytes`; the new test failed until backup creation was added.
- Verification: focused workspace tools tests passed with 11 tests.
- Verification: full Python suite passed with 37 tests and Python compilation passed.
- Remaining risks: no dedicated restore tool yet, richer approval/backup audit events are still pending, and process-tree cleanup for verification timeouts is not hardened.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-12 - Audit events and verification process-tree cleanup

- Added structured audit events for workspace write approval requests, approval decisions, rollback backup creation, and completed writes.
- Added structured audit events for verification approval requests, decisions, starts, finishes, allowlist rejections, and timeouts.
- Audit payloads include paths, byte counts, diff line counts, preset names, argv arrays, exit codes, durations, truncation flags, and process-tree cleanup flags without storing full file contents.
- Wired CLI runtime audit events into `session_store.record_cowork_event` so active sessions receive the richer JSONL timeline.
- Replaced verification subprocess execution with `Popen` so timeout handling can invoke process-tree cleanup before returning a structured timeout result.
- Windows timeout cleanup uses `taskkill /PID <pid> /T /F`; POSIX cleanup starts a new session and terminates the process group.
- TDD evidence: `WorkspaceTools` and `DeveloperTools` initially rejected `audit_sink`; `DeveloperTools` initially rejected `process_tree_killer`; CLI had no `record_cowork_event` audit sink to patch.
- Verification: focused CLI/workspace/developer tools tests passed with 24 tests.
- Verification: full Python suite passed with 40 tests and Python compilation passed.
- Verification: frontend 9 files / 22 tests passed, Vite build passed, and npm audit reported 0 vulnerabilities.
- Remaining risks: process-tree cleanup should still be validated against real long-running npm worker trees; no dedicated restore tool exists yet.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-12 - Inspect/Plan/Act/Verify state machine added

- Added `agent_state.py` with a lightweight `AgentRunState` tracker for Inspect, Plan, Act, Verify, and Report stages.
- Cowork now records `agent_stage` events for each run and records `completion_evidence` before successful final reporting.
- After a successful `write_file`, the agent loop blocks final reporting until a `run_verification` tool result with status `passed` has been observed.
- If a model tries to report success after file writes without passing verification, Cowork injects a repair message instructing it to call `run_verification` first.
- Updated the system prompt with the required `Inspect -> Plan -> Act -> Verify -> Report` flow and the post-write verification rule.
- TDD evidence: `agent_state` initially did not exist; `CoworkAgent` initially returned final text after writes without verification; the system prompt initially lacked the state flow contract.
- Verification: focused agent state/agent loop/config tests passed with 12 tests.
- Verification: full Python suite passed with 45 tests and Python compilation passed.
- Verification: frontend 9 files / 22 tests passed, Vite build passed, and npm audit reported 0 vulnerabilities.
- Live smoke: LM Studio still called `git_status` after the state prompt update and returned `STATE_GIT_UNAVAILABLE_OK` for this non-Git project root.
- Remaining risks: state is not resumable across interrupted sessions yet; failed verification repair is still minimal; UI does not display state/evidence yet.
- Skills used: `writing-plans`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-01 - Chat silent boundary and role pause controls

- Refined Chat boundary handling so ordinary Chat answers should not volunteer mode/permission explanations:
  - `CHAT_SYSTEM_PROMPT` now frames boundaries as silent runtime behavior.
  - Project route prompts ask for missing context or a workspace handoff only when project-specific evidence is required.
  - Tests now assert the old `Chat cannot read workspace files automatically` wording is no longer injected into route prompts.
- Added pause/resume controls for mode-scoped persona roles:
  - `ChatMemoryStore.set_memory_enabled(...)` keeps the memory entry but toggles `enabled`.
  - Disabled roles are skipped during prompt injection while remaining visible/editable in Memory Manager.
  - Sidecar, Electron main/preload, frontend bridge, and `CoworkApp` now forward `chat_memory_set_enabled`.
  - Memory Manager shows `Active` / `Paused` role badges and a role power button.
- Audited existing Chat source/attachment UI:
  - Source cards, citation links, attachment preview, drag/drop image attachments, and artifact attach/export are already present.
  - No duplicate implementation was added in this slice.
- Verification:
  - Python compile check passed with `python -m py_compile chat_runtime.py chat_router.py chat_memory.py ipc_sidecar.py`.
  - Targeted backend tests passed 88/88 with `python -m unittest test.test_chat_runtime test.test_chat_router test.test_chat_memory test.test_ipc_sidecar -v`.
  - Targeted frontend tests passed 24/24 with `npm test -- MemoryManager coworkBridge --run`.
  - Full backend suite passed 298/298 with `python -m unittest discover -s test -p test_*.py -v`.
  - Full frontend suite passed 108/108 with `npm test`.
  - Frontend production build passed with `npm run build`; the existing Vite chunk-size warning remains non-blocking.
- Skills used: `writing-plans`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-01 - Chat quality evaluation panel

- Added a user-visible Chat Quality view without enabling live API/model scoring from the UI:
  - Sidebar now has a `Quality` entry.
  - `QualityEvalPanel` shows fixture categories, checks, snapshot pass/fail counts, pass rate, and findings.
  - CoworkApp subscribes to `chat_quality_eval_state`, refreshes cases when the Quality view opens, and can request a local snapshot evaluation with empty fixture results.
  - Live model matrix evaluation remains CLI-gated through `chat_quality_runner.py --live`.
- Verification:
  - Targeted frontend tests passed 24/24 with `npm test -- QualityEvalPanel CoworkApp --run`.
  - Python compile check passed with `python -m py_compile chat_runtime.py chat_router.py chat_memory.py ipc_sidecar.py`.
  - Full backend suite passed 298/298 with `python -m unittest discover -s test -p test_*.py -v`.
  - Full frontend suite passed 110/110 with `npm test`.
  - Frontend production build passed with `npm run build`; the existing Vite chunk-size warning remains non-blocking.
- Skills used: `writing-plans`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-01 - Credit-aware model performance profiles for Auto Router

- Added a stable model performance profile layer for real quality data:
  - New `model_performance.py` builds and saves `work_logs/model-performance-profile.json` from live quality matrices.
  - Profiles summarize per-model/per-category executed cells, skipped cells, pass rate, hallucination rate, source quality, latency, average score, and a router score.
  - `chat_quality_runner.save_quality_report(...)` now writes the stable profile alongside timestamped JSON/Markdown reports.
- Made live quality evaluation safer for paid/provider-limited models:
  - Billing/credit/quota/auth errors are marked `skipped` with a `skip_reason` instead of failing the whole model/category matrix.
  - Aggregate pass/fail/hallucination/source rates are calculated over executed cells, while skipped cells remain visible separately.
- Wired Auto Router to real performance data:
  - `route_model(..., performance_profile=...)` can prefer the highest-scoring model for detected categories such as `web`, `coding`, `thai`, and `general`.
  - Explicit user-selected models still always win and are never overridden.
  - `ipc_sidecar.py` loads `work_logs/model-performance-profile.json` when available and passes it into the Auto Router.
- Verification:
  - TDD red checks failed as expected because `model_performance.py` did not exist, `route_model` did not accept `performance_profile`, and billing errors were still marked `failed`.
  - Targeted backend tests passed 16/16 with `python -m unittest test.test_model_performance test.test_chat_quality_runner test.test_model_router -v`.
  - Python compile check passed with `python -m py_compile model_performance.py chat_quality_runner.py model_router.py ipc_sidecar.py`.
  - Full backend suite passed 302/302 with `python -m unittest discover -s test -p test_*.py -v`.
  - Full frontend suite passed 110/110 with `npm test`.
  - Frontend production build passed with `npm run build`; the existing Vite chunk-size warning remains non-blocking.
- Skills used: `writing-plans`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-12 - Rollback restore tool added

- Added `restore_backup` to `WorkspaceTools` and the model-facing tool schema.
- The restore target is inferred from `.cowork/backups/<timestamp>/...`; the model cannot provide an arbitrary target path.
- Restore operations require approval through the existing diff proposal path.
- Before restoration, Cowork creates a pre-restore backup of the current file and returns `pre_restore_backup_path`.
- Restore operations emit structured audit events for restore approval request, restore approval decision, current-file backup creation, and file restoration without storing full file contents.
- `AgentRunState` now treats successful `restore_backup` results as file writes, so final reporting is blocked until `run_verification` passes.
- TDD evidence: restore schema and method were initially missing; `restore_backup` path outside `.cowork/backups` was initially unknown; `AgentRunState` initially did not treat restoration as a write.
- Verification: focused workspace/state tests passed with 22 tests.
- Verification: full Python suite passed with 50 tests and Python compilation passed.
- Verification: frontend 9 files / 22 tests passed, Vite build passed, and npm audit reported 0 vulnerabilities.
- Deterministic smoke: replacing `file.txt` created a rollback backup, `restore_backup` restored `before`, and the pre-restore backup preserved `after`.
- Remaining risks: backup discovery/listing is not implemented yet; restore paths must come from prior write results or audit logs.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-12 - CLI hardening four-item pass completed

- Added `list_backups` to expose rollback backup metadata without file contents and hide secret-classified targets.
- Validated verification timeout process-tree cleanup against real Python parent/child workers and a real `npm run` Node worker tree.
- Added JSON-safe `AgentRunState` snapshots and let `CoworkAgent.run()` resume from restored state while preserving the post-write verification gate.
- Added `ipc_sidecar.py`, a Cowork-owned JSONL sidecar adapter that dispatches `send_cowork` through the standalone agent interface and emits renderer events for prompts, answers, backend errors, and model lists.
- Kept sidecar default write and verification approvals denied until UI approval prompts are implemented.
- TDD evidence: `list_backups`, snapshot methods, resumed agent state, and `ipc_sidecar` imports initially failed; focused tests passed after implementation. The existing process cleanup implementation passed the new real worker-tree tests.
- Verification: focused workspace, developer tools, agent state/agent loop, and IPC sidecar tests passed.
- Verification: full backend suite passed with 61 unittests, Python compilation passed, frontend 9 files / 22 tests passed, Vite build passed, and critical npm audit reported 0 vulnerabilities.
- Runtime smoke: `ipc_sidecar.py` handled JSONL commands in a real process, Electron launched an `AI Dev Co-worker` window from the current build, and a standalone CLI PowerShell was started at `C:\AI_DEV_COWORKER`.
- Remaining risks: sidecar approval UX is still needed before Electron can safely enable file writes or verification runs; OS process-tree cleanup remains best-effort for unusual detached workers.
- Skills used: `writing-plans`, `test-driven-development`, `improve-codebase-architecture`, and `verification-before-completion`.

## 2026-06-12 - Claude-like chat-first UI refresh

- Reworked the standalone frontend toward the provided Claude-like preview: light sidebar, slim top chrome, centered greeting, large white composer, quick actions, and bottom-right status chips.
- Preserved the existing session storage, session switching, bridge injection, and prompt submission behavior.
- Deferred the heavier Code/Cowork panels intentionally; the current first screen now emphasizes chat, with code functionality to be layered in later.
- Updated message and tool timeline entries from dark cards to the light Claude-like theme.
- TDD evidence: CoworkApp tests initially failed because the old dark workspace lacked Chat/Cowork/Code tabs, Claude-like greeting, and the new composer placeholder; focused tests passed after the UI refresh.
- Verification: focused CoworkApp/Composer/Standalone tests passed, full frontend suite passed with 9 files / 22 tests, Vite production build passed, critical npm audit reported 0 vulnerabilities, and localhost preview served the built app shell.
- Browser verification note: Browser plugin startup was blocked by the Windows sandbox and Python Playwright was not installed, so visual screenshot verification could not be completed in this environment.
- Skills used: `writing-plans`, `test-driven-development`, `webapp-testing`, Browser plugin skill attempted, and `verification-before-completion`.

## 2026-06-12 - Electron blank renderer fix

- Investigated the blank Electron window reported after the Claude-like UI refresh.
- Root cause: `frontend/lib/eel.js` registered renderer IPC listeners such as `brainstorm_log`, but `electron/preload.cjs` did not allow those channels, so preload threw `IPC channel not allowed: brainstorm_log` before React could mount.
- Added a regression test that compares every renderer IPC channel in `ipcEventMap` against the preload allowlist.
- Expanded the preload inbound channel allowlist to match the renderer bridge.
- Added Electron renderer diagnostics for console messages, load failures, renderer process exits, and root mount snapshots.
- Verification: the regression test failed before the fix, then passed after the preload allowlist update.
- Verification: full frontend suite passed with 9 files / 23 tests, Vite production build passed, critical npm audit reported 0 vulnerabilities, and Electron diagnostics confirmed `rootChildren: 1` with visible UI text.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-13 - Frameless Electron shell and usable first-screen controls

- Researched the current Electron custom-window guidance and confirmed the correct approach is a frameless `BrowserWindow` plus explicit draggable/no-drag regions for the React titlebar.
- Added a plan at `docs/superpowers/plans/2026-06-13-frameless-usable-ui.md`.
- Added regression tests for frameless Electron configuration, titlebar window-control bridge calls, sidebar state, mode selection, search focus, and quick-action prompt seeding.
- Switched Electron to `frame: false` with a white background so the OS titlebar no longer duplicates the React chrome.
- Added `app-drag-region` and `app-no-drag` CSS helpers, wired header buttons to `window.electronAPI`, and kept React controls clickable inside the draggable header.
- Wired first-screen behavior in `CoworkApp`: sidebar toggle, previous/next session navigation, search-to-composer focus, active Chat/Cowork/Code mode, Artifacts/Customize prompt seeding, and quick action prompt seeding.
- Updated `Composer` to accept shell-provided suggested prompts and focus signals.
- TDD evidence: focused Vitest initially failed for `frame: true`, missing suggested prompt support, missing window bridge calls, and missing sidebar state; the same focused suite passed after implementation.
- Verification: focused frontend tests passed with 3 files / 13 tests.
- Verification: full frontend suite passed with 9 files / 27 tests.
- Verification: Vite production build passed and emitted `dist/index.html`.
- Verification: `npm.cmd audit --audit-level=critical` reported 0 vulnerabilities.
- Electron smoke: relaunched Electron from the current build; diagnostics confirmed `rootChildren: 1` and visible UI text including Chat/Cowork/Code, Projects, Artifacts, Customize, and ready status.
- Browser verification note: Browser plugin startup was blocked by the Windows sandbox with `CreateProcessAsUserW failed: 5`, and Python Playwright was not installed, so Electron diagnostics plus Vitest were used for this smoke check.
- Skills used: `writing-plans`, `systematic-debugging`, `test-driven-development`, `webapp-testing`, Browser plugin skill attempted, and `verification-before-completion`.

## 2026-06-13 - Approval prompts and Claude-like shell controls

- Added a sidecar approval queue that keeps stdin responsive while Cowork waits for a write or verification decision.
- Write approval events include the target path and unified diff; verification events include the exact allowlisted preset and argv.
- Added Approve and Deny UI prompts and routed responses back to the matching sidecar request by approval ID.
- Added structured backend error emission for failures inside background Cowork workers.
- Added functional local shell controls for the main menu, composer add menu, slash-skill suggestions, model/effort selection, Projects view and folder selection, and recent-session pin/rename/add/delete actions.
- External GitHub, connector, plugin, research, and web-search entries remain local UI affordances; no external provider integration or unrestricted network access was enabled.
- TDD evidence: sidecar approval tests initially failed because callbacks and waiting were absent; UI tests initially failed because proposal details and shell controls were absent; the worker-error test initially exposed an uncaught thread exception.
- Verification: focused frontend tests passed with 3 files / 13 tests.
- Verification: full frontend suite passed with 9 files / 30 tests.
- Verification: full Python suite passed with 64 tests and selected runtime modules compiled successfully.
- Verification: Vite production build passed and critical npm audit reported 0 vulnerabilities.
- Electron smoke: relaunched the current production build; diagnostics confirmed `rootChildren: 1` and visible Chat/Cowork/Code, Projects, Artifacts, Customize, model, and ready-state text.
- Browser verification remains blocked by the Windows sandbox, so the final desktop smoke uses Electron renderer diagnostics.
- Skills used: `writing-plans`, `test-driven-development`, `webapp-testing`, and `verification-before-completion`.

## 2026-06-13 - Code/Cowork workspace panel

- Added request-ID sidecar workspace actions for selecting a root, listing directories, reading guarded text files, inspecting Git/backups, running allowlisted verification, and restoring rollback backups.
- Kept verification and restore operations on background workers so the stdin approval channel remains responsive.
- Added narrow Electron/preload methods and `workspace_changed` / `workspace_response` events; no arbitrary command method was exposed.
- Added an Electron session allowlist so `setWorkspace` accepts only paths returned by the native folder picker.
- Added a Code/Cowork workspace panel with Files, Changes, Verification, and Backups tabs.
- Added lazy directory navigation, file preview, Git branch/change/diff display, verification output, and approval-gated restore controls.
- Added a global approval overlay for non-Chat views.
- Fixed responsive navigation: mobile starts with the drawer closed and retains a visible toggle; desktop remains unchanged.
- TDD evidence: sidecar tests initially failed on the missing workspace factory/commands; bridge tests failed on absent IPC methods; UI tests failed before workspace activation/panels; responsive tests failed before the mobile drawer fixes; Electron allowlist test failed before folder-picker enforcement.
- Verification: full frontend suite passed with 9 files / 34 tests.
- Verification: full Python suite passed with 66 tests; changed runtime modules compiled successfully.
- Verification: Vite production build passed and critical npm audit reported 0 vulnerabilities.
- Browser verification: desktop Code workspace empty state and mobile shell/drawer behavior were visually inspected in the production preview.
- Runtime smoke: the real sidecar selected `C:\AI_DEV_COWORKER`, listed 44 root entries, read `PROJECT_STATE.md`, and returned workspace inspection data.
- Electron smoke: relaunched the production build; diagnostics confirmed a mounted React root and visible Chat/Cowork/Code/Projects shell with the Cowork sidecar running.
- Skills used: `writing-plans`, `test-driven-development`, `webapp-testing`, Browser plugin, and `verification-before-completion`.

## 2026-06-13 - Separate mode histories and Cowork response recovery

- Split Chat, Cowork, and Code into independent persisted sessions and recent-history lists.
- Migrated legacy shared v3 history into Chat and introduced the v4 session schema without deleting older storage.
- Kept all three tabs chat-first and moved Files/Changes/Verification/Backups behind a dedicated Workspace navigation item.
- Added client session IDs across React, preload, Electron IPC, and `ipc_sidecar.py` so delayed replies and approvals return to the originating conversation.
- Ignored sidecar USER log echoes, hid raw `agent.status` timeline entries, and made assistant completion return a live run to idle.
- Prevented stale persisted busy events from disabling the composer after restart.
- Added an explicit "Cowork is waiting for your decision" message above approval prompts.
- Verification: focused frontend tests passed 27/27; full frontend suite passed 9 files / 40 tests; full Python suite passed 66 tests; production build and Python compile passed.
- Browser verification: sent a prompt in Chat, switched to Cowork, confirmed the Chat message was absent and the Cowork composer remained enabled.
- Skills used: `systematic-debugging`, `test-driven-development`, `webapp-testing`, Browser plugin, and `verification-before-completion`.

## 2026-06-13 - Chat processing indicator

- Added a compact processing status above the composer: `Thinking` for the first ten seconds, followed by a live `Working for` elapsed-time label.
- Hid tool/command event details from the visible conversation while retaining the underlying events for state and audit use.
- Kept approval prompts dominant: the processing indicator is hidden while Cowork waits for Approve or Deny.
- Added per-session live busy tracking so switching Chat/Cowork/Code does not mix processing indicators.
- Fixed active-session hydration so persisted history loading does not overwrite live processing state.
- TDD evidence: the new indicator import, timer expectations, CMD suppression, and app-level Thinking expectation failed before implementation.
- Verification: focused frontend tests passed 14/14; full frontend suite passed 10 files / 42 tests; full Python suite passed 66 tests; production build passed.
- Browser verification: `Thinking` rendered immediately, command text stayed absent, and the label advanced to `Working for 25s` during a held preview request.
- Skills used: `test-driven-development`, `webapp-testing`, Browser plugin, and `verification-before-completion`.

## 2026-06-13 - Conversation overflow and latest-message navigation

- Fixed long conversations where approval cards expanded outside the scrollable timeline and hid the newest content below the window.
- Moved active Chat approvals into the same bounded scroll container as messages while keeping the composer visible below it.
- Added near-bottom tracking and smooth automatic follow for new events only when the user is already reading the latest content.
- Added a compact `Jump to latest` arrow when the user scrolls upward, avoiding forced scrolling while reading history.
- TDD evidence: tests failed because the conversation scroll area did not exist, approvals were outside it, and no jump control was available.
- Verification: focused CoworkApp tests passed 11/11; full frontend suite passed 10 files / 43 tests; full Python suite passed 66 tests; production build passed.
- Browser verification: the conversation region reported bounded `overflow-y: auto`; the composer remained inside a 720px viewport below the 501px scroll region.
- Skills used: `systematic-debugging`, `test-driven-development`, `webapp-testing`, Browser plugin, and `verification-before-completion`.

## 2026-06-13 - Electron scroll and backend failure recovery

- Fixed the remaining Electron-only chat clipping by locking the main conversation column with `min-h-0` and `overflow-hidden`, letting the inner conversation region own vertical scrolling.
- Added Electron renderer diagnostics for the conversation scroll area so desktop smoke logs now include `clientHeight`, `scrollHeight`, `overflowY`, and parent overflow/min-height.
- Subscribed the frontend bridge to sidecar `backend-log` events and rendered request failures as visible system messages in the correct mode/session.
- Updated CoworkApp busy-state handling so failed events release the active session and re-enable the composer instead of leaving `Thinking` or `Working` stuck.
- Updated `ipc_sidecar.py` to emit session-scoped `cowork_ui_state` busy/idle events for every Cowork worker run, including exception paths.
- Bounded Local AI OpenAI-compatible requests to 45 seconds with no HTTP retries so a slow local model cannot keep the UI locked silently for several minutes.
- Live model check: LM Studio exposed `qwen/qwen3.5-9b`, but a simple request either returned empty text or timed out, so the fix focuses on visible recovery rather than claiming the model is reliably answering yet.
- TDD evidence: new frontend tests initially failed for missing parent scroll constraints, missing backend-log subscription, and stuck processing state after failure; sidecar tests failed until busy/idle and session-scoped backend errors were emitted.
- Verification: full frontend suite passed with 10 files / 46 tests; full Python suite passed with 66 tests; Python compile and Vite production build passed.
- Electron smoke: production Electron launched with sidecar; diagnostics confirmed `conversation.clientHeight` 701, `conversation.scrollHeight` 1000, `overflowY` `auto`, parent `overflowY` `hidden`, and parent `minHeight` `0px`.
- Skills used: `systematic-debugging`, `test-driven-development`, `webapp-testing`, Browser plugin, and `verification-before-completion`.

## 2026-06-13 - Local model fallback and availability status

- Added a local-only fallback policy to `ipc_sidecar.py`: the selected model is tried first, then configured fallback models are attempted only if LM Studio reports them in the local model list.
- Added the default fallback candidate `local:qwen2.5-7b-instruct`; cloud providers remain opt-in only and are not used for fallback.
- Sidecar now emits a visible session-scoped System message when the primary model fails and a fallback model is being tried.
- Assistant replies include the model that produced the answer in the sidecar event payload.
- Added frontend bridge support for `fetchModels` and `available_models` subscriptions.
- Updated the desktop model chip so it can show `Model loaded`, `Fallback ready`, `Model unavailable`, or unknown `Model status` instead of always claiming the model is loaded.
- TDD evidence: sidecar fallback test failed before `fallback_models` existed; bridge/UI tests failed before `fetchModels`, `subscribeModels`, and model status derivation were implemented.
- Verification: targeted sidecar tests passed 9/9; focused bridge/CoworkApp tests passed 20/20; full frontend suite passed 10 files / 48 tests; full Python suite passed 67 tests; Python compile and Vite production build passed.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-28 - Per-mode model routing

- Added independent renderer model routes for Chat, Cowork, and Code so changing the model in one mode does not change the others.
- Forwarded the active mode with each prompt through the frontend bridge, Eel/Electron adapter, preload, Electron main process, and `ipc_sidecar.py`.
- Added sidecar mode metadata to busy/idle, user, assistant, fallback, approval, and backend-error events so later permission profiles can split Chat sandbox behavior from Cowork workspace behavior.
- Kept provider behavior local-first; no cloud model route was added or selected automatically.
- TDD evidence: bridge and CoworkApp tests failed before prompt `mode` was forwarded; CoworkApp mode-route test failed before per-mode model state; sidecar mode metadata test failed before sidecar events included `mode`.
- Verification: focused frontend bridge/CoworkApp tests passed 22/22; focused sidecar mode metadata test passed.
- Verification: full frontend suite passed 10 files / 50 tests; full Python suite passed 68 tests; Vite production build passed.
- Browser verification: production preview rendered the Chat/Cowork/Code shell, exposed exactly one model menu button, selected Cowork mode successfully, and reported no browser console errors.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-28 - API provider model catalog

- Added `model_catalog.py` with a dated 2026-06-28 catalog for OpenAI, Z.ai, and Gemini model choices sourced from official provider documentation.
- Added sidecar provider metadata for `fetch_available_models` and `load_api_keys`; it reports configured provider status and key line slots without emitting raw API keys.
- Detected the current `key.txt` as OpenAI on line 1, Z.ai on line 4, and Gemini on line 7. No secret values were printed or written to logs.
- Extended the frontend bridge so API-prefixed model IDs (`openai:`, `zai:`, `gemini:`) are not rewritten as local models.
- Updated the model menu to render provider groups with configured status and model tier badges such as `main`, `fast`, and `free`.
- Clarified in `PROJECT_STATE.md` that API provider models are currently catalog/chooser-ready, while runtime adapters for provider execution are the next implementation step.
- TDD evidence: sidecar tests failed before provider catalog/key status existed; bridge tests failed before metadata forwarding and API-prefix normalization; CoworkApp tests failed before provider groups rendered in the model menu.
- Verification: focused sidecar catalog/key tests passed 2/2; focused frontend bridge/CoworkApp tests passed 24/24.
- Verification: full Python suite passed 69 tests; full frontend suite passed 10 files / 52 tests; Vite production build passed.
- Browser verification: production preview rendered the app shell, exposed exactly one model menu button, and reported no browser console errors.
- Skills used: `openai-docs`, `test-driven-development`, `webapp-testing`, Browser plugin, and `verification-before-completion`.

## 2026-06-28 - Z.ai provider correction

- Corrected the third API provider set from Claude/Anthropic to Z.ai after user confirmation that `key.txt` line 4 belongs to `https://z.ai/`.
- Replaced the Claude catalog entries with Z.ai GLM model entries, including `glm-5.2`, `glm-5.1`, `glm-5-turbo`, `glm-5`, `glm-4.7`, `glm-4.7-flashx`, `glm-4.7-flash`, and `glm-4.5-flash`.
- Updated model ID handling so `zai:` is treated as an API provider prefix and is not rewritten as a local model.
- Updated key classification so the current Z.ai key shape is reported as provider `zai` without emitting the raw key.
- Sources checked: Z.ai official docs for chat completion model options, GLM-5.2, GLM-4.7, and pricing/free model rows.
- TDD evidence: sidecar tests failed while Z.ai models and key status were missing; bridge tests failed while `zai:` was still normalized to `local:zai:`.
- Verification: focused sidecar provider tests passed 2/2; focused frontend bridge/CoworkApp tests passed 24/24.
- Verification: full Python suite passed 69 tests; full frontend suite passed 10 files / 52 tests; Vite production build passed.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-28 - API key smoke tests

- Ran redacted live API smoke tests using the three configured `key.txt` entries without printing or logging raw secret values.
- OpenAI: `/v1/models` authentication/list-model request succeeded with HTTP 200 and returned model metadata; no generation call was made because the task requested free-model testing and OpenAI API generation can consume account credits.
- Z.ai: `glm-4.7-flash` generation succeeded with HTTP 200 after disabling default thinking mode for the short smoke prompt; response returned `OK`.
- Gemini: model listing found generate-capable models, but `gemini-2.5-flash-lite` generation failed with HTTP 429 because prepayment credits are depleted.
- Gemini retest: `gemini-2.5-flash-lite`, `gemini-2.5-flash`, `gemini-2.0-flash-lite`, `gemini-2.0-flash`, Gemma, and `gemini-flash-latest` all returned the same HTTP 429 `RESOURCE_EXHAUSTED` prepayment-credits-depleted response, so the current key/project cannot generate even on free-tier-capable models.
- Runtime implication: Z.ai is ready for the first free-model runtime adapter; Gemini needs account credits/quota fixed before live generation can pass; OpenAI can be connected after the user confirms paid/credit-backed test usage.
- Sources checked: Z.ai pricing and thinking-mode docs, Gemini model/rate-limit docs, and OpenAI rate-limit/pricing docs.

## 2026-06-28 - Chat/Cowork session separation hardening

- Fixed renderer routing so sessionless or unknown-session Cowork events carrying mode metadata go to the active Cowork session instead of falling into the currently visible Chat session.
- Kept Cowork/Code approval cards out of Chat, preventing workspace permission prompts from visually crossing into the lightweight chat surface.
- Added mode metadata to renderer-created user, busy-status, and approval-resolution events so persisted history remains easier to route and audit after reloads.
- Preserved sidecar mode metadata through the frontend bridge for assistant, status, backend-error, and approval events.
- TDD evidence: the new CoworkApp regression test failed before unknown-session Cowork events could be recovered under the Cowork tab; an older approval test also exposed the previous assumption that approvals could render in Chat.
- Verification: focused CoworkApp/bridge tests passed 2 files / 26 tests; full frontend suite passed 10 files / 54 tests; Vite production build passed.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-28 - Provider model catalog visibility fix

- Fixed `fetch_available_models` so API provider catalog entries are still emitted when LM Studio/local model discovery fails with a connection error.
- Added `local_models_error` to the sidecar model metadata payload so the UI can receive API models while retaining a diagnostic reason for missing local models.
- Updated Z.ai key classification to support the current 49-character key shape with a dot separator, keeping provider status as configured without logging secret values.
- Updated UI selected-model normalization so API-prefixed model IDs are not displayed as missing `local:` models in status derivation.
- TDD evidence: sidecar regression test failed with `backend-log` instead of `available_models` before the local-list failure was isolated; Z.ai provider-status test failed until the key-shape classifier was expanded.
- Runtime evidence: direct sidecar `fetch_available_models` emitted OpenAI configured on slot 1, Z.ai configured on slot 4, and Gemini configured on slot 7, while preserving `local_models_error: Connection error.`.
- Verification: full Python suite passed 70 tests; full frontend suite passed 10 files / 54 tests; Vite production build passed.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-28 - Z.ai runtime execution fix

- Fixed the failing `zai:glm-4.7-flash` chat path shown in the UI: API-prefixed models are no longer sent to the local LM Studio client.
- Added Z.ai runtime creation through the OpenAI-compatible base URL `https://api.z.ai/api/paas/v4`, using the Z.ai key from `key.txt` without logging or printing the secret.
- Added OpenAI-compatible request support for provider-prefixed model IDs by stripping prefixes before sending the provider request and preserving provider-specific `extra_body` options.
- Kept model fallback local-only. Z.ai failures now report the Z.ai failure directly instead of silently trying a local fallback model.
- TDD evidence: sidecar Z.ai runtime test failed before `chat_model_factory`/provider routing existed; chat-model test covers prefix stripping and `extra_body` forwarding.
- Live evidence: direct sidecar smoke with `zai:glm-4.7-flash` returned AI text `OK` and emitted busy -> user -> AI -> idle events, with no local fallback event.
- Verification: full Python suite passed 72 tests; full frontend suite passed 10 files / 54 tests; Vite production build passed.
- Sources checked: Z.ai official OpenAI SDK guide and Chat Completion API docs.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-28 - Plain chatbot runtime for Chat mode

- Split `Chat` mode away from the Cowork workspace agent path. Chat now uses a plain conversational runtime with no workspace tools, no write/verification approvals, and no Cowork system prompt.
- Added a lightweight conversational system prompt for Chat mode focused on natural conversation, general questions, and explanation rather than file editing or project automation.
- Added short per-session Chat history in the sidecar so follow-up messages can include recent user/assistant context.
- Kept `Cowork` and `Code` on the existing agent/tool path, preserving workspace approvals, Secret Guard, verification gates, and audit behavior for those modes.
- TDD evidence: the new Chat runtime test failed before Chat was routed away from `agent_factory`; a history test now verifies the second Chat request includes the prior turn.
- Verification: full Python suite passed 74 tests; full frontend suite passed 10 files / 54 tests; Vite production build passed.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-28 - Three-mode architecture decision and Chat-first roadmap

- Promoted the latest product direction into `PROJECT_STATE.md` as the primary architecture decision: `Chat` = ChatGPT/Gemini-like assistant, `Cowork` = Codex-like workspace agent, and `Code` = Claude Code-like coding interface.
- Defined strict separation for memory, tools, prompts, token strategy, and permission boundaries across Chat/Cowork/Code.
- Added the Chat memory boundary: ordinary personal Chat memory is separate from project Chat memory, while Cowork and Code keep workspace/repo-specific memory.
- Added the Chat knowledge routing decision: classify questions as `general`, `project`, `web`, `memory`, or `mixed` before retrieving context.
- Added effort routing semantics for `Low`, `Medium`, and `High` so effort becomes backend behavior rather than just a UI label.
- Replaced the old next milestone list with a Chat-first implementation sequence: runtime config, memory, router, read-only project knowledge, web/MCP research, grounding, provider completion, then Cowork/Code continuation.
- Verification: confirmed the new headings and roadmap entries are present in `PROJECT_STATE.md`.
- Skills used: `writing-plans` and `verification-before-completion`.

## 2026-06-28 - Chat Runtime Foundation

- Added `chat_runtime.py` as the Chat-owned runtime configuration layer for the Chat system prompt, effort-specific generation settings, and short-history budgets.
- Wired composer effort from React through the bridge, preload, Electron main process, and `ipc_sidecar.py` into Chat model requests.
- Kept Chat effort scoped to Chat mode only. Cowork and Code continue to use the workspace-agent runtime and ignore Chat effort settings.
- Persisted per-mode model routes with the session store so Chat, Cowork, and Code model choices survive app reloads.
- Updated `PROJECT_STATE.md` to mark Chat Runtime Foundation complete and move the next active milestone to Chat Memory.
- TDD evidence: backend effort/runtime tests failed before `chat_runtime.py` and sidecar effort wiring existed; frontend persistence/effort tests failed before `modelRoutes` were saved and `effort` was forwarded to the bridge.
- Verification: full Python suite passed 76 tests; full frontend suite passed 10 files / 56 tests; Vite production build passed.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-28 - Chat personal memory foundation

- Added `chat_memory.py` as a Chat-only personal memory store for explicit user preferences, identity/name hints, and answer-style instructions.
- Stored Chat memory entries as compact JSON with `namespace`, `kind`, `content`, `source`, `created_at`, and `updated_at` fields.
- Added secret-like content rejection so messages containing API-key/token/password/private-key markers are not saved as personal memory.
- Wired Chat memory into `ipc_sidecar.py` so Chat mode stores explicit personal preferences and injects a compact `Chat Personal Memory` system block into future Chat prompts.
- Kept Cowork/Code out of Chat memory writes; workspace memory and approval-gated file writes remain separate.
- Updated `PROJECT_STATE.md` to mark Chat Memory as in progress, with personal memory complete and project Chat memory pending the Chat Router/read-only project knowledge steps.
- TDD evidence: `test_chat_memory` failed before `chat_memory.py` existed, and the sidecar memory injection test failed before Chat memory was wired into `_run_plain_chat`.
- Verification: focused Chat memory tests passed 4/4; full Python suite passed 80 tests.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-28 - Chat conversation bubble presentation

- Fixed the confusing Chat timeline label where assistant replies still appeared as `Cowork` even though the backend was already using Chat mode.
- Added Chat-specific message rendering: user messages align right, Chat replies align left, and Chat mode uses a conversational bubble layout instead of the Cowork-style log timeline.
- Kept Cowork/Code timeline presentation unchanged so workspace-agent events still read like work logs.
- TDD evidence: the new Timeline test failed while Chat assistant messages still rendered as `Cowork` and lacked left/right alignment metadata.
- Verification: focused Timeline/CoworkApp tests passed.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-28 - Chat Router foundation

- Added `chat_router.py` with deterministic routing categories: `general`, `project`, `web`, `memory`, and `mixed`.
- Wired Chat routing into `ipc_sidecar.py`; Chat requests now include a route system block and route metadata on emitted Chat logs.
- Kept the router conservative: `general` answers use model knowledge plus Chat personal memory and avoid project context by default.
- Added explicit missing-connector instructions for `project`, `web`, and `mixed` routes so Chat can say evidence is unavailable instead of inventing retrieved facts.
- Did not enable project-file reads or web/MCP calls in this step; read-only project knowledge is the next milestone.
- TDD evidence: `test_chat_router` failed before `chat_router.py` existed, and the sidecar route injection test failed before route system messages/log metadata were wired.
- Verification: focused router/sidecar tests passed 26/26.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-28 - Chat/Cowork boundary correction

- Corrected the Chat roadmap after user review: automatic workspace/project file reading does not belong in Chat.
- Updated `PROJECT_STATE.md` so Chat remains a ChatGPT/Gemini-like assistant for conversation, learning, web/MCP connectors, personal memory, artifacts, and explicitly attached context.
- Moved project/workspace inspection responsibility back to Cowork/Code. Chat project routes should ask for explicit attachments or suggest a Cowork handoff instead of reading project files.
- Replaced the previous `Read-only Project Knowledge for Chat` next milestone with `Chat Explicit Context and Attachments`.
- Verification: confirmed the updated roadmap entries and boundary language in `PROJECT_STATE.md`.
- Skills used: none; this was a documentation/architecture correction based on user direction.

## 2026-06-28 - Chat route workspace boundary enforcement

- Updated `chat_router.py` so Chat project routes explicitly say Chat cannot read workspace files automatically.
- Chat now instructs the model to ask the user to attach files/context or suggest switching to Cowork when project evidence is required.
- Updated router and sidecar tests to lock this separation: Chat route injection must not call workspace tools and must include the attachment/Cowork handoff language.
- Updated `PROJECT_STATE.md` current capability wording to match the enforced route prompt behavior.
- TDD evidence: `test_project_route_prompt_keeps_chat_out_of_workspace` failed first against the old `No project knowledge connector` wording, then passed after the router prompt change.
- Verification: `python -m unittest test.test_chat_router test.test_ipc_sidecar.IpcSidecarTests.test_chat_mode_injects_route_context_without_workspace_tools -v` passed 8/8; `python -m unittest discover -s test -p test_*.py -v` passed 88/88.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-28 - Chat explicit file attachments

- Added the first Chat-safe explicit context path: the Composer `Add files or photos` action opens a file picker, reads user-selected text-like files in the renderer, and shows removable attachment chips before submit.
- Forwarded attachment payloads through `CoworkApp`, `createCoworkBridge`, `frontend/lib/eel.js`, Electron preload/main, and `ipc_sidecar.py`.
- The sidecar now normalizes bounded Chat attachments and injects them as a `Chat Attached Context` system message with source labels. This keeps Chat from reading workspace files automatically while allowing user-selected context.
- Attachment contents are not emitted back through visible `cowork_log` UI events; runtime metadata records only labels/sources when a session log is active.
- TDD evidence: the new sidecar attachment test failed before attachment prompt injection existed; the bridge test failed before attachments were forwarded; the Composer test failed before the hidden file input existed.
- Verification: focused sidecar attachment test passed; focused Composer/bridge tests passed 14/14; CoworkApp tests passed 18/18; `python -m unittest discover -s test -p test_*.py -v` passed 89/89; `npm test -- --run` passed 59/59; `npm run build` completed successfully.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-28 - Chat pasted text context

- Added `Add pasted text` to the Chat composer context menu.
- The user can paste text or code, assign a label, and submit it as a bounded explicit Chat attachment with source `user-paste`.
- Kept this path inside the existing attachment boundary, so Chat receives user-provided context without gaining automatic workspace reads.
- TDD evidence: the new Composer test failed before the menu item and paste dialog existed, then passed after implementation.
- Verification: `npm test -- --run frontend/tests/Composer.test.jsx` passed 5/5.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-28 - Chat attachment preview chips

- Added attachment metadata chips to Chat user messages in the timeline.
- Chips show only label/source/kind metadata such as `notes.txt`, `user-file`, and `text`; attachment contents are intentionally not rendered in the conversation timeline.
- This makes explicit context visible to the user while preserving the boundary that Chat only uses user-selected context.
- TDD evidence: the Timeline test failed before `MessageEntry` rendered attachment metadata, then passed after adding chips.
- Verification: `npm test -- --run frontend/tests/Timeline.test.jsx` passed 4/4.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-28 - Chat local fallback and source contract

- Added local-only fallback behavior to Chat mode. When a selected local Chat model fails or returns an empty response, the sidecar can try an available configured local fallback model and emits a Chat-scoped System message before the fallback response.
- Kept API-prefixed models out of local fallback policy through the existing model-candidate rules, so cloud/API failures do not silently switch to a local model.
- Strengthened the attached-context prompt contract: if Chat uses attached context, it must cite source labels inline and end with a `Sources` section listing used labels and attachment names.
- TDD evidence: the Chat fallback test failed while only the primary local model was tried; the attached-context test failed before the `Sources` instruction existed.
- Verification: focused sidecar tests for attachment citation and Chat fallback passed 2/2.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-28 - Chat answer grounding guards

- Added a route-level answer grounding contract for Chat prompts: separate facts, assumptions, and suggestions; use source labels when available; and say what evidence is missing when support is insufficient.
- Strengthened web/current-fact route behavior so Chat is told not to answer current or external facts from stale model memory while no web connector exists.
- Updated `PROJECT_STATE.md` to mark the prompt-level Chat Answer Grounding guards as completed while leaving real web/MCP connector metadata and source-aware answer rendering as pending work.
- TDD evidence: `test_route_prompt_adds_answer_grounding_contract` and `test_web_route_blocks_current_fact_guessing_without_connector` failed before the router prompt contract existed, then passed after the router update.
- Verification: focused router tests passed 9/9; full Python backend suite passed 92/92.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-28 - Chat web connector foundation

- Added `chat_web_connector.py`, the first real backend web-search connector for Chat.
- Web/current-fact Chat routes can now call search, inject a `Chat Web Context` system block, and provide `[web:n]` source labels with title, URL, and snippet context to the selected model.
- Implemented DuckDuckGo HTML parsing with Bing HTML fallback because DuckDuckGo can return a challenge page in this environment. Bing redirect URLs are normalized to the destination URL when possible.
- Kept the connector Chat-only through sidecar routing and dependency injection. It does not grant workspace reads, file writes, shell commands, or Cowork/Code tool access.
- TDD evidence: `test_chat_web_connector` failed before the connector module existed; the sidecar web-context test failed before Chat injected web results; the Bing fallback test failed before fallback parsing and redirect normalization existed.
- Verification: focused connector/router/sidecar tests passed; full Python backend suite passed 96/96.
- Live smoke evidence: `ChatWebConnector(timeout_seconds=8).search("OpenAI official docs", max_results=2)` returned 2 web results with normalized destination URLs.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-28 - Chat web query cleaning and relevance reranking

- Investigated a user report where asking for Thai fuel prices returned an irrelevant LOMOSONIC song result.
- Root cause: the connector sent the full Thai request phrase (`ขอข้อมูล ราคาน้ำมันล่าสุด ของประเทศไทย`) directly to search, so the engine over-weighted the generic word `ขอ`; Bing also returned unrelated gold-price results for broad Thai price queries.
- Added query cleaning for common Thai request words and relevance reranking/filtering so terms such as `น้ำมัน` must be represented in returned context when matching results exist.
- Live smoke evidence: the same query now cleans to `ราคาน้ำมันล่าสุด ประเทศไทย` and returns a fuel-price result instead of song/gold results.
- Verification: connector tests passed 4/4; full Python backend suite passed 97/97.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-28 - Chat web coverage expansion

- Investigated whether the Thai fuel-price web connector was too restrictive after relevance filtering.
- Root cause: relevance filtering removed bad results, but the connector still stopped too early and depended on search-engine HTML returning enough relevant sources.
- Changed web search to collect multiple query variants before ranking, instead of stopping at the first relevant result.
- Added query-specific trusted source hints for Thai retail fuel-price questions, including EPPO and Bangchak pages, so Chat gets relevant source options even when generic search results are sparse.
- Live smoke evidence: `ขอข้อมูล ราคาน้ำมันล่าสุด ของประเทศไทย` now returns 4 relevant oil/fuel sources instead of one source or unrelated song/gold results.
- Verification: connector tests passed 6/6; full Python backend suite passed 99/99.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-28 - Chat web research synthesis pipeline

- Advanced the Chat web connector from search-result context toward a research pipeline: search, fetch top pages, extract readable evidence, score source quality, build source analysis, and pass that analysis into `Chat Web Context`.
- Updated the Chat web prompt contract so the model should analyze evidence across sources first, then synthesize the main answer with `[web:n]` citations.
- Added page evidence fields to `WebSearchResult` and analysis text to `WebSearchResponse`.
- Live smoke evidence: the Thai fuel-price query now fetches and extracts page evidence from Bangchak, EPPO, and the Bangchak widget; dynamic pages still need source-specific/JS-aware extraction to recover richer table values.
- Verification: focused connector/sidecar web tests passed 8/8; full Python backend suite passed 100/100.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-28 - Chat web evidence discipline and blocked-page handling

- Investigated the latest Thai fuel-price answer and found that anti-bot/captcha pages could be treated as fetched page evidence.
- Added blocked-page detection for common captcha/anti-bot responses so those results are marked `fetch-blocked` with no extracted evidence.
- Strengthened the web research contract already sent to Chat: exact dates, prices, version numbers, and table values must appear in extracted evidence, while source hints/snippets are only leads.
- Live smoke evidence: the Thai fuel-price query now marks the Bangchak oil price page as `fetch blocked; does not contain extracted exact values`, while EPPO remains usable page evidence and Bangchak's widget remains limited extracted text.
- Verification: focused captcha test passed 1/1; focused connector/sidecar web tests passed 10/10; full Python backend suite passed 102/102.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-28 - Chat web international search and user-result focus

- Updated Thai current-fact web search behavior so Thai fuel-price questions expand into English/international query variants before synthesis.
- Added international source hints for GlobalPetrolPrices gasoline and diesel pages, while keeping trusted hints behind real search results so hints do not displace relevant fetched/search results.
- Added a core oil/fuel relevance filter for Thai fuel-price searches so broad Thailand tourism, encyclopedia, or travel results are excluded even when English query variants are used.
- Updated Chat web context instructions: answer Thai prompts in Thai after using English/international sources, preserve useful original source terms, allow partial dates as partial dates, and do not add or convert years unless the year appears in extracted evidence.
- Hid unusable fetches from the Chat answer context when at least one usable source exists, so the user receives the best available answer rather than a blocked-source explanation.
- Live smoke evidence: `ขอข้อมูล ราคาน้ำมันล่าสุด ของประเทศไทย` retrieved GlobalPetrolPrices page evidence including `Thailand Gasoline prices, 22-Jun-2026` and `THB 49.59 per liter`, while generic Thailand travel/wiki results were filtered out.
- Verification: focused connector/sidecar web tests passed 13/13; full Python backend suite passed 105/105.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-29 - Track A Step 1 shared tool loop extraction

- Implemented Rollout Step 1 for Track A Research Foundation only: extracted the Cowork model/tool-calling loop into `tool_loop.py`.
- Refactored `CoworkAgent.run()` to call `run_tool_loop(...)` while keeping Cowork-specific run-state stage recording, verification-before-report repair, recorder events, and event sink behavior in `cowork_agent.py` through `LoopHooks`.
- Added focused tests for the shared loop covering tool dispatch/finalization, `before_finalize` repair turns, and empty-response recovery.
- Verification: full Python backend suite passed 108/108 with `python -m unittest discover -s test -p test_*.py -v`.
- Claude Code review request was attempted with the local `claude` CLI, but the CLI returned `401 Invalid authentication credentials`; Step 2 remains blocked until Claude Code authentication is fixed and review findings are recorded/resolved.
- Skills used: `test-driven-development`, `verification-before-completion`, and `requesting-code-review`.

## 2026-06-29 - Track A Step 2 generic table extraction

- Implemented Rollout Step 2 / A3.1 only: added generic `_extract_tables(html, *, max_tables=8, max_rows=40)` to `chat_web_connector.py`.
- Preserved row/cell structure, headers, captions, first-following preceding headings, nested-table boundaries, empty-cell alignment, multiple table caps, and row caps without adding domain-specific oil/fuel logic.
- Wired table evidence into `_extract_page_evidence` as structured `label: value` lines and prioritized those lines before prose so long prose does not truncate away exact table values.
- Removed the corrupted mojibake marker constants from `_is_thai_oil_query` and `_has_oil_relevance` without extending the oil-specific heuristics.
- Added tests for table row preservation, multiple tables/caps, nested tables, empty-cell alignment, heading consumption, multi-column serialization, table evidence prioritization, table label/value evidence, and no-table behavior.
- Verification: focused web connector tests passed 20/20; full Python backend suite passed 117/117 with `python -m unittest discover -s test -p test_*.py -v`.
- Claude Code review verdict: `PASS_WITH_NON_BLOCKING_NOTES`; no blocking findings. Non-blocking notes about duplicate table text in prose, all table rows bypassing relevance filtering, empty-value cosmetics, multi-row headers, and a few optional tests are deferred because they do not block Step 2 and can be revisited when evidence-budget pressure appears in real fetches.
- Skills used: `test-driven-development`, `verification-before-completion`, and `requesting-code-review`.

## 2026-06-29 - Track A Step 3 WebResearchTools provider

- Implemented Rollout Step 3 / A1.1 only: added `chat_web_tools.py` with `WebResearchTools`.
- Exposed only web tools through the shared tool-provider contract: `web_search` and `web_fetch`; no filesystem, workspace, Git, verification, or approval tools were added.
- `web_search` clamps `max_results` to 1..8, calls the injected `ChatWebConnector`, registers stable 1-based `[web:N]` source indices, returns indexed result metadata, and does not auto-fetch pages.
- `web_fetch` fetches through the connector fetcher, handles blocked pages with `status:"ok"` and `blocked:true`, enforces `max_fetch`, returns structured tables from the Step 2 extractor, and strips table HTML before prose extraction so table cell values are not duplicated in `evidence`.
- Added `test/test_chat_web_tools.py` with tests for strict web-only schemas, stable source indices, blocked-page handling, table-page fetches, fetch caps, no index reuse, no search auto-fetching, and dispatch error paths.
- Verification: focused web tools tests passed 7/7; full Python backend suite passed 124/124 with `python -m unittest discover -s test -p test_*.py -v`.
- Claude Code review verdict: `PASS_WITH_NON_BLOCKING_NOTES`; no blocking findings. Deferred integration notes: strict optional `max_results` may need provider-live validation at A1.4/A1.5, `web_fetch` uses page title as the current evidence relevance query, source type is not upgraded after fetch, and URL normalization is currently strip-only.
- Skills used: `test-driven-development`, `verification-before-completion`, and `requesting-code-review`.

## 2026-06-29 - Track A Step 4 ChatResearchRunner foundation

- Implemented Rollout Step 4 / A1.3 Step 2 only: added `chat_research_runner.py` as a model-driven Chat web research runner over the shared tool loop.
- Added optional `generation` plumbing to `run_tool_loop(...)`; Cowork calls still omit `generation`, preserving the previous two-argument `model.complete(messages, tools)` path.
- Added `model_fallback.py` and refactored the plain Chat fallback path in `ipc_sidecar.py` to use the same candidate-walk helper as `ChatResearchRunner`.
- Fixed `web_search` strict schema compatibility by making `max_results` nullable and required, while keeping the code default for `null`.
- Added and updated tests for generation forwarding, strict two-argument Cowork compatibility, strict web schema invariants, tool-driven research, no-tool fallback signaling, model fallback, and user-query-aware fetch relevance.
- Verification: focused Step 4 suite passed 26/26 with `python -m unittest test.test_tool_loop test.test_chat_web_tools test.test_chat_research_runner test.test_ipc_sidecar.IpcSidecarTests.test_chat_mode_falls_back_to_available_local_model test.test_cowork_agent -v`; full Python backend suite passed 131/131 with `python -m unittest discover -s test -p test_*.py -v`.
- Claude Code review verdict: `PASS_WITH_NON_BLOCKING_NOTES`; no blocking findings. One non-blocking Cowork call-shape test note was resolved immediately with `test_absent_generation_preserves_two_argument_model_call`; remaining notes are deferred to Step 6/provider hardening.
- Skills used: `test-driven-development`, `verification-before-completion`, and `requesting-code-review`.

## 2026-06-29 - Track A Step 5 deterministic answer guard

- Implemented Rollout Step 5 / A2 only: added standalone `chat_answer_guard.py` with pure deterministic validation and no network, model, global state, or live Chat integration.
- Added `GuardResult` and `validate_answer(answer, evidence_corpus, sources, allow=())`.
- Guard checks unsupported 20xx/25xx years, partial dates that gain unsupported years, price/currency figures using normalized numeric values, and dangling `[web:N]` citations.
- Guard corrections are surgical: unsupported year tokens are removed, unsupported price/currency figures are annotated, and unresolved correction cases receive guard notes.
- Added `test/test_chat_answer_guard.py` covering the headline partial-date hallucination regression, evidence-supported years, missing/supported prices including structured table evidence, numeric normalization and boundary behavior, dangling citations, allow-list false-positive protection, ordinary counts, and version-like numbers.
- Verification: focused guard tests passed 10/10 with `python -m unittest test.test_chat_answer_guard -v`; full Python backend suite passed 141/141 with `python -m unittest discover -s test -p test_*.py -v`.
- Claude Code review verdict: `PASS_WITH_NON_BLOCKING_NOTES`; no blocking findings. Non-blocking false-positive and polish notes were deferred to Step 6/guard tuning because Step 5 intentionally follows the documented standalone contract.
- Skills used: `test-driven-development`, `verification-before-completion`, and `requesting-code-review`.

## 2026-06-29 - Track A Step 6 final Chat research integration

- Completed Track A Step 6 in order: 6a legacy helper extraction, 6b additive research plumbing, 6c live Chat web-tool integration, and 6d telemetry/final closure.
- `_run_plain_chat` now uses `ChatResearchRunner` for web-routed Chat prompts only when the selected provider is enabled for tool research.
- Non-web Chat, non-tool providers, and web-routed model responses that do not call tools still fall back to the legacy web-chat path.
- The live tool path preserves route context, Chat memory, explicit attachments, recent history, and effort generation settings.
- `WebResearchTools` now exposes an evidence corpus and can be frozen during a guard correction turn.
- `validate_answer(...)` now guards tool-research answers before finalization, can trigger one evidence-only rewrite, and can apply a surgical corrected answer if the second answer remains invalid.
- Added additive telemetry for `chat_research` and `chat_answer_guard` without removing existing Chat route, web-search, message, attachment, or memory events.
- Added Step 6 tests for guarded web-tool success, no-tool fallback, provider-gated fallback, guard re-ask without extra fetch, corrected-answer fallback, and context preservation.
- Fixed package import compatibility in `chat_web_tools.py` after relocation integration exposed the issue.
- Verification: focused sidecar tests passed 30/30 with `python -m unittest test.test_ipc_sidecar -v`; full Python backend suite passed 149/149 with `python -m unittest discover -s test -p test_*.py`.
- Claude Code review verdict for Step 6c/6d integration: `PASS_WITH_NON_BLOCKING_NOTES`; no blocking findings. Deferred notes: Gemini/Anthropic provider runtimes are not implemented yet, and attempted tool-research telemetry should be interpreted with the `used_tools` flag.
- Skills used: `systematic-debugging`, `verification-before-completion`, and `requesting-code-review`.

## 2026-06-29 - Titlebar app version marker

- Added a small top-right titlebar version marker that reads from `package.json`, currently `v0.1.0`, so UI updates are easier to confirm after restarts.
- Updated the Cowork app shell test to assert the visible version marker.
- Verification: frontend build passed with `npm run build`; frontend tests passed 10/10 files and 61/61 tests with `npm test`.
- Skills used: `verification-before-completion`.

## 2026-07-01 - Quality runner v2 directness, source quality, and retry metrics

- Implemented the next quality-runner pass after the first live scorecard exposed overly permissive scoring.
- Directness metric:
  - `evaluate_case_result(...)` now flags answerable `general` / `thai` cases that dodge the request by asking for more context instead of answering.
  - Such indirect answers now fail even when they are long enough or contain Thai characters.
- Source-quality metric:
  - Web cases now inspect explicit `source_type` / `quality_score` metadata.
  - Low-quality explicit search-result-only sources fail the cell; high-quality metadata such as `official-docs`, `pricing`, or scores >= 2 pass.
  - Sources without legacy metadata are not punished, preserving older tests and callers.
- Live runner retry support:
  - `run_quality_eval_live(...)` and `python -m chat_quality_runner` now accept bounded `retry_attempts` and `retry_backoff_seconds`.
  - Retry only applies to provider-style transient failures such as HTTP 429, rate limit, overload, or too-many-requests errors.
  - Non-retryable errors still fail one cell and do not abort the matrix.
- Reporting:
  - Matrix cells now include `attempts`, `direct`, and `source_quality_ok`.
  - Aggregates now include `directness_rate` and `source_quality_rate` alongside pass rate, latency, hallucination rate, and source usage.
  - Markdown reports show attempts, directness, and source quality columns.
- Fixture improvement:
  - The Thai quality fixture is now a specific Thai prompt about separating Chat/Cowork/Code responsibilities with examples, so it measures useful Thai answer behavior instead of merely detecting Thai characters.
- Verification:
  - Targeted backend tests passed 18/18 with `python -m unittest test.test_chat_quality_eval test.test_chat_quality_runner -v`.
  - Python compile check passed with `python -m py_compile chat_quality_eval.py chat_quality_runner.py`.
  - Full backend suite passed 290/290 with `python -m unittest discover -s test -p test_*.py -v`.
  - Frontend suite passed 104/104 with `npm test`.
  - Frontend production build passed with `npm run build`; the existing Vite chunk-size warning remains non-blocking.
  - CLI help check passed with `python -m chat_quality_runner --help`.
  - An initial frontend command using Jest's unsupported `--runInBand` flag failed as a command mismatch, then the correct `npm test` command passed.
- Skills used: `writing-plans`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-29 - Concept-Complete Chatbot Phase 1 truthfulness hardening

- Implemented the first high-priority slice from `Concept-Complete Chatbot - Master Spec & Upgrade Plan` without Claude review, per user instruction for this round.
- A1 placeholder/skeleton detection: `_extract_tables(...)` now drops loading placeholder tables and uniform-fill numeric tables before they become `label: value` evidence.
- A1 evidence cleanup: `_ReadableTextParser` now skips table contents so dropped placeholder table cells do not leak back into prose evidence.
- B2 partial-date guard fix: `validate_answer(...)` now forbids attaching a year to an evidence date that was year-less, even when the current year is present in the runtime allow set.
- B1 uniform-value suspicion: the answer guard now flags answers that present three or more price-context values that are all identical, catching likely placeholder price tables even if the values appear in evidence.
- F1 provider error UX: Chat worker errors for billing, credit, quota, overload, rate-limit, and unimplemented provider runtime are mapped to concise user-facing messages. API-prefixed models still do not silently fall back to another provider.
- Added regression tests for loading tables, uniform placeholder evidence, real varied tables, partial-date/current-year allow behavior, uniform price-table answers, and provider credit errors.
- Stabilized the real npm worker-tree cleanup test by increasing its timeout from `0.8s` to `2.0s`, because npm startup on the current Windows environment could be killed before the child worker wrote its heartbeat.
- Verification: focused backend suite passed 66/66 with `python -m unittest test.test_chat_web_connector test.test_chat_answer_guard test.test_ipc_sidecar -v`; full backend suite passed 155/155 with `python -m unittest discover -s test -p test_*.py`.
- Skills used: `writing-plans`, `test-driven-development`, `systematic-debugging`, and `verification-before-completion`.

## 2026-06-29 - Concept-Complete Chatbot Phase 2 and Phase 3 implementation

- Phase 2 implemented XHR-first source adapters and search concurrency.
- Added `chat_source_adapters.py` with Bangchak and EPPO adapter registry entries. Bangchak fetches `https://oil-price.bangchak.co.th/apioilprice2/th`; EPPO fetches `https://www.eppo.go.th/wp-json/oil-api/v1/oil-prices`.
- Added captured JSON fixtures under `test/fixtures/` and adapter tests proving per-type/provider prices differ and no fake fallback values are generated.
- Wired `WebResearchTools.web_fetch` to try registered source adapters before HTML extraction, then fall back to the existing HTML/table/prose path when adapters have no data.
- Parallelized `ChatWebConnector.search` engine fetches and top-result page enrichment with bounded `ThreadPoolExecutor`, preserving ordered result collection and per-future error handling.
- Added Thai `บาท` / `ลิตร` markers to the uniform-price answer guard.
- Claude CLI review for Phase 2 returned `PASS_WITH_NON_BLOCKING_NOTES`; resolved the non-blocking float parsing note with `parse_float=Decimal` and added `source_type` to blocked fetch responses.
- Phase 3 implemented C1 routing semantics for tool-capable providers: Chat now offers web tools on non-memory routes, trusts runner answers when `used_tools=False`, and keeps legacy web chat for non-tool providers or runner error/empty cases.
- Provider access/billing/rate-limit errors are no longer retried through legacy after a runner failure; they surface through the existing friendly Chat error mapper.
- Phase 3 implemented D1 de-hardcoding by removing Thai-oil-specific query variants, relevance filters, source hints, international hints, and oil-specific source-quality boosts from the primary connector path.
- Removed old oil-pinned tests and added generic non-oil web search coverage for weather-style current queries, plus tests for no double-answering, current-fact tool search, and non-tool legacy behavior.
- Verification:
  - Phase 2 full backend suite passed 161/161 with `python -m unittest discover -s test -p test_*.py -v`.
  - Phase 3 focused suite passed 67/67 with `python -m unittest test.test_ipc_sidecar test.test_chat_web_connector test.test_chat_research_runner test.test_chat_web_tools -v`.
  - Phase 3 full backend suite passed 159/159 with `python -m unittest discover -s test -p test_*.py -v`.
- Claude CLI review for Phase 3 is pending because the CLI returned `You've hit your session limit · resets 1:50am (Asia/Bangkok)` at 2026-06-29 23:26:58 +07:00.
- Skills used: `test-driven-development`, `systematic-debugging`, `verification-before-completion`, and `requesting-code-review`.

## 2026-06-30 - Chat composer drag-and-drop attachments

- Added drag-and-drop support to the Chat composer so files/photos dropped on the composer are attached through the existing explicit Chat attachment pipeline.
- Image-like files are now classified as `kind: image` with bounded metadata context; full vision-provider payload support remains a future capability.
- Added a regression test proving a dropped `diagram.png` appears as an attachment chip and is submitted with the prompt.
- Verification before documentation update: focused Composer test passed 6/6 with `npm test -- frontend/tests/Composer.test.jsx`.
- Skills used: `test-driven-development`, `webapp-testing`, and `verification-before-completion`.

## 2026-06-30 - Phase 3 follow-up guard and source-hint registry

- Implemented follow-up Fix 1 from the Phase 3 in-session review: `_run_tool_research_chat.before_finalize` now skips grounding validation when `WebResearchTools.evidence_corpus()` is blank, preventing spurious repair turns for general no-tool answers.
- Added a defensive `validate_answer(...)` no-op for blank evidence so the grounding guard remains evidence-scoped instead of becoming a general content filter.
- Implemented follow-up Fix 2 by replacing the old `_trusted_source_hints` / `_international_source_hints` calls with one generic `_SOURCE_HINT_PROFILES` data registry and `_source_hints(clean_query)` resolver.
- Preserved EPPO, Bangchak, and GlobalPetrolPrices fuel hints as registry data so they still work with Phase 2 XHR adapters, while future topics can be added as data profiles rather than code branches.
- Added regression tests for no blank-evidence guard repair, blank-evidence guard no-op, fuel registry hints, and a dummy non-oil registry profile.
- Verification: focused follow-up tests passed 4/4; related suite passed 77/77 with `python -m unittest test.test_ipc_sidecar test.test_chat_answer_guard test.test_chat_web_connector test.test_chat_web_tools -v`; full backend suite passed 161/161 with `python -m unittest discover -s test -p test_*.py -v`.
- Claude review: skipped by explicit user instruction for this follow-up; review notes recorded in `work_logs/track-a-review-log.md`.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-30 - Phase 4 E2 markdown rendering

- Implemented Master Spec Phase 4 E2 only; E3/E1 were not started.
- Added `react-markdown`, `remark-gfm`, and `rehype-highlight`, then imported a highlight.js theme through `styles/index.css`.
- Added `frontend/components/MarkdownMessage.jsx` for assistant Chat markdown rendering with GFM, highlighted code blocks, table/list/block/code styling, and safe external links.
- Updated `MessageEntry.jsx` so only Chat assistant messages render markdown. User messages, system messages, and non-Chat/Cowork timeline messages remain plain text.
- Added Timeline tests for assistant bold/code/table rendering, user plain-text behavior, raw HTML non-rendering, and safe link attributes.
- Claude CLI review returned `PASS_WITH_NON_BLOCKING_NOTES`; resolved all non-blocking notes by dropping the leaked `node` prop, adding the link-safety test, and importing a highlight.js theme.
- Verification after fixes: `npm audit --audit-level=high` found 0 vulnerabilities; `npm test` passed 10 files / 66 tests; `npm run build` passed with a chunk-size warning; `python -m unittest discover -s test -p test_*.py -v` passed 161/161.
- Skills used: `writing-plans`, `test-driven-development`, `verification-before-completion`, and `requesting-code-review`.

## 2026-06-30 - Phase 4 E3 source cards and E1 streaming

- Implemented Master Spec Phase 4 E3 and E1 in one pass per user instruction.
- E3 source metadata: `_run_plain_chat(...)` now returns `(answer, used_model, web_sources)` and sidecar AI `cowork_log` payloads include `web_sources` only when source metadata exists.
- E3 renderer: `coworkBridge` maps `web_sources` to `webSources`; Chat assistant markdown turns matching `[web:N]` into clickable superscript citation links; `MessageEntry` renders source cards with domain, title, and source-type badges (`fetched`, `snippet`, `blocked`, `hint`).
- E1 backend streaming: `OpenAIChatModel` now supports OpenAI-compatible `stream_complete(...)` and `stream(...)`; `tool_loop.run_tool_loop(...)` accepts `on_final_delta` and emits deltas only for models that support streaming and only after a non-tool final turn passes the `before_finalize` hook.
- E1 sidecar/frontend streaming: Chat requests emit `cowork_log_delta` events; the bridge normalizes them as stable running assistant events; the reducer appends deltas into one in-flight assistant bubble and replaces it with the final post-guard `cowork_log` answer.
- Non-streaming model paths preserve the old complete-response behavior, so existing fake/non-streaming tests and Cowork mode are unchanged.
- Added regression tests for backend source payloads, source-card/citation rendering, OpenAI streaming adapter behavior, final-turn-only tool-loop streaming, sidecar delta emission, bridge delta normalization, and reducer streaming replacement.
- Verification: full backend suite passed 164/164 with `python -m unittest discover -s test -p test_*.py -v`; full frontend suite passed 10 files / 70 tests with `npm test`; frontend build passed with `npm run build` and the existing Vite chunk-size warning.
- Review: Claude review intentionally not requested for this round per user instruction. In-session review checked behavior boundaries: source cards are Chat assistant only, no source payload is emitted for no-source answers, tool-call turns do not stream, final commit replaces pending deltas, and non-streaming providers keep fallback behavior.
- Skills used: `writing-plans`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`, and `requesting-code-review` guidance without external Claude invocation.

## 2026-06-30 - E1-live follow-up and Phase 5 Playwright fallback

- Implemented the E1-live follow-up so Chat streaming deltas are emitted during model generation instead of being buffered until the final answer.
- Added stream reset handling from backend to renderer: if a streamed turn is later discarded for tool calls, empty-response recovery, or answer-guard repair, the UI clears the provisional assistant text before showing the corrected/final stream.
- Kept the final `cowork_log` event authoritative: reducer cleanup still replaces the in-flight streaming assistant event with the final post-guard Chat answer.
- Scoped streaming to the Chat research-runner path. Legacy/non-streaming Chat providers keep the complete-response path, and Cowork still calls the shared tool loop without streaming callbacks.
- Implemented Phase 5 as a feature-flagged Playwright last-resort fetch path. `WebResearchTools.web_fetch` now tries source adapters first, then static HTTP extraction, then optionally uses a Playwright renderer only when `playwright_fetch_enabled` / `COWORK_CHAT_PLAYWRIGHT_FETCH` is enabled, no registered adapter matched, and static evidence is empty or blocked.
- Added `chat_playwright_fetch.py` with lazy Playwright imports so the dependency is not required when the feature flag is off. Tests inject fake fetchers; no real browser is launched in the automated suite.
- Added `has_source_adapter(...)` so Playwright fallback can skip known XHR-backed sources and preserve adapter-first behavior.
- Added regression tests for live delta timing, reset on discarded streams, guard-repair stream reset, bridge/reducer reset behavior, feature-flag-off Playwright behavior, rendered table extraction, timeout fallback, and rendered placeholder dropping.
- Verification:
  - Focused E1-live backend tests passed 4/4.
  - Focused E1-live frontend tests passed 2 files / 12 tests.
  - Focused Phase 5 tests passed 4/4.
  - Related backend suite passed 89/89 with `python -m unittest test.test_chat_web_tools test.test_chat_source_adapters test.test_chat_web_connector test.test_ipc_sidecar test.test_tool_loop test.test_cowork_agent -v`.
  - Related frontend suite passed 3 files / 31 tests with `npm test -- frontend/tests/coworkBridge.test.js frontend/tests/coworkReducer.test.js frontend/tests/Timeline.test.jsx`.
  - Full backend suite passed 170/170 with `python -m unittest discover -s test -p test_*.py -v`.
  - Full frontend suite passed 10 files / 72 tests with `npm test`.
  - Frontend build passed with `npm run build`; Vite reported only the existing chunk-size warning.
- Review: Claude review intentionally not requested for this round per user instruction. In-session review checked that streaming is actually live, reset events remove discarded provisional text, final commits remain authoritative, Playwright is default-off, source adapters still win before browser rendering, and tests do not require a real browser.
- Skills used: `writing-plans`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`, `requesting-code-review` guidance without external Claude invocation, and `webapp-testing` guidance for frontend verification.

## 2026-06-30 - Production stability timeout and relevance pass

- Diagnosed the live `zai:glm-4.5-flash: Request timed out` failure path. Root cause: slow/free research synthesis could exceed the model client timeout, then surface through Chat as a raw backend error and frontend label still hardcoded the failure as `Cowork`.
- Added Chat-specific model timeout configuration: `ChatRuntimeConfig.model_timeout_seconds`, defaulting to 90 seconds and configurable with `COWORK_CHAT_MODEL_TIMEOUT`. Cowork/default OpenAI-compatible model construction still defaults to 45 seconds unless a caller passes a different timeout.
- Routed the configurable timeout through plain Chat completion and ChatResearchRunner model creation. Timeout failures remain retryable in the existing candidate-walk fallback, while provider billing/rate-limit access errors keep their existing friendly handling.
- Added a friendly all-timeout message: the user sees that the model timed out and can retry or pick a faster model, rather than seeing raw provider/library text.
- Added a generic relevance gate to `chat_web_connector.py`: ranking now scores significant English and Thai query terms against title, URL, snippet, and extracted evidence, and returns an empty result set when every concrete search result has zero overlap. Trusted source hints remain data-profile seeds and are not treated as random search results.
- Added Thai substring matching for longer Thai query tokens so relevant Thai pages are not over-dropped when words are not separated by spaces.
- Made frontend backend-error labels mode-aware: Chat errors say `Chat could not complete...`, Cowork/Code use their mode, and missing mode uses neutral `Request could not complete...`.
- Added regression tests for timeout fallback, all-timeout friendly errors, configured timeout propagation, off-topic Blender search gating, relevant VLC result preservation, relevant Thai gold result preservation, and mode-aware backend error labels.
- Verification:
  - Focused timeout tests passed 3/3.
  - Focused relevance tests passed 3/3.
  - `frontend/tests/coworkBridge.test.js` passed 14/14.
  - Related backend suite passed 89/89 with `python -m unittest test.test_ipc_sidecar test.test_chat_web_connector test.test_chat_web_tools test.test_chat_research_runner test.test_cowork_agent -v`.
  - Full backend suite passed 176/176 with `python -m unittest discover -s test -p test_*.py -v`.
  - Full frontend suite passed 10 files / 74 tests with `npm test`.
  - Frontend build passed with `npm run build`; Vite reported only the existing chunk-size warning.
- Review: Claude review intentionally not requested in this run. In-session review checked behavior boundaries: timeout is retryable but provider access errors are not broadened, Cowork timeout behavior remains default-compatible, all-zero-overlap search results are gated without hardcoding topics, trusted source hints still flow from data profiles, and label changes preserve existing event shape.
- Skills used: `writing-plans`, `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-02 - Chat image paste and timeline thumbnails

- Continued the Chat stabilization track after the web/MCP/text diagnostics pass.
- Fixed the image attachment UX gap from manual testing:
  - Clipboard-pasted images now use `source: user-paste` instead of being mislabeled as `user-file`.
  - Paste events on the broader composer surface attach images, so `Ctrl+V` still works when the textarea is not the direct active target.
  - Chat user-message bubbles now render local image thumbnails for image attachments while keeping raw text attachment content hidden.
  - The visible timeline event keeps only label/source/kind plus an image thumbnail data URL for local preview; the backend request still receives the full attachment payload through the existing attachment pipeline.
- TDD evidence:
  - Composer regression tests first failed because pasted images were labeled `user-file` and composer-surface paste did not attach the image.
  - Timeline regression first failed because image attachments rendered only as metadata chips.
  - CoworkApp integration regression first failed because submit-time user echo stripped image preview data from the local timeline event.
- Verification:
  - Focused Composer suite passed 16/16 with `npm.cmd run test -- --run frontend/tests/Composer.test.jsx`.
  - Focused Timeline suite passed 11/11 with `npm.cmd run test -- --run frontend/tests/Timeline.test.jsx`.
  - Focused CoworkApp suite passed 24/24 with `npm.cmd run test -- --run frontend/tests/CoworkApp.test.jsx`.
  - Full frontend suite passed 120/120 across 17 files with `npm.cmd run test`.
  - Frontend production build passed with `npm.cmd run build`.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-30 - Search API migration

- Implemented the Search API migration for the Chat web-research stack.
- Added `chat_search_api.py` with a pluggable `SearchProvider` protocol, `BraveSearchProvider`, and `get_search_provider(config)`.
- Added Chat runtime search configuration: `COWORK_SEARCH_API_PROVIDER` (default `brave`) and `COWORK_SEARCH_API_KEY`. Search API usage is opt-in and enabled only when a key is present.
- Wired `ChatWebConnector.search()` so an available provider supplies the initial `{title, url, snippet}` result list, then the existing downstream pipeline still performs source hints, dedupe, ranking, relevance gating, enrichment, and source analysis.
- Preserved no-key behavior: if no provider is configured, `ChatWebConnector` uses the existing DuckDuckGo/Bing HTML scraping path.
- Added provider-error fallback: if the Search API provider raises or times out, search falls back to HTML scraping without crashing.
- Kept Phase 2 source adapters, placeholder detection, table extraction, Playwright fetch fallback, and answer guard untouched.
- Added tests with fake providers only; no live Search API calls are made in the suite.
- Claude CLI review result: ship-ready, no blocking issues. One medium test-hygiene finding was resolved by clearing/restoring `COWORK_SEARCH_API_KEY` and `COWORK_SEARCH_API_PROVIDER` in `ChatWebConnectorTests`, ensuring HTML-path tests never hit a live API even if the developer environment has a key.
- Verification:
  - Focused Search API connector tests passed 4/4.
  - Provider module and connector tests passed 31/31 with `python -m unittest test.test_chat_search_api test.test_chat_web_connector -v`.
  - Related backend suite passed 82/82 with `python -m unittest test.test_chat_search_api test.test_chat_web_connector test.test_chat_web_tools test.test_ipc_sidecar -v`.
  - Full backend suite passed 183/183 with `python -m unittest discover -s test -p test_*.py -v`.
- Skills used: `systematic-debugging`, `test-driven-development`, `verification-before-completion`, and `requesting-code-review`.

## 2026-06-30 - Chat research status

- Implemented Chat-only live research status for the web-tool phase before the final answer visibly streams.
- Backend:
  - `ChatResearchRunner.run(...)` now accepts and forwards an `on_event` callback to the shared `tool_loop`.
  - `_run_tool_research_chat(...)` maps `tool_execution` events into additive `cowork_status` IPC events for `web_search` and `web_fetch`.
  - Status text is short and human-facing: `🔍 Searching: <query>`, `📄 Reading: <domain>`, and `✍️ Writing…`.
  - Raw tool results/evidence are not emitted in status payloads.
  - `Writing…` is emitted only after actual research tool activity, so no-tool/general answers keep the normal Thinking/streaming behavior.
- Frontend:
  - `coworkBridge` subscribes to `cowork_status` and normalizes it as `chat.status`.
  - `coworkReducer` keeps `chat.status` in `transientStatus` instead of `events`, so it never becomes a timeline message.
  - `CoworkApp` skips persisting `chat.status` to the session store and passes the active transient text into `ProcessingIndicator`.
  - `ProcessingIndicator` displays research status text instead of the generic Thinking/Working timer while status is active, then the reducer clears it on the first streaming delta, final assistant message, or failure.
- Added regression tests for runner event forwarding, sidecar `cowork_status` emission, bridge normalization, reducer transient store/clear behavior, and indicator status rendering.
- Claude CLI review result: no blocking issues. Non-blocking observations were limited to expected UX details: `Writing…` can be a very brief flash for streaming models because first delta clears it immediately; a model that streams prose before tool calls could briefly show a cosmetic writing state before reset.
- Verification:
  - Focused backend status tests passed 2/2.
  - Related backend suite passed 45/45 with `python -m unittest test.test_chat_research_runner test.test_ipc_sidecar -v`.
  - Full backend suite passed 185/185 with `python -m unittest discover -s test -p test_*.py -v`.
  - Related frontend suite passed 5 files / 58 tests.
  - Full frontend suite passed 10 files / 79 tests with `npm test -- --run`.
  - Frontend build passed with `npm run build`; Vite reported only the existing chunk-size warning.
- Skills used: `writing-plans`, `test-driven-development`, `verification-before-completion`, and `requesting-code-review`.

## 2026-06-30 - Loop Intelligence Item 2 effort-tied research budgets

- Implemented Loop Intelligence Upgrade Item 2.
- Added Chat research budget fields to `ChatEffortConfig`: `research_max_iterations` and `research_max_fetch`.
- Default budget behavior:
  - Low: 4 loop iterations, 3 fetches.
  - Medium: 6 loop iterations, 5 fetches, preserving the previous fixed defaults.
  - High: 12 loop iterations, 8 fetches.
- Wired `_run_tool_research_chat(...)` so Chat research passes `effort_config.research_max_iterations` into `ChatResearchRunner` and `effort_config.research_max_fetch` into `WebResearchTools`.
- Kept Cowork unchanged: no `tool_loop.py` behavior changed and Cowork still uses its existing agent/tool loop settings.
- Kept injection compatibility by adding `_call_chat_web_tools_factory(...)`; factories that accept `max_fetch` receive it, while older query-only factories continue to work.
- Added regression tests proving default effort budgets and that High effort can execute 7 fetches over 8 model turns without hitting the prior 6/5 cap; the test also asserts the factory receives `max_fetch=8`.
- Claude CLI review result: no blocking issues. One optional coverage note was resolved by asserting the exact `max_fetch` value delivered to the injected factory.
- Verification:
  - Focused Item 2 tests passed 2/2.
  - Related backend suite passed 77/77.
  - Full backend suite passed 187/187 with `python -m unittest discover -s test -p test_*.py -v`.
  - Full frontend suite passed 10 files / 79 tests with `npm test -- --run`.
  - Frontend build passed with `npm run build`; Vite reported only the existing chunk-size warning.
- Skills used: `writing-plans`, `test-driven-development`, `verification-before-completion`, and `requesting-code-review`.

## 2026-06-30 - Loop Intelligence Item 1 graceful forced best-effort answer

- Implemented Loop Intelligence Upgrade Item 1.
- Added opt-in `force_final_answer` support to the shared `run_tool_loop(...)`.
- When enabled and the model reaches the final allowed research iteration while still requesting tools, the loop now stops dispatching more tools and performs one final model turn with `tools=[]`.
- The forced final prompt explicitly requires using only already gathered evidence and says not to guess, fabricate, or invent missing values/citations.
- Added `ToolLoopOutcome.forced` for telemetry; `_run_tool_research_chat(...)` records it in `chat_research` audit events.
- Enabled forced final answers only for Chat research through `ChatResearchRunner`; Cowork and default shared-loop callers remain unchanged and still raise on max-iteration exhaustion.
- Preserved grounding behavior: forced final answers still run `before_finalize`, can receive one repair turn, and then pass through the IPC final answer guard.
- Added regression tests for:
  - forced final turns using no tools and still invoking `before_finalize`;
  - default `force_final_answer=False` still raising;
  - ChatResearchRunner forced behavior after research exhaustion;
  - IPC-level guard repair removing an unsupported year from a forced answer.
- Claude CLI review result: no blocking issues. Non-blocking notes were accepted/deferred:
  - `max_iterations == 1` can produce forced output before any tool dispatch; not reachable with current Chat effort config because the lowest budget is 4.
  - If forced repair still fails validation, the loop raises and IPC can use existing fallback behavior; this is intentional because no ungrounded forced answer should escape.
  - IPC's single `repair_used` flag is load-bearing with the final guard; defense-in-depth remains in place.
- Verification:
  - Focused Item 1 tests passed 4/4.
  - Related backend suite passed 67/67.
  - Full backend suite passed 191/191 with `python -m unittest discover -s test -p test_*.py -v`.
  - Full frontend suite passed 10 files / 79 tests with `npm test -- --run`.
  - Frontend build passed with `npm run build`.
- Skills used: `writing-plans`, `test-driven-development`, `verification-before-completion`, and `requesting-code-review`.

## 2026-06-30 - Loop Intelligence Items 3, 5, 6, and 4

- Completed the remaining Loop Intelligence Upgrade items in the planned order after Items 2 and 1:
  - Item 3: duplicate/stuck tool-call detection.
  - Item 5: unproductive web-fetch steering.
  - Item 6: bounded tool-result model context.
  - Item 4: parallel multi-tool dispatch for Chat research.
- Item 3:
  - `run_tool_loop(...)` now tracks normalized `(tool_name, arguments)` keys.
  - Repeated identical calls return a structured `{"status":"skipped"}` tool result instead of re-dispatching.
  - Events, hooks, and tool messages are still emitted in tool-call order.
- Item 5:
  - Added opt-in `unproductive_result_detector` and threshold support to the shared loop.
  - ChatResearchRunner enables this only for `web_fetch` results that are blocked or have no usable evidence/tables.
  - After two consecutive unproductive fetches, the loop injects a short steering message telling the model to try another source or answer with missing-data caveats.
- Item 6:
  - Added `tool_context_budget_chars` to the shared loop.
  - Oldest model-context tool messages are replaced with a compact `status: truncated` placeholder when the budget is exceeded.
  - This only changes the model message context; `WebResearchTools.evidence_corpus()` remains full for answer guarding.
  - ChatResearchRunner enables a 12k character tool-context budget; Cowork/default callers remain unchanged.
- Item 4:
  - Added opt-in `parallel_tools` to `run_tool_loop(...)`.
  - Multi-call turns can dispatch concurrently through a bounded `ThreadPoolExecutor`, while single-call turns stay simple.
  - Result events, hooks, and tool messages are appended in the original call order.
  - ChatResearchRunner enables parallel dispatch; Cowork/default callers remain sequential.
  - WebResearchTools now protects source registry, source lookup, fetch counter, frozen state, and evidence corpus with an `RLock`.
  - WebResearchTools implements `reserve_tool_calls(...)` so parallel `web_fetch` calls reserve source indices in model tool-call order before concurrent network fetches begin.
- Updated the IPC forced-answer guard test because Item 3 now correctly skips repeated same-URL fetches; the test now expects one real fetch plus skipped duplicate tool results.
- Review:
  - Claude CLI review was requested but blocked by the session limit (`resets 10:10pm Asia/Bangkok`).
  - In-session review found no blocking issues.
  - Review focus covered Cowork behavior preservation, opt-in shared-loop parameters, duplicate skip event/hook ordering, Chat-only unproductive steering, context-budget isolation from evidence corpus, parallel dispatch ordering, and WebResearchTools source-index thread safety.
- Verification:
  - Item/related backend suite passed 87/87 with `python -m unittest test.test_tool_loop test.test_chat_research_runner test.test_chat_web_tools test.test_ipc_sidecar test.test_cowork_agent -v`.
  - Full backend suite passed 198/198 with `python -m unittest discover -s test -p test_*.py -v`.
  - Full frontend suite passed 10 files / 79 tests with `npm test -- --run`.
  - Frontend build passed with `npm run build`; Vite reported only the existing chunk-size warning.
- Skills used: `writing-plans`, `test-driven-development`, `verification-before-completion`, and `requesting-code-review` (CLI review attempted; in-session review used because Claude CLI was rate-limited).

## 2026-07-01 - Chat web controls, memory manager, and vision image payloads

- Implemented the three requested Chat capability upgrades without Claude review per the user's instruction.
- Added per-request Chat web settings:
  - `web_mode: auto/off`; `off` skips both model-driven tool research and legacy web search for a pure model answer.
  - `search_provider: auto/brave/scrape`; `scrape` forces the HTML/basic scraping path even when a Brave key exists.
  - `load_api_keys` now reports Search API capabilities and provider availability without exposing secrets.
- Added the composer Tool settings menu:
  - Web Auto/Off selector.
  - Search provider selector with Brave disabled when no key is configured.
  - Memory entry point.
  - Chat web settings persist in frontend session state and are sent with each Chat prompt.
- Added Chat memory CRUD:
  - `ChatMemoryStore` now exposes list/get/update/delete while preserving the existing auto-capture path.
  - Sidecar commands `chat_memory_list`, `chat_memory_update`, and `chat_memory_delete` emit `chat_memory_state`.
  - Frontend Memory Manager panel lists, edits, and deletes Chat memory entries; edits/deletes affect the next Chat prompt injection.
- Added real image payload support:
  - Model catalog entries now include `vision` metadata and helper lookup.
  - Composer reads dropped/selected images as bounded data URLs.
  - Electron and sidecar preserve image data only through the attachment pipeline, do not echo base64 into visible logs, and reject oversized/malformed image payloads.
  - Vision-capable OpenAI-compatible models receive multimodal user content arrays with `image_url` blocks; non-vision models keep the text/metadata fallback.
- Verification:
  - Targeted backend IPC/memory tests passed 51/51 with `python -m unittest test.test_chat_memory test.test_ipc_sidecar -v`.
  - Full backend suite passed 207/207 with `python -m unittest discover -s test -p test_*.py -v`.
  - Full frontend suite passed 12 files / 88 tests with `npm.cmd test`.
  - Frontend build passed with `npm.cmd run build`; Vite reported only the existing chunk-size warning.
  - Electron syntax checks passed with `node --check electron\main.js` and `node --check electron\preload.cjs`.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-30 - Composer context usage indicator

- Added a compact context-usage indicator beside the selected model in the composer.
- The indicator resolves context-window size from selected model provider metadata when present and shows a hover tooltip with percent full plus `used / window` token labels.
- Added `frontend/model/contextUsage.js` to keep token estimation and model metadata resolution separate from UI rendering.
- Token usage is currently an estimate from the active session's visible message timeline, with Thai-aware character counting. The tooltip explicitly labels the number as estimated because provider tokenizer/usage data is not yet wired into the renderer.
- Added `context_window_tokens: 131072` metadata for `zai:glm-4.5-flash` in the provider catalog so the currently used Z.ai Flash model can show a real 128K context window.
- Fixed an existing JSX mojibake parse issue in the Composer web-search checkmark while touching the same file.
- Added tests for:
  - resolving model context metadata;
  - estimating Thai/English message token usage;
  - unknown-context fallback;
  - Composer indicator rendering and tooltip text;
  - CoworkApp passing provider metadata to the Composer indicator;
  - IPC available-model payload preserving the Z.ai context metadata.
- Verification:
  - Targeted context/Composer/CoworkApp frontend tests passed 29/29.
  - Targeted IPC catalog backend test passed 1/1.
  - Full frontend suite passed 11 files / 84 tests with `npm.cmd test`.
  - Full backend suite passed 198/198 with `python -m unittest discover -s test -p test_*.py -v`.
  - Frontend build passed with `npm.cmd run build`; Vite reported only the existing chunk-size warning.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-30 - DeepSeek provider catalog and runtime

- Added DeepSeek as a first-class provider in the model catalog.
- Added catalog entries:
  - `deepseek:deepseek-v4-flash` with `Fast / Coding`, low-cost billing metadata, strengths, and 1M context metadata.
  - `deepseek:deepseek-v4-pro` with `Top / Reasoning`, low-cost billing metadata, strengths, and 1M context metadata.
  - `deepseek:deepseek-chat` and `deepseek:deepseek-reasoner` as `Legacy` aliases so users can still find familiar names without treating them as the preferred path.
- Added DeepSeek runtime routing in `ipc_sidecar.py` using the OpenAI-compatible base URL `https://api.deepseek.com`.
- Added DeepSeek to Chat tool-research capable providers.
- Updated model-prefix normalization in backend and frontend so `deepseek:*` is not accidentally converted to `local:deepseek:*`.
- Updated the model menu to display `model.badge` before falling back to `tier` or `billing`; the old `tier` field remains for compatibility.
- Updated provider key parsing so `key.txt` can contain a key followed by provider hints/URLs, for example a DeepSeek key line with `https://api.deepseek.com/ deepseek`. The sidecar uses only the first token as the secret and does not emit the key value.
- Verified the real local `key.txt` without printing secrets: OpenAI, DeepSeek, Z.ai, and Gemini were all detected in the expected provider slots.
- Verification:
  - Targeted DeepSeek backend tests passed 6/6 before the parser refinement.
  - Targeted DeepSeek key-parser tests passed 2/2 after matching the real `key.txt` shape.
  - Full backend suite passed 200/200 with `python -m unittest discover -s test -p test_*.py -v`.
  - Full frontend suite passed 11 files / 84 tests with `npm.cmd test`.
  - Frontend build passed with `npm.cmd run build`; Vite reported only the existing chunk-size warning.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-06-30 - Nested model menu and free Z.ai default metadata

- Reworked the composer model picker from a long flat provider/model list into a compact nested menu:
  - `Recommended` shows curated default/useful models first.
  - `Providers` shows provider headings with readiness status.
  - Clicking a provider opens that provider's full model submenu.
- Kept the existing `tier` field for compatibility while adding richer Z.ai metadata for UI/routing:
  - `zai:glm-4.5-flash` is marked `recommended`, `default_model`, `Free / Reasoning`, `free-smoke-tested`, and keeps its 128K context metadata.
  - `zai:glm-4.7-flash` keeps its free catalog entry but is labeled `Free / Limited` with `free-rate-limited` availability metadata after the live smoke check hit HTTP 429.
  - Z.ai 4.7 paid variants now include skill badges and context metadata for future Cowork/Code routing.
- Live smoke check:
  - `zai:glm-4.5-flash` returned `OK`.
  - `zai:glm-4.7-flash` returned provider rate limit HTTP 429 on retry.
- Added `frontend/tests/ModelMenu.test.jsx` to lock the recommended/provider submenu behavior and updated the CoworkApp catalog test for the nested model menu.
- Verification:
  - New ModelMenu test passed 2/2 after the red-green cycle.
  - Full frontend suite passed 12 files / 86 tests with `npm.cmd test`.
  - Full backend suite passed 200/200 with `python -m unittest discover -s test -p test_*.py -v`.
  - Frontend build passed with `npm.cmd run build`; Vite reported only the existing chunk-size warning.
- Skills used: `writing-plans`, `test-driven-development`, and `verification-before-completion`.

## 2026-06-30 - Provider model capability metadata parity

- Fixed the model catalog parity issue found from the live UI:
  - OpenAI no longer only lists the newest GPT-5.x entries; useful older/legacy coding-capable entries are back in the catalog: `gpt-4.1`, `gpt-4.1-mini`, `gpt-4o`, and `gpt-4o-mini`.
  - OpenAI entries now include skill badges, strengths, and context-window metadata for the model menu/context indicator.
  - Gemini entries now use capability badges such as `Top / Fast`, `Top / Reasoning`, `Fast / Multimodal`, `Free / Balanced`, and `Free / Fast` instead of raw `main/free/fast` labels.
  - Z.ai GLM-5.2, GLM-5.1, GLM-5-Turbo, and GLM-5 now include skill badges, strengths, and context metadata so they match the richer DeepSeek and GLM-4.x entries.
- Kept the existing `tier` and `billing` fields for compatibility with tests/UI fallbacks while making `badge` the primary human-facing label in the model picker.
- Updated the IPC catalog regression test to assert the presence of OpenAI legacy models plus metadata for OpenAI, Gemini, and Z.ai GLM-5 models.
- Verification:
  - Targeted IPC catalog test passed 1/1 with `python -m unittest test.test_ipc_sidecar.IpcSidecarTests.test_fetch_available_models_emits_models_payload -v`.
  - Full frontend suite passed 12 files / 86 tests with `npm.cmd test`.
  - Full backend suite passed 200/200 with `python -m unittest discover -s test -p test_*.py -v`.
  - Frontend build passed with `npm.cmd run build`; Vite reported only the existing chunk-size warning.
- Skills used: `openai-docs`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-01 - Chat capability roadmap foundations

- Implemented the next Chat capability roadmap pass as safe-by-default foundations instead of enabling risky powers by default.
- Added `chat_tool_provider.py` with `CompositeToolProvider` so Chat research can merge web, artifact, MCP, and code-execution tools through the existing shared tool-loop contract.
- Added `chat_mcp_client.py` with an optional MCP connector registry, SDK availability detection, namespaced MCP tool schemas, read-only annotation handling, and side-effect approval callback support. Real MCP SDK server connection lifecycle remains pending until connectors/dependencies are configured.
- Added `chat_code_exec.py` with an approval-gated Python execution provider, disabled by default. It runs in a temp directory with timeout, minimal environment, output caps, simple no-network import blocking, and artifact collection.
- Added `chat_artifacts.py` with persisted artifact versioning plus HTML/code detection. The React Artifacts view renders HTML in a sandboxed iframe and text/code in a copyable preview.
- Added `model_router.py` for auto model routing by vision attachment, code-heavy prompt, long-context need, and recommended/default metadata. Explicit user model choices still always win.
- Updated Chat runtime/sidecar wiring so artifacts can be enabled by default, while Python execution and MCP remain disabled unless backend flags and UI toggles permit them.
- Added bridge/preload/Electron/frontend plumbing for artifact state, connector state, tool toggles, Artifacts navigation, and the `Auto` model option.
- Upgraded Chat memory recall so query-relevant memories are preferred while a small recent-preference fallback keeps broad style preferences from disappearing on unrelated topics.
- Added table-stakes Chat affordances:
  - Stop sends a session-scoped cancel command to the sidecar, drops the busy UI state, and suppresses late model answers when a blocked request returns after cancellation.
  - Regenerate removes/replaces the last assistant answer and resends the last user prompt with trimmed history instead of duplicating the user message.
  - Edit & resend truncates later Chat events, prompts for edited text, sends the edited prompt, and passes a history override so the sidecar/model does not keep stale truncated context.
  - Existing per-mode session/thread persistence remains the thread foundation.
- Added and updated tests for composite tools, MCP provider behavior, code execution, artifacts, model routing, Chat memory recall, IPC payloads, and frontend prompt settings.
- Verification:
  - Full backend suite passed 227/227 with `python -m unittest discover -s test -p test_*.py`.
  - Full frontend suite passed 12 files / 91 tests with `npm test`.
  - Frontend build passed with `npm run build`; Vite reported only the existing chunk-size warning.
  - Electron syntax checks passed with `node --check electron\main.js` and `node --check electron\preload.cjs`.
- Skills used: `writing-plans`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-01 - Chat tool safety gates and live connector status

- Implemented the follow-up safety pass requested after the roadmap review:
  - Relabeled legacy Chat Python execution honestly as `subprocess_tempdir_experimental` with `best_effort_static_check` network filtering instead of implying production-grade no-network isolation.
  - Added `approval_policy.py` for Approval-flow v2 payloads with risk level, risk summary, subject, details, full payload, fail-closed default decision, and backward-compatible legacy top-level fields.
  - Added `chat_pyodide_sandbox.py` as the Pyodide/WASM sandbox boundary. Chat code execution now defaults to `pyodide` when enabled, reporting unavailable until a runtime is installed; legacy subprocess requires explicit `COWORK_CHAT_CODE_EXEC_SANDBOX=legacy_subprocess`.
  - Extended `chat_mcp_client.py` with connector client creation hooks and per-connector status reporting so enabled connectors show `connected`, `disabled`, `unavailable`, or `error` instead of silently producing an empty provider.
  - Wired sidecar connector state to include MCP statuses and updated the Composer tool menu to show live connector status lines.
- Preserved safety defaults:
  - Chat Python execution remains off unless both backend config and UI tool toggle permit it.
  - MCP remains off unless backend config and UI tool toggle permit it.
  - Side-effecting MCP tools still require approval.
  - Cowork workspace behavior and approval gates are unchanged.
- Verification:
  - Targeted backend safety/MCP tests passed 22/22.
  - Full backend suite passed 240/240 with `python -m unittest discover -s test -p test_*.py -v`.
  - Full frontend suite passed 13 files / 93 tests with `npm test`.
  - Frontend build passed with `npm run build`; Vite reported only the existing chunk-size warning.
  - Electron syntax checks passed with `node --check electron\main.js` and `node --check electron\preload.cjs`.
- Skills used: `writing-plans`, `test-driven-development`, `systematic-debugging`, and `verification-before-completion`.

## 2026-07-01 - Pyodide runtime bridge for Chat code execution

- Continued the Chat safety stack by turning the Pyodide/WASM code-execution boundary from an unavailable contract into a working local runtime bridge when the npm `pyodide` package is installed.
- Added `tools/pyodide_runner.mjs`, a small Node ESM runner that loads Pyodide, executes one Python payload from JSON stdin, captures stdout/stderr, and emits a structured JSON result.
- Extended `chat_pyodide_sandbox.py` with:
  - `NodePyodideRuntime` for invoking the runner with timeout/output limits.
  - `discover_pyodide_runtime(...)` so Pyodide is lazy and optional.
  - App-root based discovery so the sidecar can find `node_modules/pyodide` without hard-coded install paths.
  - Safe `unavailable`, `timeout`, and `error` result shapes.
- Installed npm dependency `pyodide` and updated package metadata so `tools/pyodide_runner.mjs` and `node_modules/pyodide/**` are included for sidecar packaging.
- Updated `ipc_sidecar.py` so the default Chat code sandbox passes the app root into `PyodideSandbox`.
- Added tests for fake runner invocation, timeout handling, runtime discovery, and a real Pyodide smoke test (`print(40 + 2)` -> `42`) when the npm package is installed.
- Verification:
  - Pyodide targeted tests passed 6/6.
  - Full backend suite passed 244/244 with `python -m unittest discover -s test -p test_*.py -v`.
  - Full frontend suite passed 13 files / 93 tests with `npm test`.
  - Frontend build passed with `npm run build`; Vite reported only the existing chunk-size warning.
  - Electron and runner syntax checks passed with `node --check electron\main.js`, `node --check electron\preload.cjs`, and `node --check tools\pyodide_runner.mjs`.
- Skills used: `writing-plans`, `test-driven-development`, `systematic-debugging`, and `verification-before-completion`.

## 2026-07-01 - Chat code execution MCP guard

- Added the requested safety condition for Chat code execution:
  - Chat still prefers Pyodide/WASM sandbox execution.
  - If `COWORK_CHAT_CODE_EXEC_SANDBOX=legacy_subprocess` is configured but there is no connected MCP client, the sidecar refuses to choose legacy subprocess and falls back to Pyodide/WASM.
  - Legacy subprocess is now gated by three conditions: explicit legacy sandbox config, at least one connected MCP client, and the existing approval prompt.
- Recorded the product direction that Chat should become a conversational connector surface: users can explicitly ask to test/use a named MCP connection such as Roblox MCP; if no matching connector is found the app should say so, and always-on discovery should be plugin-backed and visible rather than silent broad scanning.
- Added regression tests:
  - `test_legacy_subprocess_is_blocked_without_connected_mcp`
  - `test_legacy_subprocess_requires_connected_mcp`
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-07-01 - Chat MCP diagnostics and bounded connector creation

- Added the MCP diagnostics foundation before live SDK wiring:
  - `create_mcp_clients(...)` now accepts a bounded `connection_timeout_seconds` and reports timed-out connectors as structured `timeout` statuses instead of letting Chat wait indefinitely.
  - Added read-only `McpDiagnosticsToolProvider` with `mcp_diagnose_connector`, allowing Chat to answer explicit requests such as checking a Roblox MCP connector by using configured connector/status data.
  - Wired Chat tool research to include the diagnostics provider by default while keeping side-effecting MCP tools behind the existing backend/UI enablement gates and approval flow.
  - Missing connectors are reported honestly so Chat does not pretend to connect to unavailable integrations.
- Preserved boundaries:
  - No broad silent port scanning was added.
  - MCP write/live tool execution remains opt-in and approval-gated.
  - Real SDK-backed `_create_sdk_client` remains unavailable until concrete transports are installed and native connection timeouts are wired.
- Verification:
  - Targeted MCP diagnostics tests passed 8/8 with `python -m unittest test.test_chat_mcp_client -v`.
  - Targeted sidecar diagnostics tests passed 2/2 with `python -m unittest test.test_ipc_sidecar.IpcSidecarTests.test_chat_mode_uses_plain_chat_runtime_without_workspace_tools test.test_ipc_sidecar.IpcSidecarTests.test_chat_tool_research_can_diagnose_missing_mcp_connector -v`.
  - Full backend suite passed 250/250 with `python -m unittest discover -s test -p test_*.py -v`.
- Skills used: `test-driven-development`, `systematic-debugging`, and `verification-before-completion`.

## 2026-07-01 - MCP connector configuration visibility

- Continued the MCP diagnostics path by making configured connectors visible and manageable from the Chat composer tool settings menu.
- Added a connector panel that shows each configured MCP connector as its own row with name, transport/command, current status, and error text when present.
- Added UI actions to refresh connector status, enable/disable a configured connector through the existing `chat_connector_save` bridge path, and add a disabled Roblox MCP starter preset (`roblox` / `stdio` / `roblox-mcp`) without silently enabling it.
- Wired `CoworkApp` to pass connector refresh/save callbacks into the Composer so UI actions reach the Electron/Python bridge instead of remaining local-only.
- Preserved the safety boundary: this only changes configuration visibility and save wiring. Live SDK-backed execution is still not enabled, MCP side-effecting tools remain opt-in and approval-gated, and no silent broad port scanning was added.
- Added regression coverage for Composer connector inspection/actions.
- Verification:
  - Composer targeted test passed 10/10 with `npm test -- Composer.test.jsx`.
  - Full backend suite passed 250/250 with `python -m unittest discover -s test -p test_*.py -v`.
  - Full frontend suite passed 13 files / 94 tests with `npm test`.
  - Frontend build passed with `npm run build`; Vite reported only the existing chunk-size warning.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-07-01 - MCP connector editor, test, and Roblox discovery

- Completed the next MCP connector usability pass for Chat without enabling broad scanning or changing Cowork behavior.
- Backend:
  - Added connector validation in `chat_mcp_client.py`.
  - Added a bounded live stdio SDK client wrapper for environments where the `mcp` package is installed.
  - Added sidecar commands/events for `chat_connector_test` and `chat_connector_discover`.
  - Roblox discovery now reports configured status when present or returns a disabled `roblox` preset with a clear message when not configured.
- Frontend:
  - Added inline connector detail editing in the Composer tool settings panel.
  - Added save/delete fields for name, transport, command, URL, and enabled state.
  - Added per-connector test actions and a dedicated `Test Roblox MCP` diagnostic action.
  - Wired Electron preload/main, `eel.js`, `coworkBridge`, and `CoworkApp` for connector test/discovery events.
- Current limitation:
  - The local environment still does not have the Python `mcp` SDK installed, so live stdio connection attempts report SDK unavailable until the dependency and a real server command are installed/configured.
  - HTTP/SSE transports and MCP tool browsing remain future work.
- Verification:
  - Targeted backend MCP/sidecar tests passed 12/12 with `python -m unittest test.test_ipc_sidecar.IpcSidecarTests.test_chat_connector_test_validates_and_reports_status_without_saving test.test_ipc_sidecar.IpcSidecarTests.test_chat_connector_discover_returns_disabled_roblox_preset test.test_chat_mcp_client -v`.
  - Full backend suite passed 254/254 with `python -m unittest discover -s test -p test_*.py -v`.
  - Targeted frontend connector tests passed with `npm test -- Composer.test.jsx coworkBridge.test.js`.
  - Full frontend suite passed 13 files / 94 tests with `npm test`.
  - Frontend build passed with `npm run build`; Vite reported only the existing chunk-size warning.
  - Electron syntax checks passed with `node --check electron\main.js` and `node --check electron\preload.cjs`.
- Skills used: `test-driven-development`, `systematic-debugging`, and `verification-before-completion`.

## 2026-07-01 - Chat intelligence foundation pass

- Continued the Chat-first roadmap across the requested areas without enabling new workspace write or shell powers for Chat.
- Added a clearer Chat identity/runtime profile in `CHAT_SYSTEM_PROMPT`:
  - Chat identifies itself as Chat mode.
  - Chat must not read workspace files, mutate local files, or run shell commands by default.
  - Project evidence should come from explicit attachments/context or a Cowork handoff.
- Added `chat_research_strategy.py`:
  - Cleans Thai request-style research queries.
  - Preserves the user's answer language.
  - Adds English/international query variants for Thai current-fact research such as fuel-price questions.
  - Adds source-preference metadata for official docs/current fact research.
  - `chat_web_connector.py` now uses this strategy for query variants.
- Improved `model_router.py` auto routing:
  - Research/current-fact prompts can prefer research/long-context models.
  - Translation and writing prompts can prefer translation/writing models.
  - Explicit user model choices still win.
- Improved Chat memory typing:
  - Auto-captured memories now distinguish `writing_style`, `identity`, and `long_term_goal` where possible.
  - Existing memory storage format remains compatible.
- Added read-only MCP tool browsing:
  - `McpDiagnosticsToolProvider` now exposes `mcp_list_tools`.
  - The browser returns connector tool names, descriptions, schemas, and read-only hints without calling tools.
- Added `chat_quality_eval.py`, a first quality-evaluation fixture set covering general chat, web research, Thai answers, explicit attachments, coding, memory, and MCP diagnostics.
- Verification:
  - Targeted backend tests passed 29/29 with `python -m unittest test.test_chat_runtime test.test_chat_research_strategy test.test_model_router test.test_chat_memory test.test_chat_mcp_client test.test_chat_quality_eval -v`.
  - Full backend suite passed 262/262 with `python -m unittest discover -s test -p test_*.py -v`.
- Skills used: `writing-plans`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-01 - Chat visible context and eval controls

- Continued the Chat-first capability pass with user-visible context controls and a local quality-eval bridge.
- Memory Manager:
  - Added readable badges for typed memories such as `Writing style`, `Identity`, `Preference`, and `Long-term goal`.
  - Preserved existing edit/delete behavior and storage format.
- Artifacts:
  - Added `Attach to Chat` from the Artifacts panel.
  - The action sends the selected artifact's latest version through the existing explicit Chat attachment pipeline with `source: artifact`, bounded content, artifact id, and version metadata.
  - `CoworkApp` switches back to Chat, seeds a short prompt, focuses the composer, and shows the artifact attachment chip before submission.
- Quality eval:
  - Exposed `chat_quality_eval.py` fixture cases through `chat_quality_eval_list` / `chat_quality_eval_state`.
  - Wired Electron preload/main, `eel.js`, and `coworkBridge` so future UI panels or smoke runners can list the fixture categories without reworking IPC.
- Safety/boundaries:
  - No new workspace read/write power was added to Chat.
  - Artifact attach remains explicit user-selected context, not automatic project inspection.
  - Quality eval listing is read-only fixture metadata.
- Verification:
  - Targeted frontend tests passed 31/31 with `npm test -- --run frontend/tests/MemoryManager.test.jsx frontend/tests/ArtifactsPanel.test.jsx frontend/tests/Composer.test.jsx frontend/tests/coworkBridge.test.js`.
  - Targeted backend sidecar test passed with `python -m unittest test.test_ipc_sidecar.IpcSidecarTests.test_chat_quality_eval_ipc_lists_fixture_cases -v`.
  - Electron syntax checks passed with `node --check electron\main.js` and `node --check electron\preload.cjs`.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-07-01 - Chat polish Phase A

- Started the next detailed Chat completion phase from `docs/chat-completion-phase-plan.md`.
- Memory:
  - Added `ChatMemoryStore.remember_manual(...)` for explicit user-created memories.
  - Added `chat_memory_create` sidecar command and Electron/renderer bridge wiring.
  - Memory Manager now includes a typed "Remember" form while preserving edit/delete and secret-like content rejection.
- Chat presentation:
  - Added a `Copy answer` control to assistant Chat messages. It copies only the visible assistant answer text, not hidden tool output or internal events.
  - Added local sidebar history search for sessions, filtering visible recents without mutating persisted session records.
- Quality evaluation:
  - Added `evaluate_case_result(...)` to score fixture answers by category using source presence, Thai-language checks, attachment/MCP signals, and latency target metadata.
- Verification so far:
  - Targeted backend tests passed 10/10 with `python -m unittest test.test_chat_memory test.test_chat_quality_eval test.test_ipc_sidecar.IpcSidecarTests.test_chat_memory_ipc_create_adds_typed_memory -v`.
  - Targeted frontend tests passed 31/31 with `npm test -- --run frontend/tests/MemoryManager.test.jsx frontend/tests/Timeline.test.jsx frontend/tests/SessionRail.test.jsx frontend/tests/coworkBridge.test.js`.
- Skills used: `writing-plans`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-01 - Chat research source strategy cleanup

- Continued Phase B from `docs/chat-completion-phase-plan.md`.
- Rewrote `chat_research_strategy.py` to remove corrupted Thai mojibake constants and use clean Thai/English query cleaning and category matching.
- Added source-aware research variants and preferences for:
  - official API/model documentation,
  - pricing/billing/quota/status pages,
  - GitHub repositories/readmes/releases/issues,
  - news/current-event sources,
  - Thai fuel/current-fact queries with English/international variants.
- Preserved Thai answer-language detection and fuel-price source hint behavior.
- Verification:
  - Research strategy tests passed 5/5 with `python -m unittest test.test_chat_research_strategy -v`.
  - Targeted connector regression tests passed 2/2 with `python -m unittest test.test_chat_web_connector.ChatWebConnectorTests.test_search_adds_fuel_source_hints_from_generic_registry test.test_chat_web_connector.ChatWebConnectorTests.test_search_uses_generic_query_terms_for_non_oil_topic -v`.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-07-01 - Chat completion follow-up controls

- Continued the Chat-first completion pass without Claude review, per user instruction to collect review at the end.
- Web research:
  - `ipc_sidecar.py` now includes `chat_research_strategy.build_research_plan(...)` source preferences in the legacy Chat Web Context prompt.
  - The model sees source strategy guidance for official docs, pricing/status/quota, GitHub/repository, news/current events, and Thai/current-fact queries, while still treating extracted evidence as the only source for exact values.
- Attachments:
  - `frontend/components/Composer.jsx` now supports pre-send attachment preview.
  - Text/snippet attachments show a bounded readable preview; image attachments show the attached data-url image when available.
  - Sending or removing an attachment clears the preview so attachment content does not persist into the visible timeline.
- Artifacts:
  - `frontend/components/ArtifactsPanel.jsx` now adds a `Download` action for the selected latest artifact version.
  - Filenames are sanitized and type-based extensions are used for HTML, Markdown, JavaScript, Python, or text artifacts.
- MCP:
  - `chat_mcp_client.py` now has lazy SDK paths for streamable HTTP and SSE transports in addition to stdio.
  - HTTP/SSE still require the optional MCP SDK transport modules and fail closed when they are unavailable.
- Quality evaluation:
  - `chat_quality_eval.py` was rewritten with clean UTF-8 Thai fixture data.
  - Added `run_quality_eval_snapshot(...)` for deterministic fixture scoring of supplied answers without live model calls.
  - Added `chat_quality_eval_run` IPC/Electron/renderer bridge wiring, returning snapshot results through `chat_quality_eval_state`.
- Targeted verification:
  - Backend targeted tests passed 18/18 with `python -m unittest test.test_chat_mcp_client test.test_chat_quality_eval test.test_ipc_sidecar.IpcSidecarTests.test_chat_web_context_includes_source_strategy_for_query_type test.test_ipc_sidecar.IpcSidecarTests.test_chat_quality_eval_ipc_runs_snapshot_scores -v`.
  - Frontend targeted tests passed 31/31 with `npm test -- --run frontend/tests/Composer.test.jsx frontend/tests/coworkBridge.test.js frontend/tests/ArtifactsPanel.test.jsx`.
  - Electron syntax checks passed with `node --check electron\main.js` and `node --check electron\preload.cjs`.
- Full verification:
  - Backend suite passed 274/274 with `python -m unittest discover -s test -p test_*.py -v`.
  - Frontend suite passed 104/104 with `npm test`.
  - Frontend production build passed with `npm run build`; existing Vite chunk-size warning remains non-blocking.
  - Electron syntax checks passed again with `node --check electron\main.js` and `node --check electron\preload.cjs`.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-07-01 - Live quality runner and review fixes

- Implemented `LIVE_QUALITY_RUNNER_AND_FIXES.md` A -> B -> C in one pass without Claude review, per user instruction to review once at the end.
- A: De-hardcoded Chat research strategy:
  - Replaced `chat_research_strategy.py` topic-specific control flow with `_QUERY_TYPE_PROFILES`, a data-driven query-type registry.
  - Removed fuel/oil-specific query expansion and industry source hints from query-planning code.
  - Kept generic source strategy for official documentation, pricing/status/quota, GitHub/repository, and news/current-event question types.
  - Added test coverage proving custom query-type profiles work through data injection and fuel queries no longer get the old `Thailand latest fuel prices...` expansion.
- B: Added grounding/hallucination scoring to quality eval:
  - `evaluate_case_result(...)` now accepts `evidence`.
  - It reuses `chat_answer_guard.validate_answer(...)` with normalized source indices and prompt/today allow values.
  - Hallucinated dates/prices/citations fail the eval only when evidence exists; blank evidence remains a no-op for general answers.
  - `run_quality_eval_snapshot(...)` now threads supplied `evidence` into the scorer.
- C: Added live quality runner:
  - New `chat_quality_runner.py` provides `run_quality_eval_live(...)`, `run_chat_once(...)`, `save_quality_report(...)`, and a `python -m chat_quality_runner` CLI.
  - The runner produces cells for each model x category, aggregates pass rate, average latency, hallucination rate, and source usage by model and category, and continues when one model/case fails.
  - The CLI requires `--live`, preventing accidental live model/API calls from default tests.
  - `_run_plain_chat(..., return_diagnostics=True)` can now expose `evidence_corpus`, route, tool-research usage, and source count for the live runner while preserving existing 3-value callers.
- Targeted verification:
  - `python -m unittest test.test_chat_research_strategy test.test_chat_quality_eval test.test_chat_quality_runner -v` passed 18/18.
  - `python -m unittest test.test_ipc_sidecar.IpcSidecarTests.test_plain_chat_can_return_quality_runner_diagnostics test.test_ipc_sidecar.IpcSidecarTests.test_chat_quality_eval_ipc_runs_snapshot_scores test.test_ipc_sidecar.IpcSidecarTests.test_chat_web_context_includes_source_strategy_for_query_type -v` passed 3/3.
  - `python -m chat_quality_runner --help` passed and `python -m chat_quality_runner --models fake-model` failed closed with the expected `--live is required` error.
- Full verification:
  - Backend suite passed 284/284 with `python -m unittest discover -s test -p test_*.py -v`.
  - Frontend suite passed 104/104 with `npm test`.
  - Frontend production build passed with `npm run build`; the existing Vite chunk-size warning remains non-blocking.
  - Electron syntax checks passed with `node --check electron\main.js` and `node --check electron\preload.cjs`.
- Skills used: `writing-plans`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-01 - First live quality scorecard

- Ran the first opt-in live Chat quality scorecard after the A/B/C review passed.
- Command:
  - `python -m chat_quality_runner --live --models zai:glm-4.5-flash,zai:glm-4.7-flash --categories web,thai,general --effort Medium`
- Reports:
  - JSON: `work_logs/chat-quality-live-20260701-205947.json`
  - Markdown: `work_logs/chat-quality-live-20260701-205947.md`
- Summary:
  - Total cells: 6
  - Passed cells: 4
  - Failed cells: 2
  - Pass rate: 0.6667
  - Average latency: 7288 ms
  - Hallucination rate: 0.0
  - Source usage rate: 0.3333
- Model findings:
  - `zai:glm-4.5-flash`: 3/3 passed, average latency 13787 ms, source usage 0.6667, hallucination 0.0.
  - `zai:glm-4.7-flash`: 1/3 passed; `web` and `thai` failed due provider HTTP 429 / service overloaded, not answer quality. Average latency 790 ms over recorded cells.
- Quality findings exposed by the run:
  - The runner works and captures provider failures as cells without aborting.
  - Current scoring is still too permissive for qualitative issues: a vague Thai response asking for a topic can pass because it is Thai and non-empty, and a general answer that says it lacks sources can still pass due length.
  - The web answer used sources and passed grounding, but source quality/reliability needs an explicit metric because grounded-but-low-quality evidence can still produce a questionable answer.
- Next recommended fixes:
  - Add category-specific minimum-answer checks for directness and "asks for more info instead of answering" when the prompt is answerable.
  - Add source-quality metrics using existing source_type / quality_score metadata.
  - Add retry/backoff or delay support for provider 429 cells before comparing model quality.
- Skills used: `verification-before-completion`.

## 2026-07-01 - Quality runner v2 live smoke and directness calibration

- Ran a live v2 scorecard with retry enabled:
  - `python -m chat_quality_runner --live --models zai:glm-4.5-flash,zai:glm-4.7-flash --categories general,thai,web --effort Medium --retry-attempts 1 --retry-backoff-seconds 5`
- Reports:
  - JSON: `work_logs/chat-quality-live-20260701-211524.json`
  - Markdown: `work_logs/chat-quality-live-20260701-211524.md`
- Live summary:
  - Total cells: 6
  - Passed cells: 2
  - Failed cells: 4
  - Pass rate: 0.3333
  - Average latency: 28479 ms
  - Hallucination rate: 0.0
  - Source usage rate: 0.3333
  - Directness rate: 0.5
  - Source quality rate: 0.3333
- Findings:
  - `zai:glm-4.5-flash` passed `general` and `thai`, failed `web` due explicit low source quality and latency.
  - `zai:glm-4.7-flash` failed all three cells after 2 attempts each because the provider returned HTTP 429 overload errors.
  - The live `general` answer exposed a directness false positive: it said it could not find specific current information and could not provide a practical explanation, but the original marker list was too narrow.
- Follow-up fix:
  - Added a regression test for the live-discovered `unable to find specific current information` / `cannot provide a practical` non-answer pattern.
  - Expanded the directness detector to flag that pattern.
- Final verification after the live-discovered fix:
  - Targeted backend tests passed 19/19 with `python -m unittest test.test_chat_quality_eval test.test_chat_quality_runner -v`.
  - Python compile check passed with `python -m py_compile chat_quality_eval.py chat_quality_runner.py`.
  - Full backend suite passed 291/291 with `python -m unittest discover -s test -p test_*.py -v`.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-07-01 - Session-scoped Chat role memory UI

- Added a first `Add role` path to the Chat Memory Manager so the user can pin a role/instruction set to an individual Chat thread.
- Backend:
  - `ChatMemoryStore.remember_manual(...)` now accepts kind `role`.
  - `format_for_prompt(..., source_session_id=...)` injects a dedicated `Chat Role Memory` block before ordinary `Chat Personal Memory`.
  - Role memories are scoped by `source.session_id`; roles from other Chat sessions are not injected.
  - Ordinary relevance recall excludes role entries so role instructions are not treated as searchable facts.
  - `ipc_sidecar.py` now passes the active Chat `client_session_id` into memory prompt formatting.
- Frontend:
  - `MemoryManager` now lists `Role` in the kind selector.
  - Choosing `Role` changes the create button from `Remember` to `Add role`.
  - Role entries are filtered by `activeSessionId` in the Memory Manager UI, while non-role memories remain visible as general Chat memory.
  - `CoworkApp` passes the active session ID into `MemoryManager`.
- Verification:
  - TDD red checks first failed as expected because `role`, `source_session_id`, and `Add role` did not exist yet.
  - Targeted backend tests passed 8/8 with `python -m unittest test.test_chat_memory test.test_ipc_sidecar.IpcSidecarTests.test_chat_mode_injects_session_role_memory -v`.
  - Targeted frontend test passed 5/5 with `npm test -- --run frontend/tests/MemoryManager.test.jsx`.
  - Python compile check passed with `python -m py_compile chat_memory.py ipc_sidecar.py`.
  - Full backend suite passed 293/293 with `python -m unittest discover -s test -p test_*.py -v`.
  - Frontend suite passed 106/106 with `npm test`.
  - Frontend production build passed with `npm run build`; the existing Vite chunk-size warning remains non-blocking.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-07-01 - Chat Role Contract layer refinement

- Refined the session-scoped Chat role feature into an explicit Role Contract layer following the Owner/CEO model:
  - Owner/Mode boundaries still control Chat/Cowork/Code permissions.
  - Role Contract acts as the active CEO-style instruction layer for one Chat session's tone, workflow, task focus, and output shape.
- Backend:
  - `remember_manual(..., kind="role")` now stores role entries with `authority=role_contract`, `scope=chat_session`, `mode=Chat`, and `enabled=true` metadata.
  - `format_for_prompt(..., source_session_id=...)` now emits `## Active Chat Role Contract` before ordinary `Chat Personal Memory`.
  - The role contract prompt explicitly says it applies inside Owner/Mode boundaries and cannot change Chat/Cowork/Code permissions.
  - Role entries stay out of ordinary memory relevance recall so they are not treated as searchable facts.
- Frontend:
  - Role cards now show `Active role` and `This chat` badges in Memory Manager.
  - Role cards remain filtered by active Chat session while non-role memories remain general Chat memories.
- Verification:
  - TDD red checks first failed as expected because contract metadata and `Active role` UI badges did not exist yet.
  - Targeted backend tests passed 9/9 with `python -m unittest test.test_chat_memory test.test_ipc_sidecar.IpcSidecarTests.test_chat_mode_injects_session_role_memory test.test_ipc_sidecar.IpcSidecarTests.test_chat_mode_persists_and_injects_personal_memory -v`.
  - Targeted frontend test passed 5/5 with `npm test -- --run frontend/tests/MemoryManager.test.jsx`.
  - Python compile check passed with `python -m py_compile chat_memory.py ipc_sidecar.py`.
  - Full backend suite passed 293/293 with `python -m unittest discover -s test -p test_*.py -v`.
  - Frontend suite passed 106/106 with `npm test`.
  - Frontend production build passed with `npm run build`; the existing Vite chunk-size warning remains non-blocking.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-07-01 - Chat persona role semantics correction

- Corrected the session-scoped Chat role semantics after user clarification:
  - Role is now a Chat persona/style layer only, not a CEO/workflow/agent-authority layer.
  - It may guide style, tone, formatting, vocabulary, and response shape for that Chat session.
  - It does not grant tools, file access, code editing, command execution, or any Cowork/Code capability.
- Backend:
  - New role memories now store `authority=chat_persona`, `scope=chat_session`, `mode=Chat`, and `enabled=true`.
  - Chat prompt injection now uses `## Active Chat Persona Role`.
  - Role prompt text explicitly frames the role as the persona/style layer for Chat only.
- Frontend:
  - Memory Manager role badge changed from `Active role` to `Persona role`.
- Verification:
  - TDD red checks first failed as expected because the old backend still stored `role_contract`, injected `Active Chat Role Contract`, and the UI still rendered `Active role`.
  - Targeted backend role tests passed 2/2 with `python -m unittest test.test_chat_memory.ChatMemoryStoreTests.test_manual_role_memory_is_session_scoped_persona_and_always_prompted test.test_ipc_sidecar.IpcSidecarTests.test_chat_mode_injects_session_role_memory -v`.
  - Targeted frontend memory tests passed 5/5 with `npm test -- --run frontend/tests/MemoryManager.test.jsx`.
  - Python compile check passed with `python -m py_compile chat_memory.py ipc_sidecar.py`.
  - Full backend suite passed 293/293 with `python -m unittest discover -s test -p test_*.py -v`.
  - Frontend suite passed 106/106 with `npm test`.
  - Frontend production build passed with `npm run build`; the existing Vite chunk-size warning remains non-blocking.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-07-01 - Mode-scoped persona roles for Chat, Cowork, and Code

- Extended `Add role` from Chat-only persona roles into mode-scoped persona roles for all three modes:
  - Chat role remains a persona/style layer for conversational responses.
  - Cowork role is a working-style layer for Cowork sessions.
  - Code role is a coding/review-style layer for Code sessions.
  - Roles still do not grant tools, file access, code editing, command execution, or approval bypasses.
- This entry supersedes the earlier Role Contract/CEO wording in the append-only log. The current architecture is persona/style guidance, not an agent-authority layer.
- Backend:
  - `remember_manual(..., kind="role", mode=...)` stores role entries with mode-specific authority: `chat_persona`, `cowork_persona`, or `code_persona`.
  - `format_for_prompt(..., mode=...)` filters role entries by both active session and active mode.
  - Role entries with the same text can coexist across different modes because role IDs include the mode.
  - Chat prompt injection keeps ordinary personal memory; Cowork/Code prompt injection uses role-only blocks to avoid leaking Chat personal memory into workspace/coding modes.
  - `ipc_sidecar.py` passes role `mode` through `chat_memory_create` and prefixes non-Chat agent prompts with the active mode role block when present.
- Frontend/Electron:
  - `MemoryManager` accepts `activeMode`, filters role cards by session and mode, shows the active mode in its title, and sends role creations with `mode`.
  - `CoworkApp` passes active mode/session to `MemoryManager`.
  - Electron `chat-memory-create` forwards `mode` to the Python sidecar.
- Verification:
  - TDD red checks first failed as expected because backend did not accept `mode`, Cowork/Code prompts were raw, same-text cross-mode roles overwrote each other, and the UI did not send/filter mode.
  - Targeted backend role tests passed 4/4 with `python -m unittest test.test_chat_memory.ChatMemoryStoreTests.test_manual_role_memory_is_mode_scoped_for_cowork_and_code test.test_chat_memory.ChatMemoryStoreTests.test_same_role_text_can_exist_in_different_modes test.test_ipc_sidecar.IpcSidecarTests.test_cowork_mode_injects_only_cowork_session_role test.test_ipc_sidecar.IpcSidecarTests.test_code_mode_injects_only_code_session_role -v`.
  - Targeted frontend memory tests passed 6/6 with `npm test -- --run frontend/tests/MemoryManager.test.jsx`.
  - Python compile check passed with `python -m py_compile chat_memory.py ipc_sidecar.py`.
  - Full backend suite passed 297/297 with `python -m unittest discover -s test -p test_*.py -v`.
  - Frontend suite passed 107/107 with `npm test`.
  - Frontend production build passed with `npm run build`; the existing Vite chunk-size warning remains non-blocking.
- Skills used: `writing-plans`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-02 - Chat remaining work plan completion

- Completed the remaining Chat plan areas from `CHAT_REMAINING_WORK_PLAN.md` without invoking Claude review, per user instruction:
  - UI polish: source cards now show source quality labels/dots, and the composer shows the latest Auto Router reason from `chat_model_route` telemetry.
  - In-app quality runner: `chat_quality_run` can run an opt-in live model/category matrix after explicit confirmation; the Quality panel renders matrix metrics and per-cell status while snapshot scoring remains available.
  - Web smoke harness: added `chat_web_smoke.py`, an opt-in `--live` smoke runner that reports adapter/static HTML/Playwright/blocked/empty fallback layers, evidence length, table presence, source type, and source quality.
  - MCP hardening: MCP tool input schemas are normalized to strict object schemas before model exposure, with read-only behavior still requiring `readOnlyHint` and side-effecting/missing-hint tools remaining approval-gated. The MCP SDK is exposed as an optional Python extra (`mcp>=1.28,<2`) instead of being required for the base install.
  - Semantic memory foundation: Chat memory now supports an injectable local semantic embedder seam, semantic recall/deduplication when embeddings are available, keyword fallback when unavailable, typed `profile` entries, and do-not-remember markers surfaced in the Memory Manager.
- Preserved security defaults:
  - Live model/network/browser work remains opt-in.
  - MCP write/action tools remain approval-gated.
  - Chat code execution remains disabled by default and prefers Pyodide/WASM when enabled.
  - Explicit model selections still override Auto Router.
- Updated `PROJECT_STATE.md` to remove stale pending notes for semantic memory/live quality matrix and record the completed web smoke, source-quality UI, route-reason UI, MCP schema normalization, and memory upgrades.
- Verification:
  - MCP optional extra packaging resolved with `python -m pip install -e ".[mcp]" --dry-run`.
  - Targeted frontend regression passed 20/20 with `npm.cmd run test -- --run frontend/tests/QualityEvalPanel.test.jsx frontend/tests/coworkBridge.test.js`.
  - Full backend suite passed 310/310 with `python -m unittest discover -s test -p test_*.py -v` after the MCP extra change.
  - Full frontend suite passed 114/114 with `npm.cmd run test`.
  - Production frontend build passed with `npm.cmd run build`; the existing Vite chunk-size warning remains non-blocking.
- Skills used: `writing-plans`, `test-driven-development`, `improve-codebase-architecture`, and `verification-before-completion`.

## 2026-07-02 - Chat review finding fixes

- Resolved the in-session review findings from the Chat remaining-work review without invoking a new Claude review:
  - Cowork/Code persona role prompts now explicitly state that persona instructions must not reduce approval, verification, audit, rollback, or transparency requirements.
  - Added a regression test proving a Cowork persona asking to skip approval/verification still leaves verification approval fail-closed through the code-level approval path.
  - MCP connector creation now probes `list_tools()` before reporting a connector as `connected`, so lazy SDK client construction alone no longer counts as a live connection.
  - MCP strict schemas now make originally optional properties nullable when strict mode requires all properties, preventing forced dummy values for optional arguments.
  - Semantic memory recall now blends keyword fallback with semantic recall so old entries without embeddings remain findable.
  - Public memory entries redact raw embedding vectors before returning data to the frontend.
  - Do-not-remember markers ignore generic instruction words and require at least two meaningful terms before blocking memories, reducing broad false positives.
- TDD evidence:
  - New regression tests first failed for persona non-relaxation, public embedding exposure, old-entry semantic fallback, MCP connection probing, and optional nullable schemas.
  - Targeted regression suite then passed 34/34 with `python -m unittest test.test_chat_memory test.test_chat_mcp_client test.test_ipc_sidecar.IpcSidecarTests.test_cowork_persona_cannot_relax_verification_approval_contract test.test_ipc_sidecar.IpcSidecarTests.test_cowork_mode_injects_only_cowork_session_role test.test_ipc_sidecar.IpcSidecarTests.test_code_mode_injects_only_code_session_role -v`.
- Verification:
  - Python compile check passed with `python -m py_compile chat_memory.py chat_mcp_client.py ipc_sidecar.py`.
  - MCP optional extra dry-run passed with `python -m pip install -e ".[mcp]" --dry-run`.
  - Full backend suite passed 316/316 with `python -m unittest discover -s test -p test_*.py -v`.
  - Full frontend suite passed 114/114 with `npm.cmd run test`.
  - Frontend production build passed with `npm.cmd run build`; the existing Vite/SWC and chunk-size warnings remain non-blocking.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-02 - Chat composer image paste and thumbnail previews

- Fixed the Chat composer image-attachment UX reported from manual testing:
  - Image attachments now render as inline thumbnail tiles inside the composer instead of only text chips.
  - Clipboard screenshots/images pasted with `Ctrl+V` are captured from `clipboardData.items`/`clipboardData.files`, normalized with a safe fallback filename when needed, and routed through the same bounded image attachment path as file picker and drag/drop.
  - Non-image attachments still render as compact metadata chips, and image thumbnails keep preview/remove controls.
- Root cause:
  - Existing Composer code already handled file picker and drag/drop image attachments through `attachSelectedFiles`, but it had no `onPaste` image-file handler.
  - Image attachment data URLs were only visible after opening the preview dialog; the pre-send composer row showed only a file chip.
- TDD evidence:
  - New Composer regressions first failed as expected: dropped images had no inline `<img>` thumbnail, and pasted clipboard images were ignored.
  - After the fix, `frontend/tests/Composer.test.jsx` passed 14/14, including the new thumbnail and clipboard paste cases.
- Verification:
  - Targeted Composer suite passed 14/14 with `npm.cmd run test -- --run frontend/tests/Composer.test.jsx`.
  - Full frontend suite passed 115/115 with `npm.cmd run test`.
  - Frontend production build passed with `npm.cmd run build`; the existing Vite/SWC and chunk-size warnings remain non-blocking.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-02 - Auto Router coding detection and visible restart follow-up

- Clarified the user's note that manual test items 4-6 belong to other app areas, not Chat, and focused this follow-up on concrete findings from the Chat/manual-test pass.
- Findings:
  - The app did not appear after the previous restart because the manual restart command launched Electron with `-WindowStyle Hidden`; Electron's own `ready-to-show -> show()` code was already correct.
  - No current session log evidence showed live mojibake output; the mojibake strings found by search are old test fixtures and design notes, not current runtime logs.
  - Auto Router did miss a Thai prompt asking to explain a `React app` structure because the coding keyword set did not include framework/technology terms such as React.
- Fix:
  - Added a regression test for `ช่วยอธิบายโครงสร้าง React app` and expanded Auto Router coding detection with targeted technology and Thai coding terms without treating generic Thai words such as `โครงสร้าง` alone as coding.
- TDD evidence:
  - `python -m unittest test.test_model_router -v` first failed because the new React/Thai coding prompt routed to the default `zai:glm-4.5-flash`.
  - After the router update, the focused router suite passed 8/8.
- Verification:
  - Python compile check passed with `python -m py_compile model_router.py`.
  - Full backend suite passed 317/317 with `python -m unittest discover -s test -p test_*.py -v`.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-02 - Auto Router avoids paid models without proven access

- Fixed the Auto Router behavior shown in manual testing where a coding prompt routed to `openai:gpt-5.5` and then failed because the OpenAI account had no billing/credit access.
- Behavior:
  - Explicit user-selected models still win, including paid OpenAI/Gemini/Z.ai top-tier models.
  - Auto routing now filters out `billing: paid` catalog models unless a live quality/performance profile proves that model has executed successfully.
  - Auto remains allowed to choose local models, free/free-tier models, and paid-low-cost models such as DeepSeek, so it can still pick a stronger coding candidate than the default free chat model when available.
- TDD evidence:
  - Added a regression where `openai:gpt-5.5` is the strongest paid coding model but has no success profile; the test first failed because Auto selected OpenAI.
  - After adding the eligibility filter, Auto selected `deepseek:deepseek-v4-pro` for the React/coding prompt instead of the paid OpenAI model.
- Verification:
  - Focused router suite passed 9/9 with `python -m unittest test.test_model_router -v`.
  - Python compile check passed with `python -m py_compile model_router.py`.
  - Full backend suite passed 318/318 with `python -m unittest discover -s test -p test_*.py -v`.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-02 - Auto Router paid-model hard gate reverted

- Corrected the previous Auto Router behavior after user review:
  - `Auto` should mean "choose the best model for the task", not "choose only models that appear cheap/free right now."
  - Paid top-tier models must remain valid Auto candidates so future billing/credit changes unlock their full value without changing router code.
  - Billing/credit failures should be handled as runtime provider feedback, not as a catalog-level hard gate.
- Implementation:
  - Removed the paid-model eligibility filter added in the previous entry.
  - Kept the React/Thai coding detection improvement.
  - Replaced the regression with `test_auto_router_can_select_paid_top_model_when_it_is_best_fit`, proving Auto can choose `openai:gpt-5.5` when it is the strongest coding fit.
- Verification:
  - Focused router suite passed 9/9 with `python -m unittest test.test_model_router -v`.
  - Python compile check passed with `python -m py_compile model_router.py`.
  - Full backend suite passed 318/318 with `python -m unittest discover -s test -p test_*.py -v`.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-02 - Chat web smoke source-quality profile

- Paused ChatBridge/Codex CLI integration work per user direction and focused on stabilizing the current Chat pipeline.
- Added persistent source-quality accumulation to `chat_web_smoke.py`:
  - Each saved smoke report now also updates `work_logs/chat-web-source-profile.json`.
  - The stable profile records per-domain run count, success rate, blocked rate, layer usage, table frequency, average evidence length, and average source quality score.
  - This keeps live smoke reports useful beyond one-off diagnostics and gives the app a path to learn which web sources are actually readable and reliable over repeated opt-in runs.
- Confirmed the curated hard smoke URL list in `chat_web_smoke.py` currently contains readable Thai text, not the old mojibake slug seen in historical logs.
- TDD evidence:
  - New smoke-profile tests first failed because `build_source_smoke_profile` did not exist.
  - After the implementation, focused smoke tests passed 4/4 with `python -m unittest test.test_chat_web_smoke -v`.
- Verification:
  - Python compile check passed with `python -m py_compile chat_web_smoke.py`.
  - Focused smoke suite passed 4/4 with `python -m unittest test.test_chat_web_smoke -v`.
  - Full backend suite passed 321/321 with `python -m unittest discover -s test -p test_*.py -v`.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-02 - Chat stability diagnostics pass

- Continued the current Chat stability track and kept ChatBridge/Codex CLI integration parked.
- Completed the four requested stabilization items:
  - Ran a real opt-in web smoke pass with `python -m chat_web_smoke --live --output-dir work_logs`.
  - Surfaced the stable web source profile in the Quality panel so repeated smoke runs show which domains are readable and reliable.
  - Polished MCP connector diagnostics: connected statuses now include tool count, read-only tool count, and approval/write tool count; Composer displays these counts in the connector rows.
  - Added `chat_text_diagnostics.py` for Thai/mojibake diagnostics across recent session logs and runtime encodings, then surfaced the diagnostic state in the Quality panel.
- Live smoke result:
  - Reports written: `work_logs/chat-web-smoke-20260702-102841.json` and `work_logs/chat-web-smoke-20260702-102841.md`.
  - Stable source profile updated: `work_logs/chat-web-source-profile.json`.
  - EPPO fuel price URL: `adapter`, evidence length 4272, table evidence present, quality 5.
  - Bangchak marketing page: `empty`, no static evidence.
  - Bangchak public API URL: `adapter`, evidence length 654, table evidence present, quality 2.
  - GlobalPetrolPrices Thailand gasoline page: `html`, evidence length 1631, table evidence present, quality 2.
- Root cause note:
  - The first live smoke attempt completed its fetch pipeline but crashed when printing Thai URLs to a GBK Windows console. The CLI now writes JSON output through `sys.stdout.buffer` as UTF-8 bytes, while report files remain UTF-8.
- TDD evidence:
  - New backend tests first failed for missing MCP tool-count status fields and missing quality-state `source_profile` / `text_diagnostics`.
  - New smoke CLI test covers UTF-8 stdout for Thai text.
  - New Quality panel and Composer tests cover source profile, text diagnostics, and MCP live tool counts.
- Verification:
  - Python compile check passed with `python -m py_compile chat_web_smoke.py chat_text_diagnostics.py chat_mcp_client.py ipc_sidecar.py`.
  - Full backend suite passed 326/326 with `python -m unittest discover -s test -p test_*.py -v`.
  - Full frontend suite passed 117/117 across 17 files with `npm.cmd run test`.
  - Frontend production build passed with `npm.cmd run build`.
- Skills used: `writing-plans`, `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-02 - MCP live connector runner and Chat result cards

- Continued the MCP live connector completion plan with the user-approved scope and without Claude review.
- Completed strict-schema hardening for MCP tools:
  - Optional schema properties are now nullable while still strict-mode required.
  - Nested object schemas receive recursive `additionalProperties: false` normalization.
  - `None`/null arguments are stripped before calls reach the MCP server.
- Completed Chat approval visibility for MCP/code side effects:
  - Chat no longer hides pending approval prompts.
  - The composer locks while Chat is waiting for an approval decision.
  - MCP approval prompts are labeled as MCP tool approvals instead of generic file-write approvals.
- Added manual MCP Tool Runner support:
  - `chat_mcp_tool_run` IPC command runs tools from Chat.
  - Manual runs use the same `McpToolProvider.dispatch` path as model-driven MCP calls, preserving read-only gating and approval enforcement at one backend point.
  - Connector status payloads include normalized per-tool metadata and input schemas for the UI.
  - Composer now shows connected tools with read/write badges, schema-derived argument fields, and Run / Request approval & run actions.
  - Chat timeline renders persistent MCP result cards instead of raw JSON.
- Added model-call visibility for MCP:
  - Model-driven MCP tool calls now emit transient Chat status lines such as `MCP: calendar/list_instances`.
  - Model-driven MCP results emit the same Chat timeline card format with `origin: model`.
- Added a truthful connection lifecycle polish:
  - SDK clients now expose a `probe()` seam backed by the real `list_tools()` handshake.
  - The sidecar caches successful/failed connector probe results for 60 seconds on normal state/diagnostic/tool-provider paths.
  - Explicit connector Test actions bypass the cache and force a fresh probe.
- Files touched include `chat_mcp_client.py`, `ipc_sidecar.py`, `electron/main.js`, `electron/preload.cjs`, `frontend/lib/eel.js`, `frontend/adapters/coworkBridge.js`, `frontend/model/coworkEvents.js`, `frontend/components/Composer.jsx`, `frontend/components/TimelineEntry.jsx`, new `frontend/components/McpResultCard.jsx`, `test/test_chat_mcp_client.py`, `test/test_ipc_sidecar.py`, `frontend/tests/Composer.test.jsx`, `frontend/tests/coworkBridge.test.js`, `frontend/tests/Timeline.test.jsx`, and `frontend/tests/CoworkApp.test.jsx`.
- Verification:
  - Focused backend suite passed 91/91 with `python -m unittest test.test_chat_mcp_client test.test_ipc_sidecar -v`.
  - Full backend suite passed 331/331 with `python -m unittest discover -s test -p test_*.py -v`.
  - Focused frontend MCP/chat suite passed 74/74 with `npm.cmd run test -- --run frontend/tests/Composer.test.jsx frontend/tests/coworkBridge.test.js frontend/tests/Timeline.test.jsx frontend/tests/CoworkApp.test.jsx`.
  - Full frontend suite passed 125/125 with `npm.cmd run test`.
  - Production frontend build passed with `npm.cmd run build`.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-02 - Generic MCP Connectors management view

- Reworked the Chat MCP surface so connectors are configured from a dedicated product view instead of being centered around Roblox buttons in the compact composer menu.
- Added `frontend/components/ConnectorsPanel.jsx`:
  - Shows MCP as plugin-style local server configs that must be added/tested/enabled before Chat can use them.
  - Supports arbitrary custom connector configs with `stdio`, `http`, and `sse` transports.
  - Provides optional presets for Roblox Studio MCP and Blender MCP without making either one the hardcoded primary path.
  - Shows runtime readiness, configured/enabled/connected counts, per-connector status, tool counts, test action, enable/disable, save, and delete.
- Added a `Connectors` item to the main sidebar and wired it through `CoworkApp` to the existing connector bridge calls: list, save, test, and discover.
- Simplified the compact Chat tool settings menu:
  - It now shows connector status and a `Manage MCP connectors` shortcut.
  - It no longer presents `Add Roblox MCP preset` / `Test Roblox MCP` as primary composer actions.
  - Existing manual MCP tool execution remains available for already configured connectors and still uses the backend `McpToolProvider.dispatch` enforcement point.
- Updated `PROJECT_STATE.md` to record the dedicated connector-management surface and the composer-menu responsibility split.
- TDD evidence:
  - New `ConnectorsPanel` tests first failed because the component did not exist.
  - Updated Composer/CoworkApp tests first failed because the composer still exposed Roblox-specific actions and the sidebar had no Connectors view.
  - After implementation, focused tests passed 46/46.
- Verification:
  - Focused frontend suite passed 46/46 with `npm.cmd run test -- --run frontend/tests/ConnectorsPanel.test.jsx frontend/tests/Composer.test.jsx frontend/tests/CoworkApp.test.jsx`.
  - Full frontend suite passed 129/129 across 18 files with `npm.cmd run test`.
  - Production frontend build passed with `npm.cmd run build`.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-02 - Bottom-left Settings and Developer MCP surface

- Added a bottom-left account/settings menu to the sidebar footer, matching the product pattern the user requested:
  - The footer account/workspace chip now opens a menu with Settings, Language, Get help, Get apps and extensions, View changelog, Developer, and Log out entries.
  - Settings and Developer both open the Settings modal on the Developer section.
- Added `frontend/components/SettingsModal.jsx`:
  - Provides a settings sidebar with General, Account, Privacy, Billing, Usage, Capabilities, Connectors, Code, Cowork, Desktop app General, Extensions, and Developer.
  - The Developer and Connectors sections embed the same app-level MCP connector management surface used by the main Connectors view.
  - This makes configured MCP servers discoverable across Chat sessions instead of feeling tied to one chat composer.
- Updated `ConnectorsPanel` with an `embedded` layout mode for use inside the Settings modal.
- Updated `CoworkApp` to maintain Settings modal state and pass the existing connector bridge calls into the modal.
- Updated `PROJECT_STATE.md` to record that MCP connectors are now app-level settings discoverable from Settings > Developer and the sidebar Connectors shortcut.
- TDD evidence:
  - New CoworkApp test first failed because there was no `Account and settings` button and no Settings modal.
  - After implementation, the focused CoworkApp suite passed 27/27.
- Verification:
  - Focused frontend suite passed 27/27 with `npm.cmd run test -- --run frontend/tests/CoworkApp.test.jsx`.
  - Full frontend suite passed 130/130 across 18 files with `npm.cmd run test`.
  - Production frontend build passed with `npm.cmd run build`.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-02 - MCP SDK runtime enablement and concise transport errors

- Investigated the user's Settings > Developer MCP connector screen showing `MCP SDK is not installed`.
- Confirmed the sidecar Python runtime was `C:\Users\user\AppData\Local\Python\pythoncore-3.14-64\python.exe` and did not have the `mcp` package installed.
- Installed the project MCP optional extra into that same Python runtime with `python -m pip install -e ".[mcp]"`.
- Confirmed `mcp_sdk_available=True` after installation.
- Tightened `chat_mcp_client.py` live SDK error handling:
  - Connection/transport failures are now wrapped as concise `RuntimeError` messages.
  - Raw SDK `ExceptionGroup` traces no longer escape into tests or UI diagnostics.
  - Existing missing-SDK and unsupported-transport messages remain explicit.
- Updated `PROJECT_STATE.md` to record the enabled local MCP runtime and normalized SDK diagnostics.
- Verification:
  - Focused MCP backend suite passed 18/18 with `python -m unittest test.test_chat_mcp_client -v`.
  - Full backend suite passed 331/331 with `python -m unittest discover -s test -p test_*.py -v`.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-02 - MCP diagnostic generic query handling

- Improved Chat MCP diagnostics after the Roblox Studio connector connected successfully but a generic user request such as `test MCP` was interpreted as looking for a connector literally named `test`.
- Added generic diagnostic term filtering for English and Thai words such as `test`, `mcp`, `connector`, `ทดสอบ`, `ตรวจสอบ`, `สถานะ`, and `เชื่อมต่อ`.
- Generic diagnostic requests now list configured MCP connectors and their status/tool summary instead of incorrectly reporting that no matching connector exists.
- Preserved named-connector behavior: specific names such as `roblox` still narrow the diagnostic match.
- TDD evidence:
  - Added `test_mcp_diagnostics_generic_test_query_lists_configured_connectors`.
  - The new test failed before implementation because `payload["found"]` was false for query `test`.
  - After implementation, the focused regression test passed.
- Verification:
  - Focused regression test passed with `python -m unittest test.test_chat_mcp_client.McpToolProviderTests.test_mcp_diagnostics_generic_test_query_lists_configured_connectors -v`.
  - Focused MCP backend suite passed 19/19 with `python -m unittest test.test_chat_mcp_client -v`.
  - Full backend suite passed 332/332 with `python -m unittest discover -s test -p test_*.py -v`.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-03 - MCP timeout and unreachable guidance for Roblox Studio

- Investigated the user's Roblox Studio MCP Server panel showing `Connecting (attempt 4)`.
- Live probes showed the local MCP endpoint was not ready:
  - `http://localhost:58741` timed out.
  - `http://localhost:58741/mcp` could not be reached by the MCP SDK while the Studio plugin was still connecting.
- Confirmed this is a Roblox MCP server/plugin readiness issue, not a wrong app URL or missing SDK issue.
- Improved connector diagnostics in `chat_mcp_client.py`:
  - HTTP/SSE timeout messages now include endpoint guidance and the expected full `/mcp` URL.
  - Unreachable/terminated SDK connection messages now explain that the external MCP server or plugin must be running and reachable.
  - Roblox connector messages explicitly tell the user the Roblox Studio MCP Server panel must show `Connected` before testing from the app.
- TDD evidence:
  - Added `test_create_mcp_clients_reports_actionable_unreachable_http_connector`, which failed before the normalizer because the error was the raw SDK message.
  - Added `test_create_mcp_clients_timeout_for_http_roblox_connector_is_actionable`, which failed before timeout guidance because the message only said `timed out`.
  - Both tests pass after implementation.
- Verification:
  - Focused MCP backend suite passed 21/21 with `python -m unittest test.test_chat_mcp_client -v`.
  - Live local probe while the plugin was connecting returned the new actionable timeout text.
  - Full backend suite passed 334/334 with `python -m unittest discover -s test -p test_*.py -v`.
- Skills used: `roblox-workspace-builder`, `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-03 - Smartness pipeline batch 2 code items

- Implemented `SMARTNESS_PIPELINE_BATCH_2_PLAN.md` Item 1 and Item 3.
- Item 1: `chat_quality_runner.py` now supports A/B live quality runs through `--tool-research-routes` and IPC `tool_research_routes`, while preserving the default path when no route override is supplied.
- Item 1 diagnostics: live reports now carry route variant plus `entered_tool_loop`, `research_iterations`, `research_forced`, and `answer_path_ms` so model/category scorecards can explain whether latency came from research/tool-loop routing or direct answer generation.
- Item 3: added `chat_embeddings.py` as a default-off fastembed seam, exposed the optional `embeddings` extra, added `ChatRuntimeConfig.semantic_memory_enabled`, and wired enabled local embedding generation into Chat memory create/update paths.
- Safety/local-first behavior: semantic embeddings remain disabled unless `COWORK_CHAT_SEMANTIC_MEMORY` is enabled; default tests and normal startup do not import fastembed or download embedding models.
- Operational note: GLM-5.2 validation remains a manual live run because it can consume provider credits/API quota.
- TDD evidence:
  - Added failing tests first for quality-runner route plumbing/diagnostics, IPC quality route forwarding, default-off semantic memory, enabled embedder caching, lazy fastembed import fallback, and memory embedding writes/updates.
  - Implemented until targeted tests passed.
- Verification:
  - Full backend suite passed 360/360 with `python -m unittest discover -s test -p test_*.py`.
  - Frontend suite passed 18 files / 134 tests with `npm test -- --run`.
- Skills used: `test-driven-development` and `verification-before-completion`.

## 2026-07-03 - Smartness pipeline batch 2 GLM-5.2 live validation

- Ran `SMARTNESS_PIPELINE_BATCH_2_PLAN.md` Item 2 live validation after the user confirmed Z.ai credit was available.
- Run A baseline command:
  - `python -m chat_quality_runner --live --models zai:glm-5.2,zai:glm-4.5-flash --retry-attempts 2 --retry-backoff-seconds 5`
- Run B gated command:
  - `python -m chat_quality_runner --live --models zai:glm-5.2,zai:glm-4.5-flash --tool-research-routes web,project --retry-attempts 2 --retry-backoff-seconds 5`
- Result: both models executed successfully through Z.ai billing; there were 0 skipped cells and no billing/credit/auth failures.
- Baseline report:
  - JSON: `work_logs/chat-quality-live-20260703-115752.json`
  - Markdown: `work_logs/chat-quality-live-20260703-115752.md`
  - Summary: 14/14 executed, 11 passed, 3 failed, pass rate 0.7857, average latency 13815 ms, hallucination rate 0.
- Gated route report:
  - JSON: `work_logs/chat-quality-live-20260703-120123.json`
  - Markdown: `work_logs/chat-quality-live-20260703-120123.md`
  - Summary: 14/14 executed, 12 passed, 2 failed, pass rate 0.8571, average latency 13061 ms, hallucination rate 0.
- Model-level interpretation:
  - `zai:glm-5.2`: 6/7 pass in both variants; strong-tier candidate is usable but slower than Flash on most non-web categories.
  - `zai:glm-4.5-flash`: improved from 5/7 to 6/7 under gated routing; general passed only when it skipped the tool loop.
  - Both variants still failed the web category, for different reasons: GLM-5.2 asked for clarification instead of using/citing sources; GLM-4.5-Flash used sources but failed source-quality scoring.
- Decision: Z.ai paid billing works. Keep GLM-5.2 available as a strong/capable tier, keep GLM-4.5-Flash as the fast/free-style default, and do not make `tool_research_routes=("web","project")` the global default solely from this run; it improves overall score but GLM-5.2 general latency remains high even without the tool loop.
- Skills used: `verification-before-completion`.

## 2026-07-03 - Model-agnostic pipeline decision

- Recorded the user's architecture decision that the Chat pipeline must not be tuned to favor one model/provider.
- Added the principle to `PROJECT_STATE.md`: prompts, tools, guards, source handling, research behavior, and evaluation should be shared across capable models; model differences should come from capability metadata, provider adapters, context window, latency, and the model's own quality.
- Implication for the GLM-5.2 / GLM-4.5-Flash live results: use the scorecard to choose or recommend models, but do not hard-code special behavior just to make one model pass a category. If the web category fails, improve the shared web/tool-use contract first.
- Verification: documentation-only architecture record; no runtime tests required.
- Skills used: `improve-codebase-architecture`.

## 2026-07-03 - Effort as model-independent execution budget

- Recorded the user's architecture decision that Effort must control the workflow budget for every capable model, not act as a hidden model tier.
- Added the principle to `PROJECT_STATE.md`: Low/Medium/High/Extra High should drive shared runtime budgets such as search depth, fetch count, tool-loop iterations, MCP/tool-call budget, planning/reasoning passes, verification strictness, and source-quality requirements.
- Design implication: a free/fast model at High effort should receive the same richer pipeline budget as a paid/top model at High effort; a paid/top model at Low effort should use the same lightweight pipeline budget as a smaller model at Low effort. Result quality may still differ because model capability differs.
- Verification: documentation-only architecture record; no runtime tests required.
- Skills used: none; this was a direct architecture note following the previous model-agnostic decision.

## 2026-07-03 - Roblox MCP read-only inspection routing

- Investigated why Chat answered a Roblox Studio scene question by listing available MCP tools instead of inspecting `Workspace`.
- Confirmed the live connector and Studio plugin were healthy, and direct backend calls could read `Workspace`, but the app treated every Roblox MCP tool as approval-required because the upstream server does not provide `readOnlyHint` annotations.
- Added a narrow code-level Roblox MCP read-only allowlist for inspection tools only, including `get_project_structure`, `get_instance_properties`, `get_instance_children`, `search_objects`, `get_services`, `get_place_info`, and related read/search helpers.
- Kept side-effecting tools approval-gated; live smoke with an always-deny approval callback allowed `get_project_structure` but denied `create_object` before it could mutate Studio.
- Updated Chat research instructions so when MCP tools are available and the user asks about the state of a connected app/service, the model should call a relevant read-only MCP inspection tool instead of stopping at `mcp_list_tools`.
- Fixed MCP SDK result normalization so rich SDK content objects such as `TextContent` serialize into JSON-safe dicts before returning through the tool loop or Chat timeline.
- TDD evidence:
  - Added `test_known_roblox_inspection_tools_are_read_only_without_server_annotations`; it failed before implementation because `get_project_structure` was not read-only.
  - Added `test_unknown_or_side_effecting_roblox_tools_still_require_approval`; it preserved the approval gate for `create_object`.
  - Added `test_research_instruction_tells_model_to_use_relevant_mcp_read_tools`; it failed before the prompt update because research instructions mentioned only web tools.
  - Added `test_dispatch_normalizes_rich_mcp_sdk_content_to_json_safe_payload`; it reproduced the live `TextContent` JSON serialization failure before normalization.
- Verification:
  - Focused MCP backend suite passed 25/25 with `python -m unittest test.test_chat_mcp_client -v`.
  - Focused Chat research runner suite passed 10/10 with `python -m unittest test.test_chat_research_runner -v`.
  - Live Roblox MCP smoke reported `connected`, `27` read-only tools, `39` approval tools, `get_project_structure` status `ok`, and `create_object` status `denied` with one approval proposal.
  - Full backend suite passed 339/339 with `python -m unittest discover -s test -p test_*.py -v`.
- Skills used: `roblox-workspace-builder`, `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-07-03 - Roblox MCP Workspace preflight context

- Investigated the user's live Chat result where `ตอนนี้ใน Workspace มีพาร์ทกี่ชิ้น ลักษณะเป็นอย่างไร` still produced a Roblox MCP tool catalog instead of inspecting the open Studio scene.
- Root cause: although MCP was connected and Roblox read-only tools were available, the model could still choose the diagnostics/tool-list path and stop there. Chat had no deterministic preflight context for common Roblox Workspace state questions.
- Added a read-only Roblox Workspace preflight in `ipc_sidecar.py`:
  - Runs only when Chat MCP is enabled, the prompt looks like a Roblox/Workspace inspection request, and a connected Roblox Studio MCP connector is available.
  - Uses the existing `McpToolProvider.dispatch` enforcement point with an always-deny approval callback, so only read-only tools can succeed.
  - Calls `get_instance_children` for `Workspace`, then calls `get_instance_properties` for direct BasePart-like children such as `Part`, `MeshPart`, and `SpawnLocation`.
  - Injects a `Live Roblox Workspace Context` system block before the model answers, with direct child count, physical object count, paths, size, position, material, color, anchoring, collision, and transparency.
- Added regression coverage in `test_ipc_sidecar.py` with a fake Roblox MCP client:
  - `test_chat_prefetches_roblox_workspace_context_for_part_inspection_question` failed before implementation because the model prompt had no `Live Roblox Workspace Context`.
  - The test now verifies Baseplate/NeonCube context and exact read-only tool calls.
- Live smoke:
  - Read the real Roblox Studio connector through `http://localhost:58741/mcp`.
  - The generated context reported `Workspace direct child count: 5` and `Direct physical object count: 3`.
  - Direct physical children were `Baseplate`, `NeonCube`, and `SpawnLocation`.
- Verification:
  - Focused regression test passed with `python -m unittest test.test_ipc_sidecar.IpcSidecarTests.test_chat_prefetches_roblox_workspace_context_for_part_inspection_question -v`.
  - Focused MCP/sidecar suites passed 99/99 with `python -m unittest test.test_chat_mcp_client test.test_ipc_sidecar -v`.
  - Full backend suite passed 340/340 with `python -m unittest discover -s test -p test_*.py -v`.
- Skills used: `roblox-workspace-builder`, `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-08-14 - Role settings persistence refresh state

- Investigated the Role settings screen showing an empty state after restart/update even though the installed app's per-user `chat_memory/personal.json` still contained an enabled role.
- Confirmed the persistence path and sidecar response are healthy; the issue was a frontend timing state where the empty UI rendered before `chat_memory_state` arrived.
- Added an explicit role-loading state from `CoworkApp` through `SettingsModal` to `RolesPanel`. Role settings now display `Loading roles from local storage...` until the first memory-state response, then render either the saved roles or a true empty state.
- TDD evidence: added a `RolesPanel` regression test which failed first because the pre-fix component rendered `No global role yet` while `loading` was requested; it passed after the loading branch was implemented.
- Verification:
  - Focused frontend tests passed 33/33 with `npm.cmd run test -- --run frontend/tests/RolesPanel.test.jsx frontend/tests/CoworkApp.test.jsx`.
  - Full backend suite passed 405/405 with `python -m unittest discover -s test -p test_*.py`.
  - Full frontend suite passed 169/169 with `npm.cmd run test`.
  - Production frontend build passed with `npm.cmd run build`; the existing Vite chunk-size warning remains non-blocking.
  - The local preview server started successfully. Browser-level Playwright interaction could not run because the local Python environment does not include the `playwright` package; the role rendering behavior remains covered by the focused React regression test.
- Skills used: `systematic-debugging`, `test-driven-development`, `webapp-testing`, and `verification-before-completion`.

## 2026-08-14 - Published desktop update v0.1.17

- Committed the Role settings loading-state fix as `7d702b8` and pushed it to `main`; published and pushed tag `v0.1.17`.
- Built the Windows NSIS installer from the tagged source and published GitHub Release `v0.1.17`.
- Verified the published release is not a draft and that `latest.yml` names an installer asset and matching blockmap that are both present in the release. This preserves the normal Electron auto-update path rather than altering the currently installed app.

## 2026-08-14 - Desktop updater UI-only flow

- Investigated a release-flow regression after the user clarified that startup updates and updates discovered while the app is running must both remain available through the in-app top-right `Update` button.
- Root cause: `runUpdateGate()` used a separate startup path that called `autoUpdater.quitAndInstall()` when a download completed, bypassing the renderer and forcing a relaunch.
- Removed the startup gate. The app now launches normally, then one background updater checks after startup and every 30 minutes. It publishes a retained `{state, version, percent}` snapshot through the new `get-app-update-state` IPC endpoint and normal `app-update` events.
- The React app subscribes and also hydrates the retained snapshot. This prevents an update event emitted before React finishes mounting from disappearing. The only remaining `quitAndInstall()` call is the `install-update-now` IPC handler invoked by the user-facing button. `autoInstallOnAppQuit` is explicitly disabled.
- Added a stable no-space NSIS artifact name, `AI-Dev-Co-worker-Setup-${version}.${ext}`, so the generated `latest.yml` and uploaded GitHub Release asset use exactly the same filename.
- TDD evidence: added a renderer regression test for a startup-discovered ready update and a source/release contract test. Both tests failed before implementation because no status snapshot existed, the startup gate remained, auto-install-on-quit was enabled, and no stable artifact name was configured.
- Focused verification: `npm.cmd run test -- --run frontend/tests/updaterContract.test.js frontend/tests/CoworkApp.test.jsx frontend/tests/coworkBridge.test.js frontend/tests/ipcChannelAllowlist.test.js` passed 55/55.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-08-14 - Published desktop update v0.1.18

- Committed the UI-controlled updater fix as `a8be08b`, pushed `main`, and published GitHub Release `v0.1.18`.
- Built the NSIS installer from the tagged source. The generated `latest.yml` and the uploaded release assets agree on `AI-Dev-Co-worker-Setup-0.1.18.exe` and its blockmap.
- Verified the GitHub release is published (not draft or prerelease) and downloaded its remote `latest.yml` through the GitHub API to confirm that exact filename, size, SHA-512, and version `0.1.18` are available to Electron updater clients.

## 2026-08-14 - Restored two-path desktop updater behavior

- Corrected a regression in the `v0.1.18` source change: the user required the existing startup update gate and the in-app background update button to coexist, not for the startup path to be removed.
- Restored `runUpdateGate()` for launch-time checks. When an update is present before the application opens, it shows the original small updater window, downloads, installs, and relaunches before the main UI starts.
- Kept the `v0.1.18` background improvements: after the main UI opens, background checks retain an IPC snapshot so early events cannot be lost and a downloaded update remains actionable from the top-right `Update` button. The background path does not auto-install on a normal quit.
- TDD evidence: the updater contract test was changed to require both paths; it failed before restoration because `runUpdateGate()` was absent, then passed with the startup gate and the isolated background UI path present.
- Focused verification: `npm.cmd run test -- --run frontend/tests/updaterContract.test.js frontend/tests/CoworkApp.test.jsx` passed 32/32.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-08-14 - Published desktop update v0.1.19

- Committed the restored two-path updater behavior as `fa58963`, pushed `main`, and published GitHub Release `v0.1.19`.
- Verified the published release is not a draft or prerelease. Its remote `latest.yml` names `AI-Dev-Co-worker-Setup-0.1.19.exe`, and the installer and matching blockmap are present with the same version and byte size recorded in metadata.

## 2026-08-14 - Prevent persisted Cowork stream fragments

- Investigated the installed Cowork timeline rendering one streamed answer as one-character messages and exposing a raw `verification.finished` JSON payload after a session switch or reload.
- Root cause: the live reducer correctly coalesced streaming events and kept verification evidence outside the timeline, but `appendEventToSessionStore` persisted every event. Hydration later bypassed that reducer behavior and rendered the stored delta fragments and internal evidence directly.
- Added transient-event filtering at both boundaries: live stream/status/agent/verification events are no longer written to durable session history, and session storage normalizes existing persisted state to remove those historical transient records.
- TDD evidence: the CoworkApp regression test first reproduced fragment and JSON reappearance after switching modes; the session-storage regression test first reproduced their persistence. Both pass after the filter.
- Focused verification: `npm.cmd run test -- --run frontend/tests/CoworkApp.test.jsx frontend/tests/sessionStorage.test.js` passed 40/40.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-08-14 - Published desktop update v0.1.20

- Committed the timeline persistence fix as `0069455`, pushed `main`, and published GitHub Release `v0.1.20`.
- Built the Windows NSIS installer from the tagged source. The generated `latest.yml` and uploaded release assets agree on `AI-Dev-Co-worker-Setup-0.1.20.exe` and its blockmap.
- Verified the release is neither draft nor prerelease and downloaded its remote `latest.yml`; it reports version `0.1.20`, the expected installer filename, size, and SHA-512.

## 2026-08-14 - Cowork and Code image context plus Role refresh

- Diagnosed two user-visible regressions from the source and added regression tests before implementation.
- Cowork and Code attachment requests now normalize image/file context before mode dispatch and forward a bounded OpenAI-compatible multimodal user payload to `CoworkAgent` when an attachment is present. The fallback path builds content per candidate model, so an explicitly selected text-only model is not silently overridden.
- `CoworkAgent` records only the ordinary text prompt in durable session history; raw image/base64 payloads are request-only and do not persist in the agent history.
- Added catalog metadata for Z.ai `GLM-4.6V-Flash` as a free vision-capable model. This provides a documented no-cost vision choice while retaining the existing text-only models.
- Fixed the Role Settings internal-navigation refresh gap: selecting Role inside the Settings modal now asks the sidecar for current memory state, and the Role panel has an accessible manual refresh button for a retry without closing the modal.
- TDD evidence: added backend coverage for multimodal Cowork request forwarding/history privacy and catalog metadata, plus frontend coverage for Role manual refresh and internal Role navigation refresh.
- Verification: full backend suite passed 408/408 with `python -m unittest discover -s test -p test_*.py`; full frontend suite passed 176/176 with `npm.cmd run test`.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`. No Claude review was requested.

## 2026-08-14 - Published desktop update v0.1.21

- Committed the Cowork/Code image-context and Role-refresh update as `8e23f2f`, pushed `main`, and published tag/GitHub Release `v0.1.21`.
- Built the Windows NSIS installer from the tagged source. The generated and remotely published `latest.yml` both report `0.1.21`, `AI-Dev-Co-worker-Setup-0.1.21.exe`, size `110808889`, and the matching SHA-512; the installer and blockmap assets are published and the release is neither draft nor prerelease.

## 2026-08-14 - Opt-in two-model Vision Assist

- Added an opt-in two-model image-analysis pipeline for Chat, Cowork, and Code. The selected primary model still produces the final answer. When Vision Assist is set to `Auto`, the helper model `zai:glm-4.6v-flashx` first extracts concise evidence from an attached image and the primary receives only that evidence text.
- The feature defaults to `Off` and is available from Composer Tool Settings. This prevents an unexpected paid helper call and preserves the normal direct-image path for explicitly selected vision models while Vision Assist is disabled.
- Helper failure is conservative: a vision-capable primary may receive the original image through the pre-existing direct multimodal path; a text-only primary receives an explicit unavailable-evidence note and must not claim to have inspected the image. Raw image/base64 data is excluded from durable history, event telemetry, and UI status payloads.
- Live paid validation used Z.ai `GLM-4.6V-FlashX` as helper and `GLM-5.2` as the selected primary. The real sidecar path emitted only transient `Analyzing image...` then `Writing...` status and completed in approximately 11.7 seconds.
- TDD evidence: the missing setting initially selected the helper and the regression test failed; normalization was corrected so missing/invalid settings remain `Off`. Tests also cover helper-before-primary ordering, no image forwarding to a text-only primary, safe helper failure, Cowork integration, catalog metadata, and UI-to-Electron settings plumbing.
- Verification: backend `419/419` passed with `python -m unittest discover -s test -p test_*.py -v`; frontend `177/177` passed with `npm test -- --reporter=dot`.
- Skills used: `writing-plans`, `test-driven-development`, `systematic-debugging`, and `verification-before-completion`. No Claude review was requested.

## 2026-08-14 - Published desktop update v0.1.22

- Committed the opt-in Vision Assist pipeline as `bd82756`, pushed `main`, and published tag/GitHub Release `v0.1.22`.
- Built the Windows NSIS installer from the tagged source. The remotely published `latest.yml` reports `0.1.22`, `AI-Dev-Co-worker-Setup-0.1.22.exe`, size `110811172`, and a matching SHA-512. The installer and matching blockmap are present and the release is neither draft nor prerelease.

## 2026-08-14 - Render sent image attachments in Cowork and Code timelines

- Diagnosed the missing image in a Cowork conversation: attachment thumbnail data was already included in the local user event, but `MessageEntry` rendered attachment previews only in its Chat branch. Cowork and Code therefore displayed the user text but omitted the image.
- Reused the existing attachment preview component for the non-Chat user-message branch, left-aligned to match the Cowork/Code timeline. The image stays local to session history/UI; no backend event, model input, or audit logging behavior changed.
- TDD evidence: added a Cowork timeline image regression test. It failed before the rendering change because no image was present, then passed after the shared preview was rendered in the non-Chat branch.
- Verification: focused Timeline tests passed `15/15`; full frontend suite passed `178/178`; production frontend build passed. The existing Vite bundle-size warning is non-blocking.
- Skills used: `systematic-debugging`, `test-driven-development`, and `verification-before-completion`.

## 2026-08-14 - Published desktop update v0.1.23

- Committed the non-Chat image timeline fix as `785a9b6`, pushed `main`, and published tag/GitHub Release `v0.1.23`.
- Built the Windows NSIS installer from the tagged source. GitHub Release verification confirms `AI-Dev-Co-worker-Setup-0.1.23.exe` (`110811239` bytes), its matching blockmap, and `latest.yml` are published; the release is neither draft nor prerelease.

## 2026-08-15 - Transient live work progress

- Reworked the existing processing indicator so it measures the full request lifetime rather than restarting at every backend status change. While the model is working, it shows `Working for <elapsed>` plus a rotating generic progress line; when the sidecar reports a real action such as searching, reading, writing, MCP activity, or vision analysis, that real action replaces the generic line without resetting the elapsed time.
- The reducer now creates the transient work record from the local `agent.status: busy` event, retains the original `startedAt` through subsequent `chat.status` events, and clears it on assistant streaming/final output, failure, cancellation/idle, or session completion. It remains outside durable session history and therefore disappears completely when a turn ends.
- TDD evidence: new component and reducer regression tests failed before the change because no request-level start time existed and the UI only showed the old per-step `Thinking` label. They pass after the implementation. Existing app-level expectations were updated from the former label to the new explicit elapsed-progress text.
- Verification: focused frontend tests passed `51/51`; final full frontend suite passed `180/180`; `npm run build` passed. The existing Vite bundle-size warning remains non-blocking. Browser-level Playwright verification was unavailable because the local Python environment does not include the `playwright` package.
- Skills used: `systematic-debugging`, `test-driven-development`, `webapp-testing`, and `verification-before-completion`.

## 2026-08-15 - Published desktop update v0.1.24

- Committed the transient live work-progress feature as `2e872a4`, pushed `main`, and pushed tag `v0.1.24`.
- Built the Windows NSIS installer from the tagged source. GitHub Release verification confirms `AI-Dev-Co-worker-Setup-0.1.24.exe` (`110811345` bytes), its matching blockmap, and `latest.yml` are published; the release is neither draft nor prerelease.
- The release preserves both supported update routes: the startup updater can apply an available release before the app opens, and the in-app updater can surface the top-right Update control after its background check finds this release.
