import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { getPythonEntryCandidates } from "../../electron/pathResolution.js";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(testDir, "..", "..");

describe("standalone project independence", () => {
  it("discovers only Cowork-owned IPC sidecar locations", () => {
    const candidates = getPythonEntryCandidates({
      appRoot: projectRoot,
      resourcesPath: path.join(projectRoot, "resources"),
      env: {},
    });

    expect(candidates).toContain(path.join(projectRoot, "ipc_sidecar.py"));
    expect(candidates.join("\n")).not.toContain("API-BLENDER");
    expect(candidates.join("\n")).not.toContain("app_main.py");
  });

  it("packages no source from the legacy host", () => {
    const packageJson = JSON.parse(fs.readFileSync(path.join(projectRoot, "package.json"), "utf8"));
    const serialized = JSON.stringify(packageJson);

    expect(serialized).not.toContain("API-BLENDER");
    expect(serialized).not.toContain("app_main.py");
    expect(serialized).not.toContain("cowork_feature");
  });

  it("packages Cowork-owned Python modules from the project root", () => {
    const packageJson = JSON.parse(fs.readFileSync(path.join(projectRoot, "package.json"), "utf8"));
    const coworkResource = packageJson.build.extraResources.find(
      (resource) => resource.to === "cowork-sidecar/AI_DEV_COWORKER",
    );
    const sourcePath = coworkResource ? path.resolve(projectRoot, coworkResource.from) : "";

    expect(sourcePath).toBe(projectRoot);
    expect(fs.existsSync(path.join(sourcePath, "cowork.py"))).toBe(true);
    expect(fs.existsSync(path.join(sourcePath, "cowork_agent.py"))).toBe(true);
  });

  it("allows every renderer IPC event channel registered by the eel bridge", () => {
    const eelSource = fs.readFileSync(path.join(projectRoot, "frontend", "lib", "eel.js"), "utf8");
    const preloadSource = fs.readFileSync(path.join(projectRoot, "electron", "preload.cjs"), "utf8");
    const eventMapMatch = eelSource.match(/const ipcEventMap = \{([\s\S]*?)\};/);
    const inboundMatch = preloadSource.match(/const inboundChannels = new Set\(\[([\s\S]*?)\]\);/);
    expect(eventMapMatch).not.toBeNull();
    expect(inboundMatch).not.toBeNull();

    const rendererChannels = [...eventMapMatch[1].matchAll(/^\s*([a-zA-Z0-9_-]+):/gm)].map((match) => match[1]);
    const allowedChannels = new Set([...inboundMatch[1].matchAll(/"([^"]+)"/g)].map((match) => match[1]));

    expect(rendererChannels).not.toHaveLength(0);
    expect(rendererChannels.filter((channel) => !allowedChannels.has(channel))).toEqual([]);
  });

  it("uses the React custom chrome instead of the native Electron title bar", () => {
    const mainSource = fs.readFileSync(path.join(projectRoot, "electron", "main.js"), "utf8");

    expect(mainSource).toMatch(/frame:\s*false/);
    expect(mainSource).not.toMatch(/frame:\s*true/);
  });

  it("exposes only narrow workspace IPC methods", () => {
    const preloadSource = fs.readFileSync(path.join(projectRoot, "electron", "preload.cjs"), "utf8");
    const mainSource = fs.readFileSync(path.join(projectRoot, "electron", "main.js"), "utf8");

    expect(preloadSource).toMatch(/setWorkspace:\s*\(path\)/);
    expect(preloadSource).toMatch(/workspaceAction:\s*\(payload\)/);
    expect(preloadSource).toMatch(/setPermissionMode:\s*\(mode\)/);
    expect(mainSource).toMatch(/ipcMain\.handle\("set-workspace"/);
    expect(mainSource).toMatch(/ipcMain\.handle\("workspace-action"/);
    expect(mainSource).toMatch(/ipcMain\.handle\("set-permission-mode"/);
    expect(mainSource).toMatch(/approvedWorkspacePaths\s*=\s*new Set/);
    expect(mainSource).toMatch(/Workspace path was not selected by the user/);
    expect(preloadSource).not.toMatch(/runShell|execCommand|arbitraryCommand/);
  });
});
