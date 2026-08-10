import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ProvidersPanel from "../components/ProvidersPanel";

describe("ProvidersPanel", () => {
  const modelProviders = [
    { id: "zai", label: "Z.ai", configured: true },
    { id: "openai", label: "OpenAI", configured: false },
  ];

  it("lists all providers with status and saves a pasted key (masked)", () => {
    const onSaveProviderKey = vi.fn();
    render(<ProvidersPanel modelProviders={modelProviders} onSaveProviderKey={onSaveProviderKey} onRefreshProviders={vi.fn()} />);

    // all four known providers appear, with their status
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("DeepSeek")).toBeInTheDocument();
    expect(screen.getByText("Z.ai")).toBeInTheDocument();
    expect(screen.getByText("Gemini")).toBeInTheDocument();
    expect(screen.getAllByText("✓ Key saved").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("No key yet").length).toBeGreaterThanOrEqual(1);

    const input = screen.getByLabelText("OpenAI API key");
    expect(input).toHaveAttribute("type", "password");
    fireEvent.change(input, { target: { value: "sk-proj-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Save OpenAI key" }));

    expect(onSaveProviderKey).toHaveBeenCalledWith("openai", "sk-proj-secret");
    expect(input).toHaveValue(""); // cleared, never re-shown
  });

  it("refreshes provider status on demand", () => {
    const onRefreshProviders = vi.fn();
    render(<ProvidersPanel modelProviders={modelProviders} onSaveProviderKey={vi.fn()} onRefreshProviders={onRefreshProviders} />);

    fireEvent.click(screen.getByRole("button", { name: /Refresh/i }));
    expect(onRefreshProviders).toHaveBeenCalled();
  });

  it("disables save until a key is entered", () => {
    render(<ProvidersPanel modelProviders={modelProviders} onSaveProviderKey={vi.fn()} onRefreshProviders={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Save Gemini key" })).toBeDisabled();
  });
});
