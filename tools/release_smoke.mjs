import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const root = path.resolve(process.cwd());
const executable = path.join(root, "release", "win-unpacked", "AI Dev Co-worker.exe");
const prefix = "cowork-release-smoke-";
const profile = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
const port = 9440;
const app = spawn(executable, [`--user-data-dir=${profile}`, `--remote-debugging-port=${port}`], {
  cwd: root,
  env: { ...process.env, COWORK_APP_ROOT: root },
  stdio: ["ignore", "pipe", "pipe"],
  windowsHide: true,
});

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function waitForRenderer() {
  const deadline = Date.now() + 25_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json`);
      const pages = await response.json();
      const target = pages.find((page) => page.type === "page" && String(page.url || "").includes("index.html"));
      if (target) return target;
    } catch {}
    await sleep(300);
  }
  throw new Error("Packaged Electron renderer did not become ready.");
}

try {
  if (!fs.existsSync(executable)) throw new Error(`Packaged executable is missing: ${executable}`);
  const target = await waitForRenderer();
  const version = fs.readFileSync(path.join(root, "package.json"), "utf8");
  process.stdout.write(`${JSON.stringify({ title: target.title, url: target.url, packageVersion: JSON.parse(version).version })}\n`);
} finally {
  if (app.pid) spawnSync("taskkill", ["/PID", String(app.pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
  const resolvedProfile = path.resolve(profile);
  const tempRoot = `${path.resolve(os.tmpdir())}${path.sep}`;
  if (resolvedProfile.startsWith(tempRoot) && path.basename(resolvedProfile).startsWith(prefix)) {
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
