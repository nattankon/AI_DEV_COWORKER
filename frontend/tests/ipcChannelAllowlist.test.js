import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { describe, expect, it } from "vitest";

// Regression guard for the v0.1.3 white-screen: every IPC channel the renderer
// subscribes to (ipcEventMap in eel.js) MUST be allow-listed in preload.cjs's
// inboundChannels. A missing entry makes preload's subscribeToChannel throw
// during bridge registration, which aborts before React mounts -> blank window.

const here = dirname(fileURLToPath(import.meta.url));

function readSource(relativePath) {
  return readFileSync(resolve(here, "..", "..", relativePath), "utf8");
}

function extractBlock(source, startMarker, endMarker) {
  const start = source.indexOf(startMarker);
  if (start === -1) throw new Error(`Marker not found: ${startMarker}`);
  const end = source.indexOf(endMarker, start);
  if (end === -1) throw new Error(`End marker not found: ${endMarker}`);
  return source.slice(start + startMarker.length, end);
}

function ipcEventMapKeys() {
  const block = extractBlock(readSource("frontend/lib/eel.js"), "const ipcEventMap = {", "};");
  const keys = [];
  for (const line of block.split("\n")) {
    // Match "quoted-key": ...  or  bareKey: ...
    const match = line.match(/^\s*("([^"]+)"|([A-Za-z0-9_]+))\s*:/);
    if (match) keys.push(match[2] ?? match[3]);
  }
  return keys;
}

function preloadInboundChannels() {
  const block = extractBlock(readSource("electron/preload.cjs"), "const inboundChannels = new Set([", "]);");
  return [...block.matchAll(/"([^"]+)"/g)].map((match) => match[1]);
}

describe("IPC channel allow-list", () => {
  it("allow-lists every channel the renderer subscribes to", () => {
    const rendererChannels = ipcEventMapKeys();
    const allowed = new Set(preloadInboundChannels());
    const missing = rendererChannels.filter((channel) => !allowed.has(channel));
    expect(missing, `preload.cjs inboundChannels is missing: ${missing.join(", ")}`).toEqual([]);
  });

  it("includes the app-update and cowork observability channels", () => {
    const allowed = new Set(preloadInboundChannels());
    for (const channel of ["app-update", "cowork_status", "cowork_log_delta", "cowork_completion"]) {
      expect(allowed.has(channel), `missing ${channel}`).toBe(true);
    }
  });
});
