# Web Chat Local MCP Gateway - Phase 3 Plan

## Scope

Implement only Phase 3 from `WEB_CHAT_BRIDGE_PLAN.md`. The result is a local gateway bound to the active Web Chat workspace grant. It does not start a network listener, create a tunnel, expose credentials, or let the embedded website call tools yet.

## Design

1. Add a Python gateway core that binds one canonical workspace, grant ID, grant revision, and permission profile.
2. Build a compact MCP-style catalog from an explicit read-only workspace policy. Dispatch reuses `WorkspaceTools`, preserving containment, Secret Guard, and audit behavior.
3. Keep write, verification, shell, Git, restore, and unannotated provider tools out of the catalog. Optional provider tools require trusted read-only and workspace-bound annotations.
4. Add sidecar bind, unbind, and state commands. Reject stale grant generations on every dispatch.
5. Let Electron synchronize the gateway whenever a grant is created, replaced, revoked, or restored after sidecar startup. The renderer receives only public gateway state and the compact catalog.
6. Update the Web Chat grant panel to distinguish local tool readiness from tunnel connectivity. The embedded ChatGPT `WebContentsView` remains isolated and receives no preload or IPC bridge.

## Verification

- Gateway unit tests: catalog, annotation fail-closed behavior, workspace containment, Secret Guard, stale generation, and provider dispatch seam.
- Sidecar tests: bind/unbind state and malformed/stale requests.
- Frontend tests: local gateway status/catalog and unchanged tunnel-off state.
- Full backend suite, full frontend suite, production build, and targeted browser UI verification.

## Rollback

The change is additive. Removing the gateway module and the new sidecar/Electron state wiring restores Phase 2 behavior; the persisted grant format remains unchanged.
