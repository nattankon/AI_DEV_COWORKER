# OpenAI Secure MCP Tunnel Provider Plan

**Goal:** Add a real OpenAI Secure MCP Tunnel path beside the existing Cloudflare URL path so the embedded ChatGPT plugin form can use its current **Tunnel** connection option without weakening the local MCP bearer boundary.

**Architecture:** The Python sidecar continues to own the loopback MCP server and workspace-generation checks. A new adapter launches the official `tunnel-client` process with a tunnel ID and runtime API key, forwards the existing local bearer through `mcp.extra_headers`, and reports connected only after the runtime `/readyz` endpoint succeeds. Electron keeps runtime secrets transient and out of renderer/public state. Cloudflare remains available as a separate URL-server provider.

## Task 1: Backend adapter and lifecycle

- Add failing tests for missing runtime, redacted process launch, ready-state probing, process-tree cleanup, and provider metadata.
- Add `OpenAISecureTunnelAdapter` with bounded startup, a private health URL file, environment-backed secrets, local MCP authorization headers, and complete process cleanup.
- Extend `WebChatTunnelController.start` with provider options while preserving existing adapters and tests.
- Expose only non-secret connector metadata (`connector_mode`, `tunnel_id`) in public state and audit events.

## Task 2: IPC and Electron state

- Add failing IPC/state tests for OpenAI provider payloads and secret redaction.
- Accept `openai` as a tunnel provider, validate tunnel ID/runtime key, generate the existing local bearer, and pass OpenAI-only options to the sidecar.
- Treat backend readiness as connector verification for Tunnel mode; keep remote URL probing unchanged for Cloudflare mode.
- Allow copying only the non-secret tunnel ID for Tunnel registration.

## Task 3: Web workspace UI

- Add failing React tests for provider selection, required fields, OpenAI payload shape, Tunnel-specific registration instructions, and retained Cloudflare behavior.
- Add a provider dropdown with `OpenAI Secure Tunnel` and `Cloudflare Quick Tunnel`.
- Show tunnel ID and password-masked runtime API key only for OpenAI.
- Use current ChatGPT terminology: create a **plugin**, select **Tunnel**, and choose/paste the tunnel ID. Never instruct Tunnel users to paste the local runtime key or bearer credential into ChatGPT.

## Task 4: Verification and release

- Run focused backend/frontend tests, then complete backend/frontend suites and production build.
- Update `PROJECT_STATE.md` and append `work_logs/WORK_LOG.md` without secrets.
- Bump the desktop release, build installer/updater artifacts, smoke the packaged app, publish commit/tag/release, and verify the public updater manifest.

