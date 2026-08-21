import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import WebChatPanel from "../components/WebChatPanel";

class ResizeObserverStub {
  observe() {}
  disconnect() {}
}

describe("WebChatPanel", () => {
  afterEach(() => {
    delete global.ResizeObserver;
  });

  it("shows the isolated browser surface, provides navigation, and hides it on unmount", async () => {
    global.ResizeObserver = ResizeObserverStub;
    const bridge = {
      showWebChat: vi.fn().mockResolvedValue({ ok: true }),
      hideWebChat: vi.fn().mockResolvedValue({ ok: true }),
      controlWebChat: vi.fn().mockResolvedValue({ ok: true }),
      getWebChatState: vi.fn().mockResolvedValue({
        loading: false,
        title: "ChatGPT",
        url: "https://chatgpt.com/",
        canGoBack: true,
        canGoForward: false,
      }),
      subscribeWebChatState: vi.fn(() => () => {}),
    };

    const { unmount } = render(<WebChatPanel bridge={bridge} />);

    await waitFor(() => expect(bridge.showWebChat).toHaveBeenCalled());
    expect(screen.getByText("ChatGPT Web")).toBeInTheDocument();
    expect(screen.getByText("chatgpt.com")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Web Chat back" }));
    fireEvent.click(screen.getByRole("button", { name: "Reload Web Chat" }));
    fireEvent.click(screen.getByRole("button", { name: "Open Web Chat in browser" }));

    expect(bridge.controlWebChat).toHaveBeenNthCalledWith(1, "back");
    expect(bridge.controlWebChat).toHaveBeenNthCalledWith(2, "reload");
    expect(bridge.controlWebChat).toHaveBeenNthCalledWith(3, "open-external");

    unmount();
    expect(bridge.hideWebChat).toHaveBeenCalledTimes(1);
  });

  it("hides the native Web Chat surface while an approval is pending and restores it afterward", async () => {
    global.ResizeObserver = ResizeObserverStub;
    const bridge = {
      showWebChat: vi.fn().mockResolvedValue({ ok: true }),
      hideWebChat: vi.fn().mockResolvedValue({ ok: true }),
      getWebChatState: vi.fn().mockResolvedValue({ loading: false, url: "https://chatgpt.com/" }),
      subscribeWebChatState: () => () => {},
      getWebChatGrantState: vi.fn().mockResolvedValue({ grant: null, toolsEnabled: false, tunnelConnected: false }),
      subscribeWebChatGrantState: () => () => {},
    };

    const { rerender } = render(<WebChatPanel bridge={bridge} approvalPending={false} />);
    await waitFor(() => expect(bridge.showWebChat).toHaveBeenCalled());
    bridge.showWebChat.mockClear();
    bridge.hideWebChat.mockClear();

    rerender(<WebChatPanel bridge={bridge} approvalPending />);
    await waitFor(() => expect(bridge.hideWebChat).toHaveBeenCalled());
    expect(bridge.showWebChat).not.toHaveBeenCalled();

    bridge.showWebChat.mockClear();
    rerender(<WebChatPanel bridge={bridge} approvalPending={false} />);
    await waitFor(() => expect(bridge.showWebChat).toHaveBeenCalled());
  });

  it("grants one registered workspace with an explicit profile and can revoke it", async () => {
    global.ResizeObserver = ResizeObserverStub;
    const setWebChatGrant = vi.fn().mockResolvedValue({
      grant: { id: "grant-1", workspacePath: "C:/Work/A-Mod", workspaceName: "A-Mod", permissionMode: "trusted" },
      toolsEnabled: true,
      tunnelConnected: false,
      localGateway: {
        status: "ready",
        toolCount: 3,
        tools: [{ name: "list_directory" }, { name: "search_files" }, { name: "read_file" }],
      },
    });
    const revokeWebChatGrant = vi.fn().mockResolvedValue({ grant: null, toolsEnabled: false, tunnelConnected: false });
    const bridge = {
      showWebChat: vi.fn().mockResolvedValue({ ok: true }),
      hideWebChat: vi.fn().mockResolvedValue({ ok: true }),
      controlWebChat: vi.fn().mockResolvedValue({ ok: true }),
      getWebChatState: vi.fn().mockResolvedValue({ loading: false, url: "https://chatgpt.com/" }),
      subscribeWebChatState: () => () => {},
      getWebChatGrantState: vi.fn().mockResolvedValue({ grant: null, toolsEnabled: false, tunnelConnected: false }),
      subscribeWebChatGrantState: () => () => {},
      setWebChatGrant,
      revokeWebChatGrant,
    };

    render(<WebChatPanel bridge={bridge} projects={[{ path: "C:/Work/A-Mod", name: "A-Mod" }]} />);
    fireEvent.click(screen.getByRole("button", { name: "Web Chat workspace access" }));
    expect(screen.getByText("Local tools off")).toBeInTheDocument();
    expect(screen.getByText("Tunnel off")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Web Chat permission profile"), { target: { value: "trusted" } });
    fireEvent.click(screen.getByRole("button", { name: "Grant A-Mod" }));
    await waitFor(() => expect(setWebChatGrant).toHaveBeenCalledWith({
      workspacePath: "C:/Work/A-Mod",
      workspaceName: "A-Mod",
      permissionMode: "trusted",
    }));
    expect(await screen.findByRole("button", { name: "Revoke Web Chat workspace access" })).toBeInTheDocument();
    expect(screen.getByText("3 local tools")).toBeInTheDocument();
    expect(screen.getByText("read_file")).toBeInTheDocument();
    expect(screen.getByText(/not shared with ChatGPT until a tunnel/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Revoke Web Chat workspace access" }));
    await waitFor(() => expect(revokeWebChatGrant).toHaveBeenCalledOnce());
  });

  it("starts and stops an authenticated tunnel only after local tools are ready", async () => {
    global.ResizeObserver = ResizeObserverStub;
    const startWebChatTunnel = vi.fn().mockResolvedValue({ ok: true });
    const stopWebChatTunnel = vi.fn().mockResolvedValue({ ok: true });
    let grantListener;
    const bridge = {
      showWebChat: vi.fn().mockResolvedValue({ ok: true }),
      hideWebChat: vi.fn().mockResolvedValue({ ok: true }),
      controlWebChat: vi.fn().mockResolvedValue({ ok: true }),
      getWebChatState: vi.fn().mockResolvedValue({ loading: false, url: "https://chatgpt.com/" }),
      subscribeWebChatState: () => () => {},
      getWebChatGrantState: vi.fn().mockResolvedValue({
        grant: { id: "grant-1", workspacePath: "C:/Work/A", workspaceName: "A", permissionMode: "manual" },
        toolsEnabled: true,
        tunnelConnected: false,
        localGateway: { status: "ready", toolCount: 3, tools: [{ name: "read_file" }] },
        tunnel: { status: "off", provider: "", endpoint: "", authRequired: false },
      }),
      subscribeWebChatGrantState: (listener) => { grantListener = listener; return () => {}; },
      startWebChatTunnel,
      stopWebChatTunnel,
    };
    render(<WebChatPanel bridge={bridge} />);
    fireEvent.click(screen.getByRole("button", { name: "Web Chat workspace access" }));
    const connect = await screen.findByRole("button", { name: "Connect Web Chat tunnel" });
    expect(connect).toBeEnabled();
    fireEvent.click(connect);
    await waitFor(() => expect(startWebChatTunnel).toHaveBeenCalledWith({ provider: "cloudflare" }));

    grantListener({
      grant: { id: "grant-1", workspacePath: "C:/Work/A", workspaceName: "A", permissionMode: "manual" },
      toolsEnabled: true,
      tunnelConnected: true,
      localGateway: { status: "ready", toolCount: 3, tools: [{ name: "read_file" }] },
      tunnel: { status: "connected", provider: "cloudflare", endpoint: "https://random.trycloudflare.com/mcp", authRequired: true, expiresAt: "2026-08-21T23:00:00+00:00" },
    });
    const disconnect = await screen.findByRole("button", { name: "Disconnect Web Chat tunnel" });
    expect(screen.getByText("Tunnel connected")).toBeInTheDocument();
    expect(screen.getByText("random.trycloudflare.com")).toBeInTheDocument();
    fireEvent.click(disconnect);
    await waitFor(() => expect(stopWebChatTunnel).toHaveBeenCalledOnce());
  });

  it("verifies the public connector and offers explicit copy-only setup actions", async () => {
    global.ResizeObserver = ResizeObserverStub;
    const probeWebChatConnector = vi.fn().mockResolvedValue({ ok: true });
    const copyWebChatConnectorValue = vi.fn().mockResolvedValue({ ok: true, copied: "endpoint" });
    let grantListener;
    const bridge = {
      showWebChat: vi.fn().mockResolvedValue({ ok: true }),
      hideWebChat: vi.fn().mockResolvedValue({ ok: true }),
      controlWebChat: vi.fn().mockResolvedValue({ ok: true }),
      getWebChatState: vi.fn().mockResolvedValue({ loading: false, url: "https://chatgpt.com/" }),
      subscribeWebChatState: () => () => {},
      getWebChatGrantState: vi.fn().mockResolvedValue({
        grant: { id: "grant-1", workspacePath: "C:/Work/A", workspaceName: "A", permissionMode: "manual" },
        toolsEnabled: true,
        tunnelConnected: true,
        localGateway: { status: "ready", toolCount: 3, tools: [{ name: "read_file" }] },
        tunnel: { status: "connected", provider: "cloudflare", endpoint: "https://example.test/mcp", authRequired: true },
        connectorSetup: { status: "unverified", endpoint: "https://example.test/mcp", authentication: "bearer", toolCount: 0 },
      }),
      subscribeWebChatGrantState: (listener) => { grantListener = listener; return () => {}; },
      probeWebChatConnector,
      copyWebChatConnectorValue,
    };

    render(<WebChatPanel bridge={bridge} />);
    fireEvent.click(screen.getByRole("button", { name: "Web Chat workspace access" }));
    expect(await screen.findByText("Register in ChatGPT")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy Web Chat connector URL" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Copy Web Chat bearer credential" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Verify Web Chat connector" }));
    await waitFor(() => expect(probeWebChatConnector).toHaveBeenCalledOnce());

    grantListener({
      grant: { id: "grant-1", workspacePath: "C:/Work/A", workspaceName: "A", permissionMode: "manual" },
      toolsEnabled: true,
      tunnelConnected: true,
      localGateway: { status: "ready", toolCount: 3, tools: [{ name: "read_file" }] },
      tunnel: { status: "connected", provider: "cloudflare", endpoint: "https://example.test/mcp", authRequired: true },
      connectorSetup: {
        status: "verified",
        endpoint: "https://stale.example.test/mcp",
        authentication: "bearer",
        toolCount: 3,
      },
    });
    expect(screen.getByRole("button", { name: "Copy Web Chat connector URL" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Copy Web Chat bearer credential" })).toBeDisabled();

    grantListener({
      grant: { id: "grant-1", workspacePath: "C:/Work/A", workspaceName: "A", permissionMode: "manual" },
      toolsEnabled: true,
      tunnelConnected: true,
      localGateway: { status: "ready", toolCount: 3, tools: [{ name: "read_file" }] },
      tunnel: { status: "connected", provider: "cloudflare", endpoint: "https://example.test/mcp", authRequired: true },
      connectorSetup: {
        status: "verified",
        endpoint: "https://example.test/mcp",
        authentication: "bearer",
        serverName: "AI Dev Co-worker Web Chat Gateway",
        protocolVersion: "2025-06-18",
        toolCount: 3,
        checkedAt: "2026-08-22T10:00:00.000Z",
      },
    });
    expect(await screen.findByText("Verified: 3 tools")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Copy Web Chat connector URL" }));
    fireEvent.click(screen.getByRole("button", { name: "Copy Web Chat bearer credential" }));
    await waitFor(() => {
      expect(copyWebChatConnectorValue).toHaveBeenNthCalledWith(1, "endpoint");
      expect(copyWebChatConnectorValue).toHaveBeenNthCalledWith(2, "credential");
    });
  });
});
