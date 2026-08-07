import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ConnectorsPanel from "../components/ConnectorsPanel";

describe("ConnectorsPanel", () => {
  it("presents MCP as a generic connector registry before chat can use tools", () => {
    render(
      <ConnectorsPanel
        connectorState={{ enabled: false, mcp_sdk_available: false, connectors: [], statuses: [] }}
        onRefresh={vi.fn()}
        onSaveConnectors={vi.fn()}
        onTestConnector={vi.fn()}
        onDiscoverConnector={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "MCP connectors" })).toBeInTheDocument();
    expect(screen.getByText(/Add and manage MCP servers before Chat can use them/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add custom connector" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add Roblox Studio MCP preset" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add Blender MCP preset" })).toBeInTheDocument();
  });

  it("adds and edits arbitrary connector configs without requiring a Roblox preset", () => {
    const onSaveConnectors = vi.fn();
    render(
      <ConnectorsPanel
        connectorState={{ enabled: true, mcp_sdk_available: true, connectors: [], statuses: [] }}
        onRefresh={vi.fn()}
        onSaveConnectors={onSaveConnectors}
        onTestConnector={vi.fn()}
        onDiscoverConnector={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Add custom connector" }));
    fireEvent.change(screen.getByLabelText("Connector name"), { target: { value: "calendar" } });
    fireEvent.change(screen.getByLabelText("Connector command"), { target: { value: "calendar-mcp" } });
    fireEvent.click(screen.getByLabelText("Connector enabled"));
    fireEvent.click(screen.getByRole("button", { name: "Save connector" }));

    expect(onSaveConnectors).toHaveBeenCalledWith([
      expect.objectContaining({ name: "calendar", transport: "stdio", command: "calendar-mcp", enabled: true }),
    ]);
  });

  it("keeps presets as optional examples and tests the selected connector through the shared backend path", () => {
    const onSaveConnectors = vi.fn();
    const onTestConnector = vi.fn();
    const connector = { name: "calendar", transport: "stdio", command: "calendar-mcp", enabled: true };
    render(
      <ConnectorsPanel
        connectorState={{
          enabled: true,
          mcp_sdk_available: true,
          connectors: [connector],
          statuses: [{ name: "calendar", status: "connected", tool_count: 2, read_only_tool_count: 2, write_tool_count: 0 }],
        }}
        onRefresh={vi.fn()}
        onSaveConnectors={onSaveConnectors}
        onTestConnector={onTestConnector}
        onDiscoverConnector={vi.fn()}
      />,
    );

    expect(screen.getAllByText("calendar").length).toBeGreaterThan(0);
    expect(screen.getByText("2 tools · 2 read-only · 0 approval")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Test connector calendar" }));
    expect(onTestConnector).toHaveBeenCalledWith(expect.objectContaining(connector));

    fireEvent.click(screen.getByRole("button", { name: "Add Roblox Studio MCP preset" }));
    expect(onSaveConnectors).toHaveBeenCalledWith([
      expect.objectContaining(connector),
      expect.objectContaining({ name: "robloxstudio-mcp", transport: "stdio", enabled: false }),
    ]);
  });

  it("applies the Roblox preset with consented read-only overrides as connector data", () => {
    const onSaveConnectors = vi.fn();
    render(
      <ConnectorsPanel
        connectorState={{ enabled: true, mcp_sdk_available: true, connectors: [], statuses: [] }}
        onRefresh={vi.fn()}
        onSaveConnectors={onSaveConnectors}
        onTestConnector={vi.fn()}
        onDiscoverConnector={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Add Roblox Studio MCP preset" }));

    const saved = onSaveConnectors.mock.calls[0][0][0];
    expect(saved.name).toBe("robloxstudio-mcp");
    expect(saved.read_only_overrides).toContain("get_project_structure");
    expect(saved.read_only_overrides).toContain("get_selection");
    expect(saved.read_only_overrides).not.toContain("create_object");
    expect(saved.read_only_overrides).not.toContain("execute_luau");
  });

  it("merges the preset into an existing connector with a sanitized-name collision instead of duplicating", () => {
    const onSaveConnectors = vi.fn();
    const existing = {
      name: "robloxstudio_mcp",
      transport: "http",
      url: "http://localhost:58741/mcp",
      command: "",
      enabled: true,
      read_only_overrides: ["get_selection"],
    };
    render(
      <ConnectorsPanel
        connectorState={{ enabled: true, mcp_sdk_available: true, connectors: [existing], statuses: [] }}
        onRefresh={vi.fn()}
        onSaveConnectors={onSaveConnectors}
        onTestConnector={vi.fn()}
        onDiscoverConnector={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Add Roblox Studio MCP preset" }));

    const saved = onSaveConnectors.mock.calls[0][0];
    expect(saved).toHaveLength(1);
    expect(saved[0].name).toBe("robloxstudio_mcp");
    expect(saved[0].transport).toBe("http");
    expect(saved[0].url).toBe("http://localhost:58741/mcp");
    expect(saved[0].enabled).toBe(true);
    expect(saved[0].read_only_overrides).toContain("get_selection");
    expect(saved[0].read_only_overrides).toContain("get_project_structure");
  });

  it("lets the user view and edit read-only overrides for the selected connector", () => {
    const onSaveConnectors = vi.fn();
    const connector = {
      name: "calendar",
      transport: "stdio",
      command: "calendar-mcp",
      enabled: true,
      read_only_overrides: ["read_event"],
    };
    render(
      <ConnectorsPanel
        connectorState={{ enabled: true, mcp_sdk_available: true, connectors: [connector], statuses: [] }}
        onRefresh={vi.fn()}
        onSaveConnectors={onSaveConnectors}
        onTestConnector={vi.fn()}
        onDiscoverConnector={vi.fn()}
      />,
    );

    expect(screen.getByText(/1 tools trusted without approval/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Read-only overrides"), { target: { value: "read_event\nget_status" } });
    fireEvent.click(screen.getByRole("button", { name: "Save connector" }));

    expect(onSaveConnectors).toHaveBeenCalledWith([
      expect.objectContaining({ name: "calendar", read_only_overrides: ["read_event", "get_status"] }),
    ]);
  });
});
