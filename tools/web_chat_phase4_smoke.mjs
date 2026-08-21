import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const root = path.resolve(process.cwd());
const prefix = "cowork-web-chat-phase4-";
for (const name of fs.readdirSync(os.tmpdir()).filter((item) => item.startsWith(prefix))) {
  const stale = path.resolve(os.tmpdir(), name);
  if (stale.startsWith(path.resolve(os.tmpdir()) + path.sep)) {
    try { fs.rmSync(stale, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 }); } catch {}
  }
}
const profile = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
const workspace = path.join(profile, "workspace");
fs.mkdirSync(workspace);
fs.writeFileSync(path.join(workspace, "README.md"), "phase4 smoke", "utf8");
const port = 9432;
const endpoint = "https://phase4-smoke.example.test/mcp";
const electron = spawn(path.join(root, "node_modules", "electron", "dist", "electron.exe"), [".", `--user-data-dir=${profile}`, `--remote-debugging-port=${port}`], {
  cwd: root,
  env: { ...process.env, COWORK_APP_ROOT: root, COWORK_WEB_CHAT_TEST_TUNNEL_ENDPOINT: endpoint },
  stdio: ["ignore", "pipe", "pipe"],
  windowsHide: true,
});

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitForTarget() {
  const deadline = Date.now() + 20_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json`);
      const pages = await response.json();
      const target = pages.find((page) => page.type === "page" && String(page.url || "").includes("index.html"));
      if (target?.webSocketDebuggerUrl) return target;
    } catch {}
    await sleep(200);
  }
  throw new Error("Electron renderer target did not appear.");
}

async function connect(url) {
  const socket = new WebSocket(url);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  let id = 0;
  const pending = new Map();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(String(event.data));
    if (!message.id || !pending.has(message.id)) return;
    const handlers = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) handlers.reject(new Error(message.error.message));
    else handlers.resolve(message.result);
  });
  return {
    socket,
    send(method, params = {}) {
      const requestId = ++id;
      return new Promise((resolve, reject) => {
        pending.set(requestId, { resolve, reject });
        socket.send(JSON.stringify({ id: requestId, method, params }));
      });
    },
  };
}

async function evaluate(client, expression) {
  const result = await client.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "Runtime evaluation failed.");
  return result.result?.value;
}

async function waitFor(client, predicate, label) {
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    const state = await evaluate(client, "window.electronAPI.getWebChatGrantState()");
    if (predicate(state)) return state;
    await sleep(200);
  }
  throw new Error(`Timed out waiting for ${label}.`);
}

let client;
try {
  const target = await waitForTarget();
  client = await connect(target.webSocketDebuggerUrl);
  await client.send("Runtime.enable");
  const apiShape = await evaluate(client, "({ hasStart: typeof window.electronAPI.startWebChatTunnel === 'function', hasStop: typeof window.electronAPI.stopWebChatTunnel === 'function', hasProbe: typeof window.electronAPI.probeWebChatConnector === 'function', hasCopy: typeof window.electronAPI.copyWebChatConnectorValue === 'function', hasCredentialGetter: typeof window.electronAPI.getWebChatTunnelCredential === 'function' })");
  if (!apiShape.hasStart || !apiShape.hasStop || !apiShape.hasProbe || !apiShape.hasCopy || apiShape.hasCredentialGetter) {
    throw new Error(`Unsafe preload contract: ${JSON.stringify(apiShape)}`);
  }
  await evaluate(client, `window.electronAPI.setWebChatGrant(${JSON.stringify({ workspacePath: workspace, workspaceName: "Smoke", permissionMode: "manual" })})`);
  await waitFor(client, (state) => state?.localGateway?.status === "ready" && state.toolsEnabled, "local gateway");
  await evaluate(client, "window.electronAPI.startWebChatTunnel({ provider: 'cloudflare' })");
  const connected = await waitFor(client, (state) => state?.tunnelConnected === true, "connected tunnel");
  const serialized = JSON.stringify(connected);
  if (connected.tunnel.endpoint !== endpoint || serialized.includes("credential") || serialized.includes("authorization")) {
    throw new Error(`Tunnel state was not safely redacted: ${serialized}`);
  }
  await evaluate(client, "(() => { const button = document.querySelector('button[aria-label=\"Mode Web Chat\"]'); if (!button) throw new Error('Web Chat mode button missing'); button.click(); return true; })()");
  await sleep(500);
  await evaluate(client, "(() => { const button = document.querySelector('button[aria-label=\"Web Chat workspace access\"]'); if (!button) throw new Error('Workspace access button missing'); button.click(); return true; })()");
  await sleep(300);
  const panelText = await evaluate(client, "document.body.innerText");
  if (
    !panelText.includes("Tunnel connected")
    || !panelText.includes("phase4-smoke.example.test")
    || !panelText.includes("Register in ChatGPT")
    || !panelText.includes("Not verified")
  ) {
    throw new Error(`Tunnel and connector UI did not show connected state: ${panelText.slice(0, 1600)}`);
  }
  const screenshot = await client.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  fs.writeFileSync(path.join(root, "work_logs", "web-chat-phase4-smoke.png"), Buffer.from(screenshot.data, "base64"));
  fs.writeFileSync(path.join(root, "work_logs", "web-chat-phase5-smoke.png"), Buffer.from(screenshot.data, "base64"));
  await evaluate(client, "window.electronAPI.revokeWebChatGrant()");
  const revoked = await waitFor(client, (state) => state?.grant === null && state?.tunnel?.status === "off", "tunnel teardown");
  if (revoked.toolsEnabled || revoked.tunnelConnected) throw new Error(`Revocation did not fail closed: ${JSON.stringify(revoked)}`);
  process.stdout.write(`${JSON.stringify({ apiShape, connected: { provider: connected.tunnel.provider, endpoint: connected.tunnel.endpoint, authRequired: connected.tunnel.authRequired, connectorSetup: connected.connectorSetup?.status }, revoked: { tunnel: revoked.tunnel.status, toolsEnabled: revoked.toolsEnabled } })}\n`);
} finally {
  client?.socket.close();
  if (electron.pid) spawnSync("taskkill", ["/PID", String(electron.pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
  const resolvedProfile = path.resolve(profile);
  if (resolvedProfile.startsWith(path.resolve(os.tmpdir()) + path.sep) && path.basename(resolvedProfile).startsWith(prefix)) {
    for (let attempt = 0; attempt < 10; attempt += 1) {
      try { fs.rmSync(resolvedProfile, { recursive: true, force: true, maxRetries: 2, retryDelay: 100 }); break; }
      catch (error) { if (attempt === 9) throw error; await sleep(250); }
    }
  }
}
