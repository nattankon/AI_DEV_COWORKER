import { validateCoworkEvent } from "./coworkEvents";

export function createInitialCoworkState() {
  return {
    eventIds: new Set(),
    events: [],
    runStatus: "idle",
    transientStatus: {},
    completionEvidence: {},
  };
}

function sortEvents(events) {
  return [...events].sort((left, right) => {
    const timeDelta = Date.parse(left.timestamp) - Date.parse(right.timestamp);
    if (timeDelta !== 0) return timeDelta;
    return left.id.localeCompare(right.id);
  });
}

function runStatusForEvent(event, currentStatus) {
  if (event.status === "failed") {
    return "idle";
  }
  if (event.type === "session.started" || event.type === "agent.status") {
    return event.payload?.state === "idle" ? "idle" : "busy";
  }
  if (event.type === "session.finished") {
    return "idle";
  }
  if (event.type === "message.assistant") {
    if (event.status === "running" && event.payload?.streaming === true) {
      return currentStatus;
    }
    return "idle";
  }
  return currentStatus;
}

function transientStatusKey(sessionId, mode) {
  return `${sessionId || ""}::${mode || ""}`;
}

function clearTransientStatusForEvent(transientStatus, event) {
  const mode = event.payload?.mode ?? "";
  const key = transientStatusKey(event.sessionId, mode);
  if (!Object.prototype.hasOwnProperty.call(transientStatus, key)) {
    return transientStatus;
  }
  const next = { ...transientStatus };
  delete next[key];
  return next;
}

function startTransientStatusForEvent(transientStatus, event, text = "") {
  const mode = event.payload?.mode ?? "";
  const key = transientStatusKey(event.sessionId, mode);
  const previous = transientStatus?.[key];
  return {
    ...transientStatus,
    [key]: {
      text,
      mode,
      sessionId: event.sessionId,
      startedAt: previous?.startedAt ?? event.timestamp,
    },
  };
}

function clearCompletionEvidenceForNewRun(completionEvidence, event) {
  if (!(event.type === "agent.status" && event.payload?.state === "busy")) {
    return completionEvidence;
  }
  const mode = event.payload?.mode ?? "";
  const key = transientStatusKey(event.sessionId, mode);
  if (!Object.prototype.hasOwnProperty.call(completionEvidence, key)) {
    return completionEvidence;
  }
  const next = { ...completionEvidence };
  delete next[key];
  return next;
}

export function coworkReducer(state, action) {
  if (!state) return createInitialCoworkState();
  if (action?.type === "session.hydrate") {
    const hydratedEvents = Array.isArray(action.events) ? sortEvents(action.events.filter((event) => event && typeof event === "object")) : [];
    return {
      eventIds: new Set(hydratedEvents.map((event) => event.id).filter(Boolean)),
      events: hydratedEvents,
      runStatus: "idle",
      transientStatus: {},
      completionEvidence: {},
    };
  }
  if (action?.type !== "event.received") return state;

  const event = action.event;
  const validation = validateCoworkEvent(event);
  if (!validation.valid) {
    return state;
  }

  if (event.type === "chat.status") {
    const text = String(event.payload?.text ?? "").trim();
    if (!text) return state;
    return {
      ...state,
      transientStatus: startTransientStatusForEvent(state.transientStatus ?? {}, event, text),
    };
  }

  if (event.type === "verification.finished") {
    const mode = event.payload?.mode ?? "";
    return {
      ...state,
      completionEvidence: {
        ...(state.completionEvidence ?? {}),
        [transientStatusKey(event.sessionId, mode)]: {
          mode,
          sessionId: event.sessionId,
          writesPerformed: Boolean(event.payload?.writesPerformed),
          verificationObserved: Boolean(event.payload?.verificationObserved),
          verificationPassed: Boolean(event.payload?.verificationPassed),
          verificationStatuses: Array.isArray(event.payload?.verificationStatuses)
            ? event.payload.verificationStatuses
            : [],
          verificationRuns: Array.isArray(event.payload?.verificationRuns)
            ? event.payload.verificationRuns
            : [],
          testFilesModified: Array.isArray(event.payload?.testFilesModified)
            ? event.payload.testFilesModified
            : [],
        },
      },
    };
  }

  const isStreamingAssistant =
    event.type === "message.assistant" && event.status === "running" && event.payload?.streaming === true;
  const shouldClearTransientStatus =
    event.status === "failed" ||
    (event.type === "agent.status" && event.payload?.state === "idle") ||
    event.type === "session.finished" ||
    (event.type === "message.assistant" && (
      event.status !== "running"
      || (event.payload?.streaming === true && event.payload?.mode === "Chat")
    ));
  const startsTransientStatus = event.type === "agent.status" && event.payload?.state === "busy";
  const transientStatus = startsTransientStatus
    ? startTransientStatusForEvent(state.transientStatus ?? {}, event)
    : shouldClearTransientStatus
      ? clearTransientStatusForEvent(state.transientStatus ?? {}, event)
      : state.transientStatus ?? {};
  const completionEvidence = clearCompletionEvidenceForNewRun(state.completionEvidence ?? {}, event);

  if (state.eventIds.has(event.id)) {
    if (!isStreamingAssistant) return state;
    const events = state.events.map((item) => {
      if (item.id !== event.id || item.payload?.streaming !== true) return item;
      return {
        ...item,
        timestamp: event.timestamp,
        payload: {
          ...item.payload,
          text: event.payload?.reset ? "" : `${item.payload?.text ?? ""}${event.payload?.text ?? ""}`,
        },
      };
    });
    return {
      ...state,
      events: sortEvents(events),
      runStatus: runStatusForEvent(event, state.runStatus),
      transientStatus,
      completionEvidence,
    };
  }

  const eventIds = new Set(state.eventIds);
  let events = state.events;
  const isFinalAssistant =
    event.type === "message.assistant" && event.status !== "running" && event.payload?.streaming !== true;
  if (isFinalAssistant) {
    const mode = event.payload?.mode ?? "";
    events = events.filter((item) => {
      const sameSession = item.sessionId === event.sessionId;
      const sameMode = (item.payload?.mode ?? "") === mode;
      const isStreaming = item.type === "message.assistant" && item.payload?.streaming === true;
      if (sameSession && sameMode && isStreaming) {
        eventIds.delete(item.id);
        return false;
      }
      return true;
    });
  }
  eventIds.add(event.id);

  return {
    ...state,
    eventIds,
    events: sortEvents([...events, event]),
    runStatus: runStatusForEvent(event, state.runStatus),
    transientStatus,
    completionEvidence,
  };
}
