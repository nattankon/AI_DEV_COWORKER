import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MemoryManager from "../components/MemoryManager";

describe("MemoryManager", () => {
  it("shows readable kind badges for typed chat memories", () => {
    render(
      <MemoryManager
        open
        entries={[
          { id: "m1", kind: "writing_style", text: "ตอบภาษาไทยแบบละเอียด" },
          { id: "m2", kind: "long_term_goal", text: "build a capable local chat assistant" },
        ]}
      />,
    );

    expect(screen.getAllByText("Writing style").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Long-term goal").length).toBeGreaterThan(0);
  });

  it("keeps edit and delete callbacks working for typed memories", () => {
    const onUpdate = vi.fn();
    const onDelete = vi.fn();
    render(
      <MemoryManager
        open
        entries={[{ id: "m1", kind: "identity", text: "เรียกผู้ใช้ว่า arm" }]}
        onUpdate={onUpdate}
        onDelete={onDelete}
      />,
    );

    fireEvent.click(screen.getByText("เรียกผู้ใช้ว่า arm"));
    fireEvent.change(screen.getByLabelText("Edit memory m1"), { target: { value: "เรียกผู้ใช้ว่า Jetko" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete memory m1" }));

    expect(onUpdate).toHaveBeenCalledWith("m1", "เรียกผู้ใช้ว่า Jetko");
    expect(onDelete).toHaveBeenCalledWith("m1");
  });

  it("creates a typed memory from the manager", () => {
    const onCreate = vi.fn();
    render(<MemoryManager open entries={[]} onCreate={onCreate} />);

    fireEvent.change(screen.getByLabelText("Memory kind"), { target: { value: "long_term_goal" } });
    fireEvent.change(screen.getByLabelText("New memory"), { target: { value: "Build a useful local AI product" } });
    fireEvent.click(screen.getByRole("button", { name: "Remember" }));

    expect(onCreate).toHaveBeenCalledWith({
      kind: "long_term_goal",
      text: "Build a useful local AI product",
    });
  });

  it("creates profile and do-not-remember entries from the manager", () => {
    const onCreate = vi.fn();
    render(<MemoryManager open entries={[]} onCreate={onCreate} />);

    fireEvent.change(screen.getByLabelText("Memory kind"), { target: { value: "profile" } });
    fireEvent.change(screen.getByLabelText("New memory"), { target: { value: "User is building a local AI app" } });
    fireEvent.click(screen.getByRole("button", { name: "Remember" }));
    expect(onCreate).toHaveBeenCalledWith({ kind: "profile", text: "User is building a local AI app" });

    fireEvent.change(screen.getByLabelText("Memory kind"), { target: { value: "do_not_remember" } });
    fireEvent.change(screen.getByLabelText("New memory"), { target: { value: "old Lua preference" } });
    fireEvent.click(screen.getByRole("button", { name: "Do not remember" }));
    expect(onCreate).toHaveBeenLastCalledWith({ kind: "do_not_remember", text: "old Lua preference" });
  });

  it("creates a chat role from the manager", () => {
    const onCreate = vi.fn();
    render(<MemoryManager open activeMode="Chat" entries={[]} onCreate={onCreate} />);

    fireEvent.change(screen.getByLabelText("Memory kind"), { target: { value: "role" } });
    fireEvent.change(screen.getByLabelText("New memory"), { target: { value: "Act as a focused research assistant" } });
    fireEvent.click(screen.getByRole("button", { name: "Add role" }));

    expect(onCreate).toHaveBeenCalledWith({
      kind: "role",
      mode: "Chat",
      text: "Act as a focused research assistant",
    });
  });

  it("shows only role memories for the active chat session", () => {
    render(
      <MemoryManager
        open
        activeSessionId="chat-1"
        activeMode="Chat"
        entries={[
          { id: "r1", kind: "role", text: "Role for this chat", mode: "Chat", source: { session_id: "chat-1" } },
          { id: "r2", kind: "role", text: "Role for another chat", mode: "Chat", source: { session_id: "chat-2" } },
          { id: "r3", kind: "role", text: "Role for cowork mode", mode: "Cowork", source: { session_id: "chat-1" } },
          { id: "m1", kind: "preference", text: "Global preference" },
        ]}
      />,
    );

    expect(screen.getByText("Role for this chat")).toBeTruthy();
    expect(screen.getByText("Persona role")).toBeTruthy();
    expect(screen.getByText("This chat")).toBeTruthy();
    expect(screen.queryByText("Role for another chat")).toBeNull();
    expect(screen.queryByText("Role for cowork mode")).toBeNull();
    expect(screen.getByText("Global preference")).toBeTruthy();
  });

  it("creates and shows cowork roles for the active cowork mode", () => {
    const onCreate = vi.fn();
    render(
      <MemoryManager
        open
        activeMode="Cowork"
        activeSessionId="cowork-1"
        entries={[
          { id: "r1", kind: "role", text: "Cowork role", mode: "Cowork", source: { session_id: "cowork-1" } },
          { id: "r2", kind: "role", text: "Chat role", mode: "Chat", source: { session_id: "cowork-1" } },
        ]}
        onCreate={onCreate}
      />,
    );

    expect(screen.getByText("Cowork memory")).toBeTruthy();
    expect(screen.getByText("Cowork role")).toBeTruthy();
    expect(screen.queryByText("Chat role")).toBeNull();
    fireEvent.change(screen.getByLabelText("Memory kind"), { target: { value: "role" } });
    fireEvent.change(screen.getByLabelText("New memory"), { target: { value: "Act as a TDD agent" } });
    fireEvent.click(screen.getByRole("button", { name: "Add role" }));

    expect(onCreate).toHaveBeenCalledWith({
      kind: "role",
      mode: "Cowork",
      text: "Act as a TDD agent",
    });
  });

  it("pauses and enables role memories without deleting them", () => {
    const onSetEnabled = vi.fn();
    render(
      <MemoryManager
        open
        activeMode="Chat"
        activeSessionId="chat-1"
        entries={[
          { id: "r1", kind: "role", text: "Use a calm tutoring style", mode: "Chat", enabled: true, source: { session_id: "chat-1" } },
          { id: "r2", kind: "role", text: "Paused role", mode: "Chat", enabled: false, source: { session_id: "chat-1" } },
        ]}
        onSetEnabled={onSetEnabled}
      />,
    );

    expect(screen.getByText("Active")).toBeTruthy();
    expect(screen.getByText("Paused")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Pause role r1" }));
    fireEvent.click(screen.getByRole("button", { name: "Enable role r2" }));

    expect(onSetEnabled).toHaveBeenCalledWith("r1", false);
    expect(onSetEnabled).toHaveBeenCalledWith("r2", true);
  });
});
