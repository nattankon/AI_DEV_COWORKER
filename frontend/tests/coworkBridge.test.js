import { describe, expect, it, vi } from "vitest";
import { createCoworkBridge } from "../adapters/coworkBridge";

describe("cowork bridge adapter", () => {
  it("normalizes legacy log events into event envelopes", () => {
    let logHandler;
    const legacyBridge = {
      subscribe(eventName, handler) {
        if (eventName === "cowork_log") logHandler = handler;
        return () => {};
      },
    };
    const bridge = createCoworkBridge(legacyBridge, {
      createId: () => "event-1",
      now: () => "2026-06-12T00:00:00.000Z",
    });
    const listener = vi.fn();

    bridge.subscribe("session-1", listener);
    logHandler({ detail: { role: "AI", text: "Ready" } });

    expect(listener).toHaveBeenCalledWith({
      id: "event-1",
      sessionId: "session-1",
      timestamp: "2026-06-12T00:00:00.000Z",
      type: "message.assistant",
      status: "complete",
      payload: { text: "Ready", role: "AI" },
    });
  });

  it("normalizes sidecar Chat delta events into stable streaming assistant events", () => {
    let deltaHandler;
    const bridge = createCoworkBridge({
      subscribe(eventName, handler) {
        if (eventName === "cowork_log_delta") deltaHandler = handler;
        return () => {};
      },
    }, {
      now: () => "2026-06-30T01:00:00.000Z",
    });
    const listener = vi.fn();

    bridge.subscribe("chat-1", listener);
    deltaHandler({ detail: { client_session_id: "chat-1", mode: "Chat", delta: "Hello" } });

    expect(listener).toHaveBeenCalledWith({
      id: "stream-chat-1-Chat",
      sessionId: "chat-1",
      timestamp: "2026-06-30T01:00:00.000Z",
      type: "message.assistant",
      status: "running",
      payload: { text: "Hello", role: "AI", mode: "Chat", streaming: true },
    });
  });

  it("passes reset flags from sidecar delta events", () => {
    let deltaHandler;
    const bridge = createCoworkBridge({
      subscribe(eventName, handler) {
        if (eventName === "cowork_log_delta") deltaHandler = handler;
        return () => {};
      },
    }, {
      now: () => "2026-06-30T01:00:00.000Z",
    });
    const listener = vi.fn();

    bridge.subscribe("chat-1", listener);
    deltaHandler({ detail: { client_session_id: "chat-1", mode: "Chat", reset: true } });

    expect(listener).toHaveBeenCalledWith(expect.objectContaining({
      payload: expect.objectContaining({ text: "", streaming: true, reset: true }),
    }));
  });

  it("normalizes sidecar Chat research status as transient status", () => {
    let statusHandler;
    const bridge = createCoworkBridge({
      subscribe(eventName, handler) {
        if (eventName === "cowork_status") statusHandler = handler;
        return () => {};
      },
    }, {
      now: () => "2026-06-30T01:02:00.000Z",
    });
    const listener = vi.fn();

    bridge.subscribe("chat-1", listener);
    statusHandler({ detail: { client_session_id: "chat-1", mode: "Chat", text: "🔍 Searching: fuel price" } });

    expect(listener).toHaveBeenCalledWith({
      id: "status-chat-1-Chat",
      sessionId: "chat-1",
      timestamp: "2026-06-30T01:02:00.000Z",
      type: "chat.status",
      status: "running",
      payload: { text: "🔍 Searching: fuel price", mode: "Chat", transient: true },
    });
  });

  it("normalizes sidecar completion evidence into a verification.finished event", () => {
    let completionHandler;
    const bridge = createCoworkBridge({
      subscribe(eventName, handler) {
        if (eventName === "cowork_completion") completionHandler = handler;
        return () => {};
      },
    }, {
      createId: () => "generated-id",
      now: () => "2026-06-30T01:02:00.000Z",
    });
    const listener = vi.fn();

    bridge.subscribe("cowork-1", listener);
    completionHandler({
      detail: {
        client_session_id: "cowork-1",
        mode: "Cowork",
        writes_performed: true,
        verification_observed: true,
        verification_passed: false,
        verification_statuses: ["failed"],
        verification_runs: [{ name: "python-tests", status: "failed" }],
        test_files_modified: ["test/test_app.py"],
      },
    });

    expect(listener).toHaveBeenCalledWith({
      id: "generated-id",
      sessionId: "cowork-1",
      timestamp: "2026-06-30T01:02:00.000Z",
      type: "verification.finished",
      status: "complete",
      payload: {
        mode: "Cowork",
        writesPerformed: true,
        verificationObserved: true,
        verificationPassed: false,
        verificationStatuses: ["failed"],
        verificationRuns: [{ name: "python-tests", status: "failed" }],
        testFilesModified: ["test/test_app.py"],
      },
    });
  });

  it("normalizes MCP tool results into persistent result events", () => {
    let resultHandler;
    const bridge = createCoworkBridge({
      subscribe(eventName, handler) {
        if (eventName === "chat_mcp_tool_result") resultHandler = handler;
        return () => {};
      },
    }, {
      createId: () => "mcp-event-1",
      now: () => "2026-07-02T02:00:00.000Z",
    });
    const listener = vi.fn();

    bridge.subscribe("chat-1", listener);
    resultHandler({
      detail: {
        client_session_id: "chat-1",
        mode: "Chat",
        origin: "manual",
        server: "roblox",
        tool: "list_instances",
        read_only: true,
        status: "ok",
        result: { instances: ["Studio"] },
        duration_ms: 12,
      },
    });

    expect(listener).toHaveBeenCalledWith({
      id: "mcp-event-1",
      sessionId: "chat-1",
      timestamp: "2026-07-02T02:00:00.000Z",
      type: "mcp.result",
      status: "complete",
      payload: {
        mode: "Chat",
        origin: "manual",
        server: "roblox",
        tool: "list_instances",
        arguments: {},
        status: "ok",
        readOnly: true,
        result: { instances: ["Studio"] },
        error: "",
        durationMs: 12,
      },
    });
  });

  it("does not emit sidecar USER echoes because the renderer already records submissions", () => {
    let logHandler;
    const bridge = createCoworkBridge({
      subscribe(eventName, handler) {
        if (eventName === "cowork_log") logHandler = handler;
        return () => {};
      },
    });
    const listener = vi.fn();

    bridge.subscribe("session-1", listener);
    logHandler({ detail: { role: "USER", text: "already visible" } });

    expect(listener).not.toHaveBeenCalled();
  });

  it("unsubscribes every legacy event subscription", () => {
    const disposers = [vi.fn(), vi.fn(), vi.fn(), vi.fn(), vi.fn(), vi.fn()];
    let index = 0;
    const bridge = createCoworkBridge({ subscribe: () => disposers[index++] });

    const dispose = bridge.subscribe("session-1", () => {});
    dispose();

    expect(disposers.every((item) => item.mock.calls.length === 1)).toBe(true);
  });

  it("normalizes backend failures into visible session errors", () => {
    let backendLogHandler;
    const bridge = createCoworkBridge({
      subscribe(eventName, handler) {
        if (eventName === "backend-log") backendLogHandler = handler;
        return () => {};
      },
    }, {
      createId: () => "event-error",
      now: () => "2026-06-13T03:00:00.000Z",
    });
    const listener = vi.fn();

    bridge.subscribe("cowork-1", listener);
    backendLogHandler({
      detail: {
        source: "stderr",
        message: "Local AI request timed out.",
        client_session_id: "cowork-1",
      },
    });

    expect(listener).toHaveBeenCalledWith({
      id: "event-error",
      sessionId: "cowork-1",
      timestamp: "2026-06-13T03:00:00.000Z",
      type: "message.system",
      status: "failed",
      payload: {
        text: "Request could not complete: Local AI request timed out.",
        role: "SYSTEM",
      },
    });
  });

  it("uses the originating mode in backend failure labels", () => {
    let backendLogHandler;
    const bridge = createCoworkBridge({
      subscribe(eventName, handler) {
        if (eventName === "backend-log") backendLogHandler = handler;
        return () => {};
      },
    }, {
      createId: () => "event-chat-error",
      now: () => "2026-06-13T03:01:00.000Z",
    });
    const listener = vi.fn();

    bridge.subscribe("chat-1", listener);
    backendLogHandler({
      detail: {
        source: "stderr",
        message: "The model timed out.",
        client_session_id: "chat-1",
        mode: "Chat",
      },
    });

    expect(listener).toHaveBeenCalledWith(expect.objectContaining({
      payload: expect.objectContaining({
        text: "Chat could not complete the request: The model timed out.",
        role: "SYSTEM",
      }),
    }));
  });

  it("uses a neutral backend failure label when mode is missing", () => {
    let backendLogHandler;
    const bridge = createCoworkBridge({
      subscribe(eventName, handler) {
        if (eventName === "backend-log") backendLogHandler = handler;
        return () => {};
      },
    }, {
      createId: () => "event-neutral-error",
      now: () => "2026-06-13T03:02:00.000Z",
    });
    const listener = vi.fn();

    bridge.subscribe("unknown-1", listener);
    backendLogHandler({
      detail: {
        source: "stderr",
        message: "Backend failed.",
        client_session_id: "unknown-1",
      },
    });

    expect(listener).toHaveBeenCalledWith(expect.objectContaining({
      payload: expect.objectContaining({
        text: "Request could not complete: Backend failed.",
        role: "SYSTEM",
      }),
    }));
  });

  it("normalizes sidecar approval prompts with proposal details", () => {
    let questionHandler;
    const legacyBridge = {
      subscribe(eventName, handler) {
        if (eventName === "cowork_interactive_question") questionHandler = handler;
        return () => {};
      },
    };
    const bridge = createCoworkBridge(legacyBridge, {
      createId: () => "event-approval",
      now: () => "2026-06-13T00:00:00.000Z",
    });
    const listener = vi.fn();

    bridge.subscribe("session-1", listener);
    questionHandler({
      detail: {
        approval_id: "approval-42",
        approval_kind: "write_file",
        question: "Approve writing notes.txt?",
        proposal: {
          relative_path: "notes.txt",
          diff: "--- a/notes.txt\n+++ b/notes.txt\n@@\n-old\n+new\n",
        },
      },
    });

    expect(listener).toHaveBeenCalledWith({
      id: "event-approval",
      sessionId: "session-1",
      timestamp: "2026-06-13T00:00:00.000Z",
      type: "approval.requested",
      status: "pending",
      payload: {
        approvalId: "approval-42",
        approvalKind: "write_file",
        question: "Approve writing notes.txt?",
        title: "Approve file write",
        options: ["allow", "deny"],
        proposal: {
          relative_path: "notes.txt",
          diff: "--- a/notes.txt\n+++ b/notes.txt\n@@\n-old\n+new\n",
        },
      },
    });
  });

  it("labels MCP approval prompts as MCP tool approvals", () => {
    let questionHandler;
    const bridge = createCoworkBridge({
      subscribe(eventName, handler) {
        if (eventName === "cowork_interactive_question") questionHandler = handler;
        return () => {};
      },
    }, {
      createId: () => "event-mcp-approval",
      now: () => "2026-07-02T00:00:00.000Z",
    });
    const listener = vi.fn();

    bridge.subscribe("chat-session", listener);
    questionHandler({
      detail: {
        approval_id: "approval-mcp",
        approval_kind: "mcp_tool_call",
        question: "Approve MCP tool roblox/list_instances?",
        mode: "Chat",
        proposal: { subject: "roblox/list_instances" },
      },
    });

    expect(listener).toHaveBeenCalledWith(expect.objectContaining({
      type: "approval.requested",
      payload: expect.objectContaining({
        approvalKind: "mcp_tool_call",
        title: "Approve MCP tool",
        mode: "Chat",
      }),
    }));
  });

  it("preserves sidecar mode metadata for routing in the renderer", () => {
    let logHandler;
    let questionHandler;
    const bridge = createCoworkBridge({
      subscribe(eventName, handler) {
        if (eventName === "cowork_log") logHandler = handler;
        if (eventName === "cowork_interactive_question") questionHandler = handler;
        return () => {};
      },
    }, {
      createId: () => "event-mode",
      now: () => "2026-06-28T04:00:00.000Z",
    });
    const listener = vi.fn();

    bridge.subscribe("chat-active", listener);
    logHandler({ detail: { role: "AI", text: "Cowork response", mode: "Cowork" } });
    questionHandler({ detail: { approval_id: "approval-mode", approval_kind: "run_verification", mode: "Cowork" } });

    expect(listener).toHaveBeenNthCalledWith(1, expect.objectContaining({
      sessionId: "chat-active",
      payload: expect.objectContaining({ mode: "Cowork" }),
    }));
    expect(listener).toHaveBeenNthCalledWith(2, expect.objectContaining({
      sessionId: "chat-active",
      payload: expect.objectContaining({ approvalId: "approval-mode", mode: "Cowork" }),
    }));
  });

  it("forwards workspace commands and subscriptions without changing request ids", async () => {
    const setWorkspace = vi.fn().mockResolvedValue({ ok: true });
    const workspaceAction = vi.fn().mockResolvedValue({ ok: true });
    const handlers = {};
    const bridge = createCoworkBridge({
      setWorkspace,
      workspaceAction,
      subscribe(eventName, handler) {
        handlers[eventName] = handler;
        return () => {};
      },
    });
    const listener = vi.fn();

    await bridge.setWorkspace("C:\\Work\\Demo");
    await bridge.workspaceAction({ requestId: "read-1", action: "read_file", path: "README.md" });
    bridge.subscribeWorkspace(listener);
    handlers.workspace_response({ detail: { request_id: "read-1", action: "read_file", result: { content: "hello" } } });

    expect(setWorkspace).toHaveBeenCalledWith("C:\\Work\\Demo");
    expect(workspaceAction).toHaveBeenCalledWith({ requestId: "read-1", action: "read_file", path: "README.md" });
    expect(listener).toHaveBeenCalledWith({ request_id: "read-1", action: "read_file", result: { content: "hello" } });
  });

  it("forwards model health fetches and normalizes available model events", async () => {
    const fetchModels = vi.fn().mockResolvedValue({ ok: true });
    let modelsHandler;
    const bridge = createCoworkBridge({
      fetchModels,
      subscribe(eventName, handler) {
        if (eventName === "available_models") modelsHandler = handler;
        return () => {};
      },
    });
    const listener = vi.fn();

    await bridge.fetchModels();
    bridge.subscribeModels(listener);
    modelsHandler({ detail: { models: ["local:qwen/qwen3.5-9b", "qwen2.5-7b-instruct"] } });

    expect(fetchModels).toHaveBeenCalled();
    expect(listener).toHaveBeenCalledWith(
      ["local:qwen/qwen3.5-9b", "local:qwen2.5-7b-instruct"],
      { models: ["local:qwen/qwen3.5-9b", "local:qwen2.5-7b-instruct"] },
    );
  });

  it("passes provider catalog metadata from model events", async () => {
    let modelsHandler;
    const bridge = createCoworkBridge({
      subscribe(eventName, handler) {
        if (eventName === "available_models") modelsHandler = handler;
        return () => {};
      },
    });
    const listener = vi.fn();

    bridge.subscribeModels(listener);
    modelsHandler({
      detail: {
        models: ["openai:gpt-5.5", "zai:glm-5.2"],
        providers: [
          { id: "openai", label: "OpenAI", configured: true, models: [{ id: "openai:gpt-5.5", label: "GPT-5.5", tier: "main" }] },
          { id: "zai", label: "Z.ai", configured: true, models: [{ id: "zai:glm-5.2", label: "GLM-5.2", tier: "main" }] },
        ],
      },
    });

    expect(listener).toHaveBeenCalledWith(
      ["openai:gpt-5.5", "zai:glm-5.2"],
      {
        models: ["openai:gpt-5.5", "zai:glm-5.2"],
        providers: [
          { id: "openai", label: "OpenAI", configured: true, models: [{ id: "openai:gpt-5.5", label: "GPT-5.5", tier: "main" }] },
          { id: "zai", label: "Z.ai", configured: true, models: [{ id: "zai:glm-5.2", label: "GLM-5.2", tier: "main" }] },
        ],
      },
    );
  });

  it("forwards prompt mode and explicit attachments to the legacy bridge", async () => {
    const sendPrompt = vi.fn();
    const bridge = createCoworkBridge({ sendPrompt });

    await bridge.sendPrompt({
      prompt: "hello",
      model: "local:qwen/qwen3.5-9b",
      sessionId: "chat-1",
      mode: "Chat",
      effort: "High",
      attachments: [{ label: "notes.txt", content: "attached note", source: "user-file", kind: "text" }],
      webSettings: { webMode: "off", searchProvider: "scrape" },
      visionSettings: { visionAssist: "on", visionModel: "zai:glm-4.6v-flashx" },
    });

    expect(sendPrompt).toHaveBeenCalledWith(
      "hello",
      "local:qwen/qwen3.5-9b",
      "chat-1",
      "Chat",
      "High",
      [{ label: "notes.txt", content: "attached note", source: "user-file", kind: "text" }],
      { webMode: "off", searchProvider: "scrape" },
      [],
      { visionAssist: "on", visionModel: "zai:glm-4.6v-flashx" },
    );
  });

  it("loads api key capabilities and exposes chat memory commands", async () => {
    const loadApiKeys = vi.fn();
    const listChatMemory = vi.fn();
    const createChatMemory = vi.fn();
    const updateChatMemory = vi.fn();
    const setChatMemoryEnabled = vi.fn();
    const deleteChatMemory = vi.fn();
    const bridge = createCoworkBridge({ loadApiKeys, listChatMemory, createChatMemory, updateChatMemory, setChatMemoryEnabled, deleteChatMemory });

    await bridge.loadApiKeys();
    await bridge.listChatMemory();
    await bridge.createChatMemory({ kind: "writing_style", text: "answer in Thai" });
    await bridge.updateChatMemory("mem-1", "updated");
    await bridge.setChatMemoryEnabled("mem-1", false);
    await bridge.deleteChatMemory("mem-1");

    expect(loadApiKeys).toHaveBeenCalledOnce();
    expect(listChatMemory).toHaveBeenCalledOnce();
    expect(createChatMemory).toHaveBeenCalledWith({ kind: "writing_style", text: "answer in Thai" });
    expect(updateChatMemory).toHaveBeenCalledWith("mem-1", "updated");
    expect(setChatMemoryEnabled).toHaveBeenCalledWith("mem-1", false);
    expect(deleteChatMemory).toHaveBeenCalledWith("mem-1");
  });

  it("exposes chat quality eval listing through the bridge", async () => {
    const listChatQualityEval = vi.fn();
    const runChatQualityEval = vi.fn();
    const handlers = {};
    const listener = vi.fn();
    const bridge = createCoworkBridge({
      listChatQualityEval,
      runChatQualityEval,
      subscribe(eventName, handler) {
        handlers[eventName] = handler;
        return () => {};
      },
    });

    await bridge.listChatQualityEval();
    await bridge.runChatQualityEval({ results: [{ category: "web", answer: "ok" }] });
    bridge.subscribeChatQualityEval(listener);
    handlers.chat_quality_eval_state({ detail: { count: 1, cases: [{ category: "web" }], snapshot: { status: "fail" } } });

    expect(listChatQualityEval).toHaveBeenCalledOnce();
    expect(runChatQualityEval).toHaveBeenCalledWith({ results: [{ category: "web", answer: "ok" }] });
    expect(listener).toHaveBeenCalledWith({ count: 1, cases: [{ category: "web" }], snapshot: { status: "fail" } });
  });

  it("subscribes to model route telemetry", () => {
    const handlers = {};
    const listener = vi.fn();
    const bridge = createCoworkBridge({
      subscribe(eventName, handler) {
        handlers[eventName] = handler;
        return () => {};
      },
    });

    bridge.subscribeModelRoutes(listener);
    handlers.chat_model_route({
      detail: {
        client_session_id: "chat-1",
        mode: "Chat",
        model: "zai:glm-4.7-flash",
        reason: "auto: coding task",
      },
    });

    expect(listener).toHaveBeenCalledWith({
      client_session_id: "chat-1",
      mode: "Chat",
      model: "zai:glm-4.7-flash",
      reason: "auto: coding task",
    });
  });
});
