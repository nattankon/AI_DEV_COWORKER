import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AppHeader from "../components/AppHeader";

describe("AppHeader update control", () => {
  it("shows nothing when there is no update", () => {
    render(<AppHeader appUpdate={{ state: "idle" }} onInstallUpdate={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /Install update/i })).not.toBeInTheDocument();
  });

  it("shows a spinner with percent while downloading", () => {
    render(<AppHeader appUpdate={{ state: "downloading", percent: 42 }} onInstallUpdate={vi.fn()} />);
    expect(screen.getByText("42%")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Install update/i })).not.toBeInTheDocument();
  });

  it("shows a clickable Update button when ready and installs on click", () => {
    const onInstallUpdate = vi.fn();
    render(<AppHeader appUpdate={{ state: "ready", version: "0.1.3" }} onInstallUpdate={onInstallUpdate} />);

    const button = screen.getByRole("button", { name: /Install update v0.1.3 and restart/i });
    expect(button).toBeInTheDocument();
    expect(screen.getByText("Update v0.1.3")).toBeInTheDocument();
    fireEvent.click(button);
    expect(onInstallUpdate).toHaveBeenCalled();
  });
});
