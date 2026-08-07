import { useEffect, useRef, useState } from "react";
import { ArrowUp, FolderPlus, GitBranch, Globe2, Mic, Paperclip, Palette, Plus, Puzzle, Search, SlidersHorizontal, Sparkles, X } from "lucide-react";
import ModelMenu from "./ModelMenu";

function ContextUsageIndicator({ usage }) {
  if (!usage) return null;
  const hasWindow = Number.isFinite(usage.contextWindowTokens) && usage.contextWindowTokens > 0;
  const percent = hasWindow ? Math.max(0, Math.min(999, Number(usage.percentFull) || 0)) : null;
  const tone = percent === null ? "#9b9489" : percent >= 90 ? "#c84f3d" : percent >= 70 ? "#d99a2f" : "#3f8f62";
  const ringStyle = hasWindow
    ? { background: `conic-gradient(${tone} ${Math.min(percent, 100)}%, #e7e4db 0)` }
    : { border: "2px solid #cfcac0" };

  return (
    <span
      aria-label="Context usage"
      title={usage.title || "Context usage"}
      className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg px-1.5 text-[12px] text-[#6f6b63] transition hover:bg-[#efede8]"
    >
      <span className="grid h-3.5 w-3.5 place-items-center rounded-full" style={ringStyle}>
        <span className="h-1.5 w-1.5 rounded-full bg-white" />
      </span>
      <span className="tabular-nums">{hasWindow ? `${percent}%` : "ctx"}</span>
    </span>
  );
}

const skillSuggestions = [
  "Develop CI/CD pipelines",
  "Build an app based on my idea",
  "Explain a programming concept",
  "Develop performance benchmarks",
  "Tell me what programming paradigm suits my thinking style",
];

async function readFileAsDataUrl(file) {
  if (!file || typeof file.arrayBuffer !== "function") return "";
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunkSize = 8192;
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.slice(index, index + chunkSize));
  }
  const base64 = typeof btoa === "function" ? btoa(binary) : "";
  return base64 ? `data:${file.type || "application/octet-stream"};base64,${base64}` : "";
}

function pastedImageName(file, index) {
  if (file?.name) return file.name;
  const mime = String(file?.type || "image/png").toLowerCase();
  const extension = mime.includes("jpeg") ? "jpg" : mime.includes("webp") ? "webp" : mime.includes("gif") ? "gif" : "png";
  return `pasted-image-${index + 1}.${extension}`;
}

function normalizePastedImageFile(file, index) {
  if (!file) return null;
  if (file.name) return file;
  try {
    return new File([file], pastedImageName(file, index), { type: file.type || "image/png" });
  } catch {
    return file;
  }
}

export default function Composer({
  disabled = false,
  effort = "Medium",
  focusSignal = 0,
  modelLabel,
  modelProviders = [],
  routeReason = "",
  contextUsage,
  connectorState = {},
  searchCapabilities,
  suggestedAttachments,
  suggestedPrompt,
  webSettings = { webMode: "auto", searchProvider: "auto" },
  workspaceLabel,
  onChooseWorkspace,
  onEffortChange,
  onOpenMemoryManager,
  onOpenConnectors,
  onModelChange,
  onRefreshChatConnectors,
  onSaveChatConnectors,
  onTestChatConnector,
  onDiscoverChatConnector,
  onRunChatMcpTool,
  connectorTestResult,
  connectorDiscoveryResult,
  onWebSettingsChange,
  onSubmit,
}) {
  const [draft, setDraft] = useState("");
  const [attachments, setAttachments] = useState([]);
  const [attachMenuOpen, setAttachMenuOpen] = useState(false);
  const [toolSettingsOpen, setToolSettingsOpen] = useState(false);
  const [snippetOpen, setSnippetOpen] = useState(false);
  const [snippetDraft, setSnippetDraft] = useState("");
  const [snippetLabel, setSnippetLabel] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [previewAttachment, setPreviewAttachment] = useState(null);
  const [editingConnectorName, setEditingConnectorName] = useState("");
  const [connectorDraft, setConnectorDraft] = useState(null);
  const [selectedMcpToolKey, setSelectedMcpToolKey] = useState("");
  const [mcpToolArgDrafts, setMcpToolArgDrafts] = useState({});
  const fileInputRef = useRef(null);
  const textAreaRef = useRef(null);
  const canSubmit = draft.trim().length > 0 && !disabled;
  const skillsOpen = draft.trim().startsWith("/");

  useEffect(() => {
    if (!suggestedPrompt?.text) return;
    setDraft(suggestedPrompt.text);
  }, [suggestedPrompt]);

  useEffect(() => {
    if (!Array.isArray(suggestedAttachments) || suggestedAttachments.length === 0) return;
    setAttachments((current) => [...current, ...suggestedAttachments].slice(0, 6));
  }, [suggestedAttachments]);

  useEffect(() => {
    if (!focusSignal) return;
    textAreaRef.current?.focus();
  }, [focusSignal]);

  const submit = () => {
    const prompt = draft.trim();
    if (!prompt || disabled) return;
    if (attachments.length > 0) {
      onSubmit(prompt, attachments);
    } else {
      onSubmit(prompt);
    }
    setDraft("");
    setAttachments([]);
    setPreviewAttachment(null);
  };

  const seedContextPrompt = (text) => {
    setDraft(text);
    setAttachMenuOpen(false);
    textAreaRef.current?.focus();
  };

  const attachSelectedFiles = async (fileList, source = "user-file") => {
    const files = Array.from(fileList || []).slice(0, 6);
    if (files.length === 0) return;
    const nextAttachments = [];
    for (const file of files) {
      const isTextLike = String(file.type || "").startsWith("text/") || /\.(txt|md|json|csv|log|py|js|jsx|ts|tsx|css|html|xml|yml|yaml|lua)$/i.test(file.name);
      const isImageLike = String(file.type || "").startsWith("image/") || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(file.name);
      let content = "";
      let kind = isTextLike ? "text" : isImageLike ? "image" : "unsupported";
      let dataUrl = "";
      if (isTextLike && typeof file.text === "function") {
        content = (await file.text()).slice(0, 12000);
      } else if (isImageLike) {
        dataUrl = await readFileAsDataUrl(file);
        content = `Image file ${file.name || "attached image"} is attached. Type: ${file.type || "unknown"}; size: ${file.size ?? 0} bytes.`;
      } else {
        content = `Selected file ${file.name} is not readable as text in Chat yet. Ask the user to attach a text version or use Cowork for workspace inspection.`;
      }
      nextAttachments.push({
        label: file.name || "attached-file",
        source,
        kind,
        content,
        ...(file.type ? { mime: file.type } : {}),
        ...(Number.isFinite(file.size) ? { size: file.size } : {}),
        ...(dataUrl ? { dataUrl } : {}),
      });
    }
    setAttachments((current) => [...current, ...nextAttachments].slice(0, 6));
    setAttachMenuOpen(false);
    textAreaRef.current?.focus();
  };

  const setWebMode = (webMode) => {
    onWebSettingsChange?.({ ...webSettings, webMode });
  };

  const setSearchProvider = (searchProvider) => {
    onWebSettingsChange?.({ ...webSettings, searchProvider });
  };

  const setToolToggle = (key, enabled) => {
    onWebSettingsChange?.({ ...webSettings, [key]: enabled ? "on" : "off" });
  };

  const connectorStatusesByName = new Map(
    (Array.isArray(connectorState.statuses) ? connectorState.statuses : [])
      .filter((item) => item && typeof item === "object")
      .map((item) => [String(item.name || "connector"), item]),
  );
  const configuredConnectors = Array.isArray(connectorState.connectors) ? connectorState.connectors : [];
  const connectorRows = configuredConnectors.map((connector) => {
    const name = String(connector?.name || "connector");
    return {
      ...connector,
      name,
      status: connectorStatusesByName.get(name) || { name, status: connector?.enabled ? "unknown" : "disabled" },
    };
  });

  const saveConnectorList = (connectors) => {
    onSaveChatConnectors?.(connectors);
  };

  const startEditingConnector = (connector) => {
    const next = {
      name: String(connector?.name || "connector"),
      transport: String(connector?.transport || "stdio"),
      command: String(connector?.command || ""),
      url: String(connector?.url || ""),
      enabled: Boolean(connector?.enabled),
      read_only_overrides: Array.isArray(connector?.read_only_overrides) ? connector.read_only_overrides : [],
      exposed_tools: Array.isArray(connector?.exposed_tools) ? connector.exposed_tools : [],
    };
    setEditingConnectorName(next.name);
    setConnectorDraft(next);
  };

  const updateConnectorDraft = (patch) => {
    setConnectorDraft((current) => ({ ...(current || { name: "connector", transport: "stdio", command: "", url: "", enabled: false }), ...patch }));
  };

  const saveConnectorDraft = () => {
    if (!connectorDraft) return;
    const targetName = editingConnectorName || connectorDraft.name;
    const nextConnector = {
      name: String(connectorDraft.name || "connector").trim() || "connector",
      transport: String(connectorDraft.transport || "stdio"),
      command: String(connectorDraft.command || ""),
      url: String(connectorDraft.url || ""),
      enabled: Boolean(connectorDraft.enabled),
      read_only_overrides: Array.isArray(connectorDraft.read_only_overrides) ? connectorDraft.read_only_overrides : [],
      exposed_tools: Array.isArray(connectorDraft.exposed_tools) ? connectorDraft.exposed_tools : [],
    };
    const replaced = configuredConnectors.some((connector) => String(connector?.name || "") === targetName);
    saveConnectorList(
      replaced
        ? configuredConnectors.map((connector) => (String(connector?.name || "") === targetName ? nextConnector : connector))
        : [...configuredConnectors, nextConnector],
    );
    setEditingConnectorName(nextConnector.name);
    setConnectorDraft(nextConnector);
  };

  const deleteConnectorDraft = () => {
    if (!connectorDraft) return;
    const targetName = editingConnectorName || connectorDraft.name;
    saveConnectorList(configuredConnectors.filter((connector) => String(connector?.name || "") !== targetName));
    setEditingConnectorName("");
    setConnectorDraft(null);
  };

  const toggleConnector = (name, enabled) => {
    saveConnectorList(configuredConnectors.map((connector) => (
      String(connector?.name || "") === name ? { ...connector, enabled } : connector
    )));
  };

  const addRobloxPreset = () => {
    const exists = configuredConnectors.some((connector) => String(connector?.name || "").toLowerCase() === "roblox");
    if (exists) return;
    saveConnectorList([
      ...configuredConnectors,
      { name: "roblox", transport: "stdio", command: "roblox-mcp", enabled: false },
    ]);
  };

  const selectedMcpTool = (() => {
    if (!selectedMcpToolKey) return null;
    for (const connector of connectorRows) {
      const tools = Array.isArray(connector.status?.tools) ? connector.status.tools : [];
      for (const tool of tools) {
        const key = `${connector.name}::${tool.name}`;
        if (key === selectedMcpToolKey) return { connector, tool, key };
      }
    }
    return null;
  })();

  const setMcpArgDraft = (toolKey, name, value) => {
    setMcpToolArgDrafts((current) => ({
      ...current,
      [toolKey]: { ...(current[toolKey] || {}), [name]: value },
    }));
  };

  const schemaTypeIncludes = (schema, expected) => {
    const type = schema?.type;
    return Array.isArray(type) ? type.includes(expected) : type === expected;
  };

  const buildMcpArguments = (toolKey, schema) => {
    const draft = mcpToolArgDrafts[toolKey] || {};
    const properties = schema?.properties && typeof schema.properties === "object" ? schema.properties : {};
    const out = {};
    for (const [name, propertySchema] of Object.entries(properties)) {
      const raw = draft[name];
      if (typeof raw === "undefined" || raw === "") continue;
      if (schemaTypeIncludes(propertySchema, "boolean")) {
        out[name] = Boolean(raw);
      } else if (schemaTypeIncludes(propertySchema, "integer")) {
        const parsed = Number.parseInt(raw, 10);
        if (Number.isFinite(parsed)) out[name] = parsed;
      } else if (schemaTypeIncludes(propertySchema, "number")) {
        const parsed = Number.parseFloat(raw);
        if (Number.isFinite(parsed)) out[name] = parsed;
      } else if (schemaTypeIncludes(propertySchema, "object") || schemaTypeIncludes(propertySchema, "array")) {
        try {
          out[name] = JSON.parse(raw);
        } catch {
          out[name] = raw;
        }
      } else {
        out[name] = String(raw);
      }
    }
    return out;
  };

  const runSelectedMcpTool = () => {
    if (!selectedMcpTool) return;
    onRunChatMcpTool?.({
      server: selectedMcpTool.connector.name,
      tool: selectedMcpTool.tool.name,
      arguments: buildMcpArguments(selectedMcpTool.key, selectedMcpTool.tool.input_schema || {}),
      origin: "manual",
    });
    setToolSettingsOpen(false);
  };

  const searchProviders = Array.isArray(searchCapabilities?.providers)
    ? searchCapabilities.providers
    : [
      { id: "auto", label: "Auto", available: true },
      { id: "brave", label: "Brave", available: false },
      { id: "scrape", label: "Basic scrape", available: true },
    ];

  const handleDragOver = (event) => {
    if (disabled) return;
    if (!event.dataTransfer?.types?.includes("Files")) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    setDragActive(true);
  };

  const handleDragLeave = (event) => {
    if (event.currentTarget.contains(event.relatedTarget)) return;
    setDragActive(false);
  };

  const handleDrop = (event) => {
    if (disabled) return;
    if (!event.dataTransfer?.files?.length) return;
    event.preventDefault();
    setDragActive(false);
    void attachSelectedFiles(event.dataTransfer.files);
  };

  const handlePaste = (event) => {
    if (disabled) return;
    const clipboardData = event.clipboardData;
    const imageFiles = Array.from(clipboardData?.items || [])
      .filter((item) => item?.kind === "file" && String(item.type || "").startsWith("image/"))
      .map((item, index) => normalizePastedImageFile(item.getAsFile?.(), index))
      .filter(Boolean);

    if (imageFiles.length === 0) {
      const fallbackFiles = Array.from(clipboardData?.files || [])
        .filter((file) => String(file?.type || "").startsWith("image/"))
        .map((file, index) => normalizePastedImageFile(file, index))
        .filter(Boolean);
      if (fallbackFiles.length === 0) return;
      event.preventDefault();
      void attachSelectedFiles(fallbackFiles, "user-paste");
      return;
    }

    event.preventDefault();
    void attachSelectedFiles(imageFiles, "user-paste");
  };

  const addPastedContext = () => {
    const content = snippetDraft.trim();
    if (!content) return;
    setAttachments((current) => [
      ...current,
      {
        label: snippetLabel.trim() || "Pasted context",
        source: "user-paste",
        kind: "text",
        content: content.slice(0, 12000),
      },
    ].slice(0, 6));
    setSnippetDraft("");
    setSnippetLabel("");
    setSnippetOpen(false);
    textAreaRef.current?.focus();
  };

  const attachmentSummary = (attachment) => {
    const parts = [attachment.kind || "context", attachment.source || "attached"];
    if (Number.isFinite(attachment.size)) parts.push(`${attachment.size} bytes`);
    if (attachment.mime) parts.push(attachment.mime);
    return parts.filter(Boolean).join(" · ");
  };
  const imageAttachments = attachments
    .map((attachment, index) => ({ attachment, index }))
    .filter(({ attachment }) => attachment.kind === "image" && attachment.dataUrl);
  const nonImageAttachments = attachments
    .map((attachment, index) => ({ attachment, index }))
    .filter(({ attachment }) => !(attachment.kind === "image" && attachment.dataUrl));

  return (
    <div
      aria-label="Message composer"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onPaste={handlePaste}
      className={`relative rounded-[18px] border bg-white shadow-[0_18px_48px_rgba(38,36,30,0.08)] transition ${
        dragActive ? "border-[#b9a98b] ring-2 ring-[#d9cdb7]" : "border-[#e0ded6]"
      }`}
    >
      {dragActive && (
        <div className="pointer-events-none absolute inset-2 z-20 grid place-items-center rounded-[14px] border border-dashed border-[#b9a98b] bg-white/85 text-[13px] font-medium text-[#5c5142] backdrop-blur-sm">
          Drop files or photos to attach
        </div>
      )}
      <input
        ref={fileInputRef}
        aria-label="Attach files"
        type="file"
        multiple
        className="sr-only"
        onChange={(event) => {
          void attachSelectedFiles(event.target.files);
          event.target.value = "";
        }}
      />
      <textarea
        ref={textAreaRef}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
            event.preventDefault();
            submit();
          }
        }}
        placeholder="How can I help you today?"
        rows={3}
        disabled={disabled}
        className="min-h-[76px] w-full resize-none bg-transparent px-5 pb-2 pt-5 text-[16px] leading-6 text-[#2f2f2d] placeholder:text-[#85827b] focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
      />
      {imageAttachments.length > 0 && (
        <div aria-label="Image attachments" className="flex max-w-full gap-2 overflow-x-auto px-4 pb-2">
          {imageAttachments.map(({ attachment, index }) => (
            <div
              key={`${attachment.label}-${index}`}
              className="group relative h-16 w-16 shrink-0 overflow-hidden rounded-xl border border-[#dedbd2] bg-[#f7f6f2] shadow-sm"
              title={`${attachment.label} · ${attachmentSummary(attachment)}`}
            >
              <button
                type="button"
                aria-label={`Preview ${attachment.label}`}
                onClick={() => setPreviewAttachment(attachment)}
                className="block h-full w-full"
              >
                <img
                  alt={`${attachment.label} preview`}
                  src={attachment.dataUrl}
                  className="h-full w-full object-cover"
                />
              </button>
              <button
                type="button"
                aria-label={`Remove ${attachment.label}`}
                onClick={() => {
                  setAttachments((current) => current.filter((_, itemIndex) => itemIndex !== index));
                  setPreviewAttachment(null);
                }}
                className="absolute right-1 top-1 grid h-5 w-5 place-items-center rounded-full bg-white/95 text-[#3f3d38] shadow transition hover:bg-[#efede8]"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="flex min-h-[53px] items-center gap-2 px-4 pb-3">
        <button
          type="button"
          aria-label="Attach context"
          onClick={() => setAttachMenuOpen((value) => !value)}
          className="grid h-8 w-8 place-items-center rounded-lg text-[#4a4945] transition hover:bg-[#efede8]"
        >
          <Plus size={19} strokeWidth={2} />
        </button>
        {attachMenuOpen && (
          <div
            role="menu"
            aria-label="Add context"
            className="absolute bottom-12 left-2 z-40 w-64 rounded-xl border border-[#dedbd2] bg-white p-1.5 text-[13px] shadow-[0_14px_38px_rgba(0,0,0,0.16)]"
          >
            <button
              type="button"
              role="menuitem"
              onClick={() => fileInputRef.current?.click()}
              className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]"
            >
              <Paperclip size={15} /> Add files or photos
            </button>
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setAttachMenuOpen(false);
                setSnippetOpen(true);
              }}
              className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]"
            >
              <Paperclip size={15} /> Add pasted text
            </button>
            <button type="button" role="menuitem" onClick={onChooseWorkspace} className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]">
              <FolderPlus size={15} /> Add to project
            </button>
            <button type="button" role="menuitem" onClick={() => seedContextPrompt("Review a GitHub repository")} className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]">
              <GitBranch size={15} /> Add from GitHub
            </button>
            <div className="my-1 border-t border-[#ebe8df]" />
            <button type="button" role="menuitem" onClick={() => seedContextPrompt("/")} className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]">
              <Sparkles size={15} /> Skills
            </button>
            <button type="button" role="menuitem" onClick={() => seedContextPrompt("Show available local connectors")} className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]">
              <Puzzle size={15} /> Connectors
            </button>
            <button type="button" role="menuitem" onClick={() => seedContextPrompt("List compatible local plugins for this task")} className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]">
              <Puzzle size={15} /> Add plugins...
            </button>
            <div className="my-1 border-t border-[#ebe8df]" />
            <button type="button" role="menuitem" onClick={() => seedContextPrompt("Research this topic using the available local context")} className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]">
              <Search size={15} /> Research
            </button>
            <button
              type="button"
              aria-label="Web search"
              role={webSettings.webMode !== "off" ? "menuitemcheckbox" : "menuitem"}
              aria-checked={webSettings.webMode !== "off" || undefined}
              onClick={() => setWebMode(webSettings.webMode === "off" ? "auto" : "off")}
              className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]"
            >
              <Globe2 size={15} /> Web search
              {webSettings.webMode !== "off" && <span className="ml-auto text-[#4d73df]">✓</span>}
            </button>
            <button type="button" role="menuitem" onClick={() => seedContextPrompt("Use the current project's writing and coding style")} className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]">
              <Palette size={15} /> Use style
            </button>
          </div>
        )}
        {snippetOpen && (
          <div
            role="dialog"
            aria-label="Add pasted context"
            className="absolute bottom-12 left-2 z-40 w-[320px] rounded-xl border border-[#dedbd2] bg-white p-3 text-[13px] shadow-[0_14px_38px_rgba(0,0,0,0.16)]"
          >
            <label className="block text-[12px] text-[#6f6b63]">
              Context label
              <input
                aria-label="Context label"
                value={snippetLabel}
                onChange={(event) => setSnippetLabel(event.target.value)}
                className="mt-1 h-8 w-full rounded-lg border border-[#dedbd2] px-2 text-[13px] text-[#2f2f2d] focus:outline-none focus:ring-2 focus:ring-[#d8d5cc]"
              />
            </label>
            <label className="mt-2 block text-[12px] text-[#6f6b63]">
              Paste context
              <textarea
                aria-label="Paste context"
                value={snippetDraft}
                onChange={(event) => setSnippetDraft(event.target.value)}
                rows={5}
                className="mt-1 w-full resize-none rounded-lg border border-[#dedbd2] px-2 py-2 text-[13px] leading-5 text-[#2f2f2d] focus:outline-none focus:ring-2 focus:ring-[#d8d5cc]"
              />
            </label>
            <div className="mt-3 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setSnippetOpen(false);
                  setSnippetDraft("");
                  setSnippetLabel("");
                }}
                className="h-8 rounded-lg border border-[#dedbd2] px-3 text-[13px] text-[#4a4945] hover:bg-[#f7f6f2]"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={addPastedContext}
                disabled={!snippetDraft.trim()}
                className="h-8 rounded-lg bg-[#2f2f2d] px-3 text-[13px] text-white hover:bg-[#1f1f1d] disabled:bg-[#d8d5cc]"
              >
                Add context
              </button>
            </div>
          </div>
        )}
        {nonImageAttachments.length > 0 && (
          <div className="flex max-w-[45%] flex-wrap items-center gap-1.5">
            {nonImageAttachments.map(({ attachment, index }) => (
              <span
                key={`${attachment.label}-${index}`}
                title={`${attachment.label} · ${attachmentSummary(attachment)}`}
                className="inline-flex h-7 max-w-[220px] items-center gap-1 rounded-lg border border-[#dedbd2] bg-[#f7f6f2] px-2 text-[12px] text-[#4a4945]"
              >
                <Paperclip size={13} />
                <button
                  type="button"
                  aria-label={`Preview ${attachment.label}`}
                  onClick={() => setPreviewAttachment(attachment)}
                  className="min-w-0 truncate text-left hover:underline"
                >
                  {attachment.label}
                </button>
                <span className="shrink-0 text-[11px] text-[#8a877f]">{attachment.kind}</span>
                <button
                  type="button"
                  aria-label={`Remove ${attachment.label}`}
                  onClick={() => {
                    setAttachments((current) => current.filter((_, itemIndex) => itemIndex !== index));
                    setPreviewAttachment(null);
                  }}
                  className="grid h-4 w-4 place-items-center rounded hover:bg-[#e7e4db]"
                >
                  <X size={11} />
                </button>
              </span>
            ))}
          </div>
        )}
        {previewAttachment && (
          <div
            role="dialog"
            aria-label="Attachment preview"
            className="absolute bottom-12 left-10 z-50 w-[360px] rounded-xl border border-[#dedbd2] bg-white p-3 text-[13px] shadow-[0_14px_38px_rgba(0,0,0,0.16)]"
          >
            <div className="mb-2 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate font-medium text-[#2f2f2d]">{previewAttachment.label}</div>
                <div className="mt-0.5 text-[11px] text-[#8a877f]">{attachmentSummary(previewAttachment)}</div>
              </div>
              <button
                type="button"
                aria-label="Close attachment preview"
                onClick={() => setPreviewAttachment(null)}
                className="grid h-6 w-6 shrink-0 place-items-center rounded-md text-[#6f6b63] hover:bg-[#efede8]"
              >
                <X size={13} />
              </button>
            </div>
            {previewAttachment.kind === "image" && previewAttachment.dataUrl ? (
              <img
                alt={previewAttachment.label}
                src={previewAttachment.dataUrl}
                className="max-h-48 w-full rounded-lg border border-[#ebe8df] object-contain"
              />
            ) : (
              <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-lg border border-[#ebe8df] bg-[#fbfaf7] p-2 text-[12px] leading-5 text-[#3b3934]">
                {String(previewAttachment.content || "No readable preview.").slice(0, 2000)}
              </pre>
            )}
          </div>
        )}
        <div className="min-w-0 flex-1" />
        <div className="hidden min-w-0 items-center gap-2 md:flex">
          <span className="max-w-[150px] truncate text-[12px] text-[#8a877f]">{workspaceLabel || "No project selected"}</span>
          {routeReason && (
            <span
              aria-label="Model route reason"
              title={routeReason}
              className="max-w-[170px] truncate rounded-md bg-[#f1eee7] px-2 py-1 text-[11px] text-[#7a7165]"
            >
              {routeReason}
            </span>
          )}
          <ContextUsageIndicator usage={contextUsage} />
          <ModelMenu
            effort={effort}
            modelLabel={modelLabel}
            modelProviders={modelProviders}
            onEffortChange={onEffortChange}
            onModelChange={onModelChange}
          />
        </div>
        <button
          type="button"
          aria-label="Voice input"
          className="grid h-8 w-8 place-items-center rounded-lg text-[#4a4945] transition hover:bg-[#efede8]"
        >
          <Mic size={17} strokeWidth={2} />
        </button>
        <button
          type="button"
          aria-label="Tool settings"
          onClick={() => setToolSettingsOpen((value) => !value)}
          className="grid h-8 w-8 place-items-center rounded-lg text-[#4a4945] transition hover:bg-[#efede8]"
        >
          <SlidersHorizontal size={17} strokeWidth={2} />
        </button>
        {toolSettingsOpen && (
          <div
            role="menu"
            aria-label="Tool settings menu"
            className="absolute bottom-12 right-12 z-40 w-[260px] rounded-xl border border-[#dedbd2] bg-white p-2 text-[13px] shadow-[0_14px_38px_rgba(0,0,0,0.16)]"
          >
            <div className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-[#8a877f]">Web</div>
            <div className="grid grid-cols-2 gap-1">
              {["auto", "off"].map((mode) => (
                <button
                  key={mode}
                  type="button"
                  role="menuitemradio"
                  aria-checked={webSettings.webMode === mode}
                  onClick={() => setWebMode(mode)}
                  className={`h-8 rounded-lg px-2 text-left capitalize ${webSettings.webMode === mode ? "bg-[#ebe9e2] text-[#2f2f2d]" : "hover:bg-[#f0efeb]"}`}
                >
                  {mode}
                </button>
              ))}
            </div>
            <div className="mt-3 px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-[#8a877f]">Provider</div>
            <div className="space-y-1">
              {searchProviders.map((provider) => (
                <button
                  key={provider.id}
                  type="button"
                  role="menuitemradio"
                  aria-checked={webSettings.searchProvider === provider.id}
                  disabled={!provider.available}
                  onClick={() => setSearchProvider(provider.id)}
                  className={`flex h-8 w-full items-center justify-between rounded-lg px-2 text-left disabled:cursor-not-allowed disabled:text-[#b9b4aa] ${
                    webSettings.searchProvider === provider.id ? "bg-[#ebe9e2] text-[#2f2f2d]" : "hover:bg-[#f0efeb]"
                  }`}
                >
                  <span>{provider.label}</span>
                  {!provider.available ? <span className="text-[11px]">no key</span> : webSettings.searchProvider === provider.id ? <span className="text-[#4d73df]">✓</span> : null}
                </button>
              ))}
            </div>
            <div className="my-2 border-t border-[#ebe8df]" />
            <div className="flex items-center justify-between px-2 pb-1">
              <span className="text-[11px] font-medium uppercase tracking-wide text-[#8a877f]">Connectors</span>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  aria-label="Manage MCP connectors"
                  onClick={() => {
                    setToolSettingsOpen(false);
                    onOpenConnectors?.();
                  }}
                  className="h-6 rounded-md px-1.5 text-[11px] text-[#6f6b63] hover:bg-[#f0efeb]"
                >
                  Manage
                </button>
                <button
                  type="button"
                  aria-label="Refresh MCP connectors"
                  onClick={() => onRefreshChatConnectors?.()}
                  className="h-6 rounded-md px-1.5 text-[11px] text-[#6f6b63] hover:bg-[#f0efeb]"
                >
                  Refresh
                </button>
              </div>
            </div>
            <div className="max-h-64 space-y-1 overflow-y-auto px-1">
              {connectorRows.length === 0 ? (
                <div className="px-1 py-1 text-[11px] leading-4 text-[#9b9489]">No MCP connectors configured.</div>
              ) : (
                connectorRows.map((connector) => {
                  const status = String(connector.status?.status || "unknown");
                  const error = String(connector.status?.error || "");
                  const toolCount = Number(connector.status?.tool_count || 0);
                  const readOnlyCount = Number(connector.status?.read_only_tool_count || 0);
                  const writeCount = Number(connector.status?.write_tool_count || 0);
                  const tools = Array.isArray(connector.status?.tools) ? connector.status.tools : [];
                  return (
                    <div key={connector.name} className="rounded-lg border border-[#ebe8df] bg-[#fbfaf7] px-2 py-1.5">
                      <div className="flex items-center gap-2">
                        <span className="min-w-0 flex-1 truncate text-[12px] font-medium text-[#3b3934]">{connector.name}</span>
                        <span className="rounded-md bg-[#efede8] px-1.5 py-0.5 text-[10px] text-[#6f6b63]">{status}</span>
                      </div>
                      <div className="mt-1 truncate text-[11px] text-[#9b9489]">
                        {connector.transport || "stdio"} {connector.command || connector.url || ""}
                      </div>
                      {toolCount > 0 && (
                        <div className="mt-1 text-[11px] text-[#6f6b63]">
                          {toolCount} tools · {readOnlyCount} read-only · {writeCount} approval
                        </div>
                      )}
                      {tools.length > 0 && (
                        <div className="mt-1 space-y-1">
                          {tools.map((tool) => {
                            const toolName = String(tool?.name || "tool");
                            const toolKey = `${connector.name}::${toolName}`;
                            const selected = selectedMcpToolKey === toolKey;
                            const schema = tool?.input_schema && typeof tool.input_schema === "object" ? tool.input_schema : {};
                            const properties = schema.properties && typeof schema.properties === "object" ? schema.properties : {};
                            return (
                              <div key={toolKey} className="rounded-md border border-[#ebe8df] bg-white/70 p-1">
                                <button
                                  type="button"
                                  aria-label={`Select MCP tool ${connector.name}/${toolName}`}
                                  onClick={() => setSelectedMcpToolKey(selected ? "" : toolKey)}
                                  className="flex w-full items-center gap-2 rounded px-1 py-0.5 text-left hover:bg-[#f0efeb]"
                                >
                                  <span className="min-w-0 flex-1 truncate text-[11px] text-[#3b3934]">{toolName}</span>
                                  <span className="rounded bg-[#efede8] px-1 py-0.5 text-[10px] text-[#6f6b63]">
                                    {tool?.read_only ? "read" : "write"}
                                  </span>
                                </button>
                                {selected && (
                                  <div className="mt-1 grid gap-1 px-1 pb-1">
                                    {tool?.description && <div className="text-[11px] leading-4 text-[#7a766d]">{tool.description}</div>}
                                    {Object.entries(properties).length === 0 ? (
                                      <div className="text-[11px] text-[#9b9489]">No arguments required.</div>
                                    ) : (
                                      Object.entries(properties).map(([name, propertySchema]) => {
                                        const value = mcpToolArgDrafts[toolKey]?.[name] ?? "";
                                        const label = String(name);
                                        if (schemaTypeIncludes(propertySchema, "boolean")) {
                                          return (
                                            <label key={label} className="flex items-center gap-2 text-[11px] text-[#6f6b63]">
                                              <input
                                                type="checkbox"
                                                aria-label={`MCP argument ${label}`}
                                                checked={Boolean(value)}
                                                onChange={(event) => setMcpArgDraft(toolKey, label, event.target.checked)}
                                              />
                                              {label}
                                            </label>
                                          );
                                        }
                                        return (
                                          <label key={label} className="text-[11px] text-[#6f6b63]">
                                            {label}
                                            <input
                                              aria-label={`MCP argument ${label}`}
                                              value={value}
                                              onChange={(event) => setMcpArgDraft(toolKey, label, event.target.value)}
                                              placeholder={schemaTypeIncludes(propertySchema, "object") || schemaTypeIncludes(propertySchema, "array") ? "JSON value" : ""}
                                              className="mt-0.5 h-7 w-full rounded-md border border-[#dedbd2] px-2 text-[12px] text-[#2f2f2d] focus:outline-none focus:ring-2 focus:ring-[#d8d5cc]"
                                            />
                                          </label>
                                        );
                                      })
                                    )}
                                    <button
                                      type="button"
                                      aria-label={`Run MCP tool ${connector.name}/${toolName}`}
                                      onClick={runSelectedMcpTool}
                                      className="mt-1 h-7 rounded-md bg-[#2f2f2d] px-2 text-[11px] font-medium text-white hover:bg-[#1f1f1d]"
                                    >
                                      {tool?.read_only ? "Run tool" : "Request approval & run"}
                                    </button>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                      {error && <div className="mt-1 text-[11px] leading-4 text-[#9b5a48]">{error}</div>}
                    </div>
                  );
                })
              )}
            </div>
            {connectorDraft && (
              <div className="mt-2 rounded-xl border border-[#dedbd2] bg-[#fbfaf7] p-2">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-[12px] font-medium text-[#3b3934]">Connector details</span>
                  <button
                    type="button"
                    aria-label="Close MCP connector editor"
                    onClick={() => {
                      setEditingConnectorName("");
                      setConnectorDraft(null);
                    }}
                    className="grid h-6 w-6 place-items-center rounded-md text-[#6f6b63] hover:bg-[#efede8]"
                  >
                    <X size={13} />
                  </button>
                </div>
                <div className="grid gap-1.5">
                  <label className="text-[11px] text-[#6f6b63]">
                    Name
                    <input
                      aria-label="MCP connector name"
                      value={connectorDraft.name}
                      onChange={(event) => updateConnectorDraft({ name: event.target.value })}
                      className="mt-1 h-7 w-full rounded-md border border-[#dedbd2] bg-white px-2 text-[12px] text-[#2f2f2d] focus:outline-none focus:ring-2 focus:ring-[#d8d5cc]"
                    />
                  </label>
                  <label className="text-[11px] text-[#6f6b63]">
                    Transport
                    <select
                      aria-label="MCP connector transport"
                      value={connectorDraft.transport}
                      onChange={(event) => updateConnectorDraft({ transport: event.target.value })}
                      className="mt-1 h-7 w-full rounded-md border border-[#dedbd2] bg-white px-2 text-[12px] text-[#2f2f2d] focus:outline-none focus:ring-2 focus:ring-[#d8d5cc]"
                    >
                      <option value="stdio">stdio</option>
                      <option value="http">http</option>
                      <option value="sse">sse</option>
                    </select>
                  </label>
                  <label className="text-[11px] text-[#6f6b63]">
                    Command
                    <input
                      aria-label="MCP connector command"
                      value={connectorDraft.command}
                      onChange={(event) => updateConnectorDraft({ command: event.target.value })}
                      className="mt-1 h-7 w-full rounded-md border border-[#dedbd2] bg-white px-2 text-[12px] text-[#2f2f2d] focus:outline-none focus:ring-2 focus:ring-[#d8d5cc]"
                    />
                  </label>
                  <label className="text-[11px] text-[#6f6b63]">
                    URL
                    <input
                      aria-label="MCP connector url"
                      value={connectorDraft.url}
                      onChange={(event) => updateConnectorDraft({ url: event.target.value })}
                      className="mt-1 h-7 w-full rounded-md border border-[#dedbd2] bg-white px-2 text-[12px] text-[#2f2f2d] focus:outline-none focus:ring-2 focus:ring-[#d8d5cc]"
                    />
                  </label>
                  <label className="flex items-center gap-2 text-[11px] text-[#6f6b63]">
                    <input
                      aria-label="MCP connector enabled"
                      type="checkbox"
                      checked={Boolean(connectorDraft.enabled)}
                      onChange={(event) => updateConnectorDraft({ enabled: event.target.checked })}
                    />
                    Enabled
                  </label>
                </div>
                <div className="mt-2 flex flex-wrap justify-end gap-1.5">
                  <button
                    type="button"
                    aria-label={`Test MCP connector ${connectorDraft.name}`}
                    onClick={() => onTestChatConnector?.(connectorDraft)}
                    className="h-7 rounded-md border border-[#dedbd2] px-2 text-[11px] text-[#4a4945] hover:bg-white"
                  >
                    Test
                  </button>
                  <button
                    type="button"
                    aria-label="Delete MCP connector"
                    onClick={deleteConnectorDraft}
                    className="h-7 rounded-md border border-[#edd5ce] px-2 text-[11px] text-[#9b5a48] hover:bg-white"
                  >
                    Delete
                  </button>
                  <button
                    type="button"
                    aria-label="Save MCP connector"
                    onClick={saveConnectorDraft}
                    className="h-7 rounded-md bg-[#2f2f2d] px-2 text-[11px] text-white hover:bg-[#1f1f1d]"
                  >
                    Save
                  </button>
                </div>
              </div>
            )}
            {connectorTestResult && (
              <div className="mt-2 rounded-lg border border-[#ebe8df] bg-[#f7f6f2] px-2 py-1.5 text-[11px] leading-4 text-[#6f6b63]">
                Test: {connectorTestResult.status || "unknown"}
                {Array.isArray(connectorTestResult.errors) && connectorTestResult.errors.length > 0 && (
                  <div className="text-[#9b5a48]">{connectorTestResult.errors.join(" ")}</div>
                )}
              </div>
            )}
            {connectorDiscoveryResult && (
              <div className="mt-2 rounded-lg border border-[#ebe8df] bg-[#f7f6f2] px-2 py-1.5 text-[11px] leading-4 text-[#6f6b63]">
                Discovery: {connectorDiscoveryResult.target || "connector"}
                {connectorDiscoveryResult.message && <div>{connectorDiscoveryResult.message}</div>}
              </div>
            )}
            <div className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-[#8a877f]">Tools</div>
            {webSettings.webMode === "off" && (
              <div className="mx-2 mb-1 rounded-md bg-[#f4f1ea] px-2 py-1 text-[11px] leading-4 text-[#8a7a5f]">
                Web mode is Off: every research tool (web, MCP, Python code) is disabled for this request.
              </div>
            )}
            {[
              { key: "artifacts", label: "Artifacts", enabled: webSettings.artifacts !== "off", available: true },
              { key: "codeExecution", label: "Python code", enabled: webSettings.codeExecution === "on", available: true },
              { key: "mcp", label: "MCP connectors", enabled: webSettings.mcp === "on", available: Boolean(connectorState.enabled) },
            ].map((tool) => (
              <button
                key={tool.key}
                type="button"
                role="menuitemcheckbox"
                aria-checked={tool.enabled}
                disabled={!tool.available && tool.key === "mcp"}
                onClick={() => setToolToggle(tool.key, !tool.enabled)}
                className="flex h-8 w-full items-center justify-between rounded-lg px-2 text-left hover:bg-[#f0efeb] disabled:cursor-not-allowed disabled:text-[#b9b4aa]"
              >
                <span>{tool.label}</span>
                <span className="text-[11px]">{tool.available ? (tool.enabled ? "on" : "off") : "disabled"}</span>
              </button>
            ))}
            {Array.isArray(connectorState.statuses) && connectorState.statuses.length > 0 && (
              <div className="px-2 py-1 text-[11px] leading-4 text-[#9b9489]">
                Connectors: {connectorState.statuses.map((item) => `${item.name || "connector"} ${item.status || "unknown"}`).join(", ")}
              </div>
            )}
            {connectorState.mcp_sdk_available === false && (
              <div className="px-2 py-1 text-[11px] leading-4 text-[#9b9489]">MCP SDK not installed or disabled.</div>
            )}
            <div className="my-2 border-t border-[#ebe8df]" />
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setToolSettingsOpen(false);
                onOpenMemoryManager?.();
              }}
              className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]"
            >
              <Sparkles size={15} /> Memory
            </button>
          </div>
        )}
        <button
          type="button"
          aria-label="Send prompt"
          onClick={submit}
          disabled={!canSubmit}
          className="grid h-8 w-8 place-items-center rounded-lg bg-[#2f2f2d] text-white transition hover:bg-[#1f1f1d] disabled:cursor-not-allowed disabled:bg-[#d8d5cc] disabled:text-white/70"
        >
          <ArrowUp size={16} strokeWidth={2.2} />
        </button>
      </div>
      {skillsOpen && (
        <div
          role="dialog"
          aria-label="Skills"
          className="absolute left-3 right-3 top-[calc(100%+10px)] z-30 rounded-xl border border-[#dedbd2] bg-white p-2 shadow-[0_14px_38px_rgba(0,0,0,0.14)]"
        >
          <div className="flex items-center justify-between px-2 py-1 text-[12px] text-[#8a877f]">
            <span>Code skills</span>
            <span>/</span>
          </div>
          {skillSuggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => {
                setDraft(suggestion);
                textAreaRef.current?.focus();
              }}
              className="block min-h-9 w-full border-t border-[#ebe8df] px-2 py-2 text-left text-[13px] text-[#45433f] hover:bg-[#f7f6f2]"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

