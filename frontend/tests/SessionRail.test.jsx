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
});
