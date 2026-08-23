import path from "node:path";

function comparablePath(value) {
  const normalized = path.resolve(String(value || ""));
  return process.platform === "win32" ? normalized.toLocaleLowerCase("en-US") : normalized;
}

export function emptyWebChatGatewayState(status = "off") {
  return {
    status,
    grantId: "",
    grantRevision: 0,
    permissionMode: "manual",
    workspacePath: "",
    toolsEnabled: false,
    tunnelConnected: false,
    toolCount: 0,
    tools: [],
    error: "",
  };
}

export function emptyWebChatTunnelState(status = "off") {
  return {
    status,
    provider: "",
    grantId: "",
    grantRevision: 0,
    workspacePath: "",
    endpoint: "",
    connectorMode: "url",
    tunnelId: "",
    authRequired: false,
    expiresAt: "",
    toolCount: 0,
    error: "",
  };
}

export function normalizeWebChatTunnelState(value) {
  const raw = value && typeof value === "object" ? value : {};
  const status = ["off", "starting", "connected", "error"].includes(String(raw.status || ""))
    ? String(raw.status)
    : "error";
  const endpoint = String(raw.endpoint || "");
  return {
    status,
    provider: String(raw.provider || ""),
    grantId: String(raw.grant_id ?? raw.grantId ?? ""),
    grantRevision: Number(raw.grant_revision ?? raw.grantRevision ?? 0),
    workspacePath: String(raw.workspace_path ?? raw.workspacePath ?? ""),
    endpoint: endpoint.startsWith("https://") ? endpoint : "",
    connectorMode: raw.connector_mode === "tunnel" || raw.connectorMode === "tunnel" ? "tunnel" : "url",
    tunnelId: String(raw.tunnel_id ?? raw.tunnelId ?? ""),
    authRequired: Boolean(raw.auth_required ?? raw.authRequired),
    expiresAt: String(raw.expires_at ?? raw.expiresAt ?? ""),
    toolCount: Math.max(0, Number(raw.tool_count ?? raw.toolCount ?? 0) || 0),
    error: String(raw.error || ""),
  };
}

export function normalizeWebChatGatewayState(value) {
  const raw = value && typeof value === "object" ? value : {};
  const status = ["off", "starting", "ready", "error"].includes(String(raw.status || ""))
    ? String(raw.status)
    : "error";
  const tools = Array.isArray(raw.tools)
    ? raw.tools.filter((tool) => tool && typeof tool === "object" && typeof tool.name === "string").map((tool) => ({ ...tool }))
    : [];
  return {
    status,
    grantId: String(raw.grant_id ?? raw.grantId ?? ""),
    grantRevision: Number(raw.grant_revision ?? raw.grantRevision ?? 0),
    permissionMode: String(raw.permission_mode ?? raw.permissionMode ?? "manual"),
    workspacePath: String(raw.workspace_path ?? raw.workspacePath ?? ""),
    toolsEnabled: status === "ready" && Boolean(raw.tools_enabled ?? raw.toolsEnabled),
    tunnelConnected: false,
    toolCount: Math.max(0, Number(raw.tool_count ?? raw.toolCount ?? tools.length) || 0),
    tools,
    error: String(raw.error || ""),
  };
}

export function mergeWebChatGatewayState(grantState, gatewayState, tunnelState = emptyWebChatTunnelState()) {
  const base = grantState && typeof grantState === "object" ? grantState : { revision: 0, grant: null };
  const grant = base.grant && typeof base.grant === "object" ? base.grant : null;
  const gateway = normalizeWebChatGatewayState(gatewayState);
  if (!grant) {
    return {
      ...base,
      toolsEnabled: false,
      tunnelConnected: false,
      localGateway: emptyWebChatGatewayState(),
      tunnel: emptyWebChatTunnelState(),
    };
  }
  const matches = gateway.grantId === String(grant.id || "")
    && gateway.grantRevision === Number(base.revision || 0)
    && comparablePath(gateway.workspacePath) === comparablePath(grant.workspacePath);
  const localGateway = matches ? gateway : { ...emptyWebChatGatewayState("starting"), grantId: String(grant.id || ""), grantRevision: Number(base.revision || 0) };
  const tunnel = normalizeWebChatTunnelState(tunnelState);
  const tunnelMatches = matches
    && localGateway.toolsEnabled
    && tunnel.grantId === String(grant.id || "")
    && tunnel.grantRevision === Number(base.revision || 0)
    && comparablePath(tunnel.workspacePath) === comparablePath(grant.workspacePath);
  const activeTunnel = tunnelMatches
    ? tunnel
    : { ...emptyWebChatTunnelState(tunnel.status === "error" ? "error" : "off"), error: tunnel.status === "error" ? tunnel.error : "" };
  return {
    ...base,
    toolsEnabled: matches && localGateway.toolsEnabled,
    tunnelConnected: tunnelMatches && activeTunnel.status === "connected",
    localGateway,
    tunnel: activeTunnel,
  };
}
