import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, Copy, ExternalLink, FolderOpen, KeyRound, Loader2, RefreshCw, ShieldCheck, X } from "lucide-react";

const initialState = {
  loading: true,
  title: "ChatGPT",
  url: "https://chatgpt.com/",
  canGoBack: false,
  canGoForward: false,
  error: "",
};

const initialGrantState = {
  grant: null,
  toolsEnabled: false,
  tunnelConnected: false,
  localGateway: { status: "off", toolCount: 0, tools: [], error: "" },
  tunnel: { status: "off", provider: "", endpoint: "", authRequired: false, error: "" },
  connectorSetup: { status: "unverified", endpoint: "", authentication: "bearer", serverName: "", protocolVersion: "", toolCount: 0, checkedAt: "", error: "" },
};

const permissionProfiles = [
  { id: "manual", label: "Manual control" },
  { id: "trusted", label: "Approvals only" },
  { id: "full", label: "Full access" },
];

function displayHost(url) {
  try {
    return new URL(String(url || "https://chatgpt.com/")).hostname;
  } catch {
    return "chatgpt.com";
  }
}

function displayExpiry(value) {
  const timestamp = Date.parse(String(value || ""));
  return Number.isFinite(timestamp) ? new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
}

export default function WebChatPanel({ bridge, projects = [], approvalPending = false, overlayOpen = false }) {
  const viewportRef = useRef(null);
  const [state, setState] = useState(initialState);
  const [grantState, setGrantState] = useState(initialGrantState);
  const [grantPanelOpen, setGrantPanelOpen] = useState(false);
  const [permissionMode, setPermissionMode] = useState("manual");
  const [grantBusy, setGrantBusy] = useState(false);
  const [grantError, setGrantError] = useState("");
  const [tunnelBusy, setTunnelBusy] = useState(false);
  const [tunnelError, setTunnelError] = useState("");
  const [setupBusy, setSetupBusy] = useState(false);
  const [setupNotice, setSetupNotice] = useState("");
  const autoVerifyTunnelRef = useRef(false);

  const syncBounds = useCallback(() => {
    if (approvalPending || overlayOpen) {
      void bridge?.hideWebChat?.();
      return;
    }
    const node = viewportRef.current;
    if (!node || typeof bridge?.showWebChat !== "function") return;
    const rect = node.getBoundingClientRect();
    void bridge.showWebChat({ x: rect.x, y: rect.y, width: rect.width, height: rect.height });
  }, [approvalPending, bridge, overlayOpen]);

  useEffect(() => {
    let disposed = false;
    void Promise.resolve(bridge?.getWebChatState?.()).then((nextState) => {
      if (!disposed && nextState && typeof nextState === "object") setState((current) => ({ ...current, ...nextState }));
    });
    const unsubscribe = bridge?.subscribeWebChatState?.((nextState) => {
      if (nextState && typeof nextState === "object") setState((current) => ({ ...current, ...nextState }));
    });
    void Promise.resolve(bridge?.getWebChatGrantState?.()).then((nextState) => {
      if (!disposed && nextState && typeof nextState === "object") {
        setGrantState((current) => ({ ...current, ...nextState }));
        if (nextState.grant?.permissionMode) setPermissionMode(nextState.grant.permissionMode);
      }
    });
    const unsubscribeGrant = bridge?.subscribeWebChatGrantState?.((nextState) => {
      if (!nextState || typeof nextState !== "object") return;
      setGrantState((current) => ({ ...current, ...nextState }));
      if (nextState.grant?.permissionMode) setPermissionMode(nextState.grant.permissionMode);
    });
    syncBounds();
    const observer = typeof ResizeObserver === "function" ? new ResizeObserver(syncBounds) : null;
    if (observer && viewportRef.current) observer.observe(viewportRef.current);
    window.addEventListener("resize", syncBounds);
    return () => {
      disposed = true;
      observer?.disconnect();
      window.removeEventListener("resize", syncBounds);
      unsubscribe?.();
      unsubscribeGrant?.();
      void bridge?.hideWebChat?.();
    };
  }, [bridge, syncBounds]);

  const control = (command) => void bridge?.controlWebChat?.(command);
  const grantWorkspace = async (project) => {
    if (!project?.path || grantBusy) return;
    setGrantBusy(true);
    setGrantError("");
    try {
      const result = await bridge?.setWebChatGrant?.({
        workspacePath: project.path,
        workspaceName: project.name || project.path,
        permissionMode,
      });
      if (!result?.ok && result?.error) throw new Error(result.error);
      if (result && typeof result === "object") setGrantState((current) => ({ ...current, ...result }));
    } catch (error) {
      setGrantError(error instanceof Error ? error.message : String(error));
    } finally {
      setGrantBusy(false);
    }
  };
  const revokeGrant = async () => {
    if (grantBusy) return;
    setGrantBusy(true);
    setGrantError("");
    try {
      const result = await bridge?.revokeWebChatGrant?.();
      if (!result?.ok && result?.error) throw new Error(result.error);
      if (result && typeof result === "object") setGrantState((current) => ({ ...current, ...result }));
    } catch (error) {
      setGrantError(error instanceof Error ? error.message : String(error));
    } finally {
      setGrantBusy(false);
    }
  };
  const connectTunnel = async () => {
    if (tunnelBusy || tunnel.status === "starting" || !grantState.grant || !grantState.toolsEnabled) return;
    setTunnelBusy(true);
    setTunnelError("");
    autoVerifyTunnelRef.current = true;
    try {
      const result = await bridge?.startWebChatTunnel?.({ provider: "cloudflare" });
      if (!result?.ok) throw new Error(result?.error || "Unable to connect the Web Chat tunnel.");
      setGrantState((current) => ({ ...current, ...result }));
    } catch (error) {
      autoVerifyTunnelRef.current = false;
      setTunnelError(error instanceof Error ? error.message : String(error));
    } finally {
      setTunnelBusy(false);
    }
  };
  const disconnectTunnel = async () => {
    if (tunnelBusy) return;
    autoVerifyTunnelRef.current = false;
    setTunnelBusy(true);
    setTunnelError("");
    try {
      const result = await bridge?.stopWebChatTunnel?.();
      if (!result?.ok) throw new Error(result?.error || "Unable to disconnect the Web Chat tunnel.");
      setGrantState((current) => ({ ...current, ...result }));
    } catch (error) {
      setTunnelError(error instanceof Error ? error.message : String(error));
    } finally {
      setTunnelBusy(false);
    }
  };
  const verifyConnector = useCallback(async () => {
    if (setupBusy || !grantState.tunnelConnected) return;
    setSetupBusy(true);
    setSetupNotice("");
    try {
      const result = await bridge?.probeWebChatConnector?.();
      if (!result?.ok) throw new Error(result?.error || "Connector verification failed.");
      setGrantState((current) => ({ ...current, ...result }));
    } catch (error) {
      setSetupNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setSetupBusy(false);
    }
  }, [bridge, grantState.tunnelConnected, setupBusy]);
  useEffect(() => {
    if (!autoVerifyTunnelRef.current || !grantState.tunnelConnected || grantState.connectorSetup?.status === "verified") return;
    autoVerifyTunnelRef.current = false;
    void verifyConnector();
  }, [grantState.connectorSetup?.status, grantState.tunnelConnected, verifyConnector]);
  const copySetupValue = async (kind) => {
    setSetupNotice("");
    try {
      const result = await bridge?.copyWebChatConnectorValue?.(kind);
      if (!result?.ok) throw new Error(result?.error || "Unable to copy connector setup value.");
      setSetupNotice(kind === "credential" ? "Bearer credential copied; clipboard clears in 60 seconds." : "Connector URL copied.");
    } catch (error) {
      setSetupNotice(error instanceof Error ? error.message : String(error));
    }
  };
  const buttonClass = "grid h-8 w-8 place-items-center rounded-md text-[#68665f] transition hover:bg-[#eceae4] disabled:cursor-not-allowed disabled:opacity-35";
  const localGateway = grantState.localGateway && typeof grantState.localGateway === "object"
    ? grantState.localGateway
    : initialGrantState.localGateway;
  const toolStatusLabel = localGateway.status === "ready"
    ? `${localGateway.toolCount || localGateway.tools?.length || 0} local tools`
    : localGateway.status === "starting"
      ? "Starting local tools"
      : localGateway.status === "error"
        ? "Local tools error"
        : "Local tools off";
  const tunnel = grantState.tunnel && typeof grantState.tunnel === "object"
    ? grantState.tunnel
    : initialGrantState.tunnel;
  const tunnelStatusLabel = grantState.tunnelConnected
    ? "Tunnel connected"
    : tunnel.status === "starting"
      ? "Tunnel connecting"
      : tunnel.status === "error"
        ? "Tunnel error"
        : "Tunnel off";
  const connectorSetup = grantState.connectorSetup && typeof grantState.connectorSetup === "object"
    ? grantState.connectorSetup
    : initialGrantState.connectorSetup;
  const connectorVerified = grantState.tunnelConnected
    && connectorSetup.status === "verified"
    && connectorSetup.endpoint === tunnel.endpoint;

  return (
    <section aria-label="Web Chat" className="flex h-full min-h-0 flex-col bg-white">
      <div className="flex h-11 shrink-0 items-center gap-1 border-b border-[#e6e4dd] bg-[#fafaf8] px-3">
        <button type="button" aria-label="Web Chat back" disabled={!state.canGoBack} onClick={() => control("back")} className={buttonClass}>
          <ArrowLeft size={15} />
        </button>
        <button type="button" aria-label="Web Chat forward" disabled={!state.canGoForward} onClick={() => control("forward")} className={buttonClass}>
          <ArrowRight size={15} />
        </button>
        <button type="button" aria-label="Reload Web Chat" onClick={() => control("reload")} className={buttonClass}>
          {state.loading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
        </button>
        <div className="mx-2 flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-[#e1ded7] bg-white px-3 py-1.5 text-[12px] text-[#77746d]">
          <ShieldCheck size={14} className="shrink-0 text-[#3f8f62]" />
          <strong className="shrink-0 font-medium text-[#3c3a35]">ChatGPT Web</strong>
          <span className="truncate">{displayHost(state.url)}</span>
        </div>
        <button
          type="button"
          aria-label="Web Chat workspace access"
          aria-expanded={grantPanelOpen}
          title={grantState.grant ? grantState.grant.workspaceName : "Workspace access"}
          onClick={() => setGrantPanelOpen((current) => !current)}
          className={`${buttonClass} ${grantState.grant ? "text-[#3f8f62]" : ""}`}
        >
          <FolderOpen size={15} />
        </button>
        <button type="button" aria-label="Open Web Chat in browser" onClick={() => control("open-external")} className={buttonClass}>
          <ExternalLink size={15} />
        </button>
      </div>
      {grantPanelOpen ? (
        <section aria-label="Web Chat workspace grant" className="shrink-0 border-b border-[#e6e4dd] bg-[#fafaf8] px-4 py-3 text-[12px] text-[#5f5c55]">
          <div className="flex items-center gap-2">
            <ShieldCheck size={15} className="text-[#3f8f62]" />
            <strong className="text-[13px] text-[#34322d]">Workspace access</strong>
            <span className={`rounded px-2 py-0.5 ${localGateway.status === "ready" ? "bg-[#e4f3e8] text-[#32714a]" : localGateway.status === "error" ? "bg-[#fff0ed] text-[#a6483e]" : "bg-[#eceae4]"}`}>{toolStatusLabel}</span>
            <span className={`rounded px-2 py-0.5 ${grantState.tunnelConnected ? "bg-[#e4f3e8] text-[#32714a]" : tunnel.status === "error" ? "bg-[#fff0ed] text-[#a6483e]" : "bg-[#eceae4]"}`}>{tunnelStatusLabel}</span>
            <button type="button" aria-label="Close workspace access" onClick={() => setGrantPanelOpen(false)} className="ml-auto grid h-7 w-7 place-items-center rounded-md hover:bg-[#eceae4]">
              <X size={14} />
            </button>
          </div>
          <div className="mt-3 grid grid-cols-[minmax(170px,240px)_1fr] gap-3">
            <label className="grid gap-1 text-[11px] text-[#817d74]">
              Permission profile
              <select
                aria-label="Web Chat permission profile"
                value={permissionMode}
                onChange={(event) => setPermissionMode(event.target.value)}
                className="h-9 rounded-md border border-[#dcd8cf] bg-white px-2 text-[12px] text-[#34322d] outline-none"
              >
                {permissionProfiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.label}</option>)}
              </select>
            </label>
            <div className="min-w-0">
              <div className="mb-1 text-[11px] text-[#817d74]">Registered projects</div>
              <div className="flex min-h-9 flex-wrap items-center gap-2">
                {projects.length ? projects.map((project) => (
                  <button
                    key={project.path}
                    type="button"
                    aria-label={`Grant ${project.name || project.path}`}
                    disabled={grantBusy}
                    onClick={() => grantWorkspace(project)}
                    className={`h-9 max-w-[260px] truncate rounded-md border px-3 text-left transition disabled:opacity-50 ${
                      grantState.grant?.workspacePath === project.path ? "border-[#9bc5aa] bg-[#edf7f0] text-[#2f7048]" : "border-[#dcd8cf] bg-white hover:bg-[#f3f2ee]"
                    }`}
                  >
                    {project.name || project.path}
                  </button>
                )) : <span className="text-[#9a958a]">No registered projects</span>}
              </div>
            </div>
          </div>
          {grantState.grant ? (
            <div className="mt-3 border-t border-[#e6e2da] pt-3">
              <div className="flex items-center gap-2">
                <span className="font-medium text-[#34322d]">{grantState.grant.workspaceName}</span>
                <span className="truncate text-[#8a857b]">{grantState.grant.workspacePath}</span>
                <button type="button" aria-label="Revoke Web Chat workspace access" disabled={grantBusy} onClick={revokeGrant} className="ml-auto h-8 rounded-md border border-[#e7c7c1] bg-white px-3 text-[#a6483e] hover:bg-[#fff2ef] disabled:opacity-50">
                  Revoke
                </button>
              </div>
              {localGateway.status === "ready" ? (
                <div className="mt-2">
                  <div className="flex flex-wrap gap-1.5">
                    {(localGateway.tools || []).map((tool) => (
                      <span key={tool.name} className="rounded border border-[#ddd9d0] bg-white px-2 py-1 font-mono text-[10px] text-[#5d5a53]">{tool.name}</span>
                    ))}
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <label className="grid gap-1 text-[10px] text-[#817d74]">
                      Tunnel provider
                      <select aria-label="Web Chat tunnel provider" value="cloudflare" disabled className="h-8 rounded-md border border-[#dcd8cf] bg-white px-2 text-[11px] text-[#34322d]">
                        <option value="cloudflare">Cloudflare Quick Tunnel</option>
                      </select>
                    </label>
                    {grantState.tunnelConnected ? (
                      <button type="button" aria-label="Disconnect Web Chat tunnel" disabled={tunnelBusy} onClick={disconnectTunnel} className="mt-auto h-8 rounded-md border border-[#e7c7c1] bg-white px-3 text-[#a6483e] hover:bg-[#fff2ef] disabled:opacity-50">
                        Disconnect
                      </button>
                    ) : (
                      <button type="button" aria-label="Connect Web Chat tunnel" disabled={tunnelBusy || tunnel.status === "starting" || !grantState.toolsEnabled} onClick={connectTunnel} className="mt-auto h-8 rounded-md bg-[#2f2e2a] px-3 text-white hover:bg-black disabled:opacity-40">
                        {tunnel.status === "starting" || tunnelBusy ? "Connecting..." : "Connect & verify"}
                      </button>
                    )}
                    {grantState.tunnelConnected && tunnel.endpoint ? <span className="mt-auto rounded bg-[#eceae4] px-2 py-1 font-mono text-[10px]">{displayHost(tunnel.endpoint)}</span> : null}
                    {grantState.tunnelConnected && displayExpiry(tunnel.expiresAt) ? <span className="mt-auto text-[10px] text-[#817d74]">Expires {displayExpiry(tunnel.expiresAt)}</span> : null}
                  </div>
                  {grantState.tunnelConnected ? (
                    <div className="mt-3 border-t border-[#e6e2da] pt-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <strong className="text-[12px] text-[#34322d]">Register in ChatGPT</strong>
                        <span className={`rounded px-2 py-0.5 text-[10px] ${connectorVerified ? "bg-[#e4f3e8] text-[#32714a]" : connectorSetup.status === "error" ? "bg-[#fff0ed] text-[#a6483e]" : "bg-[#eceae4] text-[#68665f]"}`}>
                          {connectorVerified ? `Verified: ${connectorSetup.toolCount} tools` : connectorSetup.status === "verifying" || setupBusy ? "Verifying..." : "Not verified"}
                        </span>
                        <button type="button" aria-label="Verify Web Chat connector" disabled={setupBusy} onClick={verifyConnector} className="ml-auto h-8 rounded-md border border-[#dcd8cf] bg-white px-3 text-[11px] hover:bg-[#f3f2ee] disabled:opacity-50">
                          {setupBusy ? "Verifying..." : "Verify"}
                        </button>
                      </div>
                      <div className="mt-2 grid gap-1.5 text-[11px] text-[#6f6b63]">
                        <div className="flex items-center gap-2"><span className="grid h-5 w-5 place-items-center rounded bg-[#eceae4] text-[10px]">1</span><span>Enable developer mode in ChatGPT Settings &gt; Apps.</span></div>
                        <div className="flex items-center gap-2"><span className="grid h-5 w-5 place-items-center rounded bg-[#eceae4] text-[10px]">2</span><span>Create a custom app and use the verified MCP endpoint.</span></div>
                        <div className="flex items-center gap-2"><span className="grid h-5 w-5 place-items-center rounded bg-[#eceae4] text-[10px]">3</span><span>Select bearer authentication, paste the credential, then scan tools.</span></div>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <button type="button" aria-label="Copy Web Chat connector URL" disabled={!connectorVerified} onClick={() => copySetupValue("endpoint")} className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[#dcd8cf] bg-white px-3 text-[11px] hover:bg-[#f3f2ee] disabled:opacity-40">
                          <Copy size={12} /> URL
                        </button>
                        <button type="button" aria-label="Copy Web Chat bearer credential" disabled={!connectorVerified} onClick={() => copySetupValue("credential")} className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[#dcd8cf] bg-white px-3 text-[11px] hover:bg-[#f3f2ee] disabled:opacity-40">
                          <KeyRound size={12} /> Credential
                        </button>
                        {connectorVerified ? <span className="inline-flex items-center gap-1 text-[10px] text-[#3f8f62]"><CheckCircle2 size={12} /> {connectorSetup.serverName || "MCP server"}</span> : null}
                      </div>
                      {connectorSetup.error || setupNotice ? <p className={`mt-2 text-[10px] ${connectorSetup.error ? "text-[#a6483e]" : "text-[#6f6b63]"}`}>{connectorSetup.error || setupNotice}</p> : null}
                    </div>
                  ) : <p className="mt-2 text-[11px] text-[#8a857b]">Local gateway only; tools are not shared with ChatGPT until a tunnel is explicitly connected.</p>}
                </div>
              ) : null}
              {localGateway.status === "error" && localGateway.error ? <p className="mt-2 text-[#a6483e]">{localGateway.error}</p> : null}
            </div>
          ) : null}
          {grantError ? <div className="mt-2 text-[#a6483e]">{grantError}</div> : null}
          {tunnel.error || tunnelError ? <div className="mt-2 text-[#a6483e]">{tunnel.error || tunnelError}</div> : null}
        </section>
      ) : null}
      {state.error ? (
        <div className="shrink-0 border-b border-[#efc9c4] bg-[#fff1ef] px-4 py-2 text-[12px] text-[#a63f36]">{state.error}</div>
      ) : null}
      <div ref={viewportRef} data-testid="web-chat-native-viewport" className="min-h-0 flex-1 bg-white" />
    </section>
  );
}
