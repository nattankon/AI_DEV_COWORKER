import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { createSessionStateStore } from "../../electron/sessionStateStore.js";

const temporaryDirectories = [];

function temporaryDirectory() {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "cowork-session-state-"));
  temporaryDirectories.push(directory);
  return directory;
}

function envelope(title, savedAt = "2026-08-22T00:00:00.000Z") {
  return {
    schemaVersion: 4,
    savedAt,
    state: {
      activeSessionIdsByMode: { Chat: "chat-1", Cowork: null, Code: null },
      sessions: [{ id: "chat-1", mode: "Chat", title }],
      eventsBySessionId: { "chat-1": [] },
    },
  };
}

afterEach(() => {
  for (const directory of temporaryDirectories.splice(0)) {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

describe("durable session state store", () => {
  it("round-trips a versioned session envelope", () => {
    const directory = temporaryDirectory();
    const store = createSessionStateStore({ directory });
    const expected = envelope("Persistent chat");

    expect(store.save(expected)).toEqual({ ok: true });
    expect(store.load()).toEqual({ ok: true, envelope: expected, source: "primary" });
    expect(JSON.parse(fs.readFileSync(path.join(directory, "session-history.json.bak"), "utf8"))).toEqual(expected);
  });

  it("keeps the previous valid state as a backup", () => {
    const directory = temporaryDirectory();
    const store = createSessionStateStore({ directory });
    const previous = envelope("Before update", "2026-08-21T00:00:00.000Z");
    store.save(previous);
    store.save(envelope("After update", "2026-08-22T00:00:00.000Z"));
    fs.writeFileSync(path.join(directory, "session-history.json"), "{broken", "utf8");

    expect(store.load()).toEqual({ ok: true, envelope: previous, source: "backup" });
  });

  it("rejects malformed renderer payloads without replacing the current state", () => {
    const store = createSessionStateStore({ directory: temporaryDirectory() });
    const expected = envelope("Keep me");
    store.save(expected);

    expect(store.save({ schemaVersion: 4, state: null })).toMatchObject({ ok: false });
    expect(store.load().envelope).toEqual(expected);
  });
});
