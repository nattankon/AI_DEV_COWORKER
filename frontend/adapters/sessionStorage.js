export const COWORK_SESSION_STORAGE_KEY = "api-blender.cowork.sessions.v4";
const LEGACY_SESSION_STORAGE_KEYS = ["api-blender.cowork.sessions.v3", "api-blender.cowork.sessions.v2"];
const MODES = ["Chat", "Cowork", "Code"];

const EMPTY_SESSION_STATE = Object.freeze({
  activeSessionId: null,
  activeSessionIdsByMode: Object.freeze({ Chat: null, Cowork: null, Code: null }),
  sessions: [],
  projects: [],
  eventsBySessionId: {},
  chatSettings: Object.freeze({ webMode: "auto", searchProvider: "auto", artifacts: "on", codeExecution: "off", mcp: "off" }),
});

function normalizeMode(value, fallback = "Cowork") {
  return MODES.includes(value) ? value : fallback;
}

function normalizeSessionProject(value) {
  if (!value || typeof value !== "object") return null;
  const path = typeof value.path === "string" ? value.path.trim() : "";
  if (!path) return null;
  const name = typeof value.name === "string" && value.name.trim()
    ? value.name.trim()
    : path.split(/[\\/]/).filter(Boolean).at(-1) || path;
  return { path, name };
}

function normalizeSessionRecord(value, fallbackMode = "Cowork") {
  if (!value || typeof value !== "object") return null;
  const project = normalizeSessionProject(value.project);
  return {
    id: typeof value.id === "string" && value.id ? value.id : null,
    mode: normalizeMode(value.mode, fallbackMode),
    title: typeof value.title === "string" && value.title.trim() ? value.title.trim() : "Untitled task",
    createdAt: typeof value.createdAt === "string" ? value.createdAt : new Date().toISOString(),
    updatedAt: typeof value.updatedAt === "string" ? value.updatedAt : new Date().toISOString(),
    eventCount: Number.isFinite(value.eventCount) ? value.eventCount : 0,
    ...(project ? { project } : {}),
    ...(value.pinned ? { pinned: true } : {}),
  };
}

function normalizeProjects(value, sessions = []) {
  const candidates = [
    ...(Array.isArray(value) ? value : []),
    ...sessions.map((session) => session.project),
  ];
  const projects = [];
  const seen = new Set();
  for (const candidate of candidates) {
    const project = normalizeSessionProject(candidate);
    if (!project || seen.has(project.path)) continue;
    seen.add(project.path);
    projects.push(project);
  }
  return projects;
}

function isTransientTimelineEvent(event) {
  if (!event || typeof event !== "object") return true;
  if (
    event.type === "agent.status"
    || event.type === "chat.status"
    || event.type === "verification.finished"
    || event.type === "approval.requested"
    || event.type === "approval.resolved"
  ) {
    return true;
  }
  return event.type === "message.assistant" && event.payload?.streaming === true;
}

function normalizeEventsBySessionId(value) {
  if (!value || typeof value !== "object") return {};
  return Object.fromEntries(
    Object.entries(value).flatMap(([sessionId, events]) => {
      if (typeof sessionId !== "string" || !sessionId) return [];
      return [[sessionId, Array.isArray(events) ? events.filter((event) => !isTransientTimelineEvent(event)) : []]];
    }),
  );
}

function normalizeModelRoutes(value) {
  if (!value || typeof value !== "object") return {};
  return Object.fromEntries(
    MODES.flatMap((mode) => {
      const route = typeof value[mode] === "string" ? value[mode].trim() : "";
      return route ? [[mode, route]] : [];
    }),
  );
}

function normalizeChatSettings(value) {
  const raw = value && typeof value === "object" ? value : {};
  const webMode = typeof raw.webMode === "string" ? raw.webMode : typeof raw.web_mode === "string" ? raw.web_mode : "auto";
  const searchProvider = typeof raw.searchProvider === "string" ? raw.searchProvider : typeof raw.search_provider === "string" ? raw.search_provider : "auto";
  const artifacts = typeof raw.artifacts === "string" ? raw.artifacts : "on";
  const codeExecution = typeof raw.codeExecution === "string" ? raw.codeExecution : typeof raw.code_execution === "string" ? raw.code_execution : "off";
  const mcp = typeof raw.mcp === "string" ? raw.mcp : "off";
  return {
    webMode: ["auto", "off"].includes(webMode) ? webMode : "auto",
    searchProvider: ["auto", "brave", "scrape"].includes(searchProvider) ? searchProvider : "auto",
    artifacts: ["on", "off"].includes(artifacts) ? artifacts : "on",
    codeExecution: ["on", "off"].includes(codeExecution) ? codeExecution : "off",
    mcp: ["on", "off"].includes(mcp) ? mcp : "off",
  };
}

function normalizeSessionState(value, fallbackMode = "Cowork") {
  if (!value || typeof value !== "object") {
    return { ...EMPTY_SESSION_STATE, activeSessionIdsByMode: { ...EMPTY_SESSION_STATE.activeSessionIdsByMode } };
  }
  const sessions = Array.isArray(value.sessions)
    ? value.sessions.map((session) => normalizeSessionRecord(session, fallbackMode)).filter((session) => session?.id)
    : [];
  const requested = value.activeSessionIdsByMode && typeof value.activeSessionIdsByMode === "object"
    ? value.activeSessionIdsByMode
    : {};
  const legacyActiveId = typeof value.activeSessionId === "string" ? value.activeSessionId : null;
  const activeSessionIdsByMode = Object.fromEntries(MODES.map((mode) => {
    const requestedId = typeof requested[mode] === "string" ? requested[mode] : null;
    const matchingRequested = sessions.some((session) => session.id === requestedId && session.mode === mode);
    const legacyMatch = mode === fallbackMode && sessions.some((session) => session.id === legacyActiveId && session.mode === mode);
    return [mode, matchingRequested ? requestedId : legacyMatch ? legacyActiveId : sessions.find((session) => session.mode === mode)?.id ?? null];
  }));
  const modelRoutes = normalizeModelRoutes(value.modelRoutes);
  return {
    activeSessionId: activeSessionIdsByMode[fallbackMode],
    activeSessionIdsByMode,
    sessions,
    projects: normalizeProjects(value.projects, sessions),
    eventsBySessionId: normalizeEventsBySessionId(value.eventsBySessionId),
    chatSettings: normalizeChatSettings(value.chatSettings),
    ...(Object.keys(modelRoutes).length > 0 ? { modelRoutes } : {}),
  };
}

function migrateLegacySessionState(parsed) {
  const state = parsed?.state ?? {};
  const legacyEvents = Array.isArray(state.events) ? state.events.filter((event) => event && typeof event === "object") : [];
  const normalized = normalizeSessionState(state, "Chat");
  if (Object.keys(normalized.eventsBySessionId).length > 0 || legacyEvents.length === 0) return normalized;
  const legacySessionId = normalized.activeSessionIdsByMode.Chat || "legacy-session";
  return normalizeSessionState({
    activeSessionId: legacySessionId,
    sessions: normalized.sessions.length > 0 ? normalized.sessions : [{ id: legacySessionId, title: "Recovered session" }],
    eventsBySessionId: { [legacySessionId]: legacyEvents },
  }, "Chat");
}

export function createSessionStorageAdapter(storage = globalThis.localStorage) {
  return {
    load() {
      try {
        const current = storage?.getItem(COWORK_SESSION_STORAGE_KEY);
        const legacy = LEGACY_SESSION_STORAGE_KEYS.map((key) => storage?.getItem(key)).find(Boolean);
        const rawValue = current ?? legacy;
        if (!rawValue) return normalizeSessionState(null);
        const parsed = JSON.parse(rawValue);
        if (parsed?.schemaVersion === 4) return normalizeSessionState(parsed.state, "Cowork");
        if (parsed?.schemaVersion === 3) return normalizeSessionState(parsed.state, "Chat");
        if (parsed?.schemaVersion === 2) return migrateLegacySessionState(parsed);
        return normalizeSessionState(null);
      } catch {
        return normalizeSessionState(null);
      }
    },
    save(state) {
      if (!storage) return;
      const normalized = normalizeSessionState(state, "Cowork");
      const envelope = { schemaVersion: 4, savedAt: new Date().toISOString(), state: normalized };
      try {
        storage.setItem(COWORK_SESSION_STORAGE_KEY, JSON.stringify(envelope));
        return;
      } catch {
        // Likely a quota error on a long-running session — persistence must never
        // break the app. Retry with progressively fewer events per session.
      }
      for (const cap of [400, 150, 40]) {
        const eventsBySessionId = {};
        for (const [sessionId, events] of Object.entries(normalized.eventsBySessionId || {})) {
          eventsBySessionId[sessionId] = Array.isArray(events) ? events.slice(-cap) : [];
        }
        try {
          storage.setItem(
            COWORK_SESSION_STORAGE_KEY,
            JSON.stringify({ ...envelope, state: { ...normalized, eventsBySessionId } }),
          );
          return;
        } catch {
          // Try an even smaller cap; if all fail, give up silently.
        }
      }
    },
    clear() {
      storage?.removeItem(COWORK_SESSION_STORAGE_KEY);
      LEGACY_SESSION_STORAGE_KEYS.forEach((key) => storage?.removeItem(key));
    },
  };
}
