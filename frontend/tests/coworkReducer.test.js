import { describe, expect, it } from "vitest";
import { coworkReducer, createInitialCoworkState } from "../model/coworkReducer";
import {
  selectChangedFiles,
  selectCompletionEvidence,
  selectPendingApprovals,
  selectTimeline,
  selectTransientStatus,
} from "../model/coworkSelectors";

function event(overrides = {}) {
  return {
    id: "event-1",
    sessionId: "session-1",
    timestamp: "2026-06-12T00:00:00.000Z",
    type: "message.user",
    status: "complete",
    payload: { text: "Hello" },
    ...overrides,
  };
}

describe("cowork reducer", () => {
  it("replays events into a deterministic chronological timeline", () => {
    const initial = createInitialCoworkState();
    const later = event({ id: "later", timestamp: "2026-06-12T00:00:02.000Z", type: "message.assistant" });
    const earlier = event({ id: "earlier", timestamp: "2026-06-12T00:00:01.000Z" });

    const state = coworkReducer(coworkReducer(initial, { type: "event.received", event: later }), {
      type: "event.received",
      event: earlier,
    });

    expect(selectTimeline(state).map((item) => item.id)).toEqual(["earlier", "later"]);
  });

  it("ignores duplicate event ids", () => {
    const initial = createInitialCoworkState();
    const next = coworkReducer(initial, { type: "event.received", event: event() });
    const duplicate = coworkReducer(next, { type: "event.received", event: event({ payload: { text: "Changed" } }) });

    expect(selectTimeline(duplicate)).toHaveLength(1);
    expect(selectTimeline(duplicate)[0].payload.text).toBe("Hello");
  });

  it("derives pending approvals and changed files", () => {
    const events = [
      event({ id: "approval", type: "approval.requested", payload: { approvalId: "a1", path: "src/app.js" } }),
      event({ id: "diff", type: "diff.proposed", payload: { files: ["src/app.js", "src/api.js"] } }),
    ];
    const state = events.reduce(
      (current, item) => coworkReducer(current, { type: "event.received", event: item }),
      createInitialCoworkState(),
    );

    expect(selectPendingApprovals(state)).toHaveLength(1);
    expect(selectChangedFiles(state)).toEqual(["src/api.js", "src/app.js"]);
  });

  it("hydrates a session from persisted events", () => {
    const state = coworkReducer(createInitialCoworkState(), {
      type: "session.hydrate",
      events: [
        event({ id: "later", timestamp: "2026-06-12T00:00:02.000Z", type: "message.assistant" }),
        event({ id: "earlier", timestamp: "2026-06-12T00:00:01.000Z" }),
      ],
    });

    expect(selectTimeline(state).map((item) => item.id)).toEqual(["earlier", "later"]);
  });

  it("does not restore a stale busy lock from persisted events", () => {
    const state = coworkReducer(createInitialCoworkState(), {
      type: "session.hydrate",
      events: [event({ id: "busy", type: "agent.status", status: "running", payload: { state: "busy" } })],
    });

    expect(state.runStatus).toBe("idle");
  });

  it("returns to idle after an assistant response completes", () => {
    const busy = coworkReducer(createInitialCoworkState(), {
      type: "event.received",
      event: event({ id: "busy", type: "agent.status", status: "running", payload: { state: "busy" } }),
    });
    const complete = coworkReducer(busy, {
      type: "event.received",
      event: event({ id: "answer", type: "message.assistant", payload: { text: "Done" } }),
    });

    expect(complete.runStatus).toBe("idle");
  });

  it("returns to idle after a failed backend message", () => {
    const busy = coworkReducer(createInitialCoworkState(), {
      type: "event.received",
      event: event({ id: "busy", type: "agent.status", status: "running", payload: { state: "busy" } }),
    });
    const failed = coworkReducer(busy, {
      type: "event.received",
      event: event({ id: "failure", type: "message.system", status: "failed", payload: { text: "Timed out" } }),
    });

    expect(failed.runStatus).toBe("idle");
  });

  it("appends streaming assistant deltas with a stable event id", () => {
    const first = coworkReducer(createInitialCoworkState(), {
      type: "event.received",
      event: event({
        id: "stream-session-1-Chat",
        type: "message.assistant",
        status: "running",
        payload: { text: "Hello", role: "AI", mode: "Chat", streaming: true },
      }),
    });
    const second = coworkReducer(first, {
      type: "event.received",
      event: event({
        id: "stream-session-1-Chat",
        type: "message.assistant",
        status: "running",
        payload: { text: " world", role: "AI", mode: "Chat", streaming: true },
      }),
    });

    expect(selectTimeline(second)).toHaveLength(1);
    expect(selectTimeline(second)[0].payload.text).toBe("Hello world");
    expect(selectTimeline(second)[0].status).toBe("running");
  });

  it("replaces an in-flight streaming assistant event with the final commit", () => {
    const streaming = coworkReducer(createInitialCoworkState(), {
      type: "event.received",
      event: event({
        id: "stream-session-1-Chat",
        sessionId: "session-1",
        type: "message.assistant",
        status: "running",
        payload: { text: "Draft", role: "AI", mode: "Chat", streaming: true },
      }),
    });
    const final = coworkReducer(streaming, {
      type: "event.received",
      event: event({
        id: "final-answer",
        sessionId: "session-1",
        type: "message.assistant",
        status: "complete",
        payload: { text: "Final answer", role: "AI", mode: "Chat" },
      }),
    });

    expect(selectTimeline(final).map((item) => item.id)).toEqual(["final-answer"]);
    expect(selectTimeline(final)[0].payload.text).toBe("Final answer");
  });

  it("clears an in-flight streaming assistant event on reset", () => {
    const first = coworkReducer(createInitialCoworkState(), {
      type: "event.received",
      event: event({
        id: "stream-session-1-Chat",
        type: "message.assistant",
        status: "running",
        payload: { text: "discard me", role: "AI", mode: "Chat", streaming: true },
      }),
    });
    const reset = coworkReducer(first, {
      type: "event.received",
      event: event({
        id: "stream-session-1-Chat",
        type: "message.assistant",
        status: "running",
        payload: { text: "", role: "AI", mode: "Chat", streaming: true, reset: true },
      }),
    });

    expect(selectTimeline(reset)).toHaveLength(1);
    expect(selectTimeline(reset)[0].payload.text).toBe("");
  });

  it("stores Chat research status transiently outside the timeline", () => {
    const state = coworkReducer(createInitialCoworkState(), {
      type: "event.received",
      event: event({
        id: "status-session-1-Chat",
        type: "chat.status",
        status: "running",
        payload: { text: "🔍 Searching: fuel price", mode: "Chat", transient: true },
      }),
    });

    expect(selectTimeline(state)).toHaveLength(0);
    expect(selectTransientStatus(state, "session-1", "Chat")).toEqual({
      text: "🔍 Searching: fuel price",
      mode: "Chat",
      sessionId: "session-1",
    });
  });

  it("clears transient Chat research status when answer streaming starts", () => {
    const withStatus = coworkReducer(createInitialCoworkState(), {
      type: "event.received",
      event: event({
        id: "status-session-1-Chat",
        type: "chat.status",
        status: "running",
        payload: { text: "📄 Reading: example.test", mode: "Chat", transient: true },
      }),
    });
    const withDelta = coworkReducer(withStatus, {
      type: "event.received",
      event: event({
        id: "stream-session-1-Chat",
        type: "message.assistant",
        status: "running",
        payload: { text: "Answer", role: "AI", mode: "Chat", streaming: true },
      }),
    });

    expect(selectTransientStatus(withDelta, "session-1", "Chat")).toBeNull();
    expect(selectTimeline(withDelta).map((item) => item.id)).toEqual(["stream-session-1-Chat"]);
  });

  it("clears transient Chat research status when the final answer arrives", () => {
    const withStatus = coworkReducer(createInitialCoworkState(), {
      type: "event.received",
      event: event({
        id: "status-session-1-Chat",
        type: "chat.status",
        status: "running",
        payload: { text: "✍️ Writing…", mode: "Chat", transient: true },
      }),
    });
    const withFinal = coworkReducer(withStatus, {
      type: "event.received",
      event: event({
        id: "final-answer",
        type: "message.assistant",
        status: "complete",
        payload: { text: "Final answer", role: "AI", mode: "Chat" },
      }),
    });

    expect(selectTransientStatus(withFinal, "session-1", "Chat")).toBeNull();
    expect(selectTimeline(withFinal).map((item) => item.id)).toEqual(["final-answer"]);
  });

  it("stores completion evidence without polluting the timeline", () => {
    const state = coworkReducer(createInitialCoworkState(), {
      type: "event.received",
      event: event({
        id: "completion-1",
        type: "verification.finished",
        status: "complete",
        payload: {
          mode: "Cowork",
          writesPerformed: true,
          verificationObserved: true,
          verificationPassed: true,
          verificationStatuses: ["passed"],
          verificationRuns: [{ name: "python-tests", status: "passed" }],
        },
      }),
    });

    expect(selectTimeline(state)).toHaveLength(0);
    expect(selectCompletionEvidence(state, "session-1", "Cowork")).toMatchObject({
      writesPerformed: true,
      verificationPassed: true,
      verificationRuns: [{ name: "python-tests", status: "passed" }],
    });
  });

  it("clears prior completion evidence when a new run goes busy", () => {
    const withEvidence = coworkReducer(createInitialCoworkState(), {
      type: "event.received",
      event: event({
        id: "completion-1",
        type: "verification.finished",
        status: "complete",
        payload: {
          mode: "Cowork",
          writesPerformed: true,
          verificationObserved: false,
          verificationPassed: false,
          verificationStatuses: [],
          verificationRuns: [],
        },
      }),
    });
    expect(selectCompletionEvidence(withEvidence, "session-1", "Cowork")).not.toBeNull();

    const newRun = coworkReducer(withEvidence, {
      type: "event.received",
      event: event({
        id: "busy-1",
        type: "agent.status",
        status: "running",
        payload: { state: "busy", mode: "Cowork" },
      }),
    });

    expect(selectCompletionEvidence(newRun, "session-1", "Cowork")).toBeNull();
  });
});
