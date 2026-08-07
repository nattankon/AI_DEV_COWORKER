import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ApprovalPrompt from "../components/ApprovalPrompt";

describe("ApprovalPrompt", () => {
  it("renders v2 risk metadata and full payload details", () => {
    const onDecision = vi.fn();
    render(
      <ApprovalPrompt
        event={{
          payload: {
            title: "Approve running Chat Python code",
            question: "Approve running Chat Python code?",
            proposal: {
              risk_level: "code",
              risk_summary: "Runs code in an experimental subprocess sandbox.",
              subject: "Python code execution",
              default_decision: "deny",
              details: {
                sandbox_level: "subprocess_tempdir_experimental",
                network_isolation: "best_effort_static_check",
              },
              full_payload: {
                full_code: "print('hello')",
              },
            },
          },
        }}
        onDecision={onDecision}
      />,
    );

    expect(screen.getByText("Risk: code")).toBeInTheDocument();
    expect(screen.getByText(/experimental subprocess sandbox/i)).toBeInTheDocument();
    expect(screen.getByText(/Default: deny/i)).toBeInTheDocument();
    expect(screen.getByText(/subprocess_tempdir_experimental/)).toBeInTheDocument();
    expect(screen.getByText(/print\('hello'\)/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Deny" }));
    expect(onDecision).toHaveBeenCalledWith("deny");
  });
});
