# Web Chat Bridge Phase 5: Connector Setup

Status: completed in source on 2026-08-22.

## Goal

Turn an authenticated Phase 4 tunnel into an explicitly verified, user-guided ChatGPT custom-app setup without reading or automating the embedded ChatGPT session.

## Scope

1. Probe the public MCP endpoint from Electron main with the transient bearer credential by completing `initialize` and `tools/list`.
2. Expose only redacted verification metadata to the renderer: status, server name, protocol version, tool count, checked time, endpoint, workspace, and error.
3. Let the user copy the endpoint or bearer credential through a narrow Electron IPC command. Electron writes directly to the OS clipboard and returns only success metadata; the credential never enters renderer state, logs, or the Web Chat page automatically.
4. Show a concise registration checklist in the Web Chat workspace-access panel. The user remains responsible for enabling ChatGPT developer mode and creating/scanning the custom app.

## Invariants

- Connector verification is valid only for the exact current grant ID, grant revision, canonical workspace, endpoint, and tunnel credential generation.
- Tunnel stop, adapter error, credential expiry, grant replacement, grant revoke, or sidecar exit clears verification state.
- A failed probe does not weaken authentication or restart an unauthenticated endpoint.
- No DOM automation, cookie access, OAuth extraction, remote preload, or automatic form filling is added.
- Clipboard credential handoff is explicit and user initiated. The clipboard is cleared after a short interval only when it still contains the exact copied credential.
- Phase 6 write/execute approval work is not included.

## Verification

- Unit tests cover successful initialize/tools-list probing, bearer rejection, timeout/error redaction, stale setup-state rejection, and clipboard handoff without returning the secret.
- Frontend tests cover the setup checklist, probe action, verified metadata, and copy actions.
- Full backend and frontend suites, production build, and an isolated Electron smoke remain green.
