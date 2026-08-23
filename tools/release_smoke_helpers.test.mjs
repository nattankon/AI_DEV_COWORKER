import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { readDevToolsPort } from "./release_smoke_helpers.mjs";

test("readDevToolsPort returns the dynamic Chromium debugging port", () => {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "cowork-devtools-port-test-"));
  try {
    fs.writeFileSync(path.join(profile, "DevToolsActivePort"), "53127\n/devtools/browser/id\n", "utf8");
    assert.equal(readDevToolsPort(profile), 53127);
  } finally {
    fs.rmSync(profile, { recursive: true, force: true });
  }
});

test("readDevToolsPort returns null until Chromium publishes a valid port", () => {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "cowork-devtools-port-test-"));
  try {
    assert.equal(readDevToolsPort(profile), null);
    fs.writeFileSync(path.join(profile, "DevToolsActivePort"), "not-a-port\n", "utf8");
    assert.equal(readDevToolsPort(profile), null);
  } finally {
    fs.rmSync(profile, { recursive: true, force: true });
  }
});
