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

  it("shows a Check-for-updates button when idle and checks on click", () => {
    const onCheckForUpdates = vi.fn();
    render(<AppHeader appUpdate={{ state: "idle" }} onInstallUpdate={vi.fn()} onCheckForUpdates={onCheckForUpdates} />);

    const button = screen.getByRole("button", { name: "Check for updates" });
    expect(button).toBeInTheDocument();
    fireEvent.click(button);
    expect(onCheckForUpdates).toHaveBeenCalled();
  });

  it("shows a spinner while checking", () => {
    render(<AppHeader appUpdate={{ state: "checking" }} onInstallUpdate={vi.fn()} onCheckForUpdates={vi.fn()} />);
    expect(screen.getByText("Checking")).toBeInTheDocument();
  });

  it("shows an up-to-date state that can re-check", () => {
    const onCheckForUpdates = vi.fn();
    render(<AppHeader appUpdate={{ state: "uptodate" }} onInstallUpdate={vi.fn()} onCheckForUpdates={onCheckForUpdates} />);
    fireEvent.click(screen.getByRole("button", { name: "Check for updates" }));
    expect(onCheckForUpdates).toHaveBeenCalled();
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
