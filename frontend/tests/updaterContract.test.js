import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));

function mainSource() {
  return readFileSync(resolve(here, "..", "..", "electron", "main.js"), "utf8");
}

function packageConfig() {
  return JSON.parse(readFileSync(resolve(here, "..", "..", "package.json"), "utf8"));
}

describe("desktop updater contract", () => {
  it("keeps the startup installer gate and the in-app background updater as separate paths", () => {
    const source = mainSource();
    const startupGate = source.slice(source.indexOf("function runUpdateGate()"), source.indexOf("function startBackgroundUpdater()"));
    const backgroundStart = source.indexOf("function startBackgroundUpdater()");
    const backgroundEnd = source.indexOf('ipcMain.handle("get-app-update-state"', backgroundStart);
    const backgroundUpdater = source.slice(backgroundStart, backgroundEnd);

    expect(startupGate).toContain("function runUpdateGate()");
    expect(startupGate).toContain('autoUpdater.on("update-downloaded"');
    expect(startupGate).toContain("autoUpdater.quitAndInstall(true, true)");
    expect(source).toContain("app.whenReady().then(() => {\n  runUpdateGate();");
    expect(backgroundUpdater).toContain("autoUpdater.autoInstallOnAppQuit = false");
    expect(backgroundUpdater).not.toContain("autoUpdater.quitAndInstall");
  });

  it("uses a stable no-space installer filename so release metadata names a real asset", () => {
    expect(packageConfig().build.artifactName).toBe("AI-Dev-Co-worker-Setup-${version}.${ext}");
  });
});
