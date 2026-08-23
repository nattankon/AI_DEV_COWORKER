const ALLOWED_STATUS = new Set(["unverified", "verifying", "verified", "error"]);

export function emptyWebChatConnectorSetupState(status = "unverified") {
  return {
    status: ALLOWED_STATUS.has(status) ? status : "unverified",
    endpoint: "",
    authentication: "bearer",
    serverName: "",
    protocolVersion: "",
    toolCount: 0,
    checkedAt: "",
    error: "",
  };
}

export function normalizeWebChatConnectorSetupState(value) {
  const raw = value && typeof value === "object" ? value : {};
  const endpoint = String(raw.endpoint || "");
  return {
    status: ALLOWED_STATUS.has(String(raw.status || "")) ? String(raw.status) : "error",
    endpoint: endpoint.startsWith("https://") ? endpoint : "",
    authentication: raw.authentication === "bearer" ? "bearer" : "bearer",
    serverName: String(raw.serverName ?? raw.server_name ?? ""),
    protocolVersion: String(raw.protocolVersion ?? raw.protocol_version ?? ""),
    toolCount: Math.max(0, Number(raw.toolCount ?? raw.tool_count ?? 0) || 0),
    checkedAt: String(raw.checkedAt ?? raw.checked_at ?? ""),
    error: String(raw.error || ""),
  };
}

function publicError(endpoint, message) {
  return normalizeWebChatConnectorSetupState({
    status: "error",
    endpoint,
    authentication: "bearer",
    error: message,
  });
}

async function readJsonRpc(response, stage) {
  if (response.status === 401 || response.status === 403) {
    throw new Error("Connector authentication was rejected. Reconnect the tunnel and try again.");
  }
  if (!response.ok) {
    throw new Error(`${stage} failed with HTTP ${response.status}.`);
  }
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error(`${stage} returned invalid JSON.`);
  }
  if (!payload || typeof payload !== "object") throw new Error(`${stage} returned an invalid response.`);
  if (payload.error) throw new Error(`${stage} failed: ${String(payload.error.message || "MCP error")}`);
  return payload.result && typeof payload.result === "object" ? payload.result : {};
}

export async function probeRemoteMcp({
  endpoint,
  credential,
  fetchImpl = globalThis.fetch,
  timeoutMs = 8_000,
  retryAttempts = 3,
  retryDelayMs = 500,
  now = () => new Date(),
}) {
  const remoteEndpoint = String(endpoint || "").trim();
  const token = String(credential || "");
  if (!remoteEndpoint.startsWith("https://")) return publicError("", "Connector endpoint must use HTTPS.");
  if (!token) return publicError(remoteEndpoint, "Connector credential is unavailable. Reconnect the tunnel.");
  if (typeof fetchImpl !== "function") return publicError(remoteEndpoint, "Connector probe is unavailable in this runtime.");

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), Math.max(100, Number(timeoutMs) || 8_000));
  const headers = {
    Accept: "application/json, text/event-stream",
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
  const fetchReachable = async (options) => {
    const retries = Math.max(0, Number(retryAttempts) || 0);
    for (let attempt = 0; ; attempt += 1) {
      try {
        return await fetchImpl(remoteEndpoint, options);
      } catch (error) {
        if (error?.name === "AbortError" || attempt >= retries) throw error;
        await new Promise((resolve) => setTimeout(resolve, Math.max(0, Number(retryDelayMs) || 0)));
        if (controller.signal.aborted) {
          const aborted = new Error("Connector probe aborted.");
          aborted.name = "AbortError";
          throw aborted;
        }
      }
    }
  };
  try {
    const initializeResponse = await fetchReachable({
      method: "POST",
      headers,
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "initialize",
        params: {
          protocolVersion: "2025-06-18",
          capabilities: {},
          clientInfo: { name: "AI Dev Co-worker Connector Probe", version: "1.0" },
        },
      }),
      signal: controller.signal,
    });
    const initialized = await readJsonRpc(initializeResponse, "MCP initialize");
    const sessionId = String(initializeResponse.headers?.get?.("mcp-session-id") || "");
    const listHeaders = { ...headers };
    if (sessionId) listHeaders["Mcp-Session-Id"] = sessionId;
    const toolsResponse = await fetchReachable({
      method: "POST",
      headers: listHeaders,
      body: JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list", params: {} }),
      signal: controller.signal,
    });
    const listed = await readJsonRpc(toolsResponse, "MCP tools/list");
    const tools = Array.isArray(listed.tools) ? listed.tools : [];
    return normalizeWebChatConnectorSetupState({
      status: "verified",
      endpoint: remoteEndpoint,
      authentication: "bearer",
      serverName: initialized.serverInfo?.name || "MCP server",
      protocolVersion: initialized.protocolVersion || "",
      toolCount: tools.length,
      checkedAt: now().toISOString(),
    });
  } catch (error) {
    const message = error?.name === "AbortError"
      ? "Connector probe timed out. Confirm the tunnel is reachable and try again."
      : String(error?.message || error || "Connector probe failed.");
    return publicError(remoteEndpoint, message);
  } finally {
    clearTimeout(timeout);
  }
}

export function writeConnectorClipboard({
  clipboard,
  kind,
  endpoint,
  credential,
  schedule = setTimeout,
}) {
  const requested = String(kind || "");
  if (requested === "endpoint") {
    clipboard.writeText(String(endpoint || ""));
    return { ok: true, copied: "endpoint" };
  }
  if (requested !== "credential" || !credential) return { ok: false, error: "Unsupported connector setup value." };
  const copiedCredential = String(credential);
  clipboard.writeText(copiedCredential);
  const timer = schedule(() => {
    if (clipboard.readText() === copiedCredential) clipboard.clear();
  }, 60_000);
  timer?.unref?.();
  return { ok: true, copied: "credential", clearsInSeconds: 60 };
}
