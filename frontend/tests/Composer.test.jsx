import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Composer from "../components/Composer";

describe("Composer", () => {
  it("submits with Ctrl+Enter and keeps Shift+Enter for new lines", () => {
    const onSubmit = vi.fn();
    render(
      <Composer
        disabled={false}
        modelLabel="qwen/qwen3.5-9b"
        workspaceLabel="API-BLENDER"
        onSubmit={onSubmit}
      />,
    );

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "Inspect architecture" } });
    fireEvent.keyDown(textbox, { key: "Enter", shiftKey: true });
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });
    expect(onSubmit).toHaveBeenCalledWith("Inspect architecture");
    expect(textbox).toHaveValue("");
  });

  it("does not submit an empty prompt", () => {
    const onSubmit = vi.fn();
    render(<Composer disabled={false} modelLabel="model" workspaceLabel="workspace" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole("button", { name: "Send prompt" }));

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows context usage metadata for the selected model", () => {
    render(
      <Composer
        disabled={false}
        modelLabel="zai:glm-4.5-flash"
        workspaceLabel="workspace"
        contextUsage={{
          contextWindowTokens: 131072,
          percentFull: 12,
          usedTokens: 16384,
          usedLabel: "16k",
          windowLabel: "131k",
          title: "Context window:\n12% full\n16k / 131k tokens used",
        }}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Context usage")).toHaveTextContent("12%");
    expect(screen.getByLabelText("Context usage")).toHaveAttribute("title", expect.stringContaining("16k / 131k"));
  });

  it("shows the latest auto router reason near the model controls", () => {
    render(
      <Composer
        disabled={false}
        modelLabel="zai:glm-4.7-flash"
        workspaceLabel="workspace"
        routeReason="auto: coding task via quality profile"
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Model route reason")).toHaveTextContent("auto: coding task");
  });

  it("accepts a suggested prompt and focus signal from the shell", () => {
    const onSubmit = vi.fn();
    const { rerender } = render(
      <Composer disabled={false} modelLabel="model" workspaceLabel="workspace" onSubmit={onSubmit} />,
    );

    rerender(
      <Composer
        disabled={false}
        modelLabel="model"
        workspaceLabel="workspace"
        onSubmit={onSubmit}
        suggestedPrompt={{ id: "write", text: "Draft release notes for this project" }}
        focusSignal={1}
      />,
    );

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    expect(textbox).toHaveValue("Draft release notes for this project");
    expect(textbox).toHaveFocus();
  });

  it("accepts suggested attachments from shell actions before submitting", () => {
    const onSubmit = vi.fn();
    render(
      <Composer
        disabled={false}
        modelLabel="model"
        workspaceLabel="workspace"
        suggestedAttachments={[
          { label: "Artifact summary", source: "artifact", kind: "text", content: "generated artifact content" },
        ]}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByText("Artifact summary")).toBeInTheDocument();
    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "Use this artifact" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });

    expect(onSubmit).toHaveBeenCalledWith("Use this artifact", [
      expect.objectContaining({
        label: "Artifact summary",
        source: "artifact",
        kind: "text",
        content: "generated artifact content",
      }),
    ]);
  });

  it("reads selected files as explicit chat attachments before submitting", async () => {
    const onSubmit = vi.fn();
    const note = new File(["attached note content"], "notes.txt", { type: "text/plain" });
    render(
      <Composer
        disabled={false}
        modelLabel="model"
        workspaceLabel="workspace"
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Attach context" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Add files or photos/i }));
    fireEvent.change(screen.getByLabelText("Attach files"), { target: { files: [note] } });

    expect(await screen.findByText("notes.txt")).toBeInTheDocument();
    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "Summarize this" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });

    expect(onSubmit).toHaveBeenCalledWith("Summarize this", [
      expect.objectContaining({
        label: "notes.txt",
        content: "attached note content",
        source: "user-file",
        kind: "text",
      }),
    ]);
    expect(screen.queryByText("notes.txt")).not.toBeInTheDocument();
  });

  it("previews text attachments before sending", async () => {
    const note = new File(["attachment preview content"], "preview.txt", { type: "text/plain" });
    render(<Composer disabled={false} modelLabel="model" workspaceLabel="workspace" onSubmit={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Attach context" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Add files or photos/i }));
    fireEvent.change(screen.getByLabelText("Attach files"), { target: { files: [note] } });

    fireEvent.click(await screen.findByRole("button", { name: "Preview preview.txt" }));

    expect(screen.getByRole("dialog", { name: "Attachment preview" })).toBeInTheDocument();
    expect(screen.getByText("attachment preview content")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close attachment preview" }));
    expect(screen.queryByRole("dialog", { name: "Attachment preview" })).not.toBeInTheDocument();
  });

  it("accepts dropped image files as explicit chat attachments before submitting", async () => {
    const onSubmit = vi.fn();
    const image = new File(["fake image bytes"], "diagram.png", { type: "image/png" });
    render(
      <Composer
        disabled={false}
        modelLabel="model"
        workspaceLabel="workspace"
        onSubmit={onSubmit}
      />,
    );

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.drop(textbox, {
      dataTransfer: {
        files: [image],
      },
    });

    expect(await screen.findByRole("img", { name: "diagram.png preview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview diagram.png" })).toBeInTheDocument();
    fireEvent.change(textbox, { target: { value: "What is in this image?" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });

    expect(onSubmit).toHaveBeenCalledWith("What is in this image?", [
      expect.objectContaining({
        label: "diagram.png",
        source: "user-file",
        kind: "image",
        mime: "image/png",
        dataUrl: expect.stringMatching(/^data:image\/png;base64,/),
        content: expect.stringContaining("Image file diagram.png"),
      }),
    ]);
  });

  it("adds pasted clipboard images as explicit chat attachments", async () => {
    const onSubmit = vi.fn();
    const image = new File(["clipboard image bytes"], "clipboard.png", { type: "image/png" });
    const clipboardItem = {
      kind: "file",
      type: "image/png",
      getAsFile: () => image,
    };
    render(
      <Composer
        disabled={false}
        modelLabel="model"
        workspaceLabel="workspace"
        onSubmit={onSubmit}
      />,
    );

    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.paste(textbox, {
      clipboardData: {
        items: [clipboardItem],
      },
    });

    expect(await screen.findByRole("img", { name: "clipboard.png preview" })).toBeInTheDocument();
    fireEvent.change(textbox, { target: { value: "Read this screenshot" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });

    expect(onSubmit).toHaveBeenCalledWith("Read this screenshot", [
      expect.objectContaining({
        label: "clipboard.png",
        source: "user-paste",
        kind: "image",
        mime: "image/png",
        dataUrl: expect.stringMatching(/^data:image\/png;base64,/),
      }),
    ]);
  });

  it("accepts clipboard images pasted on the composer surface", async () => {
    const onSubmit = vi.fn();
    const image = new File(["surface clipboard image"], "surface.png", { type: "image/png" });
    const clipboardItem = {
      kind: "file",
      type: "image/png",
      getAsFile: () => image,
    };
    render(
      <Composer
        disabled={false}
        modelLabel="model"
        workspaceLabel="workspace"
        onSubmit={onSubmit}
      />,
    );

    fireEvent.paste(screen.getByLabelText("Message composer"), {
      clipboardData: {
        items: [clipboardItem],
      },
    });

    expect(await screen.findByRole("img", { name: "surface.png preview" })).toBeInTheDocument();
  });

  it("changes web settings from the tool settings menu", () => {
    const onWebSettingsChange = vi.fn();
    render(
      <Composer
        disabled={false}
        modelLabel="model"
        workspaceLabel="workspace"
        webSettings={{ webMode: "auto", searchProvider: "auto" }}
        searchCapabilities={{
          providers: [
            { id: "auto", label: "Auto", available: true },
            { id: "brave", label: "Brave", available: false },
            { id: "scrape", label: "Basic scrape", available: true },
          ],
        }}
        onWebSettingsChange={onWebSettingsChange}
        onSubmit={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Tool settings" }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: "off" }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: "Basic scrape" }));

    expect(onWebSettingsChange).toHaveBeenCalledWith({ webMode: "off", searchProvider: "auto" });
    expect(onWebSettingsChange).toHaveBeenCalledWith({ webMode: "auto", searchProvider: "scrape" });
    expect(screen.getByRole("menuitemradio", { name: /Brave/ })).toBeDisabled();
  });

  it("shows live MCP connector statuses in the tool settings menu", () => {
    const onOpenConnectors = vi.fn();
    render(
      <Composer
        disabled={false}
        modelLabel="model"
        workspaceLabel="workspace"
        webSettings={{ webMode: "auto", searchProvider: "auto", mcp: "off" }}
        connectorState={{
          enabled: true,
          mcp_sdk_available: false,
          statuses: [{ name: "calendar", status: "unavailable" }],
        }}
        onOpenConnectors={onOpenConnectors}
        onWebSettingsChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Tool settings" }));

    expect(screen.getByText("Connectors: calendar unavailable")).toBeInTheDocument();
    expect(screen.getByText("MCP SDK not installed or disabled.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Manage MCP connectors" }));
    expect(onOpenConnectors).toHaveBeenCalledTimes(1);
  });

  it("keeps connector configuration out of the compact tool settings menu", () => {
    const onOpenConnectors = vi.fn();
    const onRefreshChatConnectors = vi.fn();
    render(
      <Composer
        disabled={false}
        modelLabel="model"
        workspaceLabel="workspace"
        webSettings={{ webMode: "auto", searchProvider: "auto", mcp: "off" }}
        connectorState={{
          enabled: true,
          mcp_sdk_available: false,
          connectors: [{ name: "calendar", transport: "stdio", command: "calendar-mcp", enabled: false }],
          statuses: [{ name: "calendar", status: "disabled", error: "disabled by user" }],
        }}
        onRefreshChatConnectors={onRefreshChatConnectors}
        onOpenConnectors={onOpenConnectors}
        onWebSettingsChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Tool settings" }));

    expect(screen.getByText("calendar")).toBeInTheDocument();
    expect(screen.getByText("disabled by user")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh MCP connectors" }));
    expect(onRefreshChatConnectors).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Manage MCP connectors" }));
    expect(onOpenConnectors).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Add Roblox MCP preset" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Test Roblox MCP" })).not.toBeInTheDocument();
  });

  it("shows MCP live tool counts when a connector reports them", () => {
    render(
      <Composer
        disabled={false}
        modelLabel="model"
        workspaceLabel="workspace"
        webSettings={{ webMode: "auto", searchProvider: "auto", mcp: "off" }}
        connectorState={{
          enabled: true,
          mcp_sdk_available: true,
          connectors: [{ name: "calendar", transport: "stdio", command: "calendar-mcp", enabled: true }],
          statuses: [{ name: "calendar", status: "connected", tool_count: 3, read_only_tool_count: 2, write_tool_count: 1 }],
        }}
        onWebSettingsChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Tool settings" }));

    expect(screen.getByText("3 tools · 2 read-only · 1 approval")).toBeInTheDocument();
  });

  it("runs a selected MCP tool with schema-derived arguments", () => {
    const onRunChatMcpTool = vi.fn();
    render(
      <Composer
        disabled={false}
        modelLabel="model"
        workspaceLabel="workspace"
        webSettings={{ webMode: "auto", searchProvider: "auto", mcp: "on" }}
        connectorState={{
          enabled: true,
          mcp_sdk_available: true,
          connectors: [{ name: "calendar", transport: "stdio", command: "calendar-mcp", enabled: true }],
          statuses: [{
            name: "calendar",
            status: "connected",
            tool_count: 1,
            read_only_tool_count: 1,
            write_tool_count: 0,
            tools: [{
              name: "list_events",
              description: "List calendar events.",
              read_only: true,
              input_schema: {
                type: "object",
                properties: { limit: { type: ["integer", "null"] }, calendar: { type: ["string", "null"] } },
                required: ["limit", "calendar"],
                additionalProperties: false,
              },
            }],
          }],
        }}
        onRunChatMcpTool={onRunChatMcpTool}
        onWebSettingsChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Tool settings" }));
    fireEvent.click(screen.getByRole("button", { name: "Select MCP tool calendar/list_events" }));
    fireEvent.change(screen.getByLabelText("MCP argument limit"), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("MCP argument calendar"), { target: { value: "work" } });
    fireEvent.click(screen.getByRole("button", { name: "Run MCP tool calendar/list_events" }));

    expect(onRunChatMcpTool).toHaveBeenCalledWith({
      server: "calendar",
      tool: "list_events",
      arguments: { limit: 3, calendar: "work" },
      origin: "manual",
    });
  });

  it("adds pasted text snippets as explicit chat attachments", async () => {
    const onSubmit = vi.fn();
    render(<Composer disabled={false} modelLabel="model" workspaceLabel="workspace" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole("button", { name: "Attach context" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Add pasted text/i }));
    fireEvent.change(screen.getByLabelText("Context label"), { target: { value: "Lua snippet" } });
    fireEvent.change(screen.getByLabelText("Paste context"), { target: { value: "print('hello')" } });
    fireEvent.click(screen.getByRole("button", { name: "Add context" }));

    expect(await screen.findByText("Lua snippet")).toBeInTheDocument();
    const textbox = screen.getByPlaceholderText("How can I help you today?");
    fireEvent.change(textbox, { target: { value: "Explain this snippet" } });
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });

    expect(onSubmit).toHaveBeenCalledWith("Explain this snippet", [
      expect.objectContaining({
        label: "Lua snippet",
        content: "print('hello')",
        source: "user-paste",
        kind: "text",
      }),
    ]);
  });
});

