import { describe, expect, it } from "vitest";
import { COWORK_EVENT_TYPES, createCoworkEvent, validateCoworkEvent } from "../model/coworkEvents";

describe("cowork event contract", () => {
  it("creates a valid immutable event envelope", () => {
    const event = createCoworkEvent({
      id: "event-1",
      sessionId: "session-1",
      timestamp: "2026-06-12T00:00:00.000Z",
      type: "message.user",
      status: "complete",
      payload: { text: "Inspect the repository" },
    });

    expect(validateCoworkEvent(event)).toEqual({ valid: true, errors: [] });
    expect(event).toEqual({
      id: "event-1",
      sessionId: "session-1",
      timestamp: "2026-06-12T00:00:00.000Z",
      type: "message.user",
      status: "complete",
      payload: { text: "Inspect the repository" },
    });
    expect(Object.isFrozen(event)).toBe(true);
  });

  it("rejects missing required fields", () => {
    const result = validateCoworkEvent({ type: "message.user", payload: {} });

    expect(result.valid).toBe(false);
    expect(result.errors).toEqual([
      "id is required",
      "sessionId is required",
      "timestamp must be an ISO-8601 string",
    ]);
  });

  it("rejects unknown event types", () => {
    const result = validateCoworkEvent({
      id: "event-1",
      sessionId: "session-1",
      timestamp: "2026-06-12T00:00:00.000Z",
      type: "unknown.event",
      payload: {},
    });

    expect(result.valid).toBe(false);
    expect(result.errors).toContain("unknown event type: unknown.event");
    expect(COWORK_EVENT_TYPES).not.toContain("unknown.event");
  });
});
