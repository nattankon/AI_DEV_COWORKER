import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const iconPngPath = path.join(projectRoot, "assets", "app-icon.png");
const iconIcoPath = path.join(projectRoot, "assets", "app-icon.ico");

describe("desktop app icon", () => {
  it("ships a transparent PNG source and a multi-frame Windows icon", () => {
    expect(fs.existsSync(iconPngPath)).toBe(true);
    expect(fs.existsSync(iconIcoPath)).toBe(true);

    expect(fs.readFileSync(iconPngPath).subarray(0, 8)).toEqual(
      Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    );

    const ico = fs.readFileSync(iconIcoPath);
    expect(ico.subarray(0, 4)).toEqual(Buffer.from([0, 0, 1, 0]));
    expect(ico.readUInt16LE(4)).toBeGreaterThanOrEqual(6);
  });

  it("includes the icon in packaged files and uses it for Electron windows", () => {
    const packageJson = JSON.parse(fs.readFileSync(path.join(projectRoot, "package.json"), "utf8"));
    const mainSource = fs.readFileSync(path.join(projectRoot, "electron", "main.js"), "utf8");

    expect(packageJson.build.files).toContain("assets/**/*");
    expect(packageJson.build.win.icon).toBe("assets/app-icon.ico");
    expect(mainSource).toContain('const appIconPath = path.join(appRoot, "assets", "app-icon.ico");');
    expect(mainSource).toContain("icon: appIconPath,");
  });
});
