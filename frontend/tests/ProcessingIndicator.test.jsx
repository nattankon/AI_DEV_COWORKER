import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ProcessingIndicator from "../components/ProcessingIndicator";

describe("ProcessingIndicator", () => {
  afterEach(() => vi.useRealTimers());

  it("starts with Thinking and then shows elapsed working time", () => {
    vi.useFakeTimers();
    render(<ProcessingIndicator active />);

    expect(screen.getByText("Thinking")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(11_000));
    expect(screen.getByText("Working for 11s")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(60_000));
    expect(screen.getByText("Working for 1m 11s")).toBeInTheDocument();
  });

  it("renders nothing while idle or waiting for approval", () => {
    const { rerender } = render(<ProcessingIndicator active={false} />);
    expect(screen.queryByText("Thinking")).not.toBeInTheDocument();

    rerender(<ProcessingIndicator active waitingForApproval />);
    expect(screen.queryByText("Thinking")).not.toBeInTheDocument();
  });

  it("shows transient research status instead of the generic timer text", () => {
    vi.useFakeTimers();
    render(<ProcessingIndicator active statusText="📄 Reading: example.test" />);

    expect(screen.getByText("📄 Reading: example.test")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(11_000));
    expect(screen.queryByText("Working for 11s")).not.toBeInTheDocument();
    expect(screen.getByText("📄 Reading: example.test")).toBeInTheDocument();
  });
});
