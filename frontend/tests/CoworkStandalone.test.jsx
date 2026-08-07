import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CoworkStandalone from "../CoworkStandalone";

describe("CoworkStandalone", () => {
  it("renders a dedicated Cowork surface without the main app shell", () => {
    render(
      <CoworkStandalone
        bridge={{ subscribe: () => () => {} }}
        bridgeState="connected"
        coworkModel="local:qwen/qwen3.5-9b"
        coworkModelLabel="qwen/qwen3.5-9b"
      />,
    );

    expect(screen.getByText(/Good afternoon/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new chat/i })).toBeInTheDocument();
    expect(screen.getByText("Recents")).toBeInTheDocument();
    expect(screen.queryByText("Designer")).not.toBeInTheDocument();
    expect(screen.queryByText("Builder")).not.toBeInTheDocument();
    expect(screen.queryByText("Blender AI Studio Desktop Shell")).not.toBeInTheDocument();
  });
});
