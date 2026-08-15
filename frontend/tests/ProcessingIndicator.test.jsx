import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ProcessingIndicator from "../components/ProcessingIndicator";

describe("ProcessingIndicator", () => {
  afterEach(() => vi.useRealTimers());

  it("shows total request duration and rotates truthful generic progress while active", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-15T00:00:00.000Z"));
    render(<ProcessingIndicator active startedAt="2026-08-15T00:00:00.000Z" />);

    expect(screen.getByText("Working for 0s · Thinking through your request...")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(4_000));
    expect(screen.getByText("Working for 4s · Preparing the response...")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(60_000));
    expect(screen.getByText("Working for 1m 4s · Thinking through your request...")).toBeInTheDocument();
  });

  it("renders nothing while idle or waiting for approval", () => {
    const { rerender } = render(<ProcessingIndicator active={false} />);
    expect(screen.queryByText(/Working for/)).not.toBeInTheDocument();

    rerender(<ProcessingIndicator active waitingForApproval />);
    expect(screen.queryByText(/Working for/)).not.toBeInTheDocument();
  });

  it("keeps total elapsed time when a real backend status replaces generic progress", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-15T00:00:00.000Z"));
    const { rerender } = render(<ProcessingIndicator active startedAt="2026-08-15T00:00:00.000Z" />);

    act(() => vi.advanceTimersByTime(5_000));
    rerender(<ProcessingIndicator active startedAt="2026-08-15T00:00:00.000Z" statusText="Reading: example.test" />);
    expect(screen.getByText("Working for 5s · Reading: example.test")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(4_000));
    expect(screen.getByText("Working for 9s · Reading: example.test")).toBeInTheDocument();
  });
});
