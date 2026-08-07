import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import QualityEvalPanel from "../components/QualityEvalPanel";

describe("QualityEvalPanel", () => {
  it("renders fixture cases and snapshot metrics", () => {
    const onRefresh = vi.fn();
    const onRunSnapshot = vi.fn();
    render(
      <QualityEvalPanel
        state={{
          count: 2,
          cases: [
            { category: "web", prompt: "Find current API docs", checks: ["cites sources"] },
            { category: "thai", prompt: "ตอบภาษาไทย", checks: ["keeps Thai answer language"] },
          ],
          snapshot: {
            count: 2,
            passed: 1,
            failed: 1,
            status: "fail",
            results: [
              { category: "web", prompt: "Find current API docs", status: "pass", score: 4, findings: [] },
              { category: "thai", prompt: "ตอบภาษาไทย", status: "fail", score: 1, findings: ["empty answer"] },
            ],
          },
        }}
        onRefresh={onRefresh}
        onRunSnapshot={onRunSnapshot}
      />,
    );

    expect(screen.getByRole("heading", { name: "Evaluation snapshot" })).toBeInTheDocument();
    expect(screen.getByText("Find current API docs")).toBeInTheDocument();
    expect(screen.getByText("ตอบภาษาไทย")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("empty answer")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    fireEvent.click(screen.getByRole("button", { name: "Run snapshot" }));

    expect(onRefresh).toHaveBeenCalledOnce();
    expect(onRunSnapshot).toHaveBeenCalledWith({ results: [] });
  });

  it("requires explicit confirmation before requesting a live matrix", () => {
    const onRunLive = vi.fn();
    render(
      <QualityEvalPanel
        state={{
          count: 1,
          cases: [{ category: "thai", prompt: "ตอบไทย", checks: [] }],
          live_matrix: {
            summary: { total_cells: 1, pass_rate: 1, avg_latency_ms: 1200, hallucination_rate: 0, source_quality_rate: 1 },
            cells: [{ model: "zai:glm-4.5-flash", category: "thai", status: "pass", latency_ms: 1200 }],
          },
        }}
        modelProviders={[{ id: "zai", models: [{ id: "zai:glm-4.5-flash", label: "GLM-4.5-Flash" }] }]}
        onRunLive={onRunLive}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Run live matrix" }));
    expect(onRunLive).not.toHaveBeenCalled();
    expect(screen.getByText("Confirm live model/API calls before running.")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Confirm live model/API calls"));
    fireEvent.click(screen.getByRole("button", { name: "Run live matrix" }));

    expect(onRunLive).toHaveBeenCalledWith(expect.objectContaining({
      live: true,
      confirmed: true,
      models: ["zai:glm-4.5-flash"],
      categories: ["thai"],
    }));
    expect(screen.getByText("Live matrix")).toBeInTheDocument();
    expect(screen.getByText("zai:glm-4.5-flash")).toBeInTheDocument();
  });

  it("renders web source profile and Thai text diagnostics", () => {
    render(
      <QualityEvalPanel
        state={{
          count: 0,
          cases: [],
          source_profile: {
            domains: {
              "good.example": { runs: 2, success_rate: 1, avg_quality_score: 4.5 },
              "blocked.example": { runs: 1, success_rate: 0, avg_quality_score: 0 },
            },
          },
          text_diagnostics: {
            status: "warning",
            runtime: { stdout_encoding: "utf-8", filesystem_encoding: "utf-8" },
            findings: [{ layer: "latest.jsonl:0", marker: "喔", sample: "喔曕腑" }],
          },
        }}
      />,
    );

    expect(screen.getByText("Web source profile")).toBeInTheDocument();
    expect(screen.getByText("good.example")).toBeInTheDocument();
    expect(screen.getByText("2 runs")).toBeInTheDocument();
    expect(screen.getByText("Thai text diagnostics")).toBeInTheDocument();
    expect(screen.getByText("Status: warning")).toBeInTheDocument();
    expect(screen.getByText("latest.jsonl:0: marker 喔")).toBeInTheDocument();
  });
});
