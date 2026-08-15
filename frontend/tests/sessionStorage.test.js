import { describe, expect, it } from "vitest";
import { createSessionStorageAdapter } from "../adapters/sessionStorage";

function createMemoryStorage() {
  const store = new Map();
  return {
    getItem(key) {
      return store.has(key) ? store.get(key) : null;
    },
    setItem(key, value) {
      store.set(key, String(value));
    },
    removeItem(key) {
      store.delete(key);
    },
  };
}

describe("session storage adapter", () => {
  it("saves separate active sessions for Chat, Cowork, and Code", () => {
    const backingStore = createMemoryStorage();
    const storage = createSessionStorageAdapter(backingStore);
    const state = {
      activeSessionIdsByMode: { Chat: "chat-1", Cowork: "cowork-1", Code: "code-1" },
      sessions: [
        { id: "chat-1", mode: "Chat", title: "Chat task" },
        { id: "cowork-1", mode: "Cowork", title: "Cowork task" },
        { id: "code-1", mode: "Code", title: "Code task" },
      ],
      eventsBySessionId: { "chat-1": [], "cowork-1": [], "code-1": [] },
    };

    storage.save(state);

    expect(storage.load()).toMatchObject(state);
  });

  it("survives a localStorage quota error by trimming events and retrying", () => {
    const store = new Map();
    let failuresLeft = 1; // the first (full) write throws; the trimmed retry succeeds
    const backing = {
      getItem: (key) => (store.has(key) ? store.get(key) : null),
      setItem: (key, value) => {
        if (failuresLeft > 0) {
          failuresLeft -= 1;
          const error = new Error("quota");
          error.name = "QuotaExceededError";
          throw error;
        }
        store.set(key, String(value));
      },
      removeItem: (key) => store.delete(key),
    };
    const storage = createSessionStorageAdapter(backing);
    const events = Array.from({ length: 1000 }, (_, index) => ({ id: `e${index}`, type: "message.user", payload: { text: "x" } }));

    // Must not throw despite the quota error.
    storage.save({
      activeSessionIdsByMode: { Cowork: "s1" },
      sessions: [{ id: "s1", mode: "Cowork", title: "t" }],
      eventsBySessionId: { s1: events },
    });

    const restored = storage.load();
    expect(restored.eventsBySessionId.s1.length).toBeGreaterThan(0);
    expect(restored.eventsBySessionId.s1.length).toBeLessThanOrEqual(400);
  });

  it("round-trips a session's project so sidebar groups survive restart", () => {
    const backingStore = createMemoryStorage();
    const storage = createSessionStorageAdapter(backingStore);
    const state = {
      activeSessionIdsByMode: { Chat: "chat-1", Cowork: "cowork-1", Code: "code-1" },
      sessions: [
        { id: "cowork-1", mode: "Cowork", title: "Config edit", project: { path: "C:/DragonNest", name: "DragonNest" } },
      ],
      eventsBySessionId: { "cowork-1": [] },
    };

    storage.save(state);

    const restored = storage.load();
    const restoredSession = restored.sessions.find((session) => session.id === "cowork-1");
    expect(restoredSession.project).toEqual({ path: "C:/DragonNest", name: "DragonNest" });
  });

  it("drops a malformed session project instead of persisting it", () => {
    const backingStore = createMemoryStorage();
    const storage = createSessionStorageAdapter(backingStore);
    storage.save({
      activeSessionIdsByMode: { Cowork: "cowork-1" },
      sessions: [{ id: "cowork-1", mode: "Cowork", title: "x", project: { name: "no path" } }],
      eventsBySessionId: { "cowork-1": [] },
    });

    const restoredSession = storage.load().sessions.find((session) => session.id === "cowork-1");
    expect(restoredSession.project).toBeUndefined();
  });

  it("saves per-mode model routes with session state", () => {
    const storage = createSessionStorageAdapter(createMemoryStorage());
    const state = {
      activeSessionIdsByMode: { Chat: "chat-1", Cowork: "cowork-1", Code: "code-1" },
      sessions: [
        { id: "chat-1", mode: "Chat", title: "Chat task" },
        { id: "cowork-1", mode: "Cowork", title: "Cowork task" },
        { id: "code-1", mode: "Code", title: "Code task" },
      ],
      eventsBySessionId: { "chat-1": [], "cowork-1": [], "code-1": [] },
      modelRoutes: {
        Chat: "zai:glm-4.7-flash",
        Cowork: "qwen/qwen3.5-9b",
        Code: "openai:gpt-5.5",
      },
    };

    storage.save(state);

    expect(storage.load()).toMatchObject({ modelRoutes: state.modelRoutes });
  });

  it("removes transient stream, verification, and live approval events from stored timelines", () => {
    const storage = createSessionStorageAdapter(createMemoryStorage());
    storage.save({
      activeSessionIdsByMode: { Chat: null, Cowork: "cowork-1", Code: null },
      sessions: [{ id: "cowork-1", mode: "Cowork", title: "Streamed task" }],
      eventsBySessionId: {
        "cowork-1": [
          { id: "user-1", type: "message.user", status: "complete", payload: { text: "Hello", mode: "Cowork" } },
          { id: "stream-1", type: "message.assistant", status: "running", payload: { text: "A", streaming: true, mode: "Cowork" } },
          { id: "stream-1", type: "message.assistant", status: "running", payload: { text: "B", streaming: true, mode: "Cowork" } },
          { id: "verification-1", type: "verification.finished", status: "complete", payload: { mode: "Cowork" } },
          { id: "approval-request-1", type: "approval.requested", status: "pending", payload: { approvalId: "approval-1", mode: "Cowork" } },
          { id: "approval-resolved-1", type: "approval.resolved", status: "complete", payload: { approvalId: "approval-1", answer: "deny", mode: "Cowork" } },
          { id: "assistant-1", type: "message.assistant", status: "complete", payload: { text: "Final answer", mode: "Cowork" } },
        ],
      },
    });

    expect(storage.load().eventsBySessionId["cowork-1"].map((event) => event.id)).toEqual([
      "user-1",
      "assistant-1",
    ]);
  });

  it("saves and restores versioned session state", () => {
    const storage = createSessionStorageAdapter(createMemoryStorage());
    const state = {
      activeSessionId: "session-1",
      sessions: [{ id: "session-1", title: "Inspect repo", createdAt: "2026-06-12T00:00:00.000Z", updatedAt: "2026-06-12T00:00:00.000Z", eventCount: 1 }],
      eventsBySessionId: {
        "session-1": [{ id: "event-1", type: "message.user" }],
      },
    };

    storage.save(state);

    expect(storage.load()).toMatchObject(state);
  });

  it("returns an empty state when persisted JSON is corrupt", () => {
    const backingStore = createMemoryStorage();
    backingStore.setItem("api-blender.cowork.sessions.v2", "{not json");

    expect(createSessionStorageAdapter(backingStore).load()).toEqual({
      activeSessionId: null,
      activeSessionIdsByMode: { Chat: null, Cowork: null, Code: null },
      sessions: [],
      eventsBySessionId: {},
      chatSettings: { webMode: "auto", searchProvider: "auto", artifacts: "on", codeExecution: "off", mcp: "off" },
    });
  });

  it("migrates legacy flat events into the new session store shape", () => {
    const backingStore = createMemoryStorage();
    backingStore.setItem(
      "api-blender.cowork.sessions.v2",
      JSON.stringify({
        schemaVersion: 2,
        savedAt: "2026-06-12T00:00:00.000Z",
        state: {
          activeSessionId: "session-legacy",
          sessions: [{ id: "session-legacy", title: "Legacy task" }],
          events: [{ id: "event-legacy", type: "message.user" }],
        },
      }),
    );

    expect(createSessionStorageAdapter(backingStore).load()).toMatchObject({
      activeSessionId: "session-legacy",
      sessions: [{ id: "session-legacy", title: "Legacy task" }],
      eventsBySessionId: {
        "session-legacy": [{ id: "event-legacy", type: "message.user" }],
      },
    });
  });
});
