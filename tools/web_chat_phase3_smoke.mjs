import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const root = path.resolve(process.cwd());
for (const name of fs.readdirSync(os.tmpdir()).filter((item) => item.startsWith("cowork-web-chat-phase3-"))) {
  const stale = path.resolve(os.tmpdir(), name);
  if (stale.startsWith(path.resolve(os.tmpdir()) + path.sep)) {
    try { fs.rmSync(stale, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 }); } catch {}
  }
}
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "cowork-web-chat-phase3-"));
const workspace = path.join(profile, "workspace");
fs.mkdirSync(workspace);
fs.writeFileSync(path.join(workspace, "README.md"), "phase3 smoke", "utf8");
const port = 9431;
const electron = spawn(path.join(root, "node_modules", "electron", "dist", "electron.exe"), [".", `--user-data-dir=${profile}`, `--remote-debugging-port=${port}`], {
  cwd: root,
  env: { ...process.env, COWORK_APP_ROOT: root },
  stdio: ["ignore", "pipe", "pipe"],
  windowsHide: true,
});

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function targets() {
  const response = await fetch(`http://127.0.0.1:${port}/json`);
  return response.json();
}

async function waitForTarget() {
  const deadline = Date.now() + 20_000;
  while (Date.now() < deadline) {
    try {
      const pages = await targets();
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
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else resolve(message.result);
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

async function evaluate(client, expression, awaitPromise = true) {
  const result = await client.send("Runtime.evaluate", { expression, awaitPromise, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "Runtime evaluation failed.");
  return result.result?.value;
}

async function waitForGateway(client, status) {
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    const state = await evaluate(client, "window.electronAPI.getWebChatGrantState()");
    if (state?.localGateway?.status === status) return state;
    await sleep(200);
  }
  throw new Error(`Gateway did not reach ${status}.`);
}

let client;
try {
  const target = await waitForTarget();
  client = await connect(target.webSocketDebuggerUrl);
  await client.send("Runtime.enable");
  await evaluate(client, `window.electronAPI.setWebChatGrant(${JSON.stringify({ workspacePath: workspace, workspaceName: "Smoke", permissionMode: "manual" })})`);
  const ready = await waitForGateway(client, "ready");
  const names = ready.localGateway.tools.map((tool) => tool.name);
  if (!ready.toolsEnabled || ready.tunnelConnected || ready.localGateway.toolCount !== 3) {
    throw new Error(`Unexpected ready state: ${JSON.stringify(ready)}`);
  }
  if (JSON.stringify(names) !== JSON.stringify(["list_directory", "search_files", "read_file"])) {
    throw new Error(`Unexpected catalog: ${JSON.stringify(names)}`);
  }
  await evaluate(client, `(() => { const button = document.querySelector('button[aria-label="Mode Web Chat"]'); if (!button) throw new Error('Web Chat mode button missing'); button.click(); return true; })()`);
  await sleep(500);
  await evaluate(client, `(() => { const button = document.querySelector('button[aria-label="Web Chat workspace access"]'); if (!button) throw new Error('Workspace access button missing'); button.click(); return true; })()`);
  await sleep(300);
  const panelText = await evaluate(client, "document.body.innerText");
  if (!panelText.includes("3 local tools") || !panelText.includes("Tunnel off") || !panelText.includes("not shared with ChatGPT until a tunnel")) {
    throw new Error(`Gateway UI did not show the local-only boundary: ${panelText.slice(0, 1000)}`);
  }
  const screenshot = await client.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  fs.writeFileSync(path.join(root, "work_logs", "web-chat-phase3-smoke.png"), Buffer.from(screenshot.data, "base64"));
  await evaluate(client, "window.electronAPI.revokeWebChatGrant()");
  const revoked = await waitForGateway(client, "off");
  if (revoked.grant !== null || revoked.toolsEnabled || revoked.tunnelConnected) {
    throw new Error(`Unexpected revoked state: ${JSON.stringify(revoked)}`);
  }
  process.stdout.write(JSON.stringify({ ready: { toolCount: ready.localGateway.toolCount, names, tunnelConnected: ready.tunnelConnected, uiVerified: true }, revoked: { status: revoked.localGateway.status, toolsEnabled: revoked.toolsEnabled } }) + "\n");
} finally {
  client?.socket.close();
  if (electron.pid) spawnSync("taskkill", ["/PID", String(electron.pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
  const resolvedProfile = path.resolve(profile);
  const resolvedTemp = path.resolve(os.tmpdir());
  if (resolvedProfile.startsWith(resolvedTemp + path.sep) && path.basename(resolvedProfile).startsWith("cowork-web-chat-phase3-")) {
    for (let attempt = 0; attempt < 10; attempt += 1) {
      try {
        fs.rmSync(resolvedProfile, { recursive: true, force: true, maxRetries: 2, retryDelay: 100 });
        break;
      } catch (error) {
        if (attempt === 9) throw error;
        await sleep(250);
      }
    }
  }
}
