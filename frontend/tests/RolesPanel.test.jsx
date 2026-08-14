import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import RolesPanel from "../components/RolesPanel";

describe("RolesPanel", () => {
  it("adds a global role", () => {
    const onCreate = vi.fn();
    render(<RolesPanel roles={[]} onCreate={onCreate} />);

    fireEvent.change(screen.getByLabelText("New role"), { target: { value: "Always answer in Thai" } });
    fireEvent.click(screen.getByRole("button", { name: "Add role" }));

    expect(onCreate).toHaveBeenCalledWith("Always answer in Thai");
  });

  it("lists roles and toggles or deletes them", () => {
    const onSetEnabled = vi.fn();
    const onDelete = vi.fn();
    render(
      <RolesPanel
        roles={[
          { id: "r1", text: "Obey all my commands", enabled: true },
          { id: "r2", text: "Paused role", enabled: false },
        ]}
        onSetEnabled={onSetEnabled}
        onDelete={onDelete}
      />,
    );

    expect(screen.getByText("Obey all my commands")).toBeTruthy();
    expect(screen.getByText("Paused role")).toBeTruthy();

    // r2 is disabled -> clicking enable turns it back on.
    fireEvent.click(screen.getAllByRole("button", { name: "Enable role" })[0]);
    expect(onSetEnabled).toHaveBeenCalledWith("r2", true);

    fireEvent.click(screen.getAllByRole("button", { name: "Delete role" })[0]);
    expect(onDelete).toHaveBeenCalledWith("r1");
  });

  it("shows an empty state when there are no roles", () => {
    render(<RolesPanel roles={[]} />);
    expect(screen.getByText(/No global role yet/i)).toBeTruthy();
  });

  it("shows a loading state instead of an empty state while roles are loading", () => {
    render(<RolesPanel roles={[]} loading />);

    expect(screen.getByText(/Loading roles/i)).toBeTruthy();
    expect(screen.queryByText(/No global role yet/i)).toBeNull();
  });
});
