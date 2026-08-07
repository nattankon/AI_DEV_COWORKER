export const COWORK_EVENT_TYPES = Object.freeze([
  "session.started",
  "session.finished",
  "message.user",
  "message.assistant",
  "message.system",
  "chat.status",
  "mcp.result",
  "agent.status",
  "tool.started",
  "tool.finished",
  "tool.failed",
  "approval.requested",
  "approval.resolved",
  "diff.proposed",
  "verification.started",
  "verification.finished",
  "error",
]);

const COWORK_EVENT_TYPE_SET = new Set(COWORK_EVENT_TYPES);

function isIsoTimestamp(value) {
  return typeof value === "string" && !Number.isNaN(Date.parse(value));
}

export function validateCoworkEvent(event) {
  const errors = [];

  if (!event || typeof event !== "object") {
    return { valid: false, errors: ["event must be an object"] };
  }

  if (!event.id || typeof event.id !== "string") {
    errors.push("id is required");
  }
  if (!event.sessionId || typeof event.sessionId !== "string") {
    errors.push("sessionId is required");
  }
  if (!isIsoTimestamp(event.timestamp)) {
    errors.push("timestamp must be an ISO-8601 string");
  }
  if (!event.type || typeof event.type !== "string") {
    errors.push("type is required");
  } else if (!COWORK_EVENT_TYPE_SET.has(event.type)) {
    errors.push(`unknown event type: ${event.type}`);
  }
  if (!Object.prototype.hasOwnProperty.call(event, "payload")) {
    errors.push("payload is required");
  }

  return { valid: errors.length === 0, errors };
}

export function createCoworkEvent(event) {
  const nextEvent = {
    id: event?.id,
    sessionId: event?.sessionId,
    timestamp: event?.timestamp,
    type: event?.type,
    status: event?.status ?? "complete",
    payload: event?.payload ?? {},
  };
  const result = validateCoworkEvent(nextEvent);
  if (!result.valid) {
    throw new Error(`Invalid Cowork event: ${result.errors.join(", ")}`);
  }
  return Object.freeze(nextEvent);
}
