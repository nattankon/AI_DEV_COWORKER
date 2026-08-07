import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Timeline from "../components/Timeline";

describe("Timeline", () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn(),
      },
    });
  });

  it("renders user and assistant messages without command details", () => {
    render(
      <Timeline
        events={[
          {
            id: "u1",
            type: "message.user",
            timestamp: "2026-06-12T00:00:00.000Z",
            payload: { text: "Map the project" },
          },
          {
            id: "t1",
            type: "tool.finished",
            timestamp: "2026-06-12T00:00:01.000Z",
            payload: { toolName: "tool_read_file", durationMs: 120, resultSummary: "Read README.md" },
          },
          {
            id: "a1",
            type: "message.assistant",
            timestamp: "2026-06-12T00:00:02.000Z",
            payload: { text: "The project has a Python sidecar." },
          },
        ]}
      />,
    );

    expect(screen.getByText("Map the project")).toBeInTheDocument();
    expect(screen.queryByText("tool_read_file")).not.toBeInTheDocument();
    expect(screen.queryByText("Read README.md")).not.toBeInTheDocument();
    expect(screen.getByText("The project has a Python sidecar.")).toBeInTheDocument();
  });

  it("does not render raw agent status JSON", () => {
    render(
      <Timeline
        events={[{
          id: "status-1",
          type: "agent.status",
          timestamp: "2026-06-13T00:00:00.000Z",
          payload: { state: "busy" },
        }]}
      />,
    );

    expect(screen.queryByText("agent.status", { exact: false })).not.toBeInTheDocument();
    expect(screen.queryByText(/\"state\": \"busy\"/)).not.toBeInTheDocument();
  });

  it("renders MCP tool result cards", () => {
    render(
      <Timeline
        mode="Chat"
        events={[{
          id: "mcp-1",
          type: "mcp.result",
          timestamp: "2026-07-02T00:00:00.000Z",
          payload: {
            server: "roblox",
            tool: "list_instances",
            origin: "manual",
            readOnly: true,
            status: "ok",
            result: { instances: ["Studio"] },
            durationMs: 12,
          },
        }]}
      />,
    );

    expect(screen.getByText("MCP")).toBeInTheDocument();
    expect(screen.getByText("roblox/list_instances")).toBeInTheDocument();
    expect(screen.getByText(/Studio/)).toBeInTheDocument();
    expect(screen.queryByText("mcp.result")).not.toBeInTheDocument();
  });

  it("shows the arguments an MCP tool ran with for the audit trail", () => {
    render(
      <Timeline
        mode="Chat"
        events={[{
          id: "mcp-2",
          type: "mcp.result",
          timestamp: "2026-07-02T00:00:00.000Z",
          payload: {
            server: "roblox",
            tool: "create_object",
            origin: "manual",
            readOnly: false,
            status: "denied",
            arguments: { className: "Part", parent: "game.Workspace" },
            error: "User denied MCP tool call.",
          },
        }]}
      />,
    );

    expect(screen.getByText("Arguments")).toBeInTheDocument();
    expect(screen.getByText(/game\.Workspace/)).toBeInTheDocument();
    expect(screen.getByText(/User denied MCP tool call/)).toBeInTheDocument();
  });

  it("renders Chat mode as left/right chat bubbles without Cowork assistant label", () => {
    render(
      <Timeline
        mode="Chat"
        events={[
          {
            id: "u1",
            type: "message.user",
            timestamp: "2026-06-12T00:00:00.000Z",
            payload: { text: "สวัสดี", mode: "Chat" },
          },
          {
            id: "a1",
            type: "message.assistant",
            timestamp: "2026-06-12T00:00:02.000Z",
            payload: { text: "สวัสดีครับ", mode: "Chat" },
          },
        ]}
      />,
    );

    const userMessage = screen.getByText("สวัสดี", { selector: ".whitespace-pre-wrap" }).closest("article");
    const assistantMessage = screen.getByText("สวัสดีครับ").closest("article");
    expect(screen.getByText("Chat")).toBeInTheDocument();
    expect(screen.queryByText("Cowork")).not.toBeInTheDocument();
    expect(userMessage).toHaveAttribute("data-align", "right");
    expect(assistantMessage).toHaveAttribute("data-align", "left");
  });

  it("renders Chat attachment chips on user messages without exposing attachment content", () => {
    render(
      <Timeline
        mode="Chat"
        events={[
          {
            id: "u1",
            type: "message.user",
            timestamp: "2026-06-28T00:00:00.000Z",
            payload: {
              text: "Explain this context",
              mode: "Chat",
              attachments: [
                { label: "notes.txt", source: "user-file", kind: "text" },
                { label: "Lua snippet", source: "user-paste", kind: "text", content: "print('secret preview')" },
              ],
            },
          },
        ]}
      />,
    );

    expect(screen.getByText("notes.txt")).toBeInTheDocument();
    expect(screen.getByText("Lua snippet")).toBeInTheDocument();
    expect(screen.getByText("user-file")).toBeInTheDocument();
    expect(screen.getByText("user-paste")).toBeInTheDocument();
    expect(screen.queryByText("print('secret preview')")).not.toBeInTheDocument();
  });

  it("renders Chat image attachment thumbnails on user messages", () => {
    render(
      <Timeline
        mode="Chat"
        events={[
          {
            id: "u-image",
            type: "message.user",
            timestamp: "2026-07-02T00:00:00.000Z",
            payload: {
              text: "ดูภาพนี้",
              mode: "Chat",
              attachments: [
                {
                  label: "screenshot.png",
                  source: "user-paste",
                  kind: "image",
                  thumbnailDataUrl: "data:image/png;base64,ZmFrZQ==",
                  content: "Image file screenshot.png contains private pixels.",
                },
              ],
            },
          },
        ]}
      />,
    );

    expect(screen.getByRole("img", { name: "screenshot.png attachment" })).toHaveAttribute(
      "src",
      "data:image/png;base64,ZmFrZQ==",
    );
    expect(screen.getByText("screenshot.png")).toBeInTheDocument();
    expect(screen.queryByText("private pixels", { exact: false })).not.toBeInTheDocument();
  });

  it("renders assistant Chat markdown as formatted elements", () => {
    const markdown = [
      "**Bold answer**",
      "",
      "```js",
      "const value = 42;",
      "```",
      "",
      "| Name | Value |",
      "| --- | --- |",
      "| Alpha | 42 |",
    ].join("\n");

    const { container } = render(
      <Timeline
        mode="Chat"
        events={[{
          id: "a1",
          type: "message.assistant",
          timestamp: "2026-06-30T00:00:00.000Z",
          payload: { text: markdown, mode: "Chat" },
        }]}
      />,
    );

    expect(container.querySelector("strong")).toHaveTextContent("Bold answer");
    expect(container.querySelector("pre code")).toHaveTextContent("const value = 42;");
    expect(container.querySelector("table")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Name" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Alpha" })).toBeInTheDocument();
    expect(screen.queryByText("**Bold answer**")).not.toBeInTheDocument();
  });

  it("keeps user Chat messages as plain text instead of markdown", () => {
    const { container } = render(
      <Timeline
        mode="Chat"
        events={[{
          id: "u1",
          type: "message.user",
          timestamp: "2026-06-30T00:00:00.000Z",
          payload: { text: "**Do not format me**", mode: "Chat" },
        }]}
      />,
    );

    expect(screen.getByText("**Do not format me**")).toBeInTheDocument();
    expect(container.querySelector("strong")).not.toBeInTheDocument();
  });

  it("does not render raw HTML from assistant markdown", () => {
    const { container } = render(
      <Timeline
        mode="Chat"
        events={[{
          id: "a1",
          type: "message.assistant",
          timestamp: "2026-06-30T00:00:00.000Z",
          payload: { text: "<img src=x onerror=alert(1)> **safe bold**", mode: "Chat" },
        }]}
      />,
    );

    expect(container.querySelector("img")).not.toBeInTheDocument();
    expect(container.querySelector("strong")).toHaveTextContent("safe bold");
  });

  it("renders assistant markdown links with safe window attributes", () => {
    render(
      <Timeline
        mode="Chat"
        events={[{
          id: "a1",
          type: "message.assistant",
          timestamp: "2026-06-30T00:00:00.000Z",
          payload: { text: "[Open docs](https://example.com/docs)", mode: "Chat" },
        }]}
      />,
    );

    const link = screen.getByRole("link", { name: "Open docs" });
    expect(link).toHaveAttribute("href", "https://example.com/docs");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    expect(link).toHaveAttribute("rel", expect.stringContaining("noreferrer"));
  });

  it("renders Chat web citations and source cards", () => {
    render(
      <Timeline
        mode="Chat"
        events={[{
          id: "a1",
          type: "message.assistant",
          timestamp: "2026-06-30T00:00:00.000Z",
          payload: {
            text: "Diesel B7 is listed at 31.94 THB/litre [web:1]. Another source is a hint [web:2].",
            mode: "Chat",
            webSources: [
              {
                index: 1,
                title: "EPPO fuel table",
                url: "https://www.eppo.go.th/oil-prices",
                domain: "www.eppo.go.th",
                source_type: "fetched-page",
                quality_score: 4,
              },
              {
                index: 2,
                title: "Known source hint",
                url: "https://example.test/hint",
                domain: "example.test",
                source_type: "trusted-hint",
                quality_score: 1,
              },
            ],
          },
        }]}
      />,
    );

    expect(screen.getByRole("link", { name: "[web:1]" })).toHaveAttribute("href", "#source-web-1");
    expect(screen.getByRole("link", { name: "[web:2]" })).toHaveAttribute("href", "#source-web-2");
    expect(screen.getByText("EPPO fuel table")).toBeInTheDocument();
    expect(screen.getByText("Known source hint")).toBeInTheDocument();
    expect(screen.getByText("fetched")).toBeInTheDocument();
    expect(screen.getByText("hint")).toBeInTheDocument();
    expect(screen.getByLabelText("Source quality 4 of 5")).toBeInTheDocument();
    expect(screen.getByLabelText("Source quality 1 of 5")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /EPPO fuel table/ })).toHaveAttribute(
      "href",
      "https://www.eppo.go.th/oil-prices",
    );
  });

  it("copies assistant Chat answers from the message controls", () => {
    render(
      <Timeline
        mode="Chat"
        events={[{
          id: "a-copy",
          type: "message.assistant",
          timestamp: "2026-06-30T00:00:00.000Z",
          payload: { text: "Copy this answer", mode: "Chat" },
        }]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Copy answer" }));

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("Copy this answer");
  });
});
