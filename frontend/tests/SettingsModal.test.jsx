import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SettingsModal from "../components/SettingsModal";

describe("SettingsModal", () => {
  it("requests a role refresh when the Role settings section opens", () => {
    const onRefreshRoles = vi.fn();
    render(<SettingsModal open onRefreshRoles={onRefreshRoles} />);

    fireEvent.click(screen.getByRole("button", { name: "Role" }));

    expect(onRefreshRoles).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Refresh roles" })).toBeInTheDocument();
  });
});
