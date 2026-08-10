import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import VerificationPanel from "../components/VerificationPanel";

describe("VerificationPanel", () => {
  it("renders nothing when no files were changed", () => {
    const { container } = render(
      <VerificationPanel evidence={{ writesPerformed: false, verificationPassed: false, verificationRuns: [] }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing without evidence", () => {
    const { container } = render(<VerificationPanel evidence={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a passing headline and the verification runs", () => {
    render(
      <VerificationPanel
        evidence={{
          writesPerformed: true,
          verificationObserved: true,
          verificationPassed: true,
          verificationRuns: [{ name: "python-tests", status: "passed" }],
        }}
      />,
    );
    expect(screen.getByText(/changes passed verification/i)).toBeInTheDocument();
    expect(screen.getByText("python-tests")).toBeInTheDocument();
    expect(screen.getByText("passed")).toBeInTheDocument();
  });

  it("warns when files changed but verification did not pass", () => {
    render(
      <VerificationPanel
        evidence={{
          writesPerformed: true,
          verificationObserved: true,
          verificationPassed: false,
          verificationRuns: [{ name: "python-tests", status: "failed" }],
        }}
      />,
    );
    expect(screen.getByText(/verification did not pass/i)).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
  });

  it("warns when files changed but nothing was verified", () => {
    render(
      <VerificationPanel
        evidence={{
          writesPerformed: true,
          verificationObserved: false,
          verificationPassed: false,
          verificationRuns: [],
        }}
      />,
    );
    expect(screen.getByText(/not verified/i)).toBeInTheDocument();
    expect(screen.getByText(/No verification preset was run/i)).toBeInTheDocument();
  });
});
