import { spawn, spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { app, BrowserWindow, clipboard, dialog, ipcMain, shell, WebContentsView } from "electron";
import electronUpdater from "electron-updater";
import { getPythonEntryCandidates, getSidecarPythonPathCandidates } from "./pathResolution.js";
import {
  CHATGPT_WEB_URL,
  WEB_CHAT_PARTITION,
  isSafeExternalWebUrl,
  normalizeWebChatBounds,
  sanitizeWebChatCommand,
} from "./webChatSurface.js";
import { WebChatGrantStore } from "./webChatGrantStore.js";
import { createSessionStateStore } from "./sessionStateStore.js";
import {
  emptyWebChatGatewayState,
  emptyWebChatTunnelState,
  mergeWebChatGatewayState,
  normalizeWebChatGatewayState,
  normalizeWebChatTunnelState,
} from "./webChatGatewayState.js";
import {
  canCopyConnectorSetupValue,
  emptyWebChatConnectorSetupState,
  normalizeWebChatConnectorSetupState,
  probeRemoteMcp,
  writeConnectorClipboard,
} from "./webChatConnectorSetup.js";

const { autoUpdater } = electronUpdater;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const appRoot = path.resolve(__dirname, "..");
const preloadPath = path.join(__dirname, "preload.cjs");
const rendererDistPath = path.join(appRoot, "dist", "index.html");
const appIconPath = path.join(appRoot, "assets", "app-icon.ico");
const isDev = process.env.NODE_ENV === "development";

let mainWindow;
let pythonProcess;
let webChatView;
let webChatVisible = false;
let webChatGrantStore;
let sessionStateStore;
let webChatGatewayState = emptyWebChatGatewayState();
let webChatTunnelState = emptyWebChatTunnelState();
let webChatTunnelCredential = "";
let webChatConnectorSetupState = emptyWebChatConnectorSetupState();
let webChatState = {
  loading: false,
  title: "ChatGPT",
  url: CHATGPT_WEB_URL,
  canGoBack: false,
  canGoForward: false,
  error: "",
};
const approvedWorkspacePaths = new Set();

function getWebChatGrantStore() {
  if (!webChatGrantStore) {
    webChatGrantStore = new WebChatGrantStore({
      filePath: path.join(app.getPath("userData"), "web-chat-workspace-grant.json"),
    });
  }
  return webChatGrantStore;
}

function getSessionStateStore() {
  if (!sessionStateStore) {
    sessionStateStore = createSessionStateStore({ directory: app.getPath("userData") });
  }
  return sessionStateStore;
}

function normalizeWorkspacePath(value) {
  const resolved = path.resolve(String(value || ""));
  return process.platform === "win32" ? resolved.toLocaleLowerCase("en-US") : resolved;
}

function firstExistingPath(candidates) {
  return candidates.find((candidate) => candidate && fs.existsSync(candidate));
}

function resolvePythonEntryPath() {
  return firstExistingPath(
    getPythonEntryCandidates({
      appRoot,
      resourcesPath: process.resourcesPath,
      env: process.env,
    }),
  );
}

function resolvePythonPath() {
  return firstExistingPath([
    process.env.PYTHON_EXECUTABLE,
    path.join(process.resourcesPath, "python", process.platform === "win32" ? "python.exe" : "python"),
  ]) ?? "python";
}

function resolveSidecarPythonPath() {
  return getSidecarPythonPathCandidates({ appRoot, resourcesPath: process.resourcesPath })
    .filter((candidate) => fs.existsSync(candidate))
    .join(path.delimiter);
}

function dispatchRendererEvent(channel, payload) {
  for (const window of BrowserWindow.getAllWindows()) {
    if (!window.isDestroyed()) {
      window.webContents.send(channel, payload);
    }
  }
}

function emitBackendLog(source, message) {
  const payload = {
    source,
    message,
    timestamp: new Date().toISOString(),
  };
  console[source === "stderr" ? "error" : "log"](`[python:${source}] ${message}`);
  dispatchRendererEvent("backend-log", payload);
}

function handlePythonStdoutLine(message) {
  try {
    const parsed = JSON.parse(message);
    if (parsed && typeof parsed === "object" && typeof parsed.__ipc_type === "string") {
      if (parsed.__ipc_type === "web_chat_gateway_state") {
        webChatGatewayState = normalizeWebChatGatewayState(parsed);
        emitWebChatGrantState();
      }
      if (parsed.__ipc_type === "web_chat_tunnel_state") {
        const previousEndpoint = webChatTunnelState.endpoint;
        webChatTunnelState = normalizeWebChatTunnelState(parsed);
        if (webChatTunnelState.status !== "connected" && webChatTunnelState.status !== "starting") {
          webChatTunnelCredential = "";
          webChatConnectorSetupState = emptyWebChatConnectorSetupState();
        } else if (previousEndpoint && previousEndpoint !== webChatTunnelState.endpoint) {
          webChatConnectorSetupState = emptyWebChatConnectorSetupState();
        }
        if (webChatTunnelState.status === "connected" && webChatTunnelState.connectorMode === "tunnel") {
          webChatConnectorSetupState = normalizeWebChatConnectorSetupState({
            status: "runtime_ready",
            endpoint: webChatTunnelState.endpoint,
            authentication: "openai-tunnel",
            serverName: "OpenAI Secure MCP Tunnel",
            protocolVersion: "2025-06-18",
            toolCount: webChatTunnelState.toolCount,
            checkedAt: new Date().toISOString(),
          });
        }
        emitWebChatGrantState();
      }
      dispatchRendererEvent(parsed.__ipc_type, parsed);
      return;
    }
  } catch {
    // Non-JSON stdout lines are plain backend logs.
  }
  emitBackendLog("stdout", message);
}

function pipePythonOutput(stream, source) {
  let buffer = "";
  stream.setEncoding("utf8");
  stream.on("data", (chunk) => {
    buffer += chunk.toString();
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const message = line.trim();
      if (!message) continue;
      if (source === "stdout") handlePythonStdoutLine(message);
      else emitBackendLog(source, message);
    }
  });
}

function spawnPythonSidecar() {
  if (pythonProcess) {
    return pythonProcess;
  }

  const pythonEntryPath = resolvePythonEntryPath();
  if (!pythonEntryPath) {
    emitBackendLog("stderr", "Unable to locate Cowork Python sidecar entry.");
    return undefined;
  }

  const userDataDir = app.getPath("userData");
  const pythonCommand = resolvePythonPath();
  const sidecarPythonPath = resolveSidecarPythonPath();
  console.log(`[electron] Spawning Cowork sidecar: ${pythonCommand} ${pythonEntryPath}`);

  pythonProcess = spawn(pythonCommand, [pythonEntryPath], {
    cwd: path.dirname(pythonEntryPath),
    env: {
      ...process.env,
      COWORK_APP_ROOT: appRoot,
      COWORK_USER_DATA_DIR: userDataDir,
      PYTHONPATH: [sidecarPythonPath, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
      PYTHONUNBUFFERED: "1",
      PYTHONIOENCODING: "utf-8",
      PYTHONUTF8: "1",
    },
    stdio: ["pipe", "pipe", "pipe"],
    windowsHide: true,
    detached: process.platform !== "win32",
  });

  pythonProcess.stdin.setDefaultEncoding("utf8");
  pipePythonOutput(pythonProcess.stdout, "stdout");
  pipePythonOutput(pythonProcess.stderr, "stderr");

  pythonProcess.on("error", (error) => {
    emitBackendLog("stderr", `Failed to start Cowork sidecar: ${error.message}`);
  });

  pythonProcess.on("close", (code, signal) => {
    emitBackendLog("stderr", `Cowork sidecar exited with code=${code ?? "null"} signal=${signal ?? "null"}`);
    pythonProcess = undefined;
    const grant = getWebChatGrantStore().getState().grant;
    webChatGatewayState = emptyWebChatGatewayState(grant ? "starting" : "off");
    webChatTunnelState = emptyWebChatTunnelState();
    webChatTunnelCredential = "";
    webChatConnectorSetupState = emptyWebChatConnectorSetupState();
    emitWebChatGrantState();
  });

  setTimeout(() => void syncWebChatGatewayGrant(), 0);

  return pythonProcess;
}

function stopPythonSidecar() {
  if (!pythonProcess) return;
  const sidecar = pythonProcess;
  pythonProcess = undefined;

  if (sidecar.stdin && !sidecar.stdin.destroyed) {
    sidecar.stdin.write(`${JSON.stringify({ command: "web_chat_tunnel_stop", reason: "application-quit" })}\n`, "utf8");
    sidecar.stdin.end();
  }

  if (process.platform === "win32" && sidecar.pid) {
    spawnSync("taskkill", ["/PID", String(sidecar.pid), "/T", "/F"], {
      encoding: "utf8",
      windowsHide: true,
    });
    return;
  }

  if (sidecar.pid) {
    try {
      process.kill(-sidecar.pid, "SIGTERM");
      return;
    } catch {
      // Fall back when the child process group is already gone.
    }
  }
  sidecar.kill("SIGTERM");
}

function sendCommandToPython(command, payload = {}) {
  return new Promise((resolve, reject) => {
    const sidecar = pythonProcess ?? spawnPythonSidecar();
    if (!sidecar?.stdin || sidecar.stdin.destroyed || !sidecar.stdin.writable) {
      reject(new Error("Cowork sidecar stdin is not writable."));
      return;
    }

    sidecar.stdin.write(`${JSON.stringify({ command, ...payload })}\n`, "utf8", (error) => {
      if (error) reject(error);
      else resolve({ ok: true });
    });
  });
}

function installRendererDiagnostics(window) {
  window.webContents.on("console-message", (_event, details) => {
    const level = details.level ?? "unknown";
    const message = details.message ?? "";
    const sourceId = details.sourceId ?? "";
    const line = details.lineNumber ?? "";
    console.log(`[renderer:${level}] ${message} (${sourceId}:${line})`);
  });
  window.webContents.on("did-fail-load", (_event, errorCode, errorDescription, validatedURL) => {
    console.error(`[electron] Renderer failed to load ${validatedURL}: ${errorCode} ${errorDescription}`);
  });
  window.webContents.on("render-process-gone", (_event, details) => {
    console.error(`[electron] Renderer process gone: ${details.reason} exitCode=${details.exitCode}`);
  });
  window.webContents.on("did-finish-load", async () => {
    try {
      await new Promise((resolve) => setTimeout(resolve, 500));
      const snapshot = await window.webContents.executeJavaScript(
        `({
          url: location.href,
          title: document.title,
          rootExists: Boolean(document.getElementById("root")),
          rootChildren: document.getElementById("root")?.childElementCount ?? -1,
          bodyText: document.body?.innerText?.slice(0, 120) ?? "",
          conversation: (() => {
            const node = document.querySelector('[aria-label="Conversation scroll area"]');
            if (!node) return null;
            const style = getComputedStyle(node);
            return {
              clientHeight: node.clientHeight,
              scrollHeight: node.scrollHeight,
              overflowY: style.overflowY,
              parentOverflowY: getComputedStyle(node.parentElement).overflowY,
              parentMinHeight: getComputedStyle(node.parentElement).minHeight
            };
          })()
        })`,
      );
      console.log(`[electron] Renderer loaded: ${JSON.stringify(snapshot)}`);
    } catch (error) {
      console.error(`[electron] Renderer diagnostic failed: ${error.message}`);
    }
  });
}

function getControllableWindow() {
  return BrowserWindow.getFocusedWindow() ?? mainWindow;
}

ipcMain.on("window-minimize", () => getControllableWindow()?.minimize());
ipcMain.on("window-close", () => getControllableWindow()?.close());
ipcMain.on("window-maximize", () => {
  const targetWindow = getControllableWindow();
  if (!targetWindow) return;
  if (targetWindow.isMaximized()) targetWindow.unmaximize();
  else targetWindow.maximize();
});

ipcMain.on("preload-ready", () => {
  console.log("[electron] Cowork preload bridge initialized.");
});

ipcMain.handle("select-folder", async () => {
  const result = await dialog.showOpenDialog({ properties: ["openDirectory"] });
  if (result.canceled || !result.filePaths[0]) return null;
  approvedWorkspacePaths.add(normalizeWorkspacePath(result.filePaths[0]));
  return result.filePaths[0];
});

function sanitizeChatAttachments(attachments) {
  if (!Array.isArray(attachments)) return [];
  return attachments.slice(0, 6).flatMap((attachment) => {
    if (!attachment || typeof attachment !== "object") return [];
    const content = typeof attachment.content === "string" ? attachment.content.trim() : "";
    const kind = typeof attachment.kind === "string" ? attachment.kind.slice(0, 40) : "text";
    const mime = typeof attachment.mime === "string" ? attachment.mime.slice(0, 120) : "";
    const dataUrl = typeof attachment.dataUrl === "string"
      ? attachment.dataUrl
      : typeof attachment.data_url === "string"
        ? attachment.data_url
        : "";
    const isImage = kind === "image" || mime.startsWith("image/");
    if (!content && !isImage) return [];
    const cleanDataUrl = isImage && dataUrl.length <= 3_000_000 && dataUrl.startsWith("data:image/") ? dataUrl : "";
    return [{
      label: typeof attachment.label === "string" ? attachment.label.slice(0, 160) : "attached-context",
      source: typeof attachment.source === "string" ? attachment.source.slice(0, 80) : "user-attached",
      kind,
      content: content.slice(0, 12000),
      ...(mime ? { mime } : {}),
      ...(Number.isFinite(attachment.size) ? { size: attachment.size } : {}),
      ...(cleanDataUrl ? { data_url: cleanDataUrl } : {}),
    }];
  });
}

function sanitizeChatWebSettings(settings) {
  const raw = settings && typeof settings === "object" && !Array.isArray(settings) ? settings : {};
  const webMode = typeof raw.webMode === "string" ? raw.webMode : typeof raw.web_mode === "string" ? raw.web_mode : "auto";
  const searchProvider = typeof raw.searchProvider === "string" ? raw.searchProvider : typeof raw.search_provider === "string" ? raw.search_provider : "auto";
  const artifacts = typeof raw.artifacts === "string" ? raw.artifacts : "on";
  const codeExecution = typeof raw.codeExecution === "string" ? raw.codeExecution : typeof raw.code_execution === "string" ? raw.code_execution : "off";
  const mcp = typeof raw.mcp === "string" ? raw.mcp : "off";
  return {
    web_mode: ["auto", "off"].includes(webMode) ? webMode : "auto",
    search_provider: ["auto", "brave", "scrape"].includes(searchProvider) ? searchProvider : "auto",
    artifacts: ["on", "off"].includes(artifacts) ? artifacts : "on",
    code_execution: ["on", "off"].includes(codeExecution) ? codeExecution : "off",
    mcp: ["on", "off"].includes(mcp) ? mcp : "off",
  };
}

function currentWebChatState(patch = {}) {
  const contents = webChatView?.webContents;
  const navigationHistory = contents?.navigationHistory;
  webChatState = {
    ...webChatState,
    ...(contents && !contents.isDestroyed()
      ? {
          url: contents.getURL() || webChatState.url,
          canGoBack: Boolean(navigationHistory?.canGoBack()),
          canGoForward: Boolean(navigationHistory?.canGoForward()),
        }
      : {}),
    ...patch,
    visible: webChatVisible,
  };
  return { ...webChatState };
}

function emitWebChatState(patch = {}) {
  const state = currentWebChatState(patch);
  dispatchRendererEvent("web-chat-state", state);
  return state;
}

function currentWebChatGrantState(state = getWebChatGrantStore().getState()) {
  const merged = mergeWebChatGatewayState(state, webChatGatewayState, webChatTunnelState);
  const connectorSetup = merged.tunnelConnected
    && webChatConnectorSetupState.endpoint === merged.tunnel.endpoint
    ? normalizeWebChatConnectorSetupState(webChatConnectorSetupState)
    : emptyWebChatConnectorSetupState();
  return { ...merged, connectorSetup };
}

function emitWebChatGrantState(state = getWebChatGrantStore().getState()) {
  const publicState = currentWebChatGrantState(state);
  dispatchRendererEvent("web-chat-grant-state", publicState);
  return publicState;
}

async function stopWebChatTunnel(reason = "manual") {
  webChatTunnelCredential = "";
  webChatTunnelState = emptyWebChatTunnelState();
  webChatConnectorSetupState = emptyWebChatConnectorSetupState();
  emitWebChatGrantState();
  try {
    await sendCommandToPython("web_chat_tunnel_stop", { reason });
    return { ok: true, ...emitWebChatGrantState() };
  } catch (error) {
    emitBackendLog("stderr", `Unable to stop Web Chat tunnel: ${error.message}`);
    return { ok: false, error: error instanceof Error ? error.message : String(error), ...emitWebChatGrantState() };
  }
}

async function syncWebChatGatewayGrant(state = getWebChatGrantStore().getState()) {
  const grant = state?.grant;
  if (!grant) {
    await stopWebChatTunnel("grant-revoked");
    webChatGatewayState = emptyWebChatGatewayState();
    emitWebChatGrantState(state);
    try {
      await sendCommandToPython("web_chat_gateway_unbind", { reason: "revoked" });
    } catch (error) {
      emitBackendLog("stderr", `Unable to stop Web Chat local gateway: ${error.message}`);
    }
    return;
  }
  webChatGatewayState = {
    ...emptyWebChatGatewayState("starting"),
    grantId: String(grant.id || ""),
    grantRevision: Number(state.revision || 0),
    permissionMode: String(grant.permissionMode || "manual"),
    workspacePath: String(grant.workspacePath || ""),
  };
  emitWebChatGrantState(state);
  try {
    await sendCommandToPython("web_chat_gateway_bind", {
      workspace_path: grant.workspacePath,
      grant_id: grant.id,
      grant_revision: state.revision,
      permission_mode: grant.permissionMode,
    });
  } catch (error) {
    webChatGatewayState = { ...webChatGatewayState, status: "error", error: error.message, toolsEnabled: false };
    emitWebChatGrantState(state);
  }
}

function createWebChatView() {
  if (webChatView && !webChatView.webContents.isDestroyed()) return webChatView;
  if (!mainWindow || mainWindow.isDestroyed()) return undefined;

  webChatView = new WebContentsView({
    webPreferences: {
      partition: WEB_CHAT_PARTITION,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
    },
  });
  webChatView.setBackgroundColor("#ffffff");
  webChatView.setVisible(false);
  mainWindow.contentView.addChildView(webChatView);

  const contents = webChatView.webContents;
  contents.setWindowOpenHandler(({ url }) => {
    if (!isSafeExternalWebUrl(url)) return { action: "deny" };
    return {
      action: "allow",
      overrideBrowserWindowOptions: {
        icon: appIconPath,
        autoHideMenuBar: true,
        webPreferences: {
          partition: WEB_CHAT_PARTITION,
          contextIsolation: true,
          nodeIntegration: false,
          sandbox: true,
          webSecurity: true,
        },
      },
    };
  });
  contents.on("did-start-loading", () => emitWebChatState({ loading: true, error: "" }));
  contents.on("did-stop-loading", () => emitWebChatState({ loading: false }));
  contents.on("did-navigate", () => emitWebChatState());
  contents.on("did-navigate-in-page", () => emitWebChatState());
  contents.on("page-title-updated", (_event, title) => emitWebChatState({ title: String(title || "ChatGPT") }));
  contents.on("did-fail-load", (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
    if (!isMainFrame || errorCode === -3) return;
    emitWebChatState({
      loading: false,
      error: `ChatGPT Web failed to load (${errorCode}): ${errorDescription}`,
      url: validatedURL || webChatState.url,
    });
  });
  return webChatView;
}

function destroyWebChatView() {
  if (!webChatView) return;
  const view = webChatView;
  webChatView = undefined;
  webChatVisible = false;
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.contentView.removeChildView(view);
  if (!view.webContents.isDestroyed()) view.webContents.close();
}

function sanitizeVisionSettings(settings) {
  const raw = settings && typeof settings === "object" && !Array.isArray(settings) ? settings : {};
  const visionAssist = typeof raw.visionAssist === "string" ? raw.visionAssist : typeof raw.vision_assist === "string" ? raw.vision_assist : "off";
  const visionModel = typeof raw.visionModel === "string" ? raw.visionModel : typeof raw.vision_model === "string" ? raw.vision_model : "zai:glm-4.6v-flashx";
  return {
    vision_assist: ["off", "auto", "on"].includes(visionAssist) ? visionAssist : "off",
    vision_model: visionModel.trim().slice(0, 160) || "zai:glm-4.6v-flashx",
  };
}

ipcMain.handle("send-cowork", async (_event, prompt, model, sessionId, mode, effort, attachments, webSettings, history, visionSettings) =>
  sendCommandToPython("send_cowork", {
    prompt: typeof prompt === "string" ? prompt : "",
    model: typeof model === "string" ? model : "",
    client_session_id: typeof sessionId === "string" ? sessionId : "",
    mode: typeof mode === "string" ? mode : "Cowork",
    effort: typeof effort === "string" ? effort : "Medium",
    attachments: sanitizeChatAttachments(attachments),
    web_settings: sanitizeChatWebSettings(webSettings),
    vision_settings: sanitizeVisionSettings(visionSettings),
    history: Array.isArray(history) ? history : undefined,
  }),
);

ipcMain.handle("cancel-cowork", async (_event, sessionId, mode) =>
  sendCommandToPython("cancel_cowork", {
    client_session_id: typeof sessionId === "string" ? sessionId : "",
    mode: typeof mode === "string" ? mode : "Cowork",
  }),
);

ipcMain.handle("set-workspace", async (_event, workspacePath) => {
  const selectedPath = typeof workspacePath === "string" ? workspacePath : "";
  if (!approvedWorkspacePaths.has(normalizeWorkspacePath(selectedPath))) {
    throw new Error("Workspace path was not selected by the user.");
  }
  return sendCommandToPython("set_workspace", { path: selectedPath });
});

ipcMain.handle("workspace-action", async (_event, payload) => {
  const actionPayload = payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
  return sendCommandToPython("workspace_action", {
    request_id: typeof actionPayload.requestId === "string" ? actionPayload.requestId : "",
    action: typeof actionPayload.action === "string" ? actionPayload.action : "",
    path: typeof actionPayload.path === "string" ? actionPayload.path : "",
    name: typeof actionPayload.name === "string" ? actionPayload.name : "",
    backup_path: typeof actionPayload.backupPath === "string" ? actionPayload.backupPath : "",
  });
});

ipcMain.handle("fetch-models", async () => sendCommandToPython("fetch_available_models"));
ipcMain.handle("session-state-load", async () => getSessionStateStore().load());
ipcMain.handle("session-state-save", async (_event, envelope) => getSessionStateStore().save(envelope));
ipcMain.handle("fetch-registered-skills", async () => sendCommandToPython("fetch_registered_skills"));
ipcMain.handle("load-api-keys", async () => sendCommandToPython("load_api_keys"));
ipcMain.handle("set-auto-approve", async (_event, enabled) => sendCommandToPython("set_auto_approve", { enabled: Boolean(enabled) }));
ipcMain.handle("set-permission-mode", async (_event, mode) => {
  const supportedModes = new Set(["manual", "trusted", "full"]);
  const normalizedMode = supportedModes.has(mode) ? mode : "manual";
  return sendCommandToPython("set_permission_mode", { mode: normalizedMode });
});
ipcMain.handle("chat-memory-list", async () => sendCommandToPython("chat_memory_list"));
ipcMain.handle("chat-memory-create", async (_event, payload) =>
  sendCommandToPython("chat_memory_create", {
    text: payload && typeof payload.text === "string" ? payload.text : "",
    kind: payload && typeof payload.kind === "string" ? payload.kind : "preference",
    client_session_id: payload && typeof payload.clientSessionId === "string" ? payload.clientSessionId : "",
    mode: payload && typeof payload.mode === "string" ? payload.mode : "Chat",
  }),
);
ipcMain.handle("chat-memory-update", async (_event, id, text) =>
  sendCommandToPython("chat_memory_update", {
    id: typeof id === "string" ? id : "",
    text: typeof text === "string" ? text : "",
  }),
);
ipcMain.handle("chat-memory-set-enabled", async (_event, id, enabled) =>
  sendCommandToPython("chat_memory_set_enabled", {
    id: typeof id === "string" ? id : "",
    enabled: Boolean(enabled),
  }),
);
ipcMain.handle("chat-memory-delete", async (_event, id) =>
  sendCommandToPython("chat_memory_delete", { id: typeof id === "string" ? id : "" }),
);
ipcMain.handle("chat-artifact-list", async () => sendCommandToPython("chat_artifact_list"));
ipcMain.handle("chat-quality-eval-list", async () => sendCommandToPython("chat_quality_eval_list"));
ipcMain.handle("chat-quality-eval-run", async (_event, payload) => sendCommandToPython("chat_quality_eval_run", payload || {}));
ipcMain.handle("chat-quality-run", async (_event, payload) => sendCommandToPython("chat_quality_run", payload || {}));
ipcMain.handle("chat-connector-list", async () => sendCommandToPython("chat_connector_list"));
ipcMain.handle("chat-connector-save", async (_event, connectors) =>
  sendCommandToPython("chat_connector_save", { connectors: Array.isArray(connectors) ? connectors : [] }),
);
ipcMain.handle("chat-connector-test", async (_event, connector) =>
  sendCommandToPython("chat_connector_test", { connector: connector && typeof connector === "object" ? connector : {} }),
);
ipcMain.handle("chat-connector-discover", async (_event, target) =>
  sendCommandToPython("chat_connector_discover", { target: typeof target === "string" ? target : "" }),
);
ipcMain.handle("chat-mcp-tool-run", async (_event, payload) => {
  const safePayload = payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
  return sendCommandToPython("chat_mcp_tool_run", safePayload);
});
ipcMain.handle("answer-question", async (_event, answer) => {
  const answerPayload = answer && typeof answer === "object" && !Array.isArray(answer)
    ? answer
    : { answer: typeof answer === "string" ? answer : "" };
  return sendCommandToPython("answer_question", answerPayload);
});
ipcMain.handle("set-provider-key", async (_event, provider, key) =>
  sendCommandToPython("set_provider_key", {
    provider: typeof provider === "string" ? provider : "",
    key: typeof key === "string" ? key : "",
  }),
);
ipcMain.handle("set-custom-anthropic-provider", async (_event, payload) =>
  sendCommandToPython("set_custom_anthropic_provider", payload && typeof payload === "object" ? payload : {}),
);
ipcMain.handle("import-custom-anthropic-models", async (_event, payload) =>
  sendCommandToPython("import_custom_anthropic_models", payload && typeof payload === "object" ? payload : {}),
);
ipcMain.handle("set-api-keys", async (_event, geminiKey, openaiKey, localAiBaseUrl, localAiApiKey) =>
  sendCommandToPython("set_api_keys", {
    geminiKey: typeof geminiKey === "string" ? geminiKey : "",
    openaiKey: typeof openaiKey === "string" ? openaiKey : "",
    localAiBaseUrl: typeof localAiBaseUrl === "string" ? localAiBaseUrl : "",
    localAiApiKey: typeof localAiApiKey === "string" ? localAiApiKey : "",
  }),
);

function startMainApp() {
  createMainWindow();
  spawnPythonSidecar();
}

// Startup checks retain the original fast path: when an update is already
// available before the app opens, show the gate and install it before launch.
// Once the app is open, the separate background updater waits for the user to
// select the in-app Update button.
const UPDATE_CHECK_TIMEOUT_MS = 20_000;

function createUpdateGateWindow() {
  const gate = new BrowserWindow({
    width: 380,
    height: 150,
    icon: appIconPath,
    frame: false,
    resizable: false,
    alwaysOnTop: true,
    backgroundColor: "#f7f6f2",
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  const html = `<!doctype html><html><body style="margin:0;font-family:'Segoe UI',system-ui,sans-serif;background:#f7f6f2;color:#3b3a36;user-select:none;-webkit-app-region:drag">
    <div style="padding:26px 28px">
      <div style="font-size:15px;font-weight:600;margin-bottom:6px">AI Dev Co-worker</div>
      <div id="status" style="font-size:13px;color:#6f6b63;margin-bottom:12px">Checking for updates…</div>
      <div style="height:6px;border-radius:3px;background:#e4e1d8;overflow:hidden">
        <div id="bar" style="height:100%;width:0%;background:#d96b4a;transition:width .25s"></div>
      </div>
    </div>
  </body></html>`;
  void gate.loadURL("data:text/html;charset=utf-8," + encodeURIComponent(html));
  return gate;
}

function setGateStatus(gate, text, percent) {
  if (!gate || gate.isDestroyed()) return;
  const script = `(() => {
    const s = document.getElementById("status");
    const b = document.getElementById("bar");
    if (s) s.textContent = ${JSON.stringify(text)};
    if (b && ${Number.isFinite(percent) ? "true" : "false"}) b.style.width = "${Number.isFinite(percent) ? Math.max(0, Math.min(100, Math.round(percent))) : 0}%";
  })()`;
  gate.webContents.executeJavaScript(script).catch(() => {});
}

function runUpdateGate() {
  if (!app.isPackaged) {
    startMainApp();
    return;
  }

  const gate = createUpdateGateWindow();
  let updateFound = false;
  let finished = false;

  const proceed = () => {
    if (finished) return;
    finished = true;
    autoUpdater.removeAllListeners();
    startMainApp();
    startBackgroundUpdater();
    setTimeout(() => {
      if (!gate.isDestroyed()) gate.destroy();
    }, 250);
  };

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on("update-available", (info) => {
    updateFound = true;
    setGateStatus(gate, `Update found: v${info?.version ?? ""} — downloading…`, 0);
  });
  autoUpdater.on("download-progress", (progress) => {
    const percent = Math.round(progress?.percent ?? 0);
    setGateStatus(gate, `Downloading update… ${percent}%`, percent);
  });
  autoUpdater.on("update-downloaded", () => {
    finished = true;
    setGateStatus(gate, "Installing update… the app will restart.", 100);
    setTimeout(() => autoUpdater.quitAndInstall(true, true), 600);
  });
  autoUpdater.on("update-not-available", () => {
    setGateStatus(gate, "You are up to date.", 100);
    setTimeout(proceed, 350);
  });
  autoUpdater.on("error", (error) => {
    emitBackendLog("stderr", `Auto-update error: ${error?.message ?? error}`);
    setGateStatus(gate, "Update check failed — starting the app.", 0);
    setTimeout(proceed, 600);
  });

  setTimeout(() => {
    if (!updateFound) proceed();
  }, UPDATE_CHECK_TIMEOUT_MS);

  autoUpdater.checkForUpdates().catch((error) => {
    emitBackendLog("stderr", `Auto-update check failed: ${error?.message ?? error}`);
    proceed();
  });
}

let backgroundUpdaterStarted = false;
let pendingUpdateReady = false;
let appUpdateState = { state: "idle", version: "", percent: 0 };

function publishAppUpdate(state, extra = {}) {
  appUpdateState = {
    state,
    version: typeof extra.version === "string" ? extra.version : appUpdateState.version,
    percent: Number.isFinite(extra.percent) ? extra.percent : state === "ready" ? 100 : 0,
  };
  dispatchRendererEvent("app-update", { ...appUpdateState, timestamp: new Date().toISOString() });
}

function startBackgroundUpdater() {
  if (!app.isPackaged || backgroundUpdaterStarted) return;
  backgroundUpdaterStarted = true;

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = false;

  autoUpdater.on("update-available", (info) => {
    pendingUpdateReady = false;
    publishAppUpdate("available", { version: info?.version ?? "", percent: 0 });
  });
  autoUpdater.on("download-progress", (progress) => {
    publishAppUpdate("downloading", { percent: Math.round(progress?.percent ?? 0) });
  });
  autoUpdater.on("update-downloaded", (info) => {
    pendingUpdateReady = true;
    publishAppUpdate("ready", { version: info?.version ?? "", percent: 100 });
  });
  autoUpdater.on("update-not-available", () => {
    if (!pendingUpdateReady) publishAppUpdate("idle", { version: "", percent: 0 });
  });
  autoUpdater.on("error", (error) => {
    emitBackendLog("stderr", `Background update error: ${error?.message ?? error}`);
  });

  const check = () =>
    autoUpdater.checkForUpdates().catch((error) => emitBackendLog("stderr", `Background update check failed: ${error?.message ?? error}`));
  setTimeout(check, 1_000); // after the main window begins loading
  setInterval(check, 30 * 60_000); // then every 30 minutes
}

ipcMain.handle("get-app-update-state", async () => ({ ...appUpdateState }));

ipcMain.handle("install-update-now", async () => {
  if (!app.isPackaged) return { ok: false, reason: "not-packaged" };
  if (!pendingUpdateReady) return { ok: false, reason: "not-downloaded" };
  autoUpdater.quitAndInstall(true, true); // silent install + relaunch on the new version
  return { ok: true };
});

ipcMain.handle("web-chat-state", async () => currentWebChatState());

ipcMain.handle("web-chat-grant-state", async () => currentWebChatGrantState());

ipcMain.handle("web-chat-grant-set", async (_event, payload) => {
  try {
    if (getWebChatGrantStore().getState().grant) {
      await stopWebChatTunnel("grant-replaced");
      webChatGatewayState = emptyWebChatGatewayState();
      emitWebChatGrantState();
      await sendCommandToPython("web_chat_gateway_unbind", { reason: "grant-replaced" });
    }
    const state = getWebChatGrantStore().setGrant(payload);
    void syncWebChatGatewayGrant(state);
    return { ok: true, ...emitWebChatGrantState(state) };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : String(error) };
  }
});

ipcMain.handle("web-chat-grant-revoke", async () => {
  await stopWebChatTunnel("grant-revoked");
  const state = getWebChatGrantStore().revoke();
  void syncWebChatGatewayGrant(state);
  return { ok: true, ...emitWebChatGrantState(state) };
});

ipcMain.handle("web-chat-tunnel-start", async (_event, payload) => {
  const provider = String(payload?.provider || "cloudflare").trim().toLocaleLowerCase("en-US");
  if (!new Set(["cloudflare", "openai"]).has(provider)) return { ok: false, error: "Unsupported Web Chat tunnel provider." };
  if (webChatTunnelState.status === "starting" || webChatTunnelState.status === "connected") {
    return { ok: false, error: "The Web Chat tunnel is already active. Disconnect it before starting another." };
  }
  const grantState = getWebChatGrantStore().getState();
  const merged = mergeWebChatGatewayState(grantState, webChatGatewayState, webChatTunnelState);
  if (!grantState.grant || !merged.toolsEnabled || merged.localGateway?.status !== "ready") {
    return { ok: false, error: "Local workspace tools must be ready before connecting a tunnel." };
  }
  const credential = randomBytes(32).toString("base64url");
  const providerOptions = provider === "openai"
    ? {
        tunnel_id: String(payload?.tunnelId || payload?.tunnel_id || "").trim(),
        runtime_api_key: String(payload?.runtimeApiKey || payload?.runtime_api_key || "").trim(),
      }
    : {};
  if (provider === "openai" && !/^tunnel_[0-9a-f]{32}$/.test(providerOptions.tunnel_id)) {
    return { ok: false, error: "Enter a valid OpenAI tunnel ID: tunnel_ followed by 32 lowercase hexadecimal characters." };
  }
  if (provider === "openai" && !providerOptions.runtime_api_key) {
    return { ok: false, error: "Enter an OpenAI tunnel runtime API key with Tunnels Read + Use permission." };
  }
  const expiresAt = Math.floor(Date.now() / 1000) + 60 * 60;
  webChatTunnelCredential = credential;
  webChatConnectorSetupState = emptyWebChatConnectorSetupState();
  webChatTunnelState = normalizeWebChatTunnelState({
    status: "starting",
    provider,
    grant_id: grantState.grant.id,
    grant_revision: grantState.revision,
    workspace_path: grantState.grant.workspacePath,
    auth_required: true,
    expires_at: new Date(expiresAt * 1000).toISOString(),
    tool_count: merged.localGateway.toolCount,
  });
  emitWebChatGrantState(grantState);
  try {
    await sendCommandToPython("web_chat_tunnel_start", {
      provider,
      credential,
      expires_at: expiresAt,
      idle_timeout_seconds: 15 * 60,
      grant_id: grantState.grant.id,
      grant_revision: grantState.revision,
      provider_options: providerOptions,
    });
    return { ok: true, ...emitWebChatGrantState(grantState) };
  } catch (error) {
    webChatTunnelCredential = "";
    webChatTunnelState = normalizeWebChatTunnelState({ status: "error", error: error.message });
    return { ok: false, error: error instanceof Error ? error.message : String(error), ...emitWebChatGrantState(grantState) };
  }
});

ipcMain.handle("web-chat-tunnel-stop", async () => stopWebChatTunnel("manual"));

ipcMain.handle("web-chat-connector-probe", async () => {
  const grantState = getWebChatGrantStore().getState();
  const merged = mergeWebChatGatewayState(grantState, webChatGatewayState, webChatTunnelState);
  const endpoint = String(merged.tunnel?.endpoint || "");
  const credential = webChatTunnelCredential;
  if (merged.tunnelConnected && merged.tunnel?.connectorMode === "tunnel") {
    const ready = webChatConnectorSetupState.status === "runtime_ready"
      && webChatConnectorSetupState.endpoint === endpoint;
    return { ok: ready, error: ready ? "" : "OpenAI tunnel runtime is not ready.", ...emitWebChatGrantState(grantState) };
  }
  if (!merged.tunnelConnected || !endpoint || !credential) {
    return { ok: false, error: "Connect an authenticated tunnel before verifying the ChatGPT connector.", ...emitWebChatGrantState(grantState) };
  }
  webChatConnectorSetupState = normalizeWebChatConnectorSetupState({
    status: "verifying",
    endpoint,
    authentication: "bearer",
  });
  emitWebChatGrantState(grantState);
  const result = await probeRemoteMcp({ endpoint, credential });
  const current = mergeWebChatGatewayState(getWebChatGrantStore().getState(), webChatGatewayState, webChatTunnelState);
  if (!current.tunnelConnected || current.tunnel?.endpoint !== endpoint || webChatTunnelCredential !== credential) {
    webChatConnectorSetupState = emptyWebChatConnectorSetupState();
    return { ok: false, error: "The tunnel changed while connector verification was running.", ...emitWebChatGrantState() };
  }
  webChatConnectorSetupState = result;
  return { ok: result.status === "verified", error: result.error, ...emitWebChatGrantState() };
});

ipcMain.handle("web-chat-connector-copy", async (_event, kind) => {
  const requested = String(kind || "");
  const grantState = getWebChatGrantStore().getState();
  const merged = mergeWebChatGatewayState(grantState, webChatGatewayState, webChatTunnelState);
  const setupMatches = webChatConnectorSetupState.endpoint === merged.tunnel?.endpoint;
  const copyAllowed = canCopyConnectorSetupValue({
    kind: requested,
    connectorMode: merged.tunnel?.connectorMode,
    status: webChatConnectorSetupState.status,
  });
  if (!merged.tunnelConnected || !setupMatches || !copyAllowed) {
    return { ok: false, error: "Verify the active connector before copying setup values." };
  }
  if (requested === "endpoint") {
    return writeConnectorClipboard({ clipboard, kind: requested, endpoint: merged.tunnel.endpoint, credential: webChatTunnelCredential });
  }
  if (requested === "tunnel_id" && merged.tunnel?.tunnelId) {
    clipboard.writeText(merged.tunnel.tunnelId);
    return { ok: true, copied: "tunnel_id" };
  }
  if (requested === "credential" && webChatTunnelCredential) {
    return writeConnectorClipboard({ clipboard, kind: requested, endpoint: merged.tunnel.endpoint, credential: webChatTunnelCredential });
  }
  return { ok: false, error: "Unsupported connector setup value." };
});

ipcMain.handle("web-chat-show", async (_event, bounds) => {
  const view = createWebChatView();
  if (!view) return { ok: false, reason: "main-window-unavailable" };
  view.setBounds(normalizeWebChatBounds(bounds));
  view.setVisible(true);
  webChatVisible = true;
  if (!view.webContents.getURL()) {
    void view.webContents.loadURL(CHATGPT_WEB_URL);
  }
  return { ok: true, state: emitWebChatState({ visible: true }) };
});

ipcMain.handle("web-chat-hide", async () => {
  webChatVisible = false;
  webChatView?.setVisible(false);
  return { ok: true, state: emitWebChatState({ visible: false }) };
});

ipcMain.handle("web-chat-control", async (_event, requestedCommand) => {
  const command = sanitizeWebChatCommand(requestedCommand);
  const contents = webChatView?.webContents;
  if (!command) return { ok: false, reason: "invalid-command" };
  if (!contents || contents.isDestroyed()) return { ok: false, reason: "web-chat-unavailable" };
  const history = contents.navigationHistory;
  if (command === "back" && history.canGoBack()) history.goBack();
  else if (command === "forward" && history.canGoForward()) history.goForward();
  else if (command === "reload") contents.reload();
  else if (command === "home") void contents.loadURL(CHATGPT_WEB_URL);
  else if (command === "open-external") {
    const url = contents.getURL() || CHATGPT_WEB_URL;
    if (!isSafeExternalWebUrl(url)) return { ok: false, reason: "unsafe-url" };
    await shell.openExternal(url);
  }
  return { ok: true, state: currentWebChatState() };
});

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    icon: appIconPath,
    minWidth: 980,
    minHeight: 680,
    frame: false,
    backgroundColor: "#ffffff",
    autoHideMenuBar: true,
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: preloadPath,
    },
  });

  installRendererDiagnostics(mainWindow);
  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.on("closed", () => {
    destroyWebChatView();
    mainWindow = undefined;
  });

  if (isDev) {
    void mainWindow.loadURL("http://127.0.0.1:5273");
  } else {
    void mainWindow.loadFile(rendererDistPath);
  }

  return mainWindow;
}

app.whenReady().then(() => {
  runUpdateGate();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("will-quit", () => {
  destroyWebChatView();
  stopPythonSidecar();
});
