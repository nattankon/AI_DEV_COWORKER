import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createSessionStorageAdapter } from "../adapters/sessionStorage";
import CoworkApp from "../CoworkApp";

function createMemoryStorage(initialValue) {
  const store = new Map(initialValue ? [["api-blender.cowork.sessions.v3", initialValue]] : []);
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

describe("CoworkApp", () => {
  it("hydrates a ready update discovered during startup and installs only after the user clicks", async () => {
    const installUpdateNow = vi.fn();
    const getAppUpdateState = vi.fn().mockResolvedValue({
      state: "ready",
      version: "0.1.18",
      percent: 100,
    });
    const bridge = {
      getAppUpdateState,
      installUpdateNow,
      subscribeAppUpdate: () => () => {},
    };

    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={bridge}
      />,
    );

    const button = await screen.findByRole("button", { name: "Install update v0.1.18 and restart" });
    expect(getAppUpdateState).toHaveBeenCalledOnce();
    fireEvent.click(button);
    expect(installUpdateNow).toHaveBeenCalledOnce();
  });

  it("starts with the navigation drawer closed on narrow screens", () => {
    const originalWidth = window.innerWidth;
    Object.defineProperty(window, "innerWidth", { value: 390, configurable: true });
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ sendPrompt: vi.fn(), subscribe: () => () => {} }}
      />,
    );

    expect(screen.getByLabelText("Session sidebar")).toHaveAttribute("data-state", "closed");
    expect(screen.getByRole("heading", { name: /Good afternoon/i }).previousElementSibling).toHaveClass("hidden", "sm:block");
    Object.defineProperty(window, "innerWidth", { value: originalWidth, configurable: true });
  });

  afterEach(() => {
    delete window.electronAPI;
  });

  it("renders the Claude-like chat-first workspace shell", () => {
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
      />,
    );

    expect(screen.getByRole("button", { name: /^mode chat$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^mode cowork$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^mode code$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new chat/i })).toBeInTheDocument();
    expect(screen.getByText("Recents")).toBeInTheDocument();
    expect(screen.getByText(/Good afternoon/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText("How can I help you today?")).toBeInTheDocument();
    expect(screen.getByText(/Ask before write/i)).toBeInTheDocument();
    expect(screen.getByText(/Server:/i)).toBeInTheDocument();
    // Don't pin the exact release number — it changes every version bump.
    expect(screen.getByText(/^v\d+\.\d+\.\d+$/)).toBeInTheDocument();
  });

  it("restores the selected session project when switching modes or sessions", async () => {
    const storage = createMemoryStorage();
    const sessionStorageAdapter = createSessionStorageAdapter(storage);
    sessionStorageAdapter.save({
      activeSessionIdsByMode: { Chat: "chat-1", Cowork: "cowork-other", Code: "code-1" },
      sessions: [
        { id: "chat-1", mode: "Chat", title: "General chat" },
        { id: "cowork-other", mode: "Cowork", title: "Other task", project: { path: "C:\\Work\\other", name: "other" } },
        { id: "cowork-scilp", mode: "Cowork", title: "Roblox task", project: { path: "C:\\Work\\scilp", name: "scilp" } },
        { id: "code-1", mode: "Code", title: "Code task" },
      ],
      eventsBySessionId: { "chat-1": [], "cowork-other": [], "cowork-scilp": [], "code-1": [] },
    });
    const setWorkspace = vi.fn();

    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ setWorkspace, subscribe: () => () => {} }}
        sessionStorageAdapter={sessionStorageAdapter}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /^mode cowork$/i }));

    await waitFor(() => expect(setWorkspace).toHaveBeenCalledWith("C:\\Work\\other"));
    fireEvent.click(screen.getByRole("button", { name: "Roblox task" }));
    await waitFor(() => expect(setWorkspace).toHaveBeenCalledWith("C:\\Work\\scilp"));
    expect(screen.getAllByText("scilp").length).toBeGreaterThanOrEqual(2);
  });

  it("does not restore an expired approval prompt after the app reopens", async () => {
    const sessionStorageAdapter = createSessionStorageAdapter(createMemoryStorage());
    sessionStorageAdapter.save({
      activeSessionIdsByMode: { Chat: "chat-1", Cowork: "cowork-1", Code: "code-1" },
      sessions: [
        { id: "chat-1", mode: "Chat", title: "Chat task" },
        { id: "cowork-1", mode: "Cowork", title: "Write task" },
        { id: "code-1", mode: "Code", title: "Code task" },
      ],
      eventsBySessionId: {
        "cowork-1": [
          {
            id: "expired-approval",
            sessionId: "cowork-1",
            timestamp: "2026-08-15T00:00:00.000Z",
            type: "approval.requested",
            status: "pending",
            payload: {
              approvalId: "approval-from-previous-process",
              approvalKind: "write_file",
              title: "Approve file write",
              question: "Approve writing speed_game.py?",
              mode: "Cowork",
              proposal: {},
            },
          },
        ],
      },
    });

    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ subscribe: () => () => {} }}
        sessionStorageAdapter={sessionStorageAdapter}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /^mode cowork$/i }));

    await waitFor(() => expect(screen.queryByLabelText("Approval prompt")).not.toBeInTheDocument());
    expect(screen.queryByText("Approve file write")).not.toBeInTheDocument();
  });

  it("opens the Chat quality evaluation panel from the sidebar", async () => {
    const listChatQualityEval = vi.fn();
    let qualityListener = null;
    const bridge = {
      fetchModels: vi.fn(),
      loadApiKeys: vi.fn(),
      listChatConnectors: vi.fn(),
      listChatQualityEval,
      subscribeModels: () => () => {},
      subscribeApiKeys: () => () => {},
      subscribeChatQualityEval: (listener) => {
        qualityListener = listener;
        return () => {};
      },
      subscribe: () => () => {},
    };
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={bridge}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Quality" }));
    qualityListener?.({ count: 1, cases: [{ category: "general", prompt: "Explain local-first AI", checks: ["answers directly"] }] });

    await waitFor(() => expect(listChatQualityEval).toHaveBeenCalled());
    expect(screen.getByRole("heading", { name: "Evaluation snapshot" })).toBeInTheDocument();
    expect(screen.getByText("Explain local-first AI")).toBeInTheDocument();
  });

  it("opens the generic MCP connectors panel from the sidebar", async () => {
    const listChatConnectors = vi.fn();
    let connectorsListener = null;
    const bridge = {
      fetchModels: vi.fn(),
      loadApiKeys: vi.fn(),
      listChatConnectors,
      subscribeModels: () => () => {},
      subscribeApiKeys: () => () => {},
      subscribeChatConnectors: (listener) => {
        connectorsListener = listener;
        return () => {};
      },
      subscribe: () => () => {},
    };
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={bridge}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Connectors" }));
    connectorsListener?.({ enabled: true, mcp_sdk_available: true, connectors: [], statuses: [] });

    await waitFor(() => expect(listChatConnectors).toHaveBeenCalled());
    expect(screen.getByRole("heading", { name: "MCP connectors" })).toBeInTheDocument();
    expect(screen.getByText(/Add and manage MCP servers before Chat can use them/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add custom connector" })).toBeInTheDocument();
  });

  it("opens Developer settings from the bottom-left account menu with shared MCP connectors", async () => {
    const listChatConnectors = vi.fn();
    let connectorsListener = null;
    const bridge = {
      fetchModels: vi.fn(),
      loadApiKeys: vi.fn(),
      listChatConnectors,
      subscribeModels: () => () => {},
      subscribeApiKeys: () => () => {},
      subscribeChatConnectors: (listener) => {
        connectorsListener = listener;
        return () => {};
      },
      subscribe: () => () => {},
    };
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={bridge}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Account and settings" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Settings" }));
    connectorsListener?.({
      enabled: true,
      mcp_sdk_available: true,
      connectors: [{ name: "robloxstudio-mcp", transport: "stdio", command: "cmd /c npx -y robloxstudio-mcp@latest", enabled: true }],
      statuses: [{ name: "robloxstudio-mcp", status: "connected", tool_count: 3, read_only_tool_count: 2, write_tool_count: 1 }],
    });

    await waitFor(() => expect(listChatConnectors).toHaveBeenCalled());
    expect(screen.getByRole("dialog", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Developer" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Local MCP servers")).toBeInTheDocument();
    expect(screen.getAllByText("robloxstudio-mcp").length).toBeGreaterThan(0);
  });

  it("connects visible titlebar controls to the Electron window bridge", () => {
    const electronAPI = {
      minimize: vi.fn(),
      maximize: vi.fn(),
      close: vi.fn(),
    };
    Object.defineProperty(window, "electronAPI", {
      value: electronAPI,
      configurable: true,
    });

    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ subscribe: () => () => {} }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Minimize" }));
    fireEvent.click(screen.getByRole("button", { name: "Maximize" }));
    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(electronAPI.minimize).toHaveBeenCalledTimes(1);
    expect(electronAPI.maximize).toHaveBeenCalledTimes(1);
    expect(electronAPI.close).toHaveBeenCalledTimes(1);
  });

  it("makes the first-screen navigation controls interactive", () => {
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ subscribe: () => () => {} }}
      />,
    );

    expect(screen.getByLabelText("Session sidebar")).toHaveAttribute("data-state", "open");
    expect(screen.getByLabelText("Session sidebar")).toHaveClass("fixed");
    expect(screen.getByRole("button", { name: "Toggle sidebar" }).parentElement).not.toHaveClass("hidden");
    fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }));
    expect(screen.getByLabelText("Session sidebar")).toHaveAttribute("data-state", "closed");

    fireEvent.click(screen.getByRole("button", { name: /^mode code$/i }));
    expect(screen.getByRole("button", { name: /^mode code$/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /^mode chat$/i })).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(screen.getByPlaceholderText("How can I help you today?")).toHaveFocus();

    fireEvent.click(screen.getByRole("button", { name: "Write" }));
    expect(screen.getByPlaceholderText("How can I help you today?")).toHaveValue("Draft release notes for this project");
  });

  it("renders approval prompts and sends allow or deny decisions to the bridge", async () => {
    let eventListener;
    const answerApproval = vi.fn();
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
        bridge={{
          answerApproval,
          subscribe: (_sessionId, listener) => {
            eventListener = listener;
            return () => {};
          },
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /^mode cowork$/i }));
    eventListener({
      id: "approval-event",
      sessionId: "session",
      timestamp: "2026-06-13T00:00:00.000Z",
      type: "approval.requested",
      status: "pending",
      payload: {
        approvalId: "approval-1",
        approvalKind: "write_file",
        title: "Approve file write",
        question: "Approve writing notes.txt?",
        mode: "Cowork",
        proposal: {
          relative_path: "notes.txt",
          diff: "--- a/notes.txt\n+++ b/notes.txt\n@@\n-old\n+new\n",
        },
      },
    });

    expect(await screen.findByText("Approve file write")).toBeInTheDocument();
    expect(screen.getByLabelText("Conversation scroll area")).toContainElement(screen.getByLabelText("Approval prompt"));
    expect(screen.getByText("Cowork is waiting for your decision.")).toBeInTheDocument();
    expect(screen.getByText("notes.txt")).toBeInTheDocument();
    expect(screen.getByText(/\+new/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    expect(answerApproval).toHaveBeenCalledWith({ approvalId: "approval-1", answer: "allow" });
    expect(screen.getByText(/Approved approval-1/i)).toBeInTheDocument();
  });

  it("renders Chat approval prompts and disables the composer while waiting", async () => {
    let eventListener;
    const answerApproval = vi.fn();
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
        bridge={{
          answerApproval,
          subscribe: (_sessionId, listener) => {
            eventListener = listener;
            return () => {};
          },
        }}
      />,
    );

    eventListener({
      id: "chat-approval-event",
      sessionId: "session",
      timestamp: "2026-07-02T00:00:00.000Z",
      type: "approval.requested",
      status: "pending",
      payload: {
        approvalId: "approval-chat-mcp",
        approvalKind: "mcp_tool_call",
        title: "Approve MCP tool",
        question: "Approve MCP tool roblox/list_instances?",
        mode: "Chat",
        proposal: {
          risk_level: "write",
          risk_summary: "Calls an external MCP tool.",
          default_decision: "deny",
          subject: "roblox/list_instances",
          details: {
            server: "roblox",
            tool: "list_instances",
            arguments: { scope: "Workspace" },
          },
        },
      },
    });

    expect(await screen.findByText("Approve MCP tool")).toBeInTheDocument();
    expect(screen.getByText("roblox/list_instances")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("How can I help you today?")).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Deny" }));

    expect(answerApproval).toHaveBeenCalledWith({ approvalId: "approval-chat-mcp", answer: "deny" });
  });

  it("offers a jump-to-latest control after the user scrolls away from the bottom", async () => {
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ subscribe: () => () => {} }}
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
      />,
    );

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "Create scrollable history" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });

    const scrollArea = screen.getByLabelText("Conversation scroll area");
    expect(scrollArea.parentElement).toHaveClass("min-h-0", "overflow-hidden");
    Object.defineProperties(scrollArea, {
      clientHeight: { configurable: true, value: 400 },
      scrollHeight: { configurable: true, value: 1200 },
      scrollTop: { configurable: true, writable: true, value: 0 },
    });
    scrollArea.scrollTo = vi.fn();
    fireEvent.scroll(scrollArea);

    const jumpButton = await screen.findByRole("button", { name: "Jump to latest" });
    fireEvent.click(jumpButton);

    expect(scrollArea.scrollTo).toHaveBeenCalledWith({ top: 1200, behavior: "smooth" });
  });

  it("stops the processing state and shows a backend failure", async () => {
    let listener;
    let sentSessionId;
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{
          sendPrompt: vi.fn(({ sessionId }) => {
            sentSessionId = sessionId;
          }),
          subscribe(_sessionId, nextListener) {
            listener = nextListener;
            return () => {};
          },
        }}
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
      />,
    );

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "Hello" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });
    expect(await screen.findByText(/Working for 0s .*Thinking through your request/)).toBeInTheDocument();

    listener({
      id: "failure-1",
      sessionId: sentSessionId,
      timestamp: "2026-06-13T03:00:00.000Z",
      type: "message.system",
      status: "failed",
      payload: { text: "Cowork could not complete the request: Local AI request timed out." },
    });

    expect(await screen.findByText(/Local AI request timed out/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/Working for/)).not.toBeInTheDocument());
    expect(textbox).not.toBeDisabled();
  });

  it("opens shell menus, projects, model choices, skills, and recent item actions", async () => {
    const selectWorkspace = vi.fn().mockResolvedValue("C:\\Work\\Demo");
    const storage = createMemoryStorage(
      JSON.stringify({
        schemaVersion: 3,
        savedAt: "2026-06-13T00:00:00.000Z",
        state: {
          activeSessionId: "session-a",
          sessions: [
            { id: "session-a", title: "Inspect repo", createdAt: "2026-06-13T00:00:00.000Z", updatedAt: "2026-06-13T00:00:00.000Z", eventCount: 0 },
          ],
          eventsBySessionId: { "session-a": [] },
        },
      }),
    );

    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ selectWorkspace, subscribe: () => () => {} }}
        sessionStorageAdapter={createSessionStorageAdapter(storage)}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Main menu" }));
    expect(screen.getByRole("menuitem", { name: "File" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Help" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Attach context" }));
    expect(screen.getByRole("menuitem", { name: /Add files or photos/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "Web search" }));
    expect(screen.getByRole("menuitem", { name: "Web search" })).toBeInTheDocument();

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "/" } });
    expect(screen.getByRole("dialog", { name: "Skills" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Develop CI/CD pipelines" }));
    expect(textbox).toHaveValue("Develop CI/CD pipelines");

    fireEvent.click(screen.getByRole("button", { name: "Model and effort" }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: "qwen2.5-7b-instruct" }));
    expect(screen.getByRole("button", { name: "Model and effort" })).toHaveTextContent("qwen2.5-7b-instruct");

    fireEvent.click(screen.getByRole("button", { name: "Projects" }));
    expect(screen.getByRole("heading", { name: "Projects" })).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("Search projects..."), { target: { value: "Demo" } });
    fireEvent.click(screen.getByRole("button", { name: "Choose a different folder" }));
    await waitFor(() => expect(selectWorkspace).toHaveBeenCalledTimes(1));
    expect((await screen.findAllByText("Demo")).length).toBeGreaterThanOrEqual(2);

    fireEvent.click(screen.getByRole("button", { name: /^mode chat$/i }));
    fireEvent.click(screen.getByRole("button", { name: "Session actions for Inspect repo" }));
    expect(screen.getByRole("menuitem", { name: "Pin" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("menuitem", { name: "Rename" }));
    fireEvent.change(screen.getByLabelText("Rename session"), { target: { value: "Renamed session" } });
    fireEvent.keyDown(screen.getByLabelText("Rename session"), { key: "Enter" });
    expect(screen.getByRole("button", { name: /^Renamed session$/i })).toBeInTheDocument();
  });

  it("shows whether the selected model or a fallback model is available", async () => {
    let modelsListener;
    const fetchModels = vi.fn();
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{
          fetchModels,
          subscribe: () => () => {},
          subscribeModels(listener) {
            modelsListener = listener;
            return () => {};
          },
        }}
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
      />,
    );

    expect(fetchModels).toHaveBeenCalled();
    modelsListener(["local:qwen2.5-7b-instruct"]);

    expect(await screen.findByText("Fallback ready")).toBeInTheDocument();
  });

  it("shows provider model catalog groups in the model menu", async () => {
    let modelsListener;
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{
          fetchModels: vi.fn(),
          subscribe: () => () => {},
          subscribeModels(listener) {
            modelsListener = listener;
            return () => {};
          },
        }}
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
      />,
    );

    modelsListener(
      ["openai:gpt-5.5", "gemini:gemini-3.1-flash-lite"],
      {
        providers: [
          {
            id: "openai",
            label: "OpenAI",
            configured: true,
            models: [{ id: "openai:gpt-5.5", label: "GPT-5.5", tier: "main", billing: "paid" }],
          },
          {
            id: "zai",
            label: "Z.ai",
            configured: true,
            models: [{ id: "zai:glm-4.7-flash", label: "GLM-4.7-Flash", tier: "free", billing: "free" }],
          },
          {
            id: "deepseek",
            label: "DeepSeek",
            configured: true,
            models: [{ id: "deepseek:deepseek-v4-flash", label: "DeepSeek V4 Flash", tier: "fast", badge: "Fast / Coding" }],
          },
        ],
      },
    );

    fireEvent.click(screen.getByRole("button", { name: "Model and effort" }));

    expect(screen.getByText("OpenAI")).toBeInTheDocument();
    expect(screen.queryByText("GPT-5.5")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("menuitem", { name: /OpenAI ready/i }));
    expect(screen.getByText("GPT-5.5")).toBeInTheDocument();
    expect(screen.getByText("main")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("menuitem", { name: "OpenAI" }));

    expect(screen.getByText("Z.ai")).toBeInTheDocument();
    expect(screen.getByText("DeepSeek")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("menuitem", { name: /DeepSeek ready/i }));
    expect(screen.getByText("DeepSeek V4 Flash")).toBeInTheDocument();
    expect(screen.getByText("Fast / Coding")).toBeInTheDocument();
  });

  it("uses selected model metadata for the composer context indicator", async () => {
    let modelsListener;
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="zai:glm-4.5-flash"
        coworkModelLabel="zai:glm-4.5-flash"
        coworkUiState="idle"
        bridge={{
          fetchModels: vi.fn(),
          subscribe: () => () => {},
          subscribeModels(listener) {
            modelsListener = listener;
            return () => {};
          },
        }}
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
      />,
    );

    modelsListener(
      ["zai:glm-4.5-flash"],
      {
        providers: [
          {
            id: "zai",
            label: "Z.ai",
            configured: true,
            models: [{ id: "zai:glm-4.5-flash", label: "GLM-4.5-Flash", context_window_tokens: 131072 }],
          },
        ],
      },
    );

    expect(await screen.findByLabelText("Context usage")).toHaveTextContent("0%");
    expect(screen.getByLabelText("Context usage")).toHaveAttribute("title", expect.stringContaining("0 / 131k tokens used"));
  });

  it("restores and switches between saved sessions", async () => {
    const storage = createMemoryStorage(
      JSON.stringify({
        schemaVersion: 3,
        savedAt: "2026-06-12T00:00:00.000Z",
        state: {
          activeSessionId: "session-a",
          sessions: [
            { id: "session-a", title: "Inspect repo", createdAt: "2026-06-12T00:00:00.000Z", updatedAt: "2026-06-12T00:00:00.000Z", eventCount: 1 },
            { id: "session-b", title: "Review diff", createdAt: "2026-06-12T00:10:00.000Z", updatedAt: "2026-06-12T00:10:00.000Z", eventCount: 1 },
          ],
          eventsBySessionId: {
            "session-a": [{ id: "event-a", sessionId: "session-a", timestamp: "2026-06-12T00:00:00.000Z", type: "message.user", status: "complete", payload: { text: "Inspect repo" } }],
            "session-b": [{ id: "event-b", sessionId: "session-b", timestamp: "2026-06-12T00:10:00.000Z", type: "message.user", status: "complete", payload: { text: "Review diff" } }],
          },
        },
      }),
    );
    const sessionStorageAdapter = createSessionStorageAdapter(storage);

    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ subscribe: () => () => {} }}
        sessionStorageAdapter={sessionStorageAdapter}
      />,
    );

    expect(await screen.findByText("Inspect repo", { selector: ".whitespace-pre-wrap" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^review diff$/i }));

    await waitFor(() => {
      expect(screen.getByText("Review diff", { selector: ".whitespace-pre-wrap" })).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /^inspect repo$/i })).toBeInTheDocument();
  });

  it("treats slash commands as local actions and never sends them to the model", async () => {
    const sendPrompt = vi.fn();
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ sendPrompt, subscribe: () => () => {} }}
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
      />,
    );

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "/new" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });

    expect(sendPrompt).not.toHaveBeenCalled();
    // A normal message still sends.
    fireEvent.change(textbox, { target: { value: "hello there" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });
    expect(sendPrompt).toHaveBeenCalledWith(expect.objectContaining({ prompt: "hello there" }));
  });

  it("sends prompts through the injected bridge", async () => {
    const sendPrompt = vi.fn();
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ sendPrompt, subscribe: () => () => {} }}
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
      />,
    );

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "Map this repo" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });

    expect(sendPrompt).toHaveBeenCalledWith({
      prompt: "Map this repo",
      model: "local:qwen/qwen3.5-9b",
      workingDirectory: "",
      sessionId: expect.any(String),
      mode: "Chat",
      effort: "Medium",
      history: [],
      webSettings: { webMode: "auto", searchProvider: "auto", artifacts: "on", codeExecution: "off", mcp: "off" },
      visionSettings: { visionAssist: "off", visionModel: "zai:glm-4.6v-flashx" },
    });
    expect(screen.getByText("Map this repo", { selector: ".whitespace-pre-wrap" })).toBeInTheDocument();
    expect(screen.getByText("working")).toBeInTheDocument();
    expect(await screen.findByText(/Working for 0s .*Thinking through your request/)).toBeInTheDocument();
  });

  it("stops an active Chat request through the bridge", async () => {
    const sendPrompt = vi.fn();
    const cancelPrompt = vi.fn();
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ sendPrompt, cancelPrompt, subscribe: () => () => {} }}
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
      />,
    );

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "slow answer" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });

    fireEvent.click(await screen.findByRole("button", { name: "Stop" }));

    expect(cancelPrompt).toHaveBeenCalledWith({ sessionId: expect.any(String), mode: "Chat" });
    await waitFor(() => expect(screen.queryByText(/Working for/)).not.toBeInTheDocument());
    expect(textbox).not.toBeDisabled();
  });

  it("denies a live approval before stopping its request", async () => {
    let eventListener;
    const sendPrompt = vi.fn();
    const answerApproval = vi.fn();
    const cancelPrompt = vi.fn();
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{
          sendPrompt,
          answerApproval,
          cancelPrompt,
          subscribe(_sessionId, listener) {
            eventListener = listener;
            return () => {};
          },
        }}
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
      />,
    );

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "wait for approval" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });
    const sessionId = sendPrompt.mock.calls[0][0].sessionId;
    eventListener({
      id: "stop-approval",
      sessionId,
      timestamp: "2026-08-15T00:00:00.000Z",
      type: "approval.requested",
      status: "pending",
      payload: {
        approvalId: "approval-stop",
        approvalKind: "write_file",
        title: "Approve file write",
        question: "Approve writing speed_game.py?",
        mode: "Chat",
        proposal: {},
      },
    });

    expect(await screen.findByLabelText("Approval prompt")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));

    expect(answerApproval).toHaveBeenCalledWith({ approvalId: "approval-stop", answer: "deny" });
    expect(cancelPrompt).toHaveBeenCalledWith({ sessionId, mode: "Chat" });
  });

  it("regenerates the last Chat answer with trimmed history", async () => {
    let listener;
    const sendPrompt = vi.fn();
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{
          sendPrompt,
          subscribe(_sessionId, nextListener) {
            listener = nextListener;
            return () => {};
          },
        }}
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
      />,
    );

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "try again" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });
    const sessionId = sendPrompt.mock.calls[0][0].sessionId;
    listener({
      id: "assistant-1",
      sessionId,
      timestamp: new Date().toISOString(),
      type: "message.assistant",
      status: "complete",
      payload: { text: "first answer", mode: "Chat" },
    });

    fireEvent.click(await screen.findByRole("button", { name: "Regenerate" }));

    expect(sendPrompt).toHaveBeenLastCalledWith(expect.objectContaining({
      prompt: "try again",
      sessionId,
      mode: "Chat",
      history: [],
    }));
  });

  it("retries the last Cowork request without echoing a duplicate user message", async () => {
    let listener;
    const sendPrompt = vi.fn();
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{
          sendPrompt,
          subscribe(_sessionId, nextListener) {
            listener = nextListener;
            return () => {};
          },
        }}
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Mode Cowork" }));

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "Refactor this module" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });

    expect(sendPrompt).toHaveBeenCalledWith(expect.objectContaining({ prompt: "Refactor this module", mode: "Cowork" }));
    const sessionId = sendPrompt.mock.calls[0][0].sessionId;
    listener({
      id: "cowork-assistant-1",
      sessionId,
      timestamp: new Date().toISOString(),
      type: "message.assistant",
      status: "complete",
      payload: { text: "done", mode: "Cowork" },
    });

    fireEvent.click(await screen.findByRole("button", { name: "Retry" }));

    expect(sendPrompt).toHaveBeenCalledTimes(2);
    expect(sendPrompt).toHaveBeenLastCalledWith(expect.objectContaining({ prompt: "Refactor this module", mode: "Cowork" }));
    expect(screen.getAllByText("Refactor this module", { selector: ".whitespace-pre-wrap" })).toHaveLength(1);
  });

  it("does not restore streamed Cowork fragments or verification payloads after switching sessions", async () => {
    let listener;
    const sendPrompt = vi.fn();
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{
          sendPrompt,
          subscribe(_sessionId, nextListener) {
            listener = nextListener;
            return () => {};
          },
        }}
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /^mode cowork$/i }));
    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "Say hello" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });
    const sessionId = sendPrompt.mock.calls[0][0].sessionId;

    listener({
      id: `stream-${sessionId}-Cowork`,
      sessionId,
      timestamp: "2026-08-14T05:00:00.000Z",
      type: "message.assistant",
      status: "running",
      payload: { text: "A", role: "AI", mode: "Cowork", streaming: true },
    });
    listener({
      id: `stream-${sessionId}-Cowork`,
      sessionId,
      timestamp: "2026-08-14T05:00:01.000Z",
      type: "message.assistant",
      status: "running",
      payload: { text: "B", role: "AI", mode: "Cowork", streaming: true },
    });
    listener({
      id: "verification-evidence",
      sessionId,
      timestamp: "2026-08-14T05:00:02.000Z",
      type: "verification.finished",
      status: "complete",
      payload: { mode: "Cowork", writesPerformed: false, verificationObserved: false, verificationPassed: false },
    });
    listener({
      id: "cowork-final-answer",
      sessionId,
      timestamp: "2026-08-14T05:00:03.000Z",
      type: "message.assistant",
      status: "complete",
      payload: { text: "Final answer", role: "AI", mode: "Cowork" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^mode chat$/i }));
    fireEvent.click(screen.getByRole("button", { name: /^mode cowork$/i }));

    expect(await screen.findByText("Final answer", { selector: ".whitespace-pre-wrap" })).toBeInTheDocument();
    expect(screen.queryByText("A", { exact: true })).not.toBeInTheDocument();
    expect(screen.queryByText("B", { exact: true })).not.toBeInTheDocument();
    expect(screen.queryByText("verification.finished", { exact: true })).not.toBeInTheDocument();
  });

  it("edits a prior Chat user message, truncates later messages, and resends", async () => {
    const originalPrompt = window.prompt;
    window.prompt = vi.fn(() => "edited question");
    const sendPrompt = vi.fn();
    let listener;
    try {
      render(
        <CoworkApp
          bridgeState="connected"
          coworkModel="local:qwen/qwen3.5-9b"
          coworkModelLabel="qwen/qwen3.5-9b"
          coworkUiState="idle"
          bridge={{
            sendPrompt,
            subscribe(_sessionId, nextListener) {
              listener = nextListener;
              return () => {};
            },
          }}
          sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
        />,
      );

      const textbox = screen.getByPlaceholderText("How can I help you today?");
      fireEvent.change(textbox, { target: { value: "original question" } });
      fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });
      const sessionId = sendPrompt.mock.calls[0][0].sessionId;
      listener({
        id: "assistant-edit-1",
        sessionId,
        timestamp: new Date().toISOString(),
        type: "message.assistant",
        status: "complete",
        payload: { text: "old answer", mode: "Chat" },
      });
      fireEvent.click(await screen.findByRole("button", { name: "Edit" }));

      expect(sendPrompt).toHaveBeenLastCalledWith(expect.objectContaining({
        prompt: "edited question",
        mode: "Chat",
        history: [],
      }));
      expect(screen.queryByText("original question")).not.toBeInTheDocument();
    } finally {
      window.prompt = originalPrompt;
    }
  });

  it("sends explicitly selected Chat file context without changing workspace access", async () => {
    const sendPrompt = vi.fn();
    const note = new File(["chat-only attached context"], "chat-note.txt", { type: "text/plain" });
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ sendPrompt, subscribe: () => () => {} }}
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Attach context" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Add files or photos/i }));
    fireEvent.change(screen.getByLabelText("Attach files"), { target: { files: [note] } });
    expect(await screen.findByText("chat-note.txt")).toBeInTheDocument();

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "Use this attached context" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });

    expect(sendPrompt).toHaveBeenCalledWith({
      prompt: "Use this attached context",
      model: "local:qwen/qwen3.5-9b",
      workingDirectory: "",
      sessionId: expect.any(String),
      mode: "Chat",
      effort: "Medium",
      history: [],
      attachments: [
        expect.objectContaining({
          label: "chat-note.txt",
          content: "chat-only attached context",
          source: "user-file",
          kind: "text",
          mime: "text/plain",
          size: 26,
        }),
      ],
      webSettings: { webMode: "auto", searchProvider: "auto", artifacts: "on", codeExecution: "off", mcp: "off" },
      visionSettings: { visionAssist: "off", visionModel: "zai:glm-4.6v-flashx" },
    });
  });

  it("keeps pasted Chat image thumbnails visible in the local timeline", async () => {
    const sendPrompt = vi.fn();
    const image = new File(["screen pixels"], "screen.png", { type: "image/png" });
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ sendPrompt, subscribe: () => () => {} }}
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
      />,
    );

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.paste(textbox, {
      clipboardData: {
        items: [{ kind: "file", type: "image/png", getAsFile: () => image }],
      },
    });
    expect(await screen.findByRole("img", { name: "screen.png preview" })).toBeInTheDocument();

    fireEvent.change(textbox, { target: { value: "อธิบายภาพนี้" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });

    expect(screen.getByRole("img", { name: "screen.png attachment" })).toBeInTheDocument();
    expect(sendPrompt).toHaveBeenCalledWith(expect.objectContaining({
      prompt: "อธิบายภาพนี้",
      attachments: [
        expect.objectContaining({
          label: "screen.png",
          source: "user-paste",
          kind: "image",
          dataUrl: expect.stringMatching(/^data:image\/png;base64,/),
        }),
      ],
    }));
  });

  it("keeps model choices scoped to each mode", async () => {
    const sendPrompt = vi.fn();
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ sendPrompt, subscribe: () => () => {} }}
        sessionStorageAdapter={createSessionStorageAdapter(createMemoryStorage())}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Model and effort" }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: "qwen2.5-7b-instruct" }));

    const chatTextbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(chatTextbox, { target: { value: "chat route" } });
    fireEvent.keyDown(chatTextbox, { key: "Enter", ctrlKey: true });

    expect(sendPrompt).toHaveBeenLastCalledWith({
      prompt: "chat route",
      model: "local:qwen2.5-7b-instruct",
      workingDirectory: "",
      sessionId: expect.any(String),
      mode: "Chat",
      effort: "Medium",
      history: [],
      webSettings: { webMode: "auto", searchProvider: "auto", artifacts: "on", codeExecution: "off", mcp: "off" },
      visionSettings: { visionAssist: "off", visionModel: "zai:glm-4.6v-flashx" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^mode cowork$/i }));
    expect(screen.getByRole("button", { name: "Model and effort" })).toHaveTextContent("qwen/qwen3.5-9b");

    const coworkTextbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(coworkTextbox, { target: { value: "cowork route" } });
    fireEvent.keyDown(coworkTextbox, { key: "Enter", ctrlKey: true });

    expect(sendPrompt).toHaveBeenLastCalledWith({
      prompt: "cowork route",
      model: "local:qwen/qwen3.5-9b",
      workingDirectory: "",
      sessionId: expect.any(String),
      mode: "Cowork",
      effort: "Medium",
      visionSettings: { visionAssist: "off", visionModel: "zai:glm-4.6v-flashx" },
    });
  });

  it("persists model routes across reloads and sends the selected effort", async () => {
    const sendPrompt = vi.fn();
    const storage = createMemoryStorage();
    const sessionStorageAdapter = createSessionStorageAdapter(storage);
    const { unmount } = render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ sendPrompt, subscribe: () => () => {} }}
        sessionStorageAdapter={sessionStorageAdapter}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Model and effort" }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: "qwen2.5-7b-instruct" }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: "Effort High" }));

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "route with effort" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });

    expect(sendPrompt).toHaveBeenLastCalledWith({
      prompt: "route with effort",
      model: "local:qwen2.5-7b-instruct",
      workingDirectory: "",
      sessionId: expect.any(String),
      mode: "Chat",
      effort: "High",
      history: [],
      webSettings: { webMode: "auto", searchProvider: "auto", artifacts: "on", codeExecution: "off", mcp: "off" },
      visionSettings: { visionAssist: "off", visionModel: "zai:glm-4.6v-flashx" },
    });

    unmount();
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{ sendPrompt: vi.fn(), subscribe: () => () => {} }}
        sessionStorageAdapter={createSessionStorageAdapter(storage)}
      />,
    );

    expect(screen.getByRole("button", { name: "Model and effort" })).toHaveTextContent("qwen2.5-7b-instruct");
  });

  it("keeps Chat, Cowork, and Code conversations separate and ignores echoed user logs", async () => {
    const handlers = {};
    const sendPrompt = vi.fn();
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{
          sendPrompt,
          subscribe(_sessionId, listener) {
            handlers.current = listener;
            return () => {};
          },
        }}
      />,
    );

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "chat only" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });
    expect(await screen.findByText("chat only", { selector: ".whitespace-pre-wrap" })).toBeInTheDocument();
    handlers.current({ id: "echo-user", sessionId: "server", timestamp: "2026-06-13T00:00:00.000Z", type: "message.user", status: "complete", payload: { text: "chat only" } });
    expect(screen.getAllByText("chat only", { selector: ".whitespace-pre-wrap" })).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: /^mode cowork$/i }));
    expect(screen.queryByText("chat only", { selector: ".whitespace-pre-wrap" })).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("How can I help you today?")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("How can I help you today?"), { target: { value: "cowork only" } });
    fireEvent.keyDown(screen.getByPlaceholderText("How can I help you today?"), { key: "Enter", ctrlKey: true });
    expect(screen.getByText("cowork only", { selector: ".whitespace-pre-wrap" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^mode code$/i }));
    expect(screen.queryByText("cowork only", { selector: ".whitespace-pre-wrap" })).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("How can I help you today?")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^mode chat$/i }));
    expect(screen.getByText("chat only", { selector: ".whitespace-pre-wrap" })).toBeInTheDocument();
    expect(screen.queryByText("cowork only", { selector: ".whitespace-pre-wrap" })).not.toBeInTheDocument();
  });

  it("routes sessionless Cowork events away from Chat and hides Cowork approvals in Chat", async () => {
    const handlers = {};
    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={{
          subscribe(_sessionId, listener) {
            handlers.current = listener;
            return () => {};
          },
        }}
      />,
    );

    handlers.current({
      id: "cowork-answer",
      sessionId: "sidecar-session-not-yet-known",
      timestamp: "2026-06-28T04:00:00.000Z",
      type: "message.assistant",
      status: "complete",
      payload: { text: "Cowork-only answer", role: "AI", mode: "Cowork" },
    });
    handlers.current({
      id: "cowork-approval",
      sessionId: "another-sidecar-session",
      timestamp: "2026-06-28T04:01:00.000Z",
      type: "approval.requested",
      status: "pending",
      payload: {
        approvalId: "approval-cowork-only",
        approvalKind: "run_verification",
        title: "Approve verification run",
        question: "Approve running tests?",
        options: ["allow", "deny"],
        proposal: {},
        mode: "Cowork",
      },
    });

    expect(screen.queryByText("Cowork-only answer", { selector: ".whitespace-pre-wrap" })).not.toBeInTheDocument();
    expect(screen.queryByText("Approve verification run")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^mode cowork$/i }));

    expect(await screen.findByText("Cowork-only answer", { selector: ".whitespace-pre-wrap" })).toBeInTheDocument();
    expect(screen.getByText("Approve verification run")).toBeInTheDocument();
  });

  it("browses files, inspects changes, runs verification, and requests backup restore", async () => {
    let workspaceListener;
    const setWorkspace = vi.fn();
    const workspaceAction = vi.fn(async (payload) => {
      const responses = {
        list_directory: { entries: ["README.md", "src/"] },
        read_file: { path: payload.path, content: "# Demo workspace\n" },
        inspect: {
          git_status: { status: "ok", branch: "main", changes: [{ code: " M", path: "src/app.py" }] },
          git_diff: { status: "ok", changed_files: ["src/app.py"], stdout: "diff --git a/src/app.py b/src/app.py\n+changed" },
          backups: [{ backup_path: ".cowork/backups/one/src/app.py", target_path: "src/app.py", bytes: 12 }],
        },
        run_verification: { status: "passed", name: payload.name, stdout: "64 tests passed", stderr: "", exit_code: 0 },
        restore_backup: { status: "restored", path: "src/app.py", restored_from: payload.backupPath },
      };
      queueMicrotask(() => workspaceListener?.({ request_id: payload.requestId, action: payload.action, result: responses[payload.action] }));
    });
    const bridge = {
      answerApproval: vi.fn(),
      selectWorkspace: vi.fn().mockResolvedValue("C:\\Work\\Demo"),
      setWorkspace,
      workspaceAction,
      subscribe: () => () => {},
      subscribeWorkspace(listener) {
        workspaceListener = listener;
        return () => {};
      },
    };

    render(
      <CoworkApp
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
        coworkUiState="idle"
        bridge={bridge}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Projects" }));
    fireEvent.click(screen.getByRole("button", { name: "Choose a different folder" }));
    await waitFor(() => expect(setWorkspace).toHaveBeenCalledWith("C:\\Work\\Demo"));

    fireEvent.click(screen.getByRole("button", { name: /^mode code$/i }));
    fireEvent.click(screen.getByRole("button", { name: "Workspace" }));
    expect(await screen.findByRole("heading", { name: "Code workspace" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "README.md" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "README.md" }));
    expect(await screen.findByText("# Demo workspace")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Changes" }));
    expect(await screen.findByText("main")).toBeInTheDocument();
    expect(screen.getByText("src/app.py")).toBeInTheDocument();
    expect(screen.getByText(/\+changed/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Verification" }));
    fireEvent.click(screen.getByRole("button", { name: "Run python-tests" }));
    expect(await screen.findByText("64 tests passed")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Backups" }));
    fireEvent.click(screen.getByRole("button", { name: "Restore src/app.py" }));
    await waitFor(() => expect(workspaceAction).toHaveBeenCalledWith(expect.objectContaining({
      action: "restore_backup",
      backupPath: ".cowork/backups/one/src/app.py",
    })));
  });
});
