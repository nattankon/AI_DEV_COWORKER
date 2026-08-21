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

    // all known providers appear, with their status
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("DeepSeek")).toBeInTheDocument();
    expect(screen.getByText("Z.ai")).toBeInTheDocument();
    expect(screen.getByText("Gemini")).toBeInTheDocument();
    expect(screen.getByText("Anthropic / Claude")).toBeInTheDocument();
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

  it("lets the user reveal a pasted key temporarily", () => {
    render(<ProvidersPanel modelProviders={modelProviders} onSaveProviderKey={vi.fn()} onRefreshProviders={vi.fn()} />);
    const input = screen.getByLabelText("Anthropic / Claude API key");
    expect(input).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByRole("button", { name: "Show Anthropic / Claude key" }));
    expect(input).toHaveAttribute("type", "text");
    fireEvent.click(screen.getByRole("button", { name: "Hide Anthropic / Claude key" }));
    expect(input).toHaveAttribute("type", "password");
  });

  it("configures and imports a custom Anthropic-compatible provider", () => {
    const onSaveCustomProvider = vi.fn();
    const onImportCustomModels = vi.fn();
    render(
      <ProvidersPanel
        modelProviders={[
          ...modelProviders,
          {
            id: "anthropic_compatible",
            label: "Custom Anthropic-compatible",
            configured: true,
            base_url: "https://proxy.example.com/v1",
            preset_id: "custom",
            protocol: "anthropic_messages",
            auth_scheme: "x_api_key",
            models_auth_scheme: "bearer",
            presets: [
              { id: "mwapi", label: "MWAPI", base_url: "https://api.mwapi.dev/v1", protocol: "anthropic_messages", auth_scheme: "x_api_key", models_auth_scheme: "bearer" },
              { id: "openrouter", label: "OpenRouter", base_url: "https://openrouter.ai/api/v1", protocol: "anthropic_messages", auth_scheme: "bearer", models_auth_scheme: "bearer" },
              { id: "custom", label: "Custom endpoint", base_url: "", protocol: "anthropic_messages", auth_scheme: "x_api_key", models_auth_scheme: "bearer" },
            ],
            models: [{ id: "anthropic-compatible:claude-sonnet-5", label: "claude-sonnet-5" }],
          },
        ]}
        onSaveProviderKey={vi.fn()}
        onSaveCustomProvider={onSaveCustomProvider}
        onImportCustomModels={onImportCustomModels}
        onRefreshProviders={vi.fn()}
      />,
    );

    expect(screen.getByDisplayValue("https://proxy.example.com/v1")).toBeInTheDocument();
    expect(screen.getByText("1 imported model")).toBeInTheDocument();
    expect(screen.getByLabelText("Compatible provider preset")).toHaveValue("custom");
    fireEvent.change(screen.getByLabelText("Custom Anthropic-compatible API key"), { target: { value: "custom-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Save custom Anthropic-compatible provider" }));
    expect(onSaveCustomProvider).toHaveBeenCalledWith({
      presetId: "custom",
      baseUrl: "https://proxy.example.com/v1",
      protocol: "anthropic_messages",
      authScheme: "x_api_key",
      modelsAuthScheme: "bearer",
      key: "custom-secret",
    });

    fireEvent.change(screen.getByLabelText("Custom Anthropic-compatible API key"), { target: { value: "another-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Test and import custom Anthropic-compatible models" }));
    expect(onImportCustomModels).toHaveBeenCalledWith(expect.objectContaining({ baseUrl: "https://proxy.example.com/v1", key: "another-secret" }));
  });

  it("fills required fields from a provider preset and still allows custom values", () => {
    const onSaveCustomProvider = vi.fn();
    render(
      <ProvidersPanel
        modelProviders={[
          ...modelProviders,
          {
            id: "anthropic_compatible",
            configured: false,
            base_url: "",
            preset_id: "custom",
            protocol: "anthropic_messages",
            auth_scheme: "x_api_key",
            models_auth_scheme: "bearer",
            presets: [
              { id: "mwapi", label: "MWAPI", base_url: "https://api.mwapi.dev/v1", protocol: "anthropic_messages", auth_scheme: "x_api_key", models_auth_scheme: "bearer" },
              { id: "groq", label: "Groq", base_url: "https://api.groq.com/openai/v1", protocol: "openai_chat_completions", auth_scheme: "bearer", models_auth_scheme: "bearer" },
              { id: "custom", label: "Custom endpoint", base_url: "", protocol: "anthropic_messages", auth_scheme: "x_api_key", models_auth_scheme: "bearer" },
            ],
            models: [],
          },
        ]}
        onSaveProviderKey={vi.fn()}
        onSaveCustomProvider={onSaveCustomProvider}
        onImportCustomModels={vi.fn()}
        onRefreshProviders={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Compatible provider preset"), { target: { value: "groq" } });
    expect(screen.getByLabelText("Custom Anthropic-compatible Base URL")).toHaveValue("https://api.groq.com/openai/v1");
    expect(screen.getByLabelText("Compatible API protocol")).toHaveValue("openai_chat_completions");
    expect(screen.getByLabelText("Request authentication")).toHaveValue("bearer");

    fireEvent.change(screen.getByLabelText("Custom Anthropic-compatible API key"), { target: { value: "groq-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Save custom Anthropic-compatible provider" }));
    expect(onSaveCustomProvider).toHaveBeenCalledWith(expect.objectContaining({
      presetId: "groq",
      baseUrl: "https://api.groq.com/openai/v1",
      protocol: "openai_chat_completions",
      authScheme: "bearer",
      modelsAuthScheme: "bearer",
    }));

    fireEvent.change(screen.getByLabelText("Compatible provider preset"), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText("Compatible API protocol"), { target: { value: "anthropic_messages" } });
    expect(screen.getByLabelText("Custom Anthropic-compatible Base URL")).toHaveValue("");
  });
});
