import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SessionRail from "../components/SessionRail";

describe("SessionRail", () => {
  it("filters visible sessions by local history search without selecting a session", () => {
    const onSelectSession = vi.fn();
    render(
      <SessionRail
        activeMode="Chat"
        activeSessionId="s1"
        sessions={[
          { id: "s1", title: "Thai fuel research", eventCount: 4 },
          { id: "s2", title: "Lua module idea", eventCount: 2 },
        ]}
        onSelectSession={onSelectSession}
      />,
    );

    fireEvent.change(screen.getByLabelText("Search chat history"), { target: { value: "lua" } });

    expect(screen.queryByText("Thai fuel research")).not.toBeInTheDocument();
    expect(screen.getByText("Lua module idea")).toBeInTheDocument();
    expect(onSelectSession).not.toHaveBeenCalled();
  });

  it("shows a flat Recents list when no session has a project", () => {
    render(
      <SessionRail
        activeMode="Cowork"
        activeSessionId="s1"
        sessions={[
          { id: "s1", title: "Untitled", eventCount: 0 },
          { id: "s2", title: "Second", eventCount: 1 },
        ]}
      />,
    );

    expect(screen.getByRole("button", { name: /Recents/ })).toBeInTheDocument();
    expect(screen.queryByText("DragonNest")).not.toBeInTheDocument();
  });

  it("groups sessions under collapsible project headers", () => {
    render(
      <SessionRail
        activeMode="Cowork"
        activeProjectName="DragonNest"
        activeSessionId="s1"
        sessions={[
          { id: "s1", title: "Config edit", eventCount: 3, project: { path: "C:/DragonNest", name: "DragonNest" } },
          { id: "s2", title: "Old chat", eventCount: 1 },
          { id: "s3", title: "PB tweak", eventCount: 2, project: { path: "C:/PB", name: "PB" } },
        ]}
      />,
    );

    // Active project first, then other projects, then the ungrouped bucket.
    const dragon = screen.getByRole("button", { name: "Collapse project DragonNest" });
    expect(screen.getByRole("button", { name: "Open project DragonNest" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open project PB" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /No project/ })).toBeInTheDocument();
    expect(screen.getByText("Config edit")).toBeInTheDocument();

    // Collapsing the DragonNest header hides its sessions.
    fireEvent.click(dragon);
    expect(screen.queryByText("Config edit")).not.toBeInTheDocument();
    expect(screen.getByText("PB tweak")).toBeInTheDocument();
  });

  it("creates a new chat inside a specific project from its header button", () => {
    const onNewSessionInProject = vi.fn();
    render(
      <SessionRail
        activeMode="Cowork"
        activeProjectName="DragonNest"
        activeSessionId="s1"
        sessions={[
          { id: "s1", title: "Config edit", eventCount: 3, project: { path: "C:/DragonNest", name: "DragonNest" } },
          { id: "s3", title: "PB tweak", eventCount: 2, project: { path: "C:/PB", name: "PB" } },
        ]}
        onNewSessionInProject={onNewSessionInProject}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "New chat in PB" }));

    expect(onNewSessionInProject).toHaveBeenCalledWith({ path: "C:/PB", name: "PB" });
  });

  it("shows and selects a registered project before it has any sessions", () => {
    const onSelectProject = vi.fn();
    render(
      <SessionRail
        activeMode="Chat"
        activeSessionId="s1"
        sessions={[{ id: "s1", title: "General chat", eventCount: 0 }]}
        projects={[{ path: "C:/A-Mod", name: "A-Mod" }]}
        onSelectProject={onSelectProject}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open project A-Mod" }));

    expect(onSelectProject).toHaveBeenCalledWith({ path: "C:/A-Mod", name: "A-Mod" });
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("does not offer a per-project new-chat button on the ungrouped Recents list", () => {
    render(
      <SessionRail
        activeMode="Cowork"
        activeSessionId="s1"
        sessions={[{ id: "s1", title: "Untitled", eventCount: 0 }]}
        onNewSessionInProject={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: /New chat in/ })).not.toBeInTheDocument();
  });
});
