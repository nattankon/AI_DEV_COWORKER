import { useEffect, useLayoutEffect, useMemo, useReducer, useRef, useState } from "react";
import { answerQuestion, cancelCowork, createChatMemory, deleteChatMemory, discoverChatConnector, eelEvents, fetchModels, installUpdateNow, listChatArtifacts, listChatConnectors, listChatMemory, listChatQualityEval, loadApiKeys, runChatMcpTool, runChatQuality, runChatQualityEval, saveChatConnectors, selectFolder, sendCowork, setAutoApprove, setChatMemoryEnabled, setWorkspace, subscribeEelEvent, testChatConnector, updateChatMemory, workspaceAction } from "./lib/eel";
import { createCoworkBridge } from "./adapters/coworkBridge";
import { createSessionStorageAdapter } from "./adapters/sessionStorage";
import ApprovalPrompt from "./components/ApprovalPrompt";
import AppHeader from "./components/AppHeader";
import ArtifactsPanel from "./components/ArtifactsPanel";
import Composer from "./components/Composer";
import ConnectorsPanel from "./components/ConnectorsPanel";
import MemoryManager from "./components/MemoryManager";
import ProjectsView from "./components/ProjectsView";
import ProcessingIndicator from "./components/ProcessingIndicator";
import VerificationPanel from "./components/VerificationPanel";
import QualityEvalPanel from "./components/QualityEvalPanel";
import SessionRail from "./components/SessionRail";
import SettingsModal from "./components/SettingsModal";
import Timeline from "./components/Timeline";
import WorkspacePanel from "./components/WorkspacePanel";
import { createCoworkEvent } from "./model/coworkEvents";
import { buildContextUsage } from "./model/contextUsage";
import { coworkReducer, createInitialCoworkState } from "./model/coworkReducer";
import { selectCompletionEvidence, selectTimeline, selectTransientStatus } from "./model/coworkSelectors";
import { ArrowDown, BookOpen, Code2, HeartHandshake, PenLine, Sparkles } from "lucide-react";

function createId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

const CHAT_MODES = ["Chat", "Cowork", "Code"];
const DEFAULT_MODEL_LABEL = "qwen/qwen3.5-9b";

function normalizeMode(mode, fallback = "") {
  return CHAT_MODES.includes(mode) ? mode : fallback;
}

function createDefaultModelRoutes(modelLabel) {
  const resolvedLabel = modelLabel || DEFAULT_MODEL_LABEL;
  return Object.fromEntries(CHAT_MODES.map((mode) => [mode, resolvedLabel]));
}

function normalizeModelRoutes(routes) {
  if (!routes || typeof routes !== "object") return {};
  return Object.fromEntries(
    CHAT_MODES.flatMap((mode) => {
      const route = typeof routes[mode] === "string" ? routes[mode].trim() : "";
      return route ? [[mode, route]] : [];
    }),
  );
}

function normalizeModelForRequest(modelLabel, coworkModelLabel, coworkModel) {
  if (modelLabel === "auto") return "auto";
  if (modelLabel === coworkModelLabel && coworkModel) return coworkModel;
  return /^(local|openai|deepseek|zai|gemini):/.test(modelLabel) ? modelLabel : `local:${modelLabel}`;
}

function normalizeProject(project) {
  if (!project || typeof project !== "object") return null;
  const path = typeof project.path === "string" ? project.path.trim() : "";
  if (!path) return null;
  const name = typeof project.name === "string" && project.name.trim()
    ? project.name.trim()
    : path.split(/[\\/]/).filter(Boolean).at(-1) || path;
  return { path, name };
}

function createSessionRecord(id, title = "New task", mode = "Cowork", project = null) {
  const now = new Date().toISOString();
  const normalizedProject = normalizeProject(project);
  return {
    id,
    mode: CHAT_MODES.includes(mode) ? mode : "Cowork",
    title,
    createdAt: now,
    updatedAt: now,
    eventCount: 0,
    ...(normalizedProject ? { project: normalizedProject } : {}),
  };
}

function deriveSessionTitle(events, fallbackTitle = "New task") {
  const firstUserMessage = [...events].find((event) => event.type === "message.user" && typeof event.payload?.text === "string" && event.payload.text.trim());
  if (!firstUserMessage) return fallbackTitle;
  return firstUserMessage.payload.text.trim().split(/\r?\n/)[0].slice(0, 48);
}

function createInitialSessionStore() {
  const sessions = CHAT_MODES.map((mode) => createSessionRecord(createId(), "New task", mode));
  return {
    activeSessionId: sessions.find((session) => session.mode === "Cowork").id,
    activeSessionIdsByMode: Object.fromEntries(sessions.map((session) => [session.mode, session.id])),
    sessions,
    eventsBySessionId: Object.fromEntries(sessions.map((session) => [session.id, []])),
  };
}

function normalizeSessionStore(store) {
  if (!store || typeof store !== "object") return createInitialSessionStore();
  const sessions = Array.isArray(store.sessions)
    ? store.sessions.filter((session) => session && typeof session === "object" && session.id).map((session) => ({
      ...createSessionRecord(session.id, session.title, session.mode),
      ...session,
      mode: CHAT_MODES.includes(session.mode) ? session.mode : "Cowork",
    }))
    : [];
  const eventsBySessionId = store.eventsBySessionId && typeof store.eventsBySessionId === "object" ? store.eventsBySessionId : {};
  const normalizedSessions = [...sessions];
  const requestedActiveIds = store.activeSessionIdsByMode && typeof store.activeSessionIdsByMode === "object" ? store.activeSessionIdsByMode : {};
  const activeSessionIdsByMode = {};
  for (const mode of CHAT_MODES) {
    const requestedId = requestedActiveIds[mode] || (mode === "Cowork" ? store.activeSessionId : "");
    let session = normalizedSessions.find((item) => item.id === requestedId && item.mode === mode)
      ?? normalizedSessions.find((item) => item.mode === mode);
    if (!session) {
      session = createSessionRecord(createId(), "New task", mode);
      normalizedSessions.push(session);
    }
    activeSessionIdsByMode[mode] = session.id;
  }
  const normalizedEventsBySessionId = Object.fromEntries(
    Object.entries(eventsBySessionId).map(([sessionId, events]) => [sessionId, Array.isArray(events) ? events.filter((event) => event && typeof event === "object") : []]),
  );
  for (const session of normalizedSessions) {
    if (!normalizedEventsBySessionId[session.id]) normalizedEventsBySessionId[session.id] = [];
  }
  return {
    activeSessionId: activeSessionIdsByMode.Cowork,
    activeSessionIdsByMode,
    sessions: normalizedSessions,
    eventsBySessionId: normalizedEventsBySessionId,
    modelRoutes: normalizeModelRoutes(store.modelRoutes),
  };
}

function summarizeSession(session, events = []) {
  const nextTitle = deriveSessionTitle(events, session?.title || "New task");
  const eventCount = events.length;
  return {
    ...session,
    title: nextTitle,
    eventCount,
    updatedAt: events.at(-1)?.timestamp || session?.updatedAt || new Date().toISOString(),
  };
}

function tagSessionProject(store, sessionId, project) {
  const normalized = normalizeProject(project);
  if (!normalized) return store;
  let changed = false;
  const sessions = store.sessions.map((session) => {
    if (session.id !== sessionId || session.project) return session;
    changed = true;
    return { ...session, project: normalized };
  });
  return changed ? { ...store, sessions } : store;
}

function appendEventToSessionStore(store, sessionId, event) {
  const currentEvents = store.eventsBySessionId[sessionId] ?? [];
  const nextEvents = [...currentEvents, event];
  const nextSessions = store.sessions.map((session) => {
    if (session.id !== sessionId) return session;
    return summarizeSession(session, nextEvents);
  });

  const existingSession = nextSessions.some((session) => session.id === sessionId);
  if (!existingSession) {
    nextSessions.unshift(summarizeSession(createSessionRecord(sessionId), nextEvents));
  }

  return {
    ...store,
    sessions: nextSessions,
    eventsBySessionId: {
      ...store.eventsBySessionId,
      [sessionId]: nextEvents,
    },
  };
}

function chatHistoryFromEvents(events = []) {
  return events.flatMap((event) => {
    if (!event || event.status === "running") return [];
    const text = typeof event.payload?.text === "string" ? event.payload.text.trim() : "";
    if (!text) return [];
    if (event.type === "message.user") return [{ role: "user", content: text }];
    if (event.type === "message.assistant") return [{ role: "assistant", content: text }];
    return [];
  });
}

function timelineAttachmentPreview(attachment) {
  if (!attachment || typeof attachment !== "object") return null;
  const item = {
    label: attachment.label,
    source: attachment.source,
    kind: attachment.kind,
  };
  const dataUrl = typeof attachment.dataUrl === "string" ? attachment.dataUrl : "";
  if (attachment.kind === "image" && dataUrl.startsWith("data:image/")) {
    item.thumbnailDataUrl = dataUrl;
  }
  return item;
}

function truncateEventsAfter(events = [], eventId = "", { includeEvent = true } = {}) {
  const index = events.findIndex((event) => event.id === eventId);
  if (index < 0) return events;
  return events.slice(0, includeEvent ? index + 1 : index);
}

function replaceSessionEvents(store, sessionId, events) {
  const nextEvents = Array.isArray(events) ? events : [];
  return {
    ...store,
    sessions: store.sessions.map((session) => (session.id === sessionId ? summarizeSession(session, nextEvents) : session)),
    eventsBySessionId: {
      ...store.eventsBySessionId,
      [sessionId]: nextEvents,
    },
  };
}

function createDefaultBridge() {
  return createCoworkBridge({
    answerApproval: answerQuestion,
    fetchModels,
    loadApiKeys,
    listChatMemory,
    updateChatMemory,
    setChatMemoryEnabled,
    deleteChatMemory,
    cancelPrompt: cancelCowork,
        listChatArtifacts,
        listChatConnectors,
        listChatQualityEval,
        runChatQuality,
        runChatQualityEval,
        runChatMcpTool,
        createChatMemory,
        saveChatConnectors,
    testChatConnector,
    discoverChatConnector,
    selectWorkspace: selectFolder,
    sendPrompt: sendCowork,
    setWorkspace,
    workspaceAction,
    installUpdateNow,
    setAutoApprove,
    subscribe: (eventName, handler) => {
      const mappedEventName = {
        available_models: eelEvents.availableModels,
        api_keys_loaded: eelEvents.apiKeysLoaded,
        "app-update": eelEvents.appUpdate,
        chat_memory_state: eelEvents.chatMemoryState,
        chat_artifacts_state: eelEvents.chatArtifactsState,
        chat_connectors_state: eelEvents.chatConnectorsState,
        chat_connector_test_result: eelEvents.chatConnectorTestResult,
        chat_connector_discovery_result: eelEvents.chatConnectorDiscoveryResult,
        chat_quality_eval_state: eelEvents.chatQualityEvalState,
        chat_model_route: eelEvents.chatModelRoute,
        cowork_interactive_question: eelEvents.coworkInteractiveQuestion,
        "backend-log": eelEvents.backendLog,
        cowork_log: eelEvents.coworkLog,
        cowork_ui_state: eelEvents.coworkUiState,
        workspace_changed: eelEvents.workspaceChanged,
        workspace_response: eelEvents.workspaceResponse,
      }[eventName] ?? eventName;
      return subscribeEelEvent(mappedEventName, handler);
    },
  });
}

export default function CoworkApp({
  bridge,
  bridgeState = "dev",
  coworkModel = "",
  coworkModelLabel = "",
  coworkUiState = "idle",
  sessionStorageAdapter,
}) {
  const resolvedSessionStorageAdapter = useMemo(
    () => sessionStorageAdapter ?? createSessionStorageAdapter(),
    [sessionStorageAdapter],
  );
  const [sessionStore, setSessionStore] = useState(() => normalizeSessionStore(resolvedSessionStorageAdapter.load()));
  const [state, dispatch] = useReducer(coworkReducer, undefined, createInitialCoworkState);
  const [workingDirectory, setWorkingDirectory] = useState("");
  const [activeMode, setActiveMode] = useState("Chat");
  const [activeView, setActiveView] = useState("chat");
  const [composerFocusSignal, setComposerFocusSignal] = useState(0);
  const [effort, setEffort] = useState("Medium");
  const [projects, setProjects] = useState([]);
  const [resolvedApprovalIds, setResolvedApprovalIds] = useState(() => new Set());
  const [busySessionIds, setBusySessionIds] = useState(() => new Set());
  const [modelRoutes, setModelRoutes] = useState(() => ({
    ...createDefaultModelRoutes(coworkModelLabel),
    ...normalizeModelRoutes(sessionStore.modelRoutes),
  }));
  const [modelRouteReasons, setModelRouteReasons] = useState({});
  const [sidebarOpen, setSidebarOpen] = useState(() => typeof window === "undefined" || window.innerWidth >= 1024);
  const [suggestedPrompt, setSuggestedPrompt] = useState(null);
  const [suggestedAttachments, setSuggestedAttachments] = useState([]);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  const [availableModels, setAvailableModels] = useState([]);
  const [modelProviders, setModelProviders] = useState([]);
  const [searchCapabilities, setSearchCapabilities] = useState(null);
  const [memoryManagerOpen, setMemoryManagerOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [appUpdate, setAppUpdate] = useState({ state: "idle", version: "", percent: 0 });
  const [autoApprove, setAutoApproveState] = useState(() => {
    try {
      return localStorage.getItem("cowork.autoApprove") === "1";
    } catch {
      return false;
    }
  });
  const [settingsSection, setSettingsSection] = useState("developer");
  const [chatMemoryEntries, setChatMemoryEntries] = useState([]);
  const [chatArtifacts, setChatArtifacts] = useState([]);
  const [chatQualityEvalState, setChatQualityEvalState] = useState({ cases: [], count: 0 });
  const [chatConnectorsState, setChatConnectorsState] = useState({ connectors: [], statuses: [], enabled: false, mcp_sdk_available: false });
  const [chatConnectorTestResult, setChatConnectorTestResult] = useState(null);
  const [chatConnectorDiscoveryResult, setChatConnectorDiscoveryResult] = useState(null);
  const [chatSettings, setChatSettings] = useState(() => ({
    webMode: sessionStore.chatSettings?.webMode || "auto",
    searchProvider: sessionStore.chatSettings?.searchProvider || "auto",
    artifacts: sessionStore.chatSettings?.artifacts || "on",
    codeExecution: sessionStore.chatSettings?.codeExecution || "off",
    mcp: sessionStore.chatSettings?.mcp || "off",
  }));
  const conversationScrollRef = useRef(null);
  const conversationNearBottomRef = useRef(true);
  const coworkBridge = useMemo(() => bridge ?? createDefaultBridge(), [bridge]);
  const activeSessionId = sessionStore.activeSessionIdsByMode[activeMode];
  const modeSessions = sessionStore.sessions.filter((session) => session.mode === activeMode);
  const activeSession = modeSessions.find((session) => session.id === activeSessionId) ?? modeSessions[0];
  const sessionEvents = sessionStore.eventsBySessionId[activeSession?.id ?? activeSessionId] ?? [];
  const workspaceLabel = workingDirectory ? workingDirectory.split(/[\\/]/).filter(Boolean).at(-1) : "";
  const currentProject = useMemo(
    () => (workingDirectory ? { path: workingDirectory, name: workspaceLabel || workingDirectory } : null),
    [workingDirectory, workspaceLabel],
  );
  const runStatus = coworkUiState === "busy" || busySessionIds.has(activeSessionId) || state.runStatus === "busy" ? "busy" : "idle";
  const selectedModelLabel = modelRoutes[activeMode] || coworkModelLabel || DEFAULT_MODEL_LABEL;
  const activeRouteReason = modelRouteReasons[`${activeMode}:${activeSessionId}`] || modelRouteReasons[activeMode] || "";
  const normalizedSelectedModel = selectedModelLabel === "auto"
    ? "auto"
    : /^(local|openai|deepseek|zai|gemini):/.test(selectedModelLabel) ? selectedModelLabel : `local:${selectedModelLabel}`;
  const fallbackModels = ["local:qwen2.5-7b-instruct"];
  const modelStatusLabel = availableModels.includes(normalizedSelectedModel)
    ? "Model loaded"
    : fallbackModels.some((model) => availableModels.includes(model))
      ? "Fallback ready"
      : availableModels.length > 0
        ? "Model unavailable"
        : "Model status";
  const contextUsage = useMemo(
    () => buildContextUsage({ events: sessionEvents, modelLabel: selectedModelLabel, modelProviders }),
    [sessionEvents, selectedModelLabel, modelProviders],
  );
  const timeline = selectTimeline(state);
  const transientStatus = selectTransientStatus(state, activeSessionId, activeMode);
  const completionEvidence = selectCompletionEvidence(state, activeSessionId, activeMode);
  const hasTimeline = timeline.length > 0;
  const pendingApproval = [...timeline]
    .reverse()
    .find(
      (event) =>
        event.type === "approval.requested" &&
        !resolvedApprovalIds.has(event.payload?.approvalId),
    );
  const activeSessionIndex = modeSessions.findIndex((session) => session.id === activeSessionId);
  const canGoBack = activeSessionIndex >= 0 && activeSessionIndex < modeSessions.length - 1;
  const canGoForward = activeSessionIndex > 0;
  const canRegenerate = activeMode === "Chat" && runStatus !== "busy" && sessionEvents.some((event) => event.type === "message.user");
  const canRetry = activeMode !== "Chat" && runStatus !== "busy" && sessionEvents.some((event) => event.type === "message.user");
  const quickActions = [
    { id: "code", label: "Code", icon: Code2, mode: "Code", prompt: "Inspect this project and suggest the next safe coding step" },
    { id: "write", label: "Write", icon: PenLine, mode: "Chat", prompt: "Draft release notes for this project" },
    { id: "learn", label: "Learn", icon: BookOpen, mode: "Cowork", prompt: "Explain this project's current architecture in simple steps" },
    { id: "life", label: "Life stuff", icon: HeartHandshake, mode: "Chat", prompt: "Help me organize today's development priorities" },
    { id: "agent", label: "Agent choice", icon: Sparkles, mode: "Cowork", prompt: "Choose the most useful next agent task and explain why" },
  ];

  useEffect(() => {
    resolvedSessionStorageAdapter.save(sessionStore);
  }, [resolvedSessionStorageAdapter, sessionStore]);

  useEffect(() => {
    setSessionStore((current) => {
      const currentRoutes = normalizeModelRoutes(current.modelRoutes);
      const nextRoutes = normalizeModelRoutes(modelRoutes);
      if (JSON.stringify(currentRoutes) === JSON.stringify(nextRoutes)) return current;
      return { ...current, modelRoutes: nextRoutes };
    });
  }, [modelRoutes]);

  useEffect(() => {
    setSessionStore((current) => {
      const currentSettings = current.chatSettings ?? {};
      if (
        currentSettings.webMode === chatSettings.webMode
        && currentSettings.searchProvider === chatSettings.searchProvider
        && currentSettings.artifacts === chatSettings.artifacts
        && currentSettings.codeExecution === chatSettings.codeExecution
        && currentSettings.mcp === chatSettings.mcp
      ) {
        return current;
      }
      return { ...current, chatSettings };
    });
  }, [chatSettings]);

  useEffect(() => {
    if (!coworkModelLabel) return;
    setModelRoutes((current) => {
      const next = { ...current };
      for (const mode of CHAT_MODES) {
        if (!next[mode]) next[mode] = coworkModelLabel;
      }
      return next;
    });
  }, [coworkModelLabel]);

  useEffect(() => {
    const unsubscribe = typeof coworkBridge.subscribeModels === "function"
      ? coworkBridge.subscribeModels((models, metadata = {}) => {
        setAvailableModels(models);
        setModelProviders(Array.isArray(metadata.providers) ? metadata.providers : []);
      })
      : undefined;
    void coworkBridge.fetchModels?.();
    return () => {
      if (typeof unsubscribe === "function") unsubscribe();
    };
  }, [coworkBridge]);

  useEffect(() => {
    const unsubscribe = typeof coworkBridge.subscribeModelRoutes === "function"
      ? coworkBridge.subscribeModelRoutes((payload = {}) => {
        const mode = String(payload.mode || "Chat");
        const sessionId = String(payload.client_session_id || payload.clientSessionId || "");
        const reason = String(payload.reason || "").trim();
        if (!reason) return;
        setModelRouteReasons((current) => ({
          ...current,
          [mode]: reason,
          ...(sessionId ? { [`${mode}:${sessionId}`]: reason } : {}),
        }));
      })
      : undefined;
    return () => {
      if (typeof unsubscribe === "function") unsubscribe();
    };
  }, [coworkBridge]);

  useEffect(() => {
    const unsubscribe = typeof coworkBridge.subscribeApiKeys === "function"
      ? coworkBridge.subscribeApiKeys((payload = {}) => {
        if (payload.search) setSearchCapabilities(payload.search);
        if (Array.isArray(payload.providers)) setModelProviders(payload.providers);
      })
      : undefined;
    void coworkBridge.loadApiKeys?.();
    return () => {
      if (typeof unsubscribe === "function") unsubscribe();
    };
  }, [coworkBridge]);

  useEffect(() => {
    const unsubscribe = typeof coworkBridge.subscribeChatMemory === "function"
      ? coworkBridge.subscribeChatMemory((payload = {}) => {
        setChatMemoryEntries(Array.isArray(payload.entries) ? payload.entries : []);
      })
      : undefined;
    if (memoryManagerOpen || (settingsOpen && settingsSection === "role")) void coworkBridge.listChatMemory?.();
    return () => {
      if (typeof unsubscribe === "function") unsubscribe();
    };
  }, [coworkBridge, memoryManagerOpen, settingsOpen, settingsSection]);

  useEffect(() => {
    const unsubscribe = typeof coworkBridge.subscribeChatArtifacts === "function"
      ? coworkBridge.subscribeChatArtifacts((payload = {}) => {
        setChatArtifacts(Array.isArray(payload.artifacts) ? payload.artifacts : []);
      })
      : undefined;
    if (activeView === "artifacts") void coworkBridge.listChatArtifacts?.();
    return () => {
      if (typeof unsubscribe === "function") unsubscribe();
    };
  }, [coworkBridge, activeView]);

  useEffect(() => {
    const unsubscribe = typeof coworkBridge.subscribeChatQualityEval === "function"
      ? coworkBridge.subscribeChatQualityEval((payload = {}) => {
        setChatQualityEvalState({
          cases: Array.isArray(payload.cases) ? payload.cases : [],
          count: Number.isFinite(payload.count) ? payload.count : Array.isArray(payload.cases) ? payload.cases.length : 0,
          ...(payload.snapshot ? { snapshot: payload.snapshot } : {}),
          ...(payload.live_matrix ? { live_matrix: payload.live_matrix } : {}),
          ...(payload.reports ? { reports: payload.reports } : {}),
          ...(payload.source_profile ? { source_profile: payload.source_profile } : {}),
          ...(payload.text_diagnostics ? { text_diagnostics: payload.text_diagnostics } : {}),
          ...(payload.requires_confirmation ? { requires_confirmation: payload.requires_confirmation, message: payload.message } : {}),
        });
      })
      : undefined;
    if (activeView === "quality") void coworkBridge.listChatQualityEval?.();
    return () => {
      if (typeof unsubscribe === "function") unsubscribe();
    };
  }, [coworkBridge, activeView]);

  useEffect(() => {
    const disposers = [];
    const unsubscribe = typeof coworkBridge.subscribeChatConnectors === "function"
      ? coworkBridge.subscribeChatConnectors((payload = {}) => {
        setChatConnectorsState({
          connectors: Array.isArray(payload.connectors) ? payload.connectors : [],
          statuses: Array.isArray(payload.statuses) ? payload.statuses : [],
          enabled: Boolean(payload.enabled),
          mcp_sdk_available: Boolean(payload.mcp_sdk_available),
        });
      })
      : undefined;
    if (typeof unsubscribe === "function") disposers.push(unsubscribe);
    if (typeof coworkBridge.subscribeChatConnectorTests === "function") {
      disposers.push(coworkBridge.subscribeChatConnectorTests((payload = {}) => {
        setChatConnectorTestResult(payload);
      }));
    }
    if (typeof coworkBridge.subscribeChatConnectorDiscovery === "function") {
      disposers.push(coworkBridge.subscribeChatConnectorDiscovery((payload = {}) => {
        setChatConnectorDiscoveryResult(payload);
      }));
    }
    void coworkBridge.listChatConnectors?.();
    return () => {
      disposers.forEach((dispose) => {
        if (typeof dispose === "function") dispose();
      });
    };
  }, [coworkBridge]);

  useEffect(() => {
    if (activeView === "connectors") void coworkBridge.listChatConnectors?.();
  }, [coworkBridge, activeView]);

  useLayoutEffect(() => {
    dispatch({ type: "session.hydrate", events: sessionStore.eventsBySessionId[activeSessionId] ?? [] });
    conversationNearBottomRef.current = true;
    setShowJumpToLatest(false);
  }, [activeSessionId]);

  const scrollConversationToLatest = (behavior = "smooth") => {
    const scrollArea = conversationScrollRef.current;
    if (!scrollArea || typeof scrollArea.scrollTo !== "function") return;
    scrollArea.scrollTo({ top: scrollArea.scrollHeight, behavior });
    conversationNearBottomRef.current = true;
    setShowJumpToLatest(false);
  };

  useEffect(() => {
    if (activeView !== "chat" || !conversationNearBottomRef.current) return undefined;
    const frame = window.requestAnimationFrame(() => scrollConversationToLatest("smooth"));
    return () => window.cancelAnimationFrame(frame);
  }, [activeView, timeline.length, pendingApproval?.payload?.approvalId]);

  const handleConversationScroll = (event) => {
    const scrollArea = event.currentTarget;
    const distanceFromBottom = scrollArea.scrollHeight - scrollArea.scrollTop - scrollArea.clientHeight;
    const nearBottom = distanceFromBottom <= 80;
    conversationNearBottomRef.current = nearBottom;
    setShowJumpToLatest(!nearBottom);
  };

  useEffect(() => {
    if (typeof coworkBridge.subscribe !== "function") return undefined;
    return coworkBridge.subscribe(activeSessionId, (event) => {
      if (event.type === "message.user") return;
      const eventMode = normalizeMode(event.payload?.mode);
      const targetSessionId = sessionStore.sessions.some((session) => session.id === event.sessionId)
        ? event.sessionId
        : eventMode && sessionStore.activeSessionIdsByMode[eventMode]
          ? sessionStore.activeSessionIdsByMode[eventMode]
        : activeSessionId;
      if (event.type === "agent.status") {
        setBusySessionIds((current) => {
          const next = new Set(current);
          if (event.payload?.state === "busy") next.add(targetSessionId);
          else next.delete(targetSessionId);
          return next;
        });
      } else if (
        event.type === "message.assistant"
        || event.type === "session.finished"
        || event.status === "failed"
      ) {
        setBusySessionIds((current) => {
          const next = new Set(current);
          next.delete(targetSessionId);
          return next;
        });
      }
      if (targetSessionId === activeSessionId) dispatch({ type: "event.received", event });
      if (event.type !== "chat.status") {
        setSessionStore((current) => appendEventToSessionStore(current, targetSessionId, event));
      }
    });
  }, [activeSessionId, coworkBridge, sessionStore.sessions]);

  const openNewSession = (project) => {
    const sessionId = createId();
    setSessionStore((current) => ({
      ...current,
      activeSessionId: activeMode === "Cowork" ? sessionId : current.activeSessionId,
      activeSessionIdsByMode: { ...current.activeSessionIdsByMode, [activeMode]: sessionId },
      sessions: [createSessionRecord(sessionId, "New task", activeMode, project), ...current.sessions],
      eventsBySessionId: {
        ...current.eventsBySessionId,
        [sessionId]: [],
      },
    }));
    dispatch({ type: "session.hydrate", events: [] });
    setActiveView("chat");
  };

  const startNewSession = () => openNewSession(currentProject);

  const startNewSessionInProject = async (project) => {
    const normalized = normalizeProject(project);
    if (normalized && normalized.path && normalized.path !== workingDirectory) {
      setWorkingDirectory(normalized.path);
      await coworkBridge.setWorkspace?.(normalized.path);
    }
    openNewSession(normalized);
  };

  const selectSession = (sessionId) => {
    setSessionStore((current) => ({
      ...current,
      activeSessionId: activeMode === "Cowork" ? sessionId : current.activeSessionId,
      activeSessionIdsByMode: { ...current.activeSessionIdsByMode, [activeMode]: sessionId },
    }));
    setActiveView("chat");
  };

  const renameSession = (sessionId, title) => {
    if (!title) return;
    setSessionStore((current) => ({
      ...current,
      sessions: current.sessions.map((session) => (session.id === sessionId ? { ...session, title } : session)),
    }));
  };

  const togglePinSession = (sessionId) => {
    setSessionStore((current) => ({
      ...current,
      sessions: current.sessions
        .map((session) => (session.id === sessionId ? { ...session, pinned: !session.pinned } : session))
        .sort((left, right) => Number(Boolean(right.pinned)) - Number(Boolean(left.pinned))),
    }));
  };

  const deleteSession = (sessionId) => {
    setSessionStore((current) => {
      const remainingSessions = current.sessions.filter((session) => session.id !== sessionId);
      const remainingModeSessions = remainingSessions.filter((session) => session.mode === activeMode);
      const nextSession = remainingModeSessions[0] ?? createSessionRecord(createId(), "New task", activeMode);
      if (remainingModeSessions.length === 0) remainingSessions.unshift(nextSession);
      const eventsBySessionId = { ...current.eventsBySessionId };
      delete eventsBySessionId[sessionId];
      if (!eventsBySessionId[nextSession.id]) eventsBySessionId[nextSession.id] = [];
      return {
        ...current,
        activeSessionId: activeMode === "Cowork" && current.activeSessionIdsByMode.Cowork === sessionId ? nextSession.id : current.activeSessionId,
        activeSessionIdsByMode: {
          ...current.activeSessionIdsByMode,
          [activeMode]: current.activeSessionIdsByMode[activeMode] === sessionId ? nextSession.id : current.activeSessionIdsByMode[activeMode],
        },
        sessions: remainingSessions,
        eventsBySessionId,
      };
    });
  };

  const selectAdjacentSession = (offset) => {
    setSessionStore((current) => {
      const currentModeSessions = current.sessions.filter((session) => session.mode === activeMode);
      const currentIndex = currentModeSessions.findIndex((session) => session.id === current.activeSessionIdsByMode[activeMode]);
      const nextSession = currentModeSessions[currentIndex + offset];
      if (!nextSession) return current;
      return {
        ...current,
        activeSessionId: activeMode === "Cowork" ? nextSession.id : current.activeSessionId,
        activeSessionIdsByMode: { ...current.activeSessionIdsByMode, [activeMode]: nextSession.id },
      };
    });
  };

  const focusComposer = () => {
    setComposerFocusSignal((value) => value + 1);
  };

  const openChatComposer = () => {
    setActiveMode("Chat");
    setActiveView("chat");
    focusComposer();
  };

  useEffect(() => {
    const unsubscribe = typeof coworkBridge.subscribeAppUpdate === "function"
      ? coworkBridge.subscribeAppUpdate((payload = {}) => {
        setAppUpdate({
          state: String(payload.state || "idle"),
          version: String(payload.version || ""),
          percent: Number(payload.percent || 0),
        });
      })
      : undefined;
    return () => {
      if (typeof unsubscribe === "function") unsubscribe();
    };
  }, [coworkBridge]);

  useEffect(() => {
    void coworkBridge.setAutoApprove?.(autoApprove);
  }, [coworkBridge, autoApprove, bridgeState]);

  const toggleAutoApprove = () => {
    setAutoApproveState((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("cowork.autoApprove", next ? "1" : "0");
      } catch {
        /* ignore persistence errors */
      }
      return next;
    });
  };

  const openSettings = (section = "developer") => {
    const targetSection = section || "developer";
    setSettingsSection(targetSection);
    setSettingsOpen(true);
    if (targetSection === "developer" || targetSection === "connectors") void coworkBridge.listChatConnectors?.();
    if (targetSection === "providers") void coworkBridge.loadApiKeys?.();
    if (targetSection === "role") void coworkBridge.listChatMemory?.();
  };

  const seedComposerPrompt = ({ id, mode, prompt }) => {
    setActiveMode(mode);
    setActiveView("chat");
    setSuggestedPrompt({ id: `${id}-${Date.now()}`, text: prompt });
    focusComposer();
  };

  const attachArtifactToChat = (attachment) => {
    if (!attachment?.content) return;
    setActiveMode("Chat");
    setActiveView("chat");
    setSuggestedPrompt({
      id: `artifact-${attachment.artifactId || Date.now()}-${Date.now()}`,
      text: "Use the attached artifact as context.",
    });
    setSuggestedAttachments([{ ...attachment, id: `${attachment.artifactId || attachment.label}-${Date.now()}` }]);
    focusComposer();
  };

  const selectWorkspace = async () => {
    if (typeof coworkBridge.selectWorkspace !== "function") return;
    const selected = await coworkBridge.selectWorkspace();
    if (!selected) return;
    setWorkingDirectory(selected);
    await coworkBridge.setWorkspace?.(selected);
    const name = selected.split(/[\\/]/).filter(Boolean).at(-1) || selected;
    setProjects((current) => {
      if (current.some((project) => project.path === selected)) return current;
      return [{ name, path: selected }, ...current];
    });
  };

  const selectMode = (mode) => {
    setActiveMode(mode);
    setActiveView("chat");
  };

  const setActiveModeModel = (modelLabel) => {
    setModelRoutes((current) => ({ ...current, [activeMode]: modelLabel }));
  };

  const resolveApproval = (event, answer) => {
    const approvalId = event?.payload?.approvalId;
    if (!approvalId) return;
    void coworkBridge.answerApproval?.({ approvalId, answer });
    setResolvedApprovalIds((current) => new Set([...current, approvalId]));
    const approvalSessionId = sessionStore.sessions.some((session) => session.id === event.sessionId)
      ? event.sessionId
      : activeSessionId;
    const resolvedEvent = createCoworkEvent({
      id: createId(),
      sessionId: approvalSessionId,
      timestamp: new Date().toISOString(),
      type: "approval.resolved",
      status: "complete",
      payload: { approvalId, answer, mode: activeMode },
    });
    if (approvalSessionId === activeSessionId) dispatch({ type: "event.received", event: resolvedEvent });
    setSessionStore((current) => appendEventToSessionStore(current, approvalSessionId, resolvedEvent));
  };

  const stopActiveRequest = () => {
    setBusySessionIds((current) => {
      const next = new Set(current);
      next.delete(activeSessionId);
      return next;
    });
    void coworkBridge.cancelPrompt?.({ sessionId: activeSessionId, mode: activeMode });
  };

  const regenerateLastResponse = () => {
    if (activeMode !== "Chat" || runStatus === "busy") return;
    const events = sessionStore.eventsBySessionId[activeSessionId] ?? [];
    const lastAssistantIndex = events.findLastIndex((event) => event.type === "message.assistant" && event.status !== "running");
    const lastUserIndex = events.findLastIndex((event, index) => index < (lastAssistantIndex >= 0 ? lastAssistantIndex : events.length) && event.type === "message.user");
    if (lastUserIndex < 0) return;
    const userEvent = events[lastUserIndex];
    const prompt = String(userEvent.payload?.text || "").trim();
    if (!prompt) return;
    const keptEvents = events.slice(0, lastUserIndex + 1);
    const historyEvents = events.slice(0, lastUserIndex);
    setSessionStore((current) => replaceSessionEvents(current, activeSessionId, keptEvents));
    dispatch({ type: "session.hydrate", events: keptEvents });
    void submitPrompt(prompt, [], { echoUser: false, historyEvents });
  };

  const retryLastRequest = () => {
    if (activeMode === "Chat" || runStatus === "busy") return;
    const events = sessionStore.eventsBySessionId[activeSessionId] ?? [];
    const lastUserIndex = events.findLastIndex((event) => event.type === "message.user");
    if (lastUserIndex < 0) return;
    const prompt = String(events[lastUserIndex].payload?.text || "").trim();
    if (!prompt) return;
    const keptEvents = events.slice(0, lastUserIndex + 1);
    setSessionStore((current) => replaceSessionEvents(current, activeSessionId, keptEvents));
    dispatch({ type: "session.hydrate", events: keptEvents });
    void submitPrompt(prompt, [], { echoUser: false });
  };

  const editAndResendUserMessage = (event) => {
    if (activeMode !== "Chat" || runStatus === "busy") return;
    const currentText = String(event?.payload?.text || "");
    if (!currentText.trim()) return;
    const edited = window.prompt("Edit message", currentText);
    if (edited === null || !edited.trim()) return;
    const events = sessionStore.eventsBySessionId[event.sessionId] ?? [];
    const keptEvents = truncateEventsAfter(events, event.id, { includeEvent: false });
    setSessionStore((current) => replaceSessionEvents(current, event.sessionId, keptEvents));
    if (event.sessionId === activeSessionId) dispatch({ type: "session.hydrate", events: keptEvents });
    void submitPrompt(edited.trim(), [], {
      sessionId: event.sessionId,
      mode: activeMode,
      historyEvents: keptEvents,
      echoUser: true,
    });
  };

  const submitPrompt = async (prompt, attachments = [], options = {}) => {
    const normalizedAttachments = Array.isArray(attachments) ? attachments : [];
    const targetSessionId = options.sessionId || activeSessionId;
    const targetMode = options.mode || activeMode;
    const shouldEchoUser = options.echoUser !== false;
    const historyEvents = Array.isArray(options.historyEvents) ? options.historyEvents : sessionStore.eventsBySessionId[targetSessionId] ?? [];
    if (currentProject) {
      setSessionStore((current) => tagSessionProject(current, targetSessionId, currentProject));
    }
    setBusySessionIds((current) => new Set([...current, targetSessionId]));
    if (shouldEchoUser) {
      const userEvent = createCoworkEvent({
        id: createId(),
        sessionId: targetSessionId,
        timestamp: new Date().toISOString(),
        type: "message.user",
        status: "complete",
        payload: {
          text: prompt,
          mode: targetMode,
          ...(normalizedAttachments.length > 0
            ? { attachments: normalizedAttachments.map(timelineAttachmentPreview).filter(Boolean) }
            : {}),
        },
      });
      if (targetSessionId === activeSessionId) dispatch({ type: "event.received", event: userEvent });
      setSessionStore((current) => appendEventToSessionStore(current, targetSessionId, userEvent));
    }
    const busyEvent = createCoworkEvent({
      id: createId(),
      sessionId: targetSessionId,
      timestamp: new Date().toISOString(),
      type: "agent.status",
      status: "running",
      payload: { state: "busy", mode: targetMode },
    });
    if (targetSessionId === activeSessionId) dispatch({ type: "event.received", event: busyEvent });
    setSessionStore((current) => appendEventToSessionStore(current, targetSessionId, busyEvent));
    const selectedModel = normalizeModelForRequest(selectedModelLabel, coworkModelLabel, coworkModel);
    const request = { prompt, model: selectedModel, workingDirectory, sessionId: targetSessionId, mode: targetMode, effort };
    if (normalizedAttachments.length > 0) request.attachments = normalizedAttachments;
    if (targetMode === "Chat") {
      request.webSettings = chatSettings;
      request.history = chatHistoryFromEvents(historyEvents);
    }
    await coworkBridge.sendPrompt?.(request);
  };

  return (
    <div
      className={`relative grid h-full min-h-[620px] overflow-hidden bg-white text-[#2f2f2d] ${
        sidebarOpen ? "lg:grid-cols-[286px_1fr]" : "lg:grid-cols-[0_1fr]"
      }`}
    >
      <AppHeader
        canGoBack={canGoBack}
        canGoForward={canGoForward}
        modelLabel={selectedModelLabel}
        runStatus={runStatus}
        workspaceLabel={workspaceLabel}
        appUpdate={appUpdate}
        onInstallUpdate={() => coworkBridge.installUpdateNow?.()}
        onBack={() => selectAdjacentSession(1)}
        onForward={() => selectAdjacentSession(-1)}
        onSearch={openChatComposer}
        onToggleSidebar={() => setSidebarOpen((value) => !value)}
      />
      <SessionRail
        activeMode={activeMode}
        activeProjectName={workspaceLabel}
        activeSessionId={activeSessionId}
        sessions={modeSessions}
        visible={sidebarOpen}
        workspaceLabel={workspaceLabel}
        onCustomize={() =>
          seedComposerPrompt({
            id: "customize",
            mode: "Chat",
            prompt: "Suggest a cleaner UI customization for this Cowork screen",
          })
        }
        onNewSession={startNewSession}
        onNewSessionInProject={startNewSessionInProject}
        onOpenArtifacts={() => setActiveView("artifacts")}
        onOpenConnectors={() => setActiveView("connectors")}
        onOpenQuality={() => setActiveView("quality")}
        onDeleteSession={deleteSession}
        onOpenProjects={() => setActiveView("projects")}
        onOpenSettings={openSettings}
        onOpenWorkspace={() => setActiveView("workspace")}
        onPinSession={togglePinSession}
        onRenameSession={renameSession}
        onSelectMode={selectMode}
        onSelectSession={selectSession}
      />

      <section className="relative flex min-h-0 min-w-0 flex-col overflow-hidden bg-[radial-gradient(circle_at_52%_42%,rgba(217,107,74,0.035),transparent_18%),linear-gradient(#fff,#fff)] pt-[38px]">
        <main
          ref={conversationScrollRef}
          aria-label="Conversation scroll area"
          onScroll={handleConversationScroll}
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain"
        >
          {activeView === "projects" ? (
            <ProjectsView projects={projects} onChooseFolder={selectWorkspace} />
          ) : activeView === "workspace" ? (
            <WorkspacePanel bridge={coworkBridge} mode={activeMode} workspacePath={workingDirectory} />
          ) : activeView === "artifacts" ? (
            <ArtifactsPanel artifacts={chatArtifacts} onAttachArtifact={attachArtifactToChat} />
          ) : activeView === "connectors" ? (
            <ConnectorsPanel
              connectorState={chatConnectorsState}
              connectorTestResult={chatConnectorTestResult}
              connectorDiscoveryResult={chatConnectorDiscoveryResult}
              onRefresh={() => coworkBridge.listChatConnectors?.()}
              onSaveConnectors={(connectors) => coworkBridge.saveChatConnectors?.(connectors)}
              onTestConnector={(connector) => coworkBridge.testChatConnector?.(connector)}
              onDiscoverConnector={(target) => coworkBridge.discoverChatConnector?.(target)}
            />
          ) : activeView === "quality" ? (
            <QualityEvalPanel
              state={chatQualityEvalState}
              modelProviders={modelProviders}
              onRefresh={() => coworkBridge.listChatQualityEval?.()}
              onRunSnapshot={(payload) => coworkBridge.runChatQualityEval?.(payload)}
              onRunLive={(payload) => coworkBridge.runChatQuality?.(payload)}
            />
          ) : hasTimeline ? (
            <div className="min-h-full pb-4">
              <Timeline events={timeline} mode={activeMode} onEditUserMessage={editAndResendUserMessage} />
              {pendingApproval && (
                <div className="mx-auto w-full max-w-3xl px-4">
                  <ApprovalPrompt event={pendingApproval} onDecision={(answer) => resolveApproval(pendingApproval, answer)} />
                </div>
              )}
            </div>
          ) : (
            <section className="grid min-h-full place-items-center px-5 py-10">
              <div className="w-full max-w-[720px] -translate-y-3">
                <div className="mb-7 flex items-center justify-center gap-4 text-[#3b3a36]">
                  <span aria-hidden="true" className="relative hidden h-7 w-7 shrink-0 rounded-full sm:block">
                    <span className="absolute inset-0 rounded-full bg-[conic-gradient(from_0deg,transparent_0_8deg,#d96b4a_8deg_18deg,transparent_18deg_30deg)]" />
                    <span className="absolute inset-1 rounded-full bg-[conic-gradient(from_11deg,transparent_0_8deg,#d96b4a_8deg_18deg,transparent_18deg_30deg)] opacity-90" />
                  </span>
                  <h1 className="font-serif text-[clamp(34px,4vw,46px)] font-normal leading-tight text-[#3b3a36]">
                    Good afternoon, arm
                  </h1>
                </div>

                <Composer
                  disabled={runStatus === "busy" || Boolean(pendingApproval)}
                  effort={effort}
                  focusSignal={composerFocusSignal}
                  modelLabel={selectedModelLabel}
                  modelProviders={modelProviders}
                  onManageKeys={() => openSettings("providers")}
                  routeReason={activeRouteReason}
                  contextUsage={contextUsage}
                  searchCapabilities={searchCapabilities}
                  suggestedAttachments={suggestedAttachments}
                  suggestedPrompt={suggestedPrompt}
                  webSettings={chatSettings}
                  connectorState={chatConnectorsState}
                  connectorTestResult={chatConnectorTestResult}
                  connectorDiscoveryResult={chatConnectorDiscoveryResult}
                  workspaceLabel={workspaceLabel || "No project selected"}
                  onChooseWorkspace={selectWorkspace}
                  onEffortChange={setEffort}
                  onOpenMemoryManager={() => setMemoryManagerOpen(true)}
                  onOpenConnectors={() => setActiveView("connectors")}
                  onModelChange={setActiveModeModel}
                  onRefreshChatConnectors={() => coworkBridge.listChatConnectors?.()}
                  onSaveChatConnectors={(connectors) => coworkBridge.saveChatConnectors?.(connectors)}
                  onTestChatConnector={(connector) => coworkBridge.testChatConnector?.(connector)}
                  onDiscoverChatConnector={(target) => coworkBridge.discoverChatConnector?.(target)}
                  onWebSettingsChange={setChatSettings}
                  onSubmit={submitPrompt}
                />

                {bridgeState === "dev" && (
                  <div className="mx-auto flex min-h-9 w-[calc(100%-14px)] items-center gap-2 rounded-b-[10px] bg-[#f8dfdc] px-4 py-2 text-[14px] text-[#9d3e39]">
                    <span className="h-2 w-2 rounded-full bg-[#c44a42]" />
                    Renderer preview mode: Electron bridge is not connected.
                  </div>
                )}

                <div className="mt-3 flex flex-wrap justify-center gap-2">
                  {quickActions.map(({ label, icon: Icon, ...action }) => (
                    <button
                      key={label}
                      type="button"
                      onClick={() => seedComposerPrompt(action)}
                      className="flex h-[31px] items-center gap-1.5 rounded-lg border border-[#dedbd2] bg-white px-3 text-[13px] text-[#2f2f2d] shadow-[0_1px_2px_rgba(0,0,0,0.03)] transition hover:bg-[#f6f5f2]"
                    >
                      <Icon size={14} strokeWidth={2} />
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </section>
          )}
        </main>
        {activeView === "chat" && hasTimeline && (
          <div className="mx-auto w-full max-w-3xl shrink-0 px-4 pb-5">
            <ProcessingIndicator active={runStatus === "busy"} waitingForApproval={Boolean(pendingApproval)} statusText={transientStatus?.text ?? ""} />
            {activeMode !== "Chat" && runStatus !== "busy" ? <VerificationPanel evidence={completionEvidence} /> : null}
            <div className="mb-2 flex justify-end gap-2">
              {runStatus === "busy" && (
                <button
                  type="button"
                  onClick={stopActiveRequest}
                  className="h-8 rounded-lg border border-[#ded9ce] bg-white px-3 text-[12px] font-medium text-[#4f4b43] shadow-sm hover:bg-[#f7f5ef]"
                >
                  Stop
                </button>
              )}
              {canRegenerate && (
                <button
                  type="button"
                  onClick={regenerateLastResponse}
                  className="h-8 rounded-lg border border-[#ded9ce] bg-white px-3 text-[12px] font-medium text-[#4f4b43] shadow-sm hover:bg-[#f7f5ef]"
                >
                  Regenerate
                </button>
              )}
              {canRetry && (
                <button
                  type="button"
                  onClick={retryLastRequest}
                  className="h-8 rounded-lg border border-[#ded9ce] bg-white px-3 text-[12px] font-medium text-[#4f4b43] shadow-sm hover:bg-[#f7f5ef]"
                >
                  Retry
                </button>
              )}
            </div>
            <Composer
              disabled={runStatus === "busy" || Boolean(pendingApproval)}
              effort={effort}
              focusSignal={composerFocusSignal}
              modelLabel={selectedModelLabel}
              modelProviders={modelProviders}
              onManageKeys={() => openSettings("providers")}
              routeReason={activeRouteReason}
              contextUsage={contextUsage}
              searchCapabilities={searchCapabilities}
              suggestedAttachments={suggestedAttachments}
              suggestedPrompt={suggestedPrompt}
              webSettings={chatSettings}
              connectorState={chatConnectorsState}
              connectorTestResult={chatConnectorTestResult}
              connectorDiscoveryResult={chatConnectorDiscoveryResult}
              workspaceLabel={workspaceLabel || "No project selected"}
              onChooseWorkspace={selectWorkspace}
              onEffortChange={setEffort}
              onOpenMemoryManager={() => setMemoryManagerOpen(true)}
              onOpenConnectors={() => setActiveView("connectors")}
              onModelChange={setActiveModeModel}
              onRefreshChatConnectors={() => coworkBridge.listChatConnectors?.()}
              onSaveChatConnectors={(connectors) => coworkBridge.saveChatConnectors?.(connectors)}
              onTestChatConnector={(connector) => coworkBridge.testChatConnector?.(connector)}
              onDiscoverChatConnector={(target) => coworkBridge.discoverChatConnector?.(target)}
              onRunChatMcpTool={(payload) => coworkBridge.runChatMcpTool?.({ ...payload, clientSessionId: activeSessionId })}
              onWebSettingsChange={setChatSettings}
              onSubmit={submitPrompt}
            />
          </div>
        )}

        <MemoryManager
          activeMode={activeMode}
          activeSessionId={activeSessionId}
          activeProject={workingDirectory}
          entries={chatMemoryEntries}
          open={memoryManagerOpen}
          onClose={() => setMemoryManagerOpen(false)}
          onCreate={(payload) => coworkBridge.createChatMemory?.({ ...payload, mode: payload.mode || activeMode, clientSessionId: activeSessionId })}
          onDelete={(id) => coworkBridge.deleteChatMemory?.(id)}
          onSetEnabled={(id, enabled) => coworkBridge.setChatMemoryEnabled?.(id, enabled)}
          onUpdate={(id, text) => coworkBridge.updateChatMemory?.(id, text)}
        />

        <SettingsModal
          open={settingsOpen}
          initialSection={settingsSection}
          connectorState={chatConnectorsState}
          connectorTestResult={chatConnectorTestResult}
          connectorDiscoveryResult={chatConnectorDiscoveryResult}
          modelProviders={modelProviders}
          roles={chatMemoryEntries.filter((entry) => String(entry?.kind || "") === "role")}
          onCreateRole={(text) => coworkBridge.createChatMemory?.({ text, kind: "role", mode: activeMode, clientSessionId: activeSessionId })}
          onDeleteRole={(id) => coworkBridge.deleteChatMemory?.(id)}
          onSetRoleEnabled={(id, enabled) => coworkBridge.setChatMemoryEnabled?.(id, enabled)}
          onClose={() => setSettingsOpen(false)}
          onRefreshConnectors={() => coworkBridge.listChatConnectors?.()}
          onSaveConnectors={(connectors) => coworkBridge.saveChatConnectors?.(connectors)}
          onTestConnector={(connector) => coworkBridge.testChatConnector?.(connector)}
          onDiscoverConnector={(target) => coworkBridge.discoverChatConnector?.(target)}
          onSaveProviderKey={(provider, key) => coworkBridge.setProviderKey?.(provider, key)}
          onRefreshProviders={() => coworkBridge.loadApiKeys?.()}
        />

        {activeView === "chat" && hasTimeline && showJumpToLatest && (
          <button
            type="button"
            aria-label="Jump to latest"
            title="Jump to latest"
            onClick={() => scrollConversationToLatest("smooth")}
            className="absolute bottom-[176px] left-1/2 z-30 grid h-9 w-9 -translate-x-1/2 place-items-center rounded-full border border-[#dedbd2] bg-white text-[#5d5a53] shadow-[0_8px_24px_rgba(0,0,0,0.14)] transition hover:bg-[#f6f5f2]"
          >
            <ArrowDown size={17} strokeWidth={2} />
          </button>
        )}

        {activeView !== "chat" && pendingApproval && (
          <div className="absolute bottom-5 left-1/2 z-40 w-[min(760px,calc(100%-32px))] -translate-x-1/2">
            <ApprovalPrompt event={pendingApproval} onDecision={(answer) => resolveApproval(pendingApproval, answer)} />
          </div>
        )}

        <div className="pointer-events-none absolute bottom-4 right-5 hidden items-center gap-2 text-[12px] text-[#8c887f] md:flex">
          <span className="inline-flex h-[29px] items-center gap-2 rounded-full border border-[#e6e4dd] bg-white/90 px-3 shadow-[0_4px_15px_rgba(0,0,0,0.04)]">
            <span className={`h-[7px] w-[7px] rounded-full ${runStatus === "busy" ? "bg-[#d96b4a]" : "bg-[#3f8f62]"}`} />
            Server: {bridgeState === "connected" ? "Connected" : "Preview"}
          </span>
          <span className="inline-flex h-[29px] items-center gap-2 rounded-full border border-[#e6e4dd] bg-white/90 px-3 shadow-[0_4px_15px_rgba(0,0,0,0.04)]">
            <span className={`h-[7px] w-[7px] rounded-full ${modelStatusLabel === "Model unavailable" ? "bg-[#c84f3d]" : modelStatusLabel === "Model loaded" ? "bg-[#3f8f62]" : "bg-[#d9a441]"}`} />
            {modelStatusLabel}
          </span>
          <button
            type="button"
            onClick={toggleAutoApprove}
            aria-pressed={autoApprove}
            title={autoApprove ? "Auto-approving writes and commands. Click to require approval." : "Asking before writes and commands. Click to auto-approve."}
            className={`pointer-events-auto inline-flex h-[29px] items-center gap-2 rounded-full border px-3 shadow-[0_4px_15px_rgba(0,0,0,0.04)] transition ${autoApprove ? "border-[#e0b7a8] bg-[#fbeee7] text-[#a2503a]" : "border-[#e6e4dd] bg-white/90 text-[#8c887f] hover:bg-white"}`}
          >
            <span className={`h-[7px] w-[7px] rounded-full ${autoApprove ? "bg-[#d96b4a]" : "bg-[#3f8f62]"}`} />
            {autoApprove ? "Auto-approve" : "Ask before write"}
          </button>
        </div>
      </section>
    </div>
  );
}
