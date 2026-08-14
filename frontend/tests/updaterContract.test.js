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
  it("does not retain a startup gate that auto-installs downloaded updates", () => {
    const source = mainSource();

    expect(source).not.toContain("function runUpdateGate()");
    expect(source.match(/quitAndInstall\(/g) ?? []).toHaveLength(1);
    expect(source).toContain("autoUpdater.autoInstallOnAppQuit = false");
  });

  it("uses a stable no-space installer filename so release metadata names a real asset", () => {
    expect(packageConfig().build.artifactName).toBe("AI-Dev-Co-worker-Setup-${version}.${ext}");
  });
});
