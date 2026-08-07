import { useMemo, useState } from "react";
import { Cable, CheckCircle2, Plus, RefreshCw, Server, Trash2, Wrench, XCircle } from "lucide-react";

// Inspection tools the Roblox Studio MCP server exposes WITHOUT readOnlyHint
// annotations. Applying the preset is the user's explicit consent to treat them
// as read-only (no approval). Stored as per-connector DATA (read_only_overrides),
// never hardcoded in backend control flow.
const robloxReadOnlyPreset = [
  "get_file_tree",
  "search_files",
  "get_place_info",
  "get_services",
  "search_objects",
  "get_instance_properties",
  "get_instance_children",
  "search_by_property",
  "get_class_info",
  "get_project_structure",
  "mass_get_property",
  "get_attribute",
  "get_attributes",
  "get_tags",
  "get_tagged",
  "get_selection",
  "grep_scripts",
  "get_script_source",
  "get_connected_instances",
  "get_playtest_output",
  "list_library",
  "search_assets",
  "get_asset_details",
  "get_asset_thumbnail",
  "preview_asset",
  "search_materials",
  "get_build",
];

const connectorPresets = [
  {
    id: "robloxstudio-mcp",
    label: "Roblox Studio MCP",
    connector: {
      name: "robloxstudio-mcp",
      transport: "stdio",
      command: "cmd /c npx -y robloxstudio-mcp@latest",
      url: "",
      enabled: false,
      read_only_overrides: robloxReadOnlyPreset,
    },
  },
  {
    id: "blender",
    label: "Blender MCP",
    connector: {
      name: "blender",
      transport: "stdio",
      command: "blender-mcp",
      url: "",
      enabled: false,
      read_only_overrides: [],
    },
  },
];

function normalizeOverrides(value) {
  if (!Array.isArray(value)) return [];
  const seen = new Set();
  const out = [];
  for (const item of value) {
    const name = String(item || "").trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    out.push(name);
  }
  return out;
}

function normalizeConnector(connector = {}) {
  return {
    name: String(connector.name || "connector"),
    transport: String(connector.transport || "stdio"),
    command: String(connector.command || ""),
    url: String(connector.url || ""),
    enabled: Boolean(connector.enabled),
    read_only_overrides: normalizeOverrides(connector.read_only_overrides),
    exposed_tools: normalizeOverrides(connector.exposed_tools),
  };
}

// Mirrors the backend _safe_name sanitizer so "robloxstudio-mcp" (preset) and
// "robloxstudio_mcp" (already saved, sanitized) compare as the SAME connector.
function sanitizedNameKey(name) {
  return String(name || "")
    .trim()
    .replace(/[^a-zA-Z0-9_]/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase() || "tool";
}

function statusTone(status) {
  const value = String(status || "").toLowerCase();
  if (value === "connected" || value === "running") return "text-[#257d4f] bg-[#edf7f1]";
  if (value === "disabled") return "text-[#80786c] bg-[#f0eee8]";
  if (value === "error" || value === "unavailable") return "text-[#a23f34] bg-[#fff0ee]";
  return "text-[#7c7469] bg-[#f3f1eb]";
}

export default function ConnectorsPanel({
  connectorState = {},
  connectorTestResult,
  connectorDiscoveryResult,
  embedded = false,
  onRefresh,
  onSaveConnectors,
  onTestConnector,
  onDiscoverConnector,
}) {
  const connectors = Array.isArray(connectorState.connectors) ? connectorState.connectors.map(normalizeConnector) : [];
  const statusesByName = new Map(
    (Array.isArray(connectorState.statuses) ? connectorState.statuses : [])
      .filter((item) => item && typeof item === "object")
      .map((item) => [String(item.name || "connector"), item]),
  );
  const rows = connectors.map((connector) => ({
    ...connector,
    status: statusesByName.get(connector.name) || { name: connector.name, status: connector.enabled ? "unknown" : "disabled" },
  }));
  const [selectedName, setSelectedName] = useState(rows[0]?.name || "");
  const selectedConnector = rows.find((connector) => connector.name === selectedName) || rows[0] || null;
  const [draft, setDraft] = useState(() => normalizeConnector(selectedConnector || { name: "custom-mcp" }));

  const selectedStatus = selectedConnector?.status || {};
  const canSave = draft.name.trim().length > 0;
  const sdkReady = connectorState.mcp_sdk_available !== false;
  const connectorBackendReady = connectorState.enabled !== false;

  const summary = useMemo(() => {
    const connected = rows.filter((row) => String(row.status?.status || "").toLowerCase() === "connected").length;
    const enabled = rows.filter((row) => row.enabled).length;
    return { connected, enabled, total: rows.length };
  }, [rows]);

  const saveList = (nextConnectors) => onSaveConnectors?.(nextConnectors.map(normalizeConnector));

  const selectConnector = (connector) => {
    setSelectedName(connector.name);
    setDraft(normalizeConnector(connector));
  };

  const addCustom = () => {
    const connector = normalizeConnector({ name: "custom-mcp" });
    setSelectedName(connector.name);
    setDraft(connector);
  };

  const addPreset = (preset) => {
    const presetKey = sanitizedNameKey(preset.connector.name);
    const existing = connectors.find((connector) => sanitizedNameKey(connector.name) === presetKey);
    if (existing) {
      // Merge, never clobber: the user's saved transport/command/url stay as
      // configured; the preset can only ADD read-only consent entries.
      const merged = normalizeConnector({
        ...existing,
        read_only_overrides: normalizeOverrides([
          ...(existing.read_only_overrides || []),
          ...(preset.connector.read_only_overrides || []),
        ]),
      });
      saveList(connectors.map((connector) => (sanitizedNameKey(connector.name) === presetKey ? merged : connector)));
      setSelectedName(merged.name);
      setDraft(merged);
      return;
    }
    const next = [...connectors, preset.connector].map(normalizeConnector);
    saveList(next);
    setSelectedName(preset.connector.name);
    setDraft(normalizeConnector(preset.connector));
  };

  const saveDraft = () => {
    if (!canSave) return;
    const nextConnector = normalizeConnector({ ...draft, name: draft.name.trim() });
    const replaced = connectors.some((connector) => connector.name === selectedName);
    saveList(replaced ? connectors.map((connector) => (connector.name === selectedName ? nextConnector : connector)) : [...connectors, nextConnector]);
    setSelectedName(nextConnector.name);
    setDraft(nextConnector);
  };

  const deleteDraft = () => {
    saveList(connectors.filter((connector) => connector.name !== selectedName));
    const next = connectors.find((connector) => connector.name !== selectedName);
    setSelectedName(next?.name || "");
    setDraft(normalizeConnector(next || { name: "custom-mcp" }));
  };

  const toggleConnector = (connector, enabled) => {
    saveList(connectors.map((item) => (item.name === connector.name ? { ...item, enabled } : item)));
  };

  const testConnector = (connector = draft) => onTestConnector?.(normalizeConnector(connector));

  return (
    <section className={`${embedded ? "flex min-h-0 w-full flex-col" : "mx-auto flex min-h-full w-full max-w-5xl flex-col px-6 py-12"}`}>
      <div className={`${embedded ? "mb-5" : "mb-7"} flex flex-wrap items-start justify-between gap-4`}>
        <div>
          <div className="mb-2 flex items-center gap-2 text-[13px] font-medium uppercase tracking-wide text-[#8a877f]">
            <Cable size={15} />
            Local MCP servers
          </div>
          <h1 className="font-serif text-[34px] font-normal text-[#2f2f2d]">MCP connectors</h1>
          <p className="mt-2 max-w-2xl text-[14px] leading-6 text-[#6f6b63]">
            Add and manage MCP servers before Chat can use them. Connectors are plugin-style configs:
            choose a server, test it, enable it, then Chat can call its read-only tools or request approval for write tools.
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-[#dedbd2] bg-white px-3 text-[13px] text-[#3f3d38] shadow-sm hover:bg-[#f6f5f2]"
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="mb-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-[#e7e3da] bg-[#fbfaf7] p-4">
          <div className="text-[12px] uppercase tracking-wide text-[#8a877f]">Configured</div>
          <div className="mt-2 text-2xl text-[#2f2f2d]">{summary.total}</div>
          <div className="mt-1 text-[12px] text-[#7c776f]">{summary.enabled} enabled</div>
        </div>
        <div className="rounded-xl border border-[#e7e3da] bg-[#fbfaf7] p-4">
          <div className="text-[12px] uppercase tracking-wide text-[#8a877f]">Connected</div>
          <div className="mt-2 text-2xl text-[#2f2f2d]">{summary.connected}</div>
          <div className="mt-1 text-[12px] text-[#7c776f]">live probe result</div>
        </div>
        <div className="rounded-xl border border-[#e7e3da] bg-[#fbfaf7] p-4">
          <div className="text-[12px] uppercase tracking-wide text-[#8a877f]">Runtime</div>
          <div className="mt-2 flex items-center gap-2 text-[14px] text-[#2f2f2d]">
            {sdkReady && connectorBackendReady ? <CheckCircle2 size={16} className="text-[#2d8a57]" /> : <XCircle size={16} className="text-[#b94b3f]" />}
            {sdkReady && connectorBackendReady ? "ready" : "disabled"}
          </div>
          <div className="mt-1 text-[12px] text-[#7c776f]">{sdkReady ? "MCP SDK available" : "MCP SDK not installed or disabled"}</div>
        </div>
      </div>

      <div className="grid min-h-[430px] overflow-hidden rounded-xl border border-[#dedbd2] bg-white md:grid-cols-[280px_1fr]">
        <aside className="border-r border-[#ebe8df] bg-[#f7f6f2] p-3">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[12px] font-medium uppercase tracking-wide text-[#8a877f]">Connectors</span>
            <button type="button" aria-label="Add custom connector" onClick={addCustom} className="inline-flex h-8 items-center gap-1 rounded-lg bg-white px-2 text-[12px] text-[#3f3d38] shadow-sm hover:bg-[#efede8]">
              <Plus size={13} /> Add
            </button>
          </div>
          <div className="space-y-1">
            {rows.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[#d8d4ca] bg-white p-3 text-[12px] leading-5 text-[#8a877f]">
                No MCP connectors configured yet.
              </div>
            ) : (
              rows.map((connector) => {
                const active = connector.name === selectedName;
                const status = String(connector.status?.status || "unknown");
                return (
                  <button
                    key={connector.name}
                    type="button"
                    onClick={() => selectConnector(connector)}
                    className={`flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left ${active ? "bg-white shadow-sm" : "hover:bg-white/70"}`}
                  >
                    <Server size={14} className="shrink-0 text-[#6f6b63]" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[13px] font-medium text-[#2f2f2d]">{connector.name}</span>
                      <span className="block truncate text-[11px] text-[#8a877f]">{connector.transport} {connector.command || connector.url}</span>
                    </span>
                    <span className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10px] ${statusTone(status)}`}>{status}</span>
                  </button>
                );
              })
            )}
          </div>

          <div className="mt-5 border-t border-[#e4e1d8] pt-3">
            <div className="mb-2 text-[12px] font-medium uppercase tracking-wide text-[#8a877f]">Presets</div>
            <div className="grid gap-1">
              {connectorPresets.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  aria-label={`Add ${preset.label} preset`}
                  onClick={() => addPreset(preset)}
                  className="flex h-8 items-center justify-between rounded-lg px-2 text-left text-[12px] hover:bg-white"
                >
                  <span>{preset.label}</span>
                  <span className="text-[#8a877f]">preset</span>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <div className="min-w-0 p-5">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-[18px] font-semibold text-[#2f2f2d]">{selectedConnector?.name || "New connector"}</h2>
              <p className="mt-1 text-[13px] text-[#7c776f]">Connector configs are generic. Roblox, Blender, browser tools, or private MCP servers all use the same shape.</p>
            </div>
            {selectedConnector && (
              <div className="flex gap-2">
                <button
                  type="button"
                  aria-label={`Test connector ${selectedConnector.name}`}
                  onClick={() => testConnector(selectedConnector)}
                  className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-[#dedbd2] px-3 text-[12px] hover:bg-[#f6f5f2]"
                >
                  <Wrench size={13} /> Test
                </button>
                <button
                  type="button"
                  aria-label={`${selectedConnector.enabled ? "Disable" : "Enable"} connector ${selectedConnector.name}`}
                  onClick={() => toggleConnector(selectedConnector, !selectedConnector.enabled)}
                  className="h-8 rounded-lg border border-[#dedbd2] px-3 text-[12px] hover:bg-[#f6f5f2]"
                >
                  {selectedConnector.enabled ? "Disable" : "Enable"}
                </button>
              </div>
            )}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-[12px] font-medium text-[#6f6b63]">
              Connector name
              <input
                aria-label="Connector name"
                value={draft.name}
                onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
                className="mt-1 h-9 w-full rounded-lg border border-[#dedbd2] px-3 text-[13px] text-[#2f2f2d] outline-none focus:ring-2 focus:ring-[#d8d5cc]"
              />
            </label>
            <label className="text-[12px] font-medium text-[#6f6b63]">
              Transport
              <select
                aria-label="Connector transport"
                value={draft.transport}
                onChange={(event) => setDraft((current) => ({ ...current, transport: event.target.value }))}
                className="mt-1 h-9 w-full rounded-lg border border-[#dedbd2] bg-white px-3 text-[13px] text-[#2f2f2d] outline-none focus:ring-2 focus:ring-[#d8d5cc]"
              >
                <option value="stdio">stdio</option>
                <option value="http">http</option>
                <option value="sse">sse</option>
              </select>
            </label>
            <label className="text-[12px] font-medium text-[#6f6b63]">
              Connector command
              <input
                aria-label="Connector command"
                value={draft.command}
                onChange={(event) => setDraft((current) => ({ ...current, command: event.target.value }))}
                className="mt-1 h-9 w-full rounded-lg border border-[#dedbd2] px-3 text-[13px] text-[#2f2f2d] outline-none focus:ring-2 focus:ring-[#d8d5cc]"
              />
            </label>
            <label className="text-[12px] font-medium text-[#6f6b63]">
              Connector URL
              <input
                aria-label="Connector URL"
                value={draft.url}
                onChange={(event) => setDraft((current) => ({ ...current, url: event.target.value }))}
                className="mt-1 h-9 w-full rounded-lg border border-[#dedbd2] px-3 text-[13px] text-[#2f2f2d] outline-none focus:ring-2 focus:ring-[#d8d5cc]"
              />
            </label>
          </div>
          <label className="mt-4 flex items-center gap-2 text-[13px] text-[#4c4942]">
            <input
              aria-label="Connector enabled"
              type="checkbox"
              checked={draft.enabled}
              onChange={(event) => setDraft((current) => ({ ...current, enabled: event.target.checked }))}
            />
            Enable connector after saving
          </label>

          <label className="mt-4 block text-[12px] font-medium text-[#6f6b63]">
            Read-only overrides ({draft.read_only_overrides.length} tools trusted without approval)
            <textarea
              aria-label="Read-only overrides"
              value={draft.read_only_overrides.join("\n")}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  read_only_overrides: normalizeOverrides(event.target.value.split(/[\n,]+/)),
                }))
              }
              rows={3}
              placeholder="one tool name per line"
              className="mt-1 w-full rounded-lg border border-[#dedbd2] px-3 py-2 font-mono text-[12px] text-[#2f2f2d] outline-none focus:ring-2 focus:ring-[#d8d5cc]"
            />
            <span className="mt-1 block font-normal text-[#8a877f]">
              Tools listed here run WITHOUT approval even when the server does not declare readOnlyHint.
              Only list tools you trust to be inspection-only. Everything else stays approval-gated.
            </span>
          </label>

          <label className="mt-4 block text-[12px] font-medium text-[#6f6b63]">
            Exposed tools ({draft.exposed_tools.length === 0 ? "all tools visible to the model" : `model sees only ${draft.exposed_tools.length} tools`})
            <textarea
              aria-label="Exposed tools"
              value={draft.exposed_tools.join("\n")}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  exposed_tools: normalizeOverrides(event.target.value.split(/[\n,]+/)),
                }))
              }
              rows={3}
              placeholder="empty = expose every tool to the model"
              className="mt-1 w-full rounded-lg border border-[#dedbd2] px-3 py-2 font-mono text-[12px] text-[#2f2f2d] outline-none focus:ring-2 focus:ring-[#d8d5cc]"
            />
            <span className="mt-1 block font-normal text-[#8a877f]">
              On servers with many tools, exposing only what you need keeps every chat message smaller,
              faster, and easier for the model to pick the right tool. Manual runs from this panel can
              still use every tool.
            </span>
          </label>

          <div className="mt-5 flex flex-wrap justify-between gap-3 border-t border-[#ebe8df] pt-4">
            <button
              type="button"
              aria-label="Delete connector"
              onClick={deleteDraft}
              disabled={!selectedConnector}
              className="inline-flex h-9 items-center gap-2 rounded-lg border border-[#ecd2cc] px-3 text-[13px] text-[#9b4b3f] disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Trash2 size={14} /> Delete
            </button>
            <div className="flex flex-wrap gap-2">
              {onDiscoverConnector && (
                <button
                  type="button"
                  aria-label="Diagnose Roblox MCP preset"
                  onClick={() => onDiscoverConnector("roblox")}
                  className="h-9 rounded-lg border border-[#dedbd2] px-3 text-[13px] text-[#4a4741] hover:bg-[#f6f5f2]"
                >
                  Diagnose Roblox MCP
                </button>
              )}
              <button
                type="button"
                aria-label="Save connector"
                onClick={saveDraft}
                disabled={!canSave}
                className="h-9 rounded-lg bg-[#2f2f2d] px-4 text-[13px] font-medium text-white hover:bg-[#1f1f1d] disabled:cursor-not-allowed disabled:bg-[#d8d5cc]"
              >
                Save connector
              </button>
            </div>
          </div>

          {selectedConnector && (
            <div className="mt-5 rounded-xl border border-[#ebe8df] bg-[#fbfaf7] p-3">
              <div className="flex flex-wrap items-center gap-2 text-[12px] text-[#6f6b63]">
                <span className={`rounded-md px-2 py-1 ${statusTone(selectedStatus.status)}`}>{selectedStatus.status || "unknown"}</span>
                <span>{Number(selectedStatus.tool_count || 0)} tools · {Number(selectedStatus.read_only_tool_count || 0)} read-only · {Number(selectedStatus.write_tool_count || 0)} approval</span>
              </div>
              {selectedStatus.error && <div className="mt-2 text-[12px] leading-5 text-[#9b4b3f]">{selectedStatus.error}</div>}
            </div>
          )}

          {connectorTestResult && (
            <div className="mt-4 rounded-xl border border-[#ebe8df] bg-[#f7f6f2] p-3 text-[12px] leading-5 text-[#5f5a52]">
              Test: {connectorTestResult.status || "unknown"}
              {Array.isArray(connectorTestResult.errors) && connectorTestResult.errors.length > 0 && (
                <div className="text-[#9b4b3f]">{connectorTestResult.errors.join(" ")}</div>
              )}
            </div>
          )}
          {connectorDiscoveryResult && (
            <div className="mt-4 rounded-xl border border-[#ebe8df] bg-[#f7f6f2] p-3 text-[12px] leading-5 text-[#5f5a52]">
              Discovery: {connectorDiscoveryResult.target || "connector"}
              {connectorDiscoveryResult.message && <div>{connectorDiscoveryResult.message}</div>}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
