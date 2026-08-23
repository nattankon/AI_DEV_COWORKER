import { afterEach, describe, expect, it, vi } from "vitest";

import {
  canCopyConnectorSetupValue,
  emptyWebChatConnectorSetupState,
  normalizeWebChatConnectorSetupState,
  probeRemoteMcp,
  writeConnectorClipboard,
} from "../../electron/webChatConnectorSetup.js";

function jsonResponse(payload, { status = 200, headers = {} } = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

describe("web chat connector setup", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("probes initialize and tools/list with bearer authentication", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        jsonrpc: "2.0",
        id: 1,
        result: {
          protocolVersion: "2025-06-18",
          serverInfo: { name: "AI Dev Co-worker Web Chat Gateway", version: "1.0" },
        },
      }, { headers: { "mcp-session-id": "session-1" } }))
      .mockResolvedValueOnce(jsonResponse({
        jsonrpc: "2.0",
        id: 2,
        result: { tools: [{ name: "list_directory" }, { name: "read_file" }] },
      }));

    const result = await probeRemoteMcp({
      endpoint: "https://example.test/mcp",
      credential: "top-secret",
      fetchImpl,
      now: () => new Date("2026-08-22T10:00:00.000Z"),
    });

    expect(result).toEqual({
      status: "verified",
      endpoint: "https://example.test/mcp",
      authentication: "bearer",
      serverName: "AI Dev Co-worker Web Chat Gateway",
      protocolVersion: "2025-06-18",
      toolCount: 2,
      checkedAt: "2026-08-22T10:00:00.000Z",
      error: "",
    });
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect(fetchImpl.mock.calls[0][1].headers.Authorization).toBe("Bearer top-secret");
    expect(fetchImpl.mock.calls[1][1].headers["Mcp-Session-Id"]).toBe("session-1");
    expect(JSON.stringify(result)).not.toContain("top-secret");
  });

  it("returns a redacted actionable error when authentication fails", async () => {
    const result = await probeRemoteMcp({
      endpoint: "https://example.test/mcp",
      credential: "never-return-this",
      fetchImpl: vi.fn().mockResolvedValue(jsonResponse({ error: "unauthorized" }, { status: 401 })),
    });

    expect(result.status).toBe("error");
    expect(result.error).toMatch(/authentication/i);
    expect(JSON.stringify(result)).not.toContain("never-return-this");
  });

  it("retries a newly-created tunnel while its public endpoint becomes reachable", async () => {
    const fetchImpl = vi.fn()
      .mockRejectedValueOnce(new TypeError("getaddrinfo failed"))
      .mockResolvedValueOnce(jsonResponse({
        jsonrpc: "2.0",
        id: 1,
        result: {
          protocolVersion: "2025-06-18",
          serverInfo: { name: "AI Dev Co-worker Web Chat Gateway", version: "1.0" },
        },
      }))
      .mockResolvedValueOnce(jsonResponse({
        jsonrpc: "2.0",
        id: 2,
        result: { tools: [{ name: "read_file" }] },
      }));

    const result = await probeRemoteMcp({
      endpoint: "https://new-tunnel.trycloudflare.com/mcp",
      credential: "top-secret",
      fetchImpl,
      retryAttempts: 2,
      retryDelayMs: 0,
    });

    expect(result.status).toBe("verified");
    expect(result.toolCount).toBe(1);
    expect(fetchImpl).toHaveBeenCalledTimes(3);
  });

  it("bounds a stalled public probe with an actionable timeout", async () => {
    vi.useFakeTimers();
    const fetchImpl = vi.fn((_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => {
        const error = new Error("aborted");
        error.name = "AbortError";
        reject(error);
      }, { once: true });
    }));

    const pending = probeRemoteMcp({
      endpoint: "https://example.test/mcp",
      credential: "never-return-this",
      fetchImpl,
      timeoutMs: 100,
    });
    await vi.advanceTimersByTimeAsync(100);
    const result = await pending;

    expect(result.status).toBe("error");
    expect(result.error).toMatch(/timed out/i);
    expect(JSON.stringify(result)).not.toContain("never-return-this");
  });

  it("normalizes only public setup metadata", () => {
    expect(normalizeWebChatConnectorSetupState({
      status: "verified",
      endpoint: "https://example.test/mcp",
      authentication: "bearer",
      serverName: "Gateway",
      protocolVersion: "2025-06-18",
      toolCount: 3,
      checkedAt: "2026-08-22T10:00:00.000Z",
      credential: "secret",
      authorization: "Bearer secret",
    })).toEqual({
      ...emptyWebChatConnectorSetupState(),
      status: "verified",
      endpoint: "https://example.test/mcp",
      authentication: "bearer",
      serverName: "Gateway",
      protocolVersion: "2025-06-18",
      toolCount: 3,
      checkedAt: "2026-08-22T10:00:00.000Z",
    });
  });

  it("keeps tunnel runtime readiness distinct from product-side verification", () => {
    expect(normalizeWebChatConnectorSetupState({
      status: "runtime_ready",
      endpoint: "https://api.openai.com/v1/mcp/tunnel_0123456789abcdef0123456789abcdef",
      authentication: "openai-tunnel",
      serverName: "OpenAI Secure MCP Tunnel",
      toolCount: 3,
    }).status).toBe("runtime_ready");
  });

  it("allows only the provider-specific setup values for each truthful state", () => {
    expect(canCopyConnectorSetupValue({ kind: "tunnel_id", connectorMode: "tunnel", status: "runtime_ready" })).toBe(true);
    expect(canCopyConnectorSetupValue({ kind: "credential", connectorMode: "tunnel", status: "runtime_ready" })).toBe(false);
    expect(canCopyConnectorSetupValue({ kind: "endpoint", connectorMode: "tunnel", status: "runtime_ready" })).toBe(false);
    expect(canCopyConnectorSetupValue({ kind: "endpoint", connectorMode: "server_url", status: "verified" })).toBe(true);
    expect(canCopyConnectorSetupValue({ kind: "credential", connectorMode: "server_url", status: "verified" })).toBe(true);
    expect(canCopyConnectorSetupValue({ kind: "tunnel_id", connectorMode: "server_url", status: "verified" })).toBe(false);
  });

  it("copies a credential without returning it and clears only the unchanged clipboard", () => {
    let clipboardText = "";
    let scheduled;
    const clipboard = {
      writeText: vi.fn((value) => { clipboardText = value; }),
      readText: vi.fn(() => clipboardText),
      clear: vi.fn(() => { clipboardText = ""; }),
    };
    const schedule = vi.fn((callback, delay) => {
      scheduled = callback;
      expect(delay).toBe(60_000);
      return { unref: vi.fn() };
    });

    expect(writeConnectorClipboard({ clipboard, kind: "credential", endpoint: "https://example.test/mcp", credential: "secret", schedule }))
      .toEqual({ ok: true, copied: "credential", clearsInSeconds: 60 });
    expect(clipboardText).toBe("secret");
    scheduled();
    expect(clipboard.clear).toHaveBeenCalledOnce();

    clipboardText = "secret";
    writeConnectorClipboard({ clipboard, kind: "credential", endpoint: "https://example.test/mcp", credential: "secret", schedule });
    clipboardText = "user copied something else";
    scheduled();
    expect(clipboard.clear).toHaveBeenCalledOnce();
  });
});
