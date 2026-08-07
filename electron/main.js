import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { app, BrowserWindow, dialog, ipcMain } from "electron";
import electronUpdater from "electron-updater";
import { getPythonEntryCandidates, getSidecarPythonPathCandidates } from "./pathResolution.js";

const { autoUpdater } = electronUpdater;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const appRoot = path.resolve(__dirname, "..");
const preloadPath = path.join(__dirname, "preload.cjs");
const rendererDistPath = path.join(appRoot, "dist", "index.html");
const isDev = process.env.NODE_ENV === "development";

let mainWindow;
let pythonProcess;
const approvedWorkspacePaths = new Set();

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
  });

  return pythonProcess;
}

function stopPythonSidecar() {
  if (!pythonProcess) return;
  const sidecar = pythonProcess;
  pythonProcess = undefined;

  if (sidecar.stdin && !sidecar.stdin.destroyed) {
    sidecar.stdin.end();
  }

  if (process.platform === "win32" && sidecar.pid) {
    spawnSync("taskkill", ["/PID", String(sidecar.pid), "/T"], {
      encoding: "utf8",
      windowsHide: true,
    });
    return;
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

ipcMain.handle("send-cowork", async (_event, prompt, model, sessionId, mode, effort, attachments, webSettings, history) =>
  sendCommandToPython("send_cowork", {
    prompt: typeof prompt === "string" ? prompt : "",
    model: typeof model === "string" ? model : "",
    client_session_id: typeof sessionId === "string" ? sessionId : "",
    mode: typeof mode === "string" ? mode : "Cowork",
    effort: typeof effort === "string" ? effort : "Medium",
    attachments: sanitizeChatAttachments(attachments),
    web_settings: sanitizeChatWebSettings(webSettings),
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
ipcMain.handle("fetch-registered-skills", async () => sendCommandToPython("fetch_registered_skills"));
ipcMain.handle("load-api-keys", async () => sendCommandToPython("load_api_keys"));
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
ipcMain.handle("set-api-keys", async (_event, geminiKey, openaiKey, localAiBaseUrl, localAiApiKey) =>
  sendCommandToPython("set_api_keys", {
    geminiKey: typeof geminiKey === "string" ? geminiKey : "",
    openaiKey: typeof openaiKey === "string" ? openaiKey : "",
    localAiBaseUrl: typeof localAiBaseUrl === "string" ? localAiBaseUrl : "",
    localAiApiKey: typeof localAiApiKey === "string" ? localAiApiKey : "",
  }),
);

// --- Update gate: a small visible window shown BEFORE the app opens. ---
// The user sees "checking… / downloading X% / installing…" instead of a silent
// background update. If an update exists it installs IMMEDIATELY and the app
// relaunches on the new version; if not (or on any error/timeout) the app opens.

const UPDATE_CHECK_TIMEOUT_MS = 20_000;

function createUpdateGateWindow() {
  const gate = new BrowserWindow({
    width: 380,
    height: 150,
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

function startMainApp() {
  createMainWindow();
  spawnPythonSidecar();
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
    startMainApp();
    // Open the main window BEFORE destroying the gate so window-all-closed
    // never sees zero windows mid-transition (that would quit the app).
    setTimeout(() => {
      if (!gate.isDestroyed()) gate.destroy();
    }, 250);
  };

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true; // safety net if we ever proceed mid-download

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
    // Silent NSIS install + relaunch on the new version.
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

  // Only the CHECK phase can time out; once a download started we wait for it.
  setTimeout(() => {
    if (!updateFound) proceed();
  }, UPDATE_CHECK_TIMEOUT_MS);

  autoUpdater.checkForUpdates().catch((error) => {
    emitBackendLog("stderr", `Auto-update check failed: ${error?.message ?? error}`);
    proceed();
  });
}

ipcMain.handle("install-update-now", async () => {
  if (!app.isPackaged) return { ok: false, reason: "not-packaged" };
  autoUpdater.quitAndInstall();
  return { ok: true };
});

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
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
  stopPythonSidecar();
});
