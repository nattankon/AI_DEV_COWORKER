# Web Chat Bridge Implementation Plan

Last updated: 2026-08-21

## Goal

Add an experimental ChatGPT Web surface to AI Dev Co-worker so a user can sign in to the real website inside the desktop application, then later grant a selected workspace to ChatGPT through an authenticated remote MCP tunnel.

## Architectural invariants

- Chat, Cowork, and Code remain the three product modes. Web Chat is a browser surface, not a fourth conversation runtime and does not share their sessions, memory, model routes, or tool state.
- The website runs in an Electron `WebContentsView`, never an iframe and never the trusted React renderer.
- The website uses the dedicated persistent partition `persist:web-chat` so Chromium can retain the user's website session across application restarts.
- The embedded website has no preload script, Node integration, or direct IPC access.
- AI Dev Co-worker does not inspect, export, log, or reuse ChatGPT cookies or OAuth tokens.
- Workspace and tunnel permissions are separate from the ChatGPT login session. Disconnecting a tunnel does not sign the website out, and clearing the website session cannot retain a workspace grant.
- Remote access is off by default, scoped to one explicitly selected workspace, authenticated, approval-gated, audited, and torn down when the application exits.

## Rollout

### Phase 1: Isolated Web Chat surface

- Add a `Web Chat` surface selector beside Chat/Cowork/Code.
- Create the `WebContentsView` lazily with `partition: "persist:web-chat"`.
- Provide Back, Forward, Reload, Open in browser, and connection/loading status controls.
- Keep the view hidden when another surface is active without destroying its Chromium session.
- Allow normal website login and OAuth popup behavior inside the same persistent partition.
- Do not expose cookies, storage, request interception, or DOM automation interfaces.

### Phase 2: Workspace grant

- Let the user explicitly choose one registered workspace for Web Chat.
- Persist only the selected workspace identifier and requested permission profile.
- Reuse canonical workspace containment, Secret Guard, and approval policy.
- Revoke the active grant before changing workspaces.

Status: completed in source on 2026-08-21. The grant is persisted independently under Electron user data and remains capability-only metadata until Phase 3. Tools and tunnel state are hard-off in the main-process response.

### Phase 3: Local MCP gateway

- Expose a compact tool catalog backed by existing WorkspaceTools and MCP provider dispatch.
- Preserve read-only metadata and fail closed when a tool has no trusted annotation.
- Do not expose arbitrary shell or unrestricted filesystem access.

Status: completed in source on 2026-08-21. The main process binds an internal, local-only gateway to the active canonical grant generation and workspace path. Its built-in catalog exposes only `list_directory`, `search_files`, and `read_file`; optional provider tools require explicit trusted read-only and workspace-bound annotations. Every call revalidates the grant generation and uses existing workspace containment, Secret Guard, result-contract, and audit enforcement. No listener, public URL, tunnel, website IPC, shell, write, Git, verification, or restore capability is exposed in this phase.

### Phase 4: Authenticated tunnel

- Add a tunnel adapter seam with explicit start, stop, health, and endpoint state.
- Generate a short-lived high-entropy credential; redact it from UI events and logs.
- Stop the tunnel and child process on disconnect, application quit, timeout, or workspace change.
- Keep tunnel implementations optional so Cloudflare, a private relay, or another provider can be selected without changing permission logic.

Status: completed in source on 2026-08-21. Electron creates a fresh 256-bit bearer credential for each explicit connection and passes it directly to the Python sidecar; it exists transiently only in those two trusted processes and is never exposed to the React renderer or remote website. The sidecar exposes the active Phase 3 catalog through a loopback MCP HTTP listener and an optional Cloudflare Quick Tunnel adapter. Public renderer state is redacted and accepted only when grant ID, revision, and canonical workspace path match. Disconnect, grant replacement/revoke, credential expiry, idle timeout, sidecar shutdown, and application teardown close the listener and tunnel process tree. `cloudflared` remains an optional local runtime dependency; a missing executable produces an actionable error instead of weakening authentication. Connector registration and credential handoff remain Phase 5.

### Phase 5: ChatGPT connector setup

- Show the remote MCP URL, authentication state, exposed tool count, and workspace scope.
- Probe MCP initialize and tools/list before reporting connected.
- Guide the user through connector registration without reading the ChatGPT browser session.

Implementation plan: `docs/superpowers/plans/2026-08-22-web-chat-connector-setup.md`.

Status: completed in source on 2026-08-22. Electron main verifies the exact active HTTPS endpoint with the transient bearer credential by completing bounded MCP `initialize` and `tools/list` calls before setup values become available. The renderer receives only redacted server/protocol/tool-count metadata. URL and credential handoff are separate, explicit user actions: Electron writes directly to the OS clipboard, never returns the bearer through IPC, and clears an unchanged credential after 60 seconds. The Web Chat panel provides a concise user-guided ChatGPT custom-app checklist; it does not inspect or automate the embedded website, read cookies, extract OAuth, or fill forms. Verification is cleared when the tunnel, endpoint, credential generation, grant, sidecar, or workspace changes. Approval bridging was intentionally excluded from Phase 5 and is completed separately in Phase 6 below.

### Phase 6: Approval bridge

- Route write, execute, and ambiguous tools through the existing approval system.
- Bind approval IDs to the active tunnel generation and reject stale decisions.
- Display complete arguments and diffs; timeout and close mean deny.

Implementation plan: `docs/superpowers/plans/2026-08-22-web-chat-approval-bridge.md`.

Status: completed in source on 2026-08-22. The local gateway exposes the ten existing bounded workspace tools with explicit read-only and destructive annotations. Read-only inspection calls stay direct. Writes, edits, backup restore, allowlisted verification, and workspace-bound provider side effects reuse the native approval engine and the selected Manual/Trusted/Full profile. Approval payloads carry full arguments, diffs or exact verification commands, grant identity, workspace, and tunnel generation. Side effects check the active generation both before and after approval; disconnect, expiry, grant replacement/revoke, and sidecar close cancel pending prompts and stale decisions fail closed. React temporarily hides the isolated website `WebContentsView` while a native Web Chat approval card is present, then restores it after resolution. No arbitrary shell, unrestricted code execution, cookie/OAuth access, or permanent approval rule was introduced.

### Phase 7: Activity and audit

- Show transient, truthful tool activity without persisting it as conversation messages.
- Record connector, tool, redacted arguments, decision, status, workspace, and timestamps.

### Phase 8: Release verification

- Verify login persistence, navigation, popup login, workspace containment, tunnel teardown, stale approval rejection, update survival, and installer behavior.
- Keep both existing desktop update paths unchanged.

## Phase 1 acceptance criteria

- Selecting Web Chat shows the real ChatGPT website inside the main application content area.
- Switching back to Chat/Cowork/Code hides the website and restores the unchanged native surface.
- The dedicated partition is persistent and no preload or Node access is attached to the website.
- Renderer IPC cannot request arbitrary URLs or access browser storage.
- Navigation status is transient and no Web Chat item is written to native session history.
- Frontend tests, backend tests, and production build remain green.

## Phase 2 acceptance criteria

- The user can grant exactly one registered project and choose `manual`, `trusted`, or `full` as the requested permission profile.
- The canonical real directory, display name, profile, grant ID, timestamp, and revision survive an Electron restart without sharing data with the website login partition.
- Changing workspace or profile persists revocation before the replacement grant; explicit revoke leaves no active grant.
- Invalid, missing, non-directory, corrupt, or stale paths fail closed.
- The renderer receives `toolsEnabled: false` and `tunnelConnected: false`; Phase 2 cannot read or write workspace files and cannot expose tools to ChatGPT.
- Frontend tests, backend tests, production build, and an isolated Electron persistence smoke remain green.
