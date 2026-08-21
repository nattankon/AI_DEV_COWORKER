# Web Chat Bridge Phase 6: Approval-Gated Tools

Status: completed in source on 2026-08-22.

## Goal

Expose the existing workspace tool capabilities through the authenticated Web Chat MCP tunnel without creating a second permission system. Read-only calls remain direct. Writes, restores, provider side effects, and allowlisted verification runs use the same approval policy, diff display, rollback path, and audit trail as native Cowork.

## Scope

1. Expand the local gateway catalog to all existing `WorkspaceTools` operations with explicit read-only/destructive annotations.
2. Require the exact active tunnel generation for every remote side-effect call.
3. Carry the complete remote tool arguments, workspace grant, tunnel generation, and generated file diff into the existing approval payload.
4. Cancel outstanding Web Chat approvals when the tunnel stops, expires, errors, or the workspace grant changes. Timeout, close, stale decisions, and unknown decisions remain deny-by-default.
5. Temporarily hide the embedded `WebContentsView` while the native approval prompt is visible, then restore it after the decision so the prompt cannot be obscured by the Chromium surface.
6. Preserve existing permission profiles: Manual prompts for every side effect, Trusted may skip prompts only for routine local writes and verification, and Full may skip known prompts while workspace containment, Secret Guard, allowlists, atomic writes, rollback, and auditing still execute.

## Non-goals

- No arbitrary shell command or unrestricted code execution is exposed.
- No cookie, OAuth token, or ChatGPT DOM access is added.
- No approval memory or permanent allow rule is added.
- No release/version bump is included in this implementation batch.

## Verification

- Backend tests cover catalog annotations, read calls without approval, write/edit/restore/verification decisions, complete approval context, stale tunnel generations, timeout/revoke cancellation, and permission profile parity.
- Tunnel tests prove the current generation is forwarded and disconnect invalidates a pending side effect.
- Frontend tests prove Web Chat hides while approval is pending, shows the full approval payload, sends allow/deny through the existing bridge, and restores the embedded surface after resolution.
- Run the complete backend and frontend suites, production frontend build, and an isolated Electron smoke before completion.

## Result

- The authenticated tunnel now exposes all ten existing `WorkspaceTools` operations. Six inspection operations are read-only; writes, edits, backup restoration, and allowlisted verification use the existing approval engine and permission profiles.
- Every remote side effect requires the exact active tunnel generation before approval and is checked again after approval. Tunnel stop, expiry, replacement, revoke, and sidecar close cancel pending Web Chat approvals and prevent stale decisions from executing.
- Approval cards identify Web Chat as the origin and include the complete arguments, workspace/grant identity, tunnel generation, exact verification command, and generated file diff. The native website surface is hidden while the prompt is visible and restored after resolution.
- Workspace containment, Secret Guard, fixed verification presets, atomic writes, rollback backups, and audit events remain the enforcement boundary. No arbitrary shell, unrestricted Python execution, approval memory, cookie access, or OAuth extraction was added.
