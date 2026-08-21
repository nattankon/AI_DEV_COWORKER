import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PermissionModeMenu from "../components/PermissionModeMenu";


describe("PermissionModeMenu", () => {
  it("shows three truthful permission profiles and the enforced project boundary", () => {
    render(<PermissionModeMenu mode="manual" workspaceLabel="scilp" onChange={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Permission mode: Manual control" }));

    expect(screen.getByRole("menu", { name: "Permission mode" })).toBeInTheDocument();
    expect(screen.getByRole("menuitemradio", { name: /Manual control/ })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("menuitemradio", { name: /Approvals only/ })).toBeInTheDocument();
    expect(screen.getByRole("menuitemradio", { name: /Full access/ })).toBeInTheDocument();
    expect(screen.getByText(/Project boundary: scilp/)).toBeInTheDocument();
    expect(screen.getByText(/Secret Guard remain enforced/)).toBeInTheDocument();
  });

  it("reports the selected mode without changing it locally", () => {
    const onChange = vi.fn();
    render(<PermissionModeMenu mode="manual" workspaceLabel="scilp" onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: "Permission mode: Manual control" }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: /Approvals only/ }));

    expect(onChange).toHaveBeenCalledWith("trusted");
  });
});
