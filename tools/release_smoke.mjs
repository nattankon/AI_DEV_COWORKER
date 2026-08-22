import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const root = path.resolve(process.cwd());
const executable = path.join(root, "release", "win-unpacked", "AI Dev Co-worker.exe");
const providerPresetRegistry = path.join(
  root,
  "release",
  "win-unpacked",
  "resources",
  "cowork-sidecar",
  "AI_DEV_COWORKER",
  "compatible_provider_presets.json",
);
const packagedSidecar = path.join(path.dirname(providerPresetRegistry), "ipc_sidecar.py");
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
  if (!fs.existsSync(providerPresetRegistry)) {
    throw new Error(`Packaged provider preset registry is missing: ${providerPresetRegistry}`);
  }
  const providerPresets = JSON.parse(fs.readFileSync(providerPresetRegistry, "utf8"));
  if (!Array.isArray(providerPresets) || !providerPresets.some((preset) => preset?.id === "custom")) {
    throw new Error("Packaged provider preset registry is invalid.");
  }
  const sidecarCheck = spawnSync("python", [packagedSidecar], {
    cwd: root,
    input: '{"command":"fetch_available_models"}\n',
    encoding: "utf8",
    windowsHide: true,
  });
  if (sidecarCheck.status !== 0) {
    throw new Error(`Packaged sidecar model check failed: ${sidecarCheck.stderr || sidecarCheck.stdout}`);
  }
  const modelEvent = String(sidecarCheck.stdout || "")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line))
    .find((event) => event.__ipc_type === "available_models");
  const requiredCloudModels = [
    "openai:gpt-5.5",
    "anthropic:claude-sonnet-4-20250514",
    "zai:glm-5.2",
    "deepseek:deepseek-v4-flash",
    "gemini:gemini-3.5-flash",
  ];
  const missingCloudModels = requiredCloudModels.filter((model) => !modelEvent?.models?.includes(model));
  if (missingCloudModels.length) {
    throw new Error(`Packaged sidecar is missing cloud models: ${missingCloudModels.join(", ")}`);
  }
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
