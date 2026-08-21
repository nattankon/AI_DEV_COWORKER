import { describe, expect, it } from "vitest";
import {
  emptyWebChatGatewayState,
  emptyWebChatTunnelState,
  mergeWebChatGatewayState,
  normalizeWebChatGatewayState,
  normalizeWebChatTunnelState,
} from "../../electron/webChatGatewayState.js";

const grantState = {
  revision: 7,
  grant: { id: "grant-7", workspacePath: "C:/Work/A", workspaceName: "A", permissionMode: "manual" },
  toolsEnabled: false,
  tunnelConnected: false,
};

describe("webChatGatewayState", () => {
  it("enables only a ready gateway matching the active grant generation", () => {
    const gateway = normalizeWebChatGatewayState({
      status: "ready",
      grant_id: "grant-7",
      grant_revision: 7,
      workspace_path: "C:/Work/A",
      tools_enabled: true,
      tunnel_connected: false,
      tool_count: 3,
      tools: [{ name: "read_file", annotations: { readOnlyHint: true } }],
    });

    expect(mergeWebChatGatewayState(grantState, gateway, emptyWebChatTunnelState())).toMatchObject({
      toolsEnabled: true,
      tunnelConnected: false,
      localGateway: { status: "ready", toolCount: 3 },
    });
  });

  it("fails closed for stale, missing, or malformed gateway state", () => {
    const stale = normalizeWebChatGatewayState({ status: "ready", grant_id: "old", grant_revision: 6, tools_enabled: true });
    const merged = mergeWebChatGatewayState(grantState, stale, emptyWebChatTunnelState());

    expect(merged.toolsEnabled).toBe(false);
    expect(merged.tunnelConnected).toBe(false);
    expect(merged.localGateway.status).toBe("starting");
    expect(mergeWebChatGatewayState({ ...grantState, grant: null }, emptyWebChatGatewayState(), emptyWebChatTunnelState()).localGateway.status).toBe("off");

    const wrongWorkspace = normalizeWebChatGatewayState({
      status: "ready",
      grant_id: "grant-7",
      grant_revision: 7,
      workspace_path: "C:/Work/Other",
      tools_enabled: true,
    });
    expect(mergeWebChatGatewayState(grantState, wrongWorkspace, emptyWebChatTunnelState()).toolsEnabled).toBe(false);
  });

  it("accepts only redacted connected tunnel state matching the active grant", () => {
    const gateway = normalizeWebChatGatewayState({
      status: "ready", grant_id: "grant-7", grant_revision: 7, workspace_path: "C:/Work/A", tools_enabled: true,
    });
    const tunnel = normalizeWebChatTunnelState({
      status: "connected",
      provider: "cloudflare",
      grant_id: "grant-7",
      grant_revision: 7,
      workspace_path: "C:/Work/A",
      endpoint: "https://random.trycloudflare.com/mcp",
      auth_required: true,
      expires_at: "2026-08-21T23:00:00+00:00",
      credential: "must-not-survive",
    });
    const merged = mergeWebChatGatewayState(grantState, gateway, tunnel);
    expect(merged.tunnelConnected).toBe(true);
    expect(merged.tunnel).toMatchObject({ status: "connected", provider: "cloudflare", authRequired: true });
    expect(JSON.stringify(merged)).not.toContain("must-not-survive");

    const stale = normalizeWebChatTunnelState({ ...tunnel, grant_id: "old", status: "connected" });
    expect(mergeWebChatGatewayState(grantState, gateway, stale).tunnelConnected).toBe(false);
  });
});
