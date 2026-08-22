const { contextBridge, ipcRenderer } = require("electron");

const inboundChannels = new Set([
  "api_keys_loaded",
  "app-update",
  "available_models",
  "backend-log",
  "chat_memory_state",
  "chat_artifacts_state",
  "chat_connectors_state",
  "chat_connector_test_result",
  "chat_connector_discovery_result",
  "chat_mcp_tool_result",
  "chat_quality_eval_state",
  "chat_model_route",
  "brainstorm_log",
  "brainstorm_ui_state",
  "cowork_interactive_question",
  "cowork_log",
  "cowork_log_delta",
  "cowork_status",
  "cowork_completion",
  "cowork_ui_state",
  "factory_attach_label",
  "factory_log",
  "qc_enabled",
  "registered_skills",
  "save_skill_enabled",
  "show_hitl",
  "ui_state",
  "viewport_snap",
  "workspace_changed",
  "workspace_response",
  "web-chat-state",
  "web-chat-grant-state",
]);

function subscribeToChannel(channel, callback) {
  if (!inboundChannels.has(channel)) {
    throw new TypeError(`IPC channel not allowed: ${channel}`);
  }

  if (typeof callback !== "function") {
    throw new TypeError("IPC listener requires a function callback.");
  }

  const listener = (_event, payload) => {
    callback(payload);
  };

  ipcRenderer.on(channel, listener);

  return () => {
    ipcRenderer.removeListener(channel, listener);
  };
}

ipcRenderer.send("preload-ready");

contextBridge.exposeInMainWorld("electronAPI", {
  isElectron: true,
  platform: process.platform,
  versions: {
    chrome: process.versions.chrome,
    electron: process.versions.electron,
    node: process.versions.node,
  },
  minimize: () => ipcRenderer.send("window-minimize"),
  maximize: () => ipcRenderer.send("window-maximize"),
  close: () => ipcRenderer.send("window-close"),
  answerQuestion: (answer) => ipcRenderer.invoke("answer-question", answer),
  fetchModels: () => ipcRenderer.invoke("fetch-models"),
  fetchRegisteredSkills: () => ipcRenderer.invoke("fetch-registered-skills"),
  loadApiKeys: () => ipcRenderer.invoke("load-api-keys"),
  setProviderKey: (provider, key) => ipcRenderer.invoke("set-provider-key", provider, key),
  setCustomAnthropicProvider: (payload) => ipcRenderer.invoke("set-custom-anthropic-provider", payload),
  importCustomAnthropicModels: (payload) => ipcRenderer.invoke("import-custom-anthropic-models", payload),
  getAppUpdateState: () => ipcRenderer.invoke("get-app-update-state"),
  installUpdateNow: () => ipcRenderer.invoke("install-update-now"),
  loadSessionState: () => ipcRenderer.invoke("session-state-load"),
  saveSessionState: (envelope) => ipcRenderer.invoke("session-state-save", envelope),
  getWebChatState: () => ipcRenderer.invoke("web-chat-state"),
  showWebChat: (bounds) => ipcRenderer.invoke("web-chat-show", bounds),
  hideWebChat: () => ipcRenderer.invoke("web-chat-hide"),
  controlWebChat: (command) => ipcRenderer.invoke("web-chat-control", command),
  getWebChatGrantState: () => ipcRenderer.invoke("web-chat-grant-state"),
  setWebChatGrant: (payload) => ipcRenderer.invoke("web-chat-grant-set", payload),
  revokeWebChatGrant: () => ipcRenderer.invoke("web-chat-grant-revoke"),
  startWebChatTunnel: (payload) => ipcRenderer.invoke("web-chat-tunnel-start", payload),
  stopWebChatTunnel: () => ipcRenderer.invoke("web-chat-tunnel-stop"),
  probeWebChatConnector: () => ipcRenderer.invoke("web-chat-connector-probe"),
  copyWebChatConnectorValue: (kind) => ipcRenderer.invoke("web-chat-connector-copy", kind),
  setAutoApprove: (enabled) => ipcRenderer.invoke("set-auto-approve", enabled),
  setPermissionMode: (mode) => ipcRenderer.invoke("set-permission-mode", mode),
  listChatMemory: () => ipcRenderer.invoke("chat-memory-list"),
  createChatMemory: (payload) => ipcRenderer.invoke("chat-memory-create", payload),
  updateChatMemory: (id, text) => ipcRenderer.invoke("chat-memory-update", id, text),
  setChatMemoryEnabled: (id, enabled) => ipcRenderer.invoke("chat-memory-set-enabled", id, enabled),
  deleteChatMemory: (id) => ipcRenderer.invoke("chat-memory-delete", id),
  listChatArtifacts: () => ipcRenderer.invoke("chat-artifact-list"),
  listChatQualityEval: () => ipcRenderer.invoke("chat-quality-eval-list"),
  runChatQualityEval: (payload) => ipcRenderer.invoke("chat-quality-eval-run", payload),
  runChatQuality: (payload) => ipcRenderer.invoke("chat-quality-run", payload),
  listChatConnectors: () => ipcRenderer.invoke("chat-connector-list"),
  saveChatConnectors: (connectors) => ipcRenderer.invoke("chat-connector-save", connectors),
  testChatConnector: (connector) => ipcRenderer.invoke("chat-connector-test", connector),
  discoverChatConnector: (target) => ipcRenderer.invoke("chat-connector-discover", target),
  runChatMcpTool: (payload) => ipcRenderer.invoke("chat-mcp-tool-run", payload),
  selectFolder: () => ipcRenderer.invoke("select-folder"),
  sendCowork: (prompt, model, sessionId, mode, effort, attachments, webSettings, history, visionSettings) => ipcRenderer.invoke("send-cowork", prompt, model, sessionId, mode, effort, attachments, webSettings, history, visionSettings),
  cancelCowork: (sessionId, mode) => ipcRenderer.invoke("cancel-cowork", sessionId, mode),
  setWorkspace: (path) => ipcRenderer.invoke("set-workspace", path),
  workspaceAction: (payload) => ipcRenderer.invoke("workspace-action", payload),
  setApiKeys: (geminiKey, openaiKey, localAiBaseUrl, localAiApiKey) =>
    ipcRenderer.invoke("set-api-keys", geminiKey, openaiKey, localAiBaseUrl, localAiApiKey),
  onBackendLog: (callback) => subscribeToChannel("backend-log", callback),
  onIpcEvent: (channel, callback) => subscribeToChannel(channel, callback),
  onModelsFetched: (callback) => subscribeToChannel("available_models", callback),
});
