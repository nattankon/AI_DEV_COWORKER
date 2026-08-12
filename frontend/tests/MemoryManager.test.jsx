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

  it("does not offer role as a memory kind (roles live in Settings) and hides role entries", () => {
    render(
      <MemoryManager
        open
        activeMode="Cowork"
        entries={[
          { id: "r1", kind: "role", text: "A global role" },
          { id: "m1", kind: "preference", text: "A chat preference" },
        ]}
      />,
    );

    expect(screen.queryByRole("option", { name: "Role" })).toBeNull();
    expect(screen.queryByText("A global role")).toBeNull();
    expect(screen.getByText("A chat preference")).toBeTruthy();
  });
});
