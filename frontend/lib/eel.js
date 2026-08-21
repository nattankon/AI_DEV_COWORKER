const eelEvents = {
  apiKeysLoaded: "eel:api_keys_loaded",
  appUpdate: "eel:app_update",
  availableModels: "eel:available_models",
  brainstormLog: "eel:brainstorm_log",
  backendLog: "eel:backend_log",
  chatMemoryState: "eel:chat_memory_state",
  chatArtifactsState: "eel:chat_artifacts_state",
  chatConnectorsState: "eel:chat_connectors_state",
  chatConnectorTestResult: "eel:chat_connector_test_result",
  chatConnectorDiscoveryResult: "eel:chat_connector_discovery_result",
  chatMcpToolResult: "eel:chat_mcp_tool_result",
  chatQualityEvalState: "eel:chat_quality_eval_state",
  chatModelRoute: "eel:chat_model_route",
  coworkInteractiveQuestion: "eel:cowork_interactive_question",
  brainstormUiState: "eel:brainstorm_ui_state",
  coworkLog: "eel:cowork_log",
  coworkUiState: "eel:cowork_ui_state",
  factoryLog: "eel:factory_log",
  uiState: "eel:ui_state",
  viewportSnap: "eel:viewport_snap",
  factoryAttachLabel: "eel:factory_attach_label",
  qcEnabled: "eel:qc_enabled",
  registeredSkills: "eel:registered_skills",
  saveSkillEnabled: "eel:save_skill_enabled",
  showHitl: "eel:show_hitl",
  workspaceChanged: "eel:workspace_changed",
  workspaceResponse: "eel:workspace_response",
};

const ipcEventMap = {
  api_keys_loaded: eelEvents.apiKeysLoaded,
  "app-update": eelEvents.appUpdate,
  available_models: eelEvents.availableModels,
  "backend-log": eelEvents.backendLog,
  chat_memory_state: eelEvents.chatMemoryState,
  chat_artifacts_state: eelEvents.chatArtifactsState,
  chat_connectors_state: eelEvents.chatConnectorsState,
  chat_connector_test_result: eelEvents.chatConnectorTestResult,
  chat_connector_discovery_result: eelEvents.chatConnectorDiscoveryResult,
  chat_mcp_tool_result: eelEvents.chatMcpToolResult,
  chat_quality_eval_state: eelEvents.chatQualityEvalState,
  brainstorm_log: eelEvents.brainstormLog,
  cowork_interactive_question: eelEvents.coworkInteractiveQuestion,
  brainstorm_ui_state: eelEvents.brainstormUiState,
  cowork_log: eelEvents.coworkLog,
  cowork_log_delta: "cowork_log_delta",
  cowork_status: "cowork_status",
  cowork_completion: "cowork_completion",
  cowork_ui_state: eelEvents.coworkUiState,
  factory_attach_label: eelEvents.factoryAttachLabel,
  factory_log: eelEvents.factoryLog,
  qc_enabled: eelEvents.qcEnabled,
  registered_skills: eelEvents.registeredSkills,
  save_skill_enabled: eelEvents.saveSkillEnabled,
  show_hitl: eelEvents.showHitl,
  ui_state: eelEvents.uiState,
  viewport_snap: eelEvents.viewportSnap,
  workspace_changed: eelEvents.workspaceChanged,
  workspace_response: eelEvents.workspaceResponse,
};

const readyCallbacks = new Set();
let bridgeRegistered = false;
let bridgeReadyDispatched = false;
let bridgeBootstrapTimer;

export { eelEvents };

function getBridge() {
  return typeof window !== "undefined" ? window.electronAPI : undefined;
}

export function hasEel() {
  return typeof window !== "undefined" && !!window.electronAPI;
}

function flushReadyCallbacks() {
  const bridge = getBridge();
  if (!bridge) {
    return;
  }

  for (const callback of readyCallbacks) {
    callback(bridge);
  }

  readyCallbacks.clear();
}

function finalizeBridgeRegistration() {
  const bridge = getBridge();
  if (!bridge || typeof bridge.onIpcEvent !== "function") {
    return false;
  }

  if (!bridgeRegistered) {
    bridgeRegistered = true;

    for (const [ipcType, eventName] of Object.entries(ipcEventMap)) {
      // A single disallowed/broken channel must never abort registration and
      // white-screen the app — isolate each subscription.
      try {
        bridge.onIpcEvent(ipcType, (payload) => {
          window.dispatchEvent(
            new CustomEvent(eventName, {
              detail: buildEventDetail(payload),
            }),
          );
        });
      } catch (error) {
        console.error(`[eel] Failed to subscribe to IPC channel "${ipcType}":`, error);
      }
    }
  }

  if (!bridgeReadyDispatched) {
    bridgeReadyDispatched = true;
    window.dispatchEvent(new Event("eel:ready"));
  }

  flushReadyCallbacks();
  return true;
}

function ensureBridgeRegistration() {
  if (typeof window === "undefined") {
    return;
  }

  if (finalizeBridgeRegistration() || typeof bridgeBootstrapTimer !== "undefined") {
    return;
  }

  let attempts = 0;
  const maxAttempts = 120;

  const tick = () => {
    bridgeBootstrapTimer = undefined;

    if (finalizeBridgeRegistration()) {
      return;
    }

    attempts += 1;
    if (attempts >= maxAttempts) {
      return;
    }

    bridgeBootstrapTimer = window.setTimeout(tick, 50);
  };

  bridgeBootstrapTimer = window.setTimeout(tick, 0);
}

if (typeof window !== "undefined") {
  queueMicrotask(() => {
    ensureBridgeRegistration();
  });
}

export function onEelReady(callback) {
  const bridge = getBridge();
  if (bridge) {
    callback(bridge);
    return () => {};
  }

  readyCallbacks.add(callback);
  ensureBridgeRegistration();

  return () => {
    readyCallbacks.delete(callback);
  };
}

export function subscribeEelEvent(eventName, handler) {
  window.addEventListener(eventName, handler);

  return () => {
    window.removeEventListener(eventName, handler);
  };
}

function normalizeArgs(argsOrFirstArg, restArgs) {
  if (Array.isArray(argsOrFirstArg)) {
    return argsOrFirstArg;
  }

  if (typeof argsOrFirstArg === "undefined") {
    return [];
  }

  return [argsOrFirstArg, ...restArgs];
}

function invokeBridgeMethod(method, args = []) {
  const bridge = getBridge();
  if (!bridge) {
    return null;
  }

  const methodMap = {
    answer_question: bridge.answerQuestion,
    attach_image: bridge.attachImage,
    fetch_registered_skills: bridge.fetchRegisteredSkills,
    fetch_models: bridge.fetchModels,
    chat_memory_list: bridge.listChatMemory,
    chat_memory_create: bridge.createChatMemory,
    chat_memory_update: bridge.updateChatMemory,
    chat_memory_set_enabled: bridge.setChatMemoryEnabled,
    chat_memory_delete: bridge.deleteChatMemory,
    chat_artifact_list: bridge.listChatArtifacts,
    chat_quality_eval_list: bridge.listChatQualityEval,
    chat_quality_eval_run: bridge.runChatQualityEval,
    chat_quality_run: bridge.runChatQuality,
    chat_connector_list: bridge.listChatConnectors,
    chat_connector_save: bridge.saveChatConnectors,
    chat_connector_test: bridge.testChatConnector,
    chat_connector_discover: bridge.discoverChatConnector,
    chat_mcp_tool_run: bridge.runChatMcpTool,
    cancel_cowork: bridge.cancelCowork,
    load_api_keys: bridge.loadApiKeys,
    set_provider_key: bridge.setProviderKey,
    set_custom_anthropic_provider: bridge.setCustomAnthropicProvider,
    import_custom_anthropic_models: bridge.importCustomAnthropicModels,
    get_app_update_state: bridge.getAppUpdateState,
    install_update_now: bridge.installUpdateNow,
    set_auto_approve: bridge.setAutoApprove,
    set_permission_mode: bridge.setPermissionMode,
    resolve_hitl: bridge.resolveHitl,
    select_folder: bridge.selectFolder,
    send_brainstorm: bridge.sendBrainstorm,
    send_cowork: bridge.sendCowork,
    send_factory: bridge.sendFactory,
    set_api_keys: bridge.setApiKeys,
    snap_viewport: bridge.snapViewport,
    set_workspace: bridge.setWorkspace,
    trigger_save_skill: bridge.triggerSaveSkill,
    trigger_visual_qc: bridge.triggerVisualQc,
    workspace_action: bridge.workspaceAction,
  };

  const bridgeMethod = methodMap[method];
  if (typeof bridgeMethod !== "function") {
    return null;
  }

  return bridgeMethod(...args);
}

export async function callEel(method, argsOrFirstArg, ...restArgs) {
  return invokeBridgeMethod(method, normalizeArgs(argsOrFirstArg, restArgs));
}

export function sendBrainstorm(prompt, imageB64, model) {
  return invokeBridgeMethod("send_brainstorm", [prompt, imageB64, model]);
}

export function selectFolder() {
  return invokeBridgeMethod("select_folder");
}

export function sendCowork(prompt, model, sessionId, mode, effort, attachments, webSettings, history, visionSettings) {
  return invokeBridgeMethod("send_cowork", [prompt, model, sessionId, mode, effort, attachments, webSettings, history, visionSettings]);
}

export function cancelCowork(sessionId, mode) {
  return invokeBridgeMethod("cancel_cowork", [sessionId, mode]);
}

export function sendFactory(prompt, model) {
  return invokeBridgeMethod("send_factory", [prompt, model]);
}

export function fetchRegisteredSkills() {
  return invokeBridgeMethod("fetch_registered_skills");
}

export function fetchModels() {
  return invokeBridgeMethod("fetch_models");
}

export function snapViewport() {
  return invokeBridgeMethod("snap_viewport");
}

export function loadApiKeys() {
  return invokeBridgeMethod("load_api_keys");
}

export function setProviderKey(provider, key) {
  return invokeBridgeMethod("set_provider_key", provider, key);
}

export function setCustomAnthropicProvider(payload) {
  return invokeBridgeMethod("set_custom_anthropic_provider", [payload]);
}

export function importCustomAnthropicModels(payload) {
  return invokeBridgeMethod("import_custom_anthropic_models", [payload]);
}

export function installUpdateNow() {
  return invokeBridgeMethod("install_update_now");
}

export function getAppUpdateState() {
  return invokeBridgeMethod("get_app_update_state");
}

export function listChatMemory() {
  return invokeBridgeMethod("chat_memory_list");
}

export function createChatMemory(payload) {
  return invokeBridgeMethod("chat_memory_create", [payload]);
}

export function setAutoApprove(enabled) {
  return invokeBridgeMethod("set_auto_approve", [enabled]);
}

export function setPermissionMode(mode) {
  return invokeBridgeMethod("set_permission_mode", [mode]);
}

export function updateChatMemory(id, text) {
  return invokeBridgeMethod("chat_memory_update", [id, text]);
}

export function setChatMemoryEnabled(id, enabled) {
  return invokeBridgeMethod("chat_memory_set_enabled", [id, enabled]);
}

export function deleteChatMemory(id) {
  return invokeBridgeMethod("chat_memory_delete", [id]);
}

export function listChatArtifacts() {
  return invokeBridgeMethod("chat_artifact_list");
}

export function listChatConnectors() {
  return invokeBridgeMethod("chat_connector_list");
}

export function listChatQualityEval() {
  return invokeBridgeMethod("chat_quality_eval_list");
}

export function runChatQualityEval(payload) {
  return invokeBridgeMethod("chat_quality_eval_run", [payload]);
}

export function runChatQuality(payload) {
  return invokeBridgeMethod("chat_quality_run", [payload]);
}

export function saveChatConnectors(connectors) {
  return invokeBridgeMethod("chat_connector_save", [connectors]);
}

export function testChatConnector(connector) {
  return invokeBridgeMethod("chat_connector_test", [connector]);
}

export function discoverChatConnector(target) {
  return invokeBridgeMethod("chat_connector_discover", [target]);
}

export function runChatMcpTool(payload) {
  return invokeBridgeMethod("chat_mcp_tool_run", [payload]);
}

export function answerQuestion(answer) {
  return invokeBridgeMethod("answer_question", [answer]);
}

export function setApiKeys(geminiKey, openaiKey, localAiBaseUrl, localAiApiKey) {
  return invokeBridgeMethod("set_api_keys", [geminiKey, openaiKey, localAiBaseUrl, localAiApiKey]);
}

export function setWorkspace(path) {
  return invokeBridgeMethod("set_workspace", [path]);
}

export function workspaceAction(payload) {
  return invokeBridgeMethod("workspace_action", [payload]);
}

export function triggerVisualQc() {
  return invokeBridgeMethod("trigger_visual_qc");
}

function buildEventDetail(payload) {
  if (!payload || typeof payload !== "object") {
    return {};
  }

  const { __ipc_type: _ignoredIpcType, ...detail } = payload;
  return detail;
}

export function registerDefaultEelBridge() {
  ensureBridgeRegistration();
}
