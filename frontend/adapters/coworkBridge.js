import { createCoworkEvent } from "../model/coworkEvents";

function defaultCreateId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function normalizeRole(role) {
  const normalized = String(role || "").toUpperCase();
  if (normalized === "USER") return "message.user";
  if (normalized === "SYSTEM") return "message.system";
  return "message.assistant";
}

function normalizeMode(mode) {
  const normalized = String(mode || "").trim();
  return ["Chat", "Cowork", "Code"].includes(normalized) ? normalized : "";
}

function normalizeLegacyLog(payload, sessionId, options) {
  const mode = normalizeMode(payload?.mode);
  const webSources = Array.isArray(payload?.web_sources)
    ? payload.web_sources
    : Array.isArray(payload?.webSources)
      ? payload.webSources
      : [];
  return createCoworkEvent({
    id: options.createId(),
    sessionId: String(payload?.client_session_id ?? payload?.clientSessionId ?? sessionId),
    timestamp: payload?.timestamp || options.now(),
    type: normalizeRole(payload?.role),
    status: "complete",
    payload: {
      text: String(payload?.text ?? ""),
      role: String(payload?.role ?? "AI"),
      ...(mode ? { mode } : {}),
      ...(webSources.length ? { webSources } : {}),
    },
  });
}

function normalizeLegacyUiState(payload, sessionId, options) {
  const mode = normalizeMode(payload?.mode);
  return createCoworkEvent({
    id: options.createId(),
    sessionId: String(payload?.client_session_id ?? payload?.clientSessionId ?? sessionId),
    timestamp: payload?.timestamp || options.now(),
    type: "agent.status",
    status: payload?.state === "busy" ? "running" : "complete",
    payload: {
      state: payload?.state === "busy" ? "busy" : "idle",
      ...(mode ? { mode } : {}),
    },
  });
}

function normalizeBackendLog(payload, sessionId, options) {
  const message = String(payload?.message ?? "Cowork request failed.").trim() || "Cowork request failed.";
  const mode = normalizeMode(payload?.mode);
  const label = mode ? `${mode} could not complete the request` : "Request could not complete";
  return createCoworkEvent({
    id: options.createId(),
    sessionId: String(payload?.client_session_id ?? payload?.clientSessionId ?? sessionId),
    timestamp: payload?.timestamp || options.now(),
    type: "message.system",
    status: "failed",
    payload: {
      text: `${label}: ${message}`,
      role: "SYSTEM",
      ...(mode ? { mode } : {}),
    },
  });
}

function normalizeLegacyDelta(payload, sessionId, options) {
  const mode = normalizeMode(payload?.mode);
  const targetSessionId = String(payload?.client_session_id ?? payload?.clientSessionId ?? sessionId);
  const modeKey = mode || "Cowork";
  return createCoworkEvent({
    id: `stream-${targetSessionId}-${modeKey}`,
    sessionId: targetSessionId,
    timestamp: payload?.timestamp || options.now(),
    type: "message.assistant",
    status: "running",
    payload: {
      text: String(payload?.delta ?? ""),
      role: "AI",
      ...(mode ? { mode } : {}),
      streaming: true,
      ...(payload?.reset ? { reset: true } : {}),
    },
  });
}

function normalizeLegacyStatus(payload, sessionId, options) {
  const mode = normalizeMode(payload?.mode);
  const targetSessionId = String(payload?.client_session_id ?? payload?.clientSessionId ?? sessionId);
  const modeKey = mode || "Chat";
  return createCoworkEvent({
    id: `status-${targetSessionId}-${modeKey}`,
    sessionId: targetSessionId,
    timestamp: payload?.timestamp || options.now(),
    type: "chat.status",
    status: "running",
    payload: {
      text: String(payload?.text ?? ""),
      ...(mode ? { mode } : {}),
      transient: true,
    },
  });
}

function normalizeMcpToolResult(payload, sessionId, options) {
  const mode = normalizeMode(payload?.mode) || "Chat";
  return createCoworkEvent({
    id: options.createId(),
    sessionId: String(payload?.client_session_id ?? payload?.clientSessionId ?? sessionId),
    timestamp: payload?.timestamp || options.now(),
    type: "mcp.result",
    status: String(payload?.status || "complete") === "ok" ? "complete" : "failed",
    payload: {
      mode,
      origin: String(payload?.origin || "manual"),
      server: String(payload?.server || ""),
      tool: String(payload?.tool || ""),
      arguments: payload?.arguments && typeof payload.arguments === "object" ? payload.arguments : {},
      status: String(payload?.status || "error"),
      readOnly: Boolean(payload?.read_only ?? payload?.readOnly),
      result: payload?.result,
      error: String(payload?.error || ""),
      durationMs: Number(payload?.duration_ms ?? payload?.durationMs ?? 0),
    },
  });
}

function normalizeModelName(model) {
  const normalized = String(model || "").trim();
  if (!normalized) return "";
  return /^(local|openai|deepseek|zai|gemini):/.test(normalized) ? normalized : `local:${normalized}`;
}

function normalizeLegacyQuestion(payload, sessionId, options) {
  const approvalKind = String(payload?.approval_kind ?? payload?.approvalKind ?? "");
  const title = approvalKind === "run_verification"
    ? "Approve verification run"
    : approvalKind === "mcp_tool_call"
      ? "Approve MCP tool"
      : approvalKind === "chat_run_python"
        ? "Approve Chat Python code"
        : "Approve file write";
  const mode = normalizeMode(payload?.mode);
  return createCoworkEvent({
    id: options.createId(),
    sessionId: String(payload?.client_session_id ?? payload?.clientSessionId ?? sessionId),
    timestamp: payload?.timestamp || options.now(),
    type: "approval.requested",
    status: "pending",
    payload: {
      approvalId: String(payload?.approval_id ?? payload?.approvalId ?? options.createId()),
      approvalKind,
      question: String(payload?.question ?? ""),
      title,
      options: Array.isArray(payload?.options) ? payload.options.map(String) : ["allow", "deny"],
      proposal: payload?.proposal && typeof payload.proposal === "object" ? payload.proposal : {},
      ...(mode ? { mode } : {}),
    },
  });
}

export function createCoworkBridge(legacyBridge, overrides = {}) {
  const options = {
    createId: defaultCreateId,
    now: () => new Date().toISOString(),
    ...overrides,
  };

  return {
    async sendPrompt({ prompt, model, workingDirectory = "", sessionId = "", mode = "Cowork", effort = "Medium", attachments = [], webSettings = {}, history = [] }) {
      if (typeof legacyBridge?.sendPrompt !== "function") return;
      const promptWithContext = workingDirectory
        ? `[Target Working Directory: ${workingDirectory}]\n${prompt}`
        : prompt;
      await legacyBridge.sendPrompt(promptWithContext, model, sessionId, mode, effort, attachments, webSettings, history);
    },
    async cancelPrompt({ sessionId = "", mode = "Cowork" } = {}) {
      if (typeof legacyBridge?.cancelPrompt === "function") {
        await legacyBridge.cancelPrompt(sessionId, mode);
      }
    },
    async selectWorkspace() {
      if (typeof legacyBridge?.selectWorkspace !== "function") return "";
      const selected = await legacyBridge.selectWorkspace();
      return typeof selected === "string" ? selected.trim() : "";
    },
    async answerApproval(answer) {
      if (typeof legacyBridge?.answerApproval === "function") {
        await legacyBridge.answerApproval(answer);
      }
    },
    async setWorkspace(path) {
      if (typeof legacyBridge?.setWorkspace === "function") {
        await legacyBridge.setWorkspace(path);
      }
    },
    async workspaceAction(payload) {
      if (typeof legacyBridge?.workspaceAction === "function") {
        await legacyBridge.workspaceAction(payload);
      }
    },
    async fetchModels() {
      if (typeof legacyBridge?.fetchModels === "function") {
        await legacyBridge.fetchModels();
      }
    },
    async loadApiKeys() {
      if (typeof legacyBridge?.loadApiKeys === "function") {
        await legacyBridge.loadApiKeys();
      }
    },
    async setProviderKey(provider, key) {
      if (typeof legacyBridge?.setProviderKey === "function") {
        await legacyBridge.setProviderKey(provider, key);
      }
    },
    async listChatMemory() {
      if (typeof legacyBridge?.listChatMemory === "function") {
        await legacyBridge.listChatMemory();
      }
    },
    async createChatMemory(payload) {
      if (typeof legacyBridge?.createChatMemory === "function") {
        await legacyBridge.createChatMemory(payload);
      }
    },
    async updateChatMemory(id, text) {
      if (typeof legacyBridge?.updateChatMemory === "function") {
        await legacyBridge.updateChatMemory(id, text);
      }
    },
    async setChatMemoryEnabled(id, enabled) {
      if (typeof legacyBridge?.setChatMemoryEnabled === "function") {
        await legacyBridge.setChatMemoryEnabled(id, enabled);
      }
    },
    async deleteChatMemory(id) {
      if (typeof legacyBridge?.deleteChatMemory === "function") {
        await legacyBridge.deleteChatMemory(id);
      }
    },
    async listChatArtifacts() {
      if (typeof legacyBridge?.listChatArtifacts === "function") {
        await legacyBridge.listChatArtifacts();
      }
    },
    async listChatQualityEval() {
      if (typeof legacyBridge?.listChatQualityEval === "function") {
        await legacyBridge.listChatQualityEval();
      }
    },
    async runChatQualityEval(payload) {
      if (typeof legacyBridge?.runChatQualityEval === "function") {
        await legacyBridge.runChatQualityEval(payload);
      }
    },
    async runChatQuality(payload) {
      if (typeof legacyBridge?.runChatQuality === "function") {
        await legacyBridge.runChatQuality(payload);
        return;
      }
      if (typeof legacyBridge?.runChatQualityEval === "function") {
        await legacyBridge.runChatQualityEval(payload);
      }
    },
    async listChatConnectors() {
      if (typeof legacyBridge?.listChatConnectors === "function") {
        await legacyBridge.listChatConnectors();
      }
    },
    async saveChatConnectors(connectors) {
      if (typeof legacyBridge?.saveChatConnectors === "function") {
        await legacyBridge.saveChatConnectors(connectors);
      }
    },
    async testChatConnector(connector) {
      if (typeof legacyBridge?.testChatConnector === "function") {
        await legacyBridge.testChatConnector(connector);
      }
    },
    async discoverChatConnector(target) {
      if (typeof legacyBridge?.discoverChatConnector === "function") {
        await legacyBridge.discoverChatConnector(target);
      }
    },
    async runChatMcpTool(payload) {
      if (typeof legacyBridge?.runChatMcpTool === "function") {
        await legacyBridge.runChatMcpTool(payload);
      }
    },
    subscribeApiKeys(listener) {
      const subscribe = legacyBridge?.subscribe;
      if (typeof subscribe !== "function") return () => {};
      return subscribe("api_keys_loaded", (event) => listener(event?.detail ?? event ?? {}));
    },
    subscribeAppUpdate(listener) {
      const subscribe = legacyBridge?.subscribe;
      if (typeof subscribe !== "function") return () => {};
      return subscribe("app-update", (event) => listener(event?.detail ?? event ?? {}));
    },
    async installUpdateNow() {
      if (typeof legacyBridge?.installUpdateNow === "function") {
        await legacyBridge.installUpdateNow();
      }
    },
    subscribeChatMemory(listener) {
      const subscribe = legacyBridge?.subscribe;
      if (typeof subscribe !== "function") return () => {};
      return subscribe("chat_memory_state", (event) => listener(event?.detail ?? event ?? {}));
    },
    subscribeChatArtifacts(listener) {
      const subscribe = legacyBridge?.subscribe;
      if (typeof subscribe !== "function") return () => {};
      return subscribe("chat_artifacts_state", (event) => listener(event?.detail ?? event ?? {}));
    },
    subscribeChatConnectors(listener) {
      const subscribe = legacyBridge?.subscribe;
      if (typeof subscribe !== "function") return () => {};
      return subscribe("chat_connectors_state", (event) => listener(event?.detail ?? event ?? {}));
    },
    subscribeChatConnectorTests(listener) {
      const subscribe = legacyBridge?.subscribe;
      if (typeof subscribe !== "function") return () => {};
      return subscribe("chat_connector_test_result", (event) => listener(event?.detail ?? event ?? {}));
    },
    subscribeChatConnectorDiscovery(listener) {
      const subscribe = legacyBridge?.subscribe;
      if (typeof subscribe !== "function") return () => {};
      return subscribe("chat_connector_discovery_result", (event) => listener(event?.detail ?? event ?? {}));
    },
    subscribeChatQualityEval(listener) {
      const subscribe = legacyBridge?.subscribe;
      if (typeof subscribe !== "function") return () => {};
      return subscribe("chat_quality_eval_state", (event) => listener(event?.detail ?? event ?? {}));
    },
    subscribeModelRoutes(listener) {
      const subscribe = legacyBridge?.subscribe;
      if (typeof subscribe !== "function") return () => {};
      return subscribe("chat_model_route", (event) => listener(event?.detail ?? event ?? {}));
    },
    subscribeModels(listener) {
      const subscribe = legacyBridge?.subscribe;
      if (typeof subscribe !== "function") return () => {};
      return subscribe("available_models", (event) => {
        const payload = event?.detail ?? event ?? {};
        const models = Array.isArray(payload?.models) ? payload.models.map(normalizeModelName).filter(Boolean) : [];
        listener(models, { ...payload, models });
      });
    },
    subscribeWorkspace(listener) {
      const subscribe = legacyBridge?.subscribe;
      if (typeof subscribe !== "function") return () => {};
      const disposers = ["workspace_changed", "workspace_response"].map((eventName) =>
        subscribe(eventName, (event) => listener(event?.detail ?? event ?? {})),
      ).filter((dispose) => typeof dispose === "function");
      return () => disposers.forEach((dispose) => dispose());
    },
    subscribe(sessionId, listener) {
      const subscribe = legacyBridge?.subscribe;
      if (typeof subscribe !== "function") return () => {};

      const disposers = [
        subscribe("cowork_log", (event) => {
          const payload = event?.detail ?? event ?? {};
          if (String(payload?.role || "").toUpperCase() === "USER") return;
          listener(normalizeLegacyLog(payload, sessionId, options));
        }),
        subscribe("cowork_ui_state", (event) => {
          listener(normalizeLegacyUiState(event?.detail ?? event ?? {}, sessionId, options));
        }),
        subscribe("cowork_log_delta", (event) => {
          listener(normalizeLegacyDelta(event?.detail ?? event ?? {}, sessionId, options));
        }),
        subscribe("cowork_status", (event) => {
          listener(normalizeLegacyStatus(event?.detail ?? event ?? {}, sessionId, options));
        }),
        subscribe("chat_mcp_tool_result", (event) => {
          listener(normalizeMcpToolResult(event?.detail ?? event ?? {}, sessionId, options));
        }),
        subscribe("backend-log", (event) => {
          listener(normalizeBackendLog(event?.detail ?? event ?? {}, sessionId, options));
        }),
        subscribe("cowork_interactive_question", (event) => {
          listener(normalizeLegacyQuestion(event?.detail ?? event ?? {}, sessionId, options));
        }),
      ].filter((dispose) => typeof dispose === "function");

      return () => {
        for (const dispose of disposers) {
          dispose();
        }
      };
    },
  };
}
