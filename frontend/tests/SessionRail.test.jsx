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
    const dragon = screen.getByRole("button", { name: /DragonNest/ });
    expect(dragon).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "PB1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /No project/ })).toBeInTheDocument();
    expect(screen.getByText("Config edit")).toBeInTheDocument();

    // Collapsing the DragonNest header hides its sessions.
    fireEvent.click(dragon);
    expect(screen.queryByText("Config edit")).not.toBeInTheDocument();
    expect(screen.getByText("PB tweak")).toBeInTheDocument();
  });
});
