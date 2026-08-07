import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ModelMenu from "../components/ModelMenu";

describe("ModelMenu", () => {
  const providers = [
    {
      id: "zai",
      label: "Z.ai",
      configured: true,
      models: [
        { id: "zai:glm-4.5-flash", label: "GLM-4.5-Flash", badge: "Free / Reasoning", recommended: true, default_model: true },
        { id: "zai:glm-4.7-flash", label: "GLM-4.7-Flash", badge: "Free / Limited" },
      ],
    },
    {
      id: "deepseek",
      label: "DeepSeek",
      configured: true,
      models: [{ id: "deepseek:deepseek-v4-flash", label: "DeepSeek V4 Flash", badge: "Fast / Coding", recommended: true }],
    },
  ];

  it("opens to recommended models and provider headings instead of a long flat list", () => {
    render(
      <ModelMenu
        effort="Medium"
        modelLabel="zai:glm-4.5-flash"
        modelProviders={providers}
        onModelChange={vi.fn()}
        onEffortChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Model and effort" }));

    expect(screen.getByText("Recommended")).toBeInTheDocument();
    expect(screen.getByText("Free default")).toBeInTheDocument();
    expect(screen.getByText("DeepSeek V4 Flash")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /Z.ai ready/i })).toBeInTheDocument();
    expect(screen.queryByRole("menuitemradio", { name: /GLM-4.7-Flash/i })).not.toBeInTheDocument();
  });

  it("opens a provider submenu before showing the rest of that provider's models", () => {
    const onModelChange = vi.fn();
    render(
      <ModelMenu
        effort="Medium"
        modelLabel="zai:glm-4.5-flash"
        modelProviders={providers}
        onModelChange={onModelChange}
        onEffortChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Model and effort" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Z.ai ready/i }));

    const submenu = screen.getByRole("menu", { name: "Z.ai models" });
    fireEvent.click(within(submenu).getByRole("menuitemradio", { name: /GLM-4.7-Flash/i }));

    expect(onModelChange).toHaveBeenCalledWith("zai:glm-4.7-flash");
  });

  it("shows key status and saves a pasted key for a provider", () => {
    const onSaveProviderKey = vi.fn();
    const onRefreshProviders = vi.fn();
    const withMissing = [
      { id: "openai", label: "OpenAI", configured: false, models: [{ id: "openai:gpt-x", label: "GPT-X" }] },
      ...providers,
    ];
    render(
      <ModelMenu
        effort="Medium"
        modelLabel="zai:glm-4.5-flash"
        modelProviders={withMissing}
        onModelChange={vi.fn()}
        onEffortChange={vi.fn()}
        onSaveProviderKey={onSaveProviderKey}
        onRefreshProviders={onRefreshProviders}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Model and effort" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /OpenAI no key/i }));

    // status reflects the missing key, and there is a masked input + save
    expect(screen.getByText("No key yet")).toBeInTheDocument();
    const input = screen.getByLabelText("OpenAI API key");
    expect(input).toHaveAttribute("type", "password");
    fireEvent.change(input, { target: { value: "sk-proj-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Save OpenAI key" }));

    expect(onSaveProviderKey).toHaveBeenCalledWith("openai", "sk-proj-secret");

    fireEvent.click(screen.getByRole("button", { name: "Refresh provider keys" }));
    expect(onRefreshProviders).toHaveBeenCalled();
  });

  it("closes when clicking anywhere outside the menu", () => {
    render(
      <ModelMenu
        effort="Medium"
        modelLabel="zai:glm-4.5-flash"
        modelProviders={providers}
        onModelChange={vi.fn()}
        onEffortChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Model and effort" }));
    expect(screen.getByRole("menu", { name: "Model choices" })).toBeInTheDocument();

    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("menu", { name: "Model choices" })).not.toBeInTheDocument();
  });

  it("closes on Escape", () => {
    render(
      <ModelMenu
        effort="Medium"
        modelLabel="zai:glm-4.5-flash"
        modelProviders={providers}
        onModelChange={vi.fn()}
        onEffortChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Model and effort" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu", { name: "Model choices" })).not.toBeInTheDocument();
  });

  it("shows a saved-key status for a configured provider", () => {
    render(
      <ModelMenu
        effort="Medium"
        modelLabel="zai:glm-4.5-flash"
        modelProviders={providers}
        onModelChange={vi.fn()}
        onEffortChange={vi.fn()}
        onSaveProviderKey={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Model and effort" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Z.ai ready/i }));

    expect(screen.getByText("✓ Key saved")).toBeInTheDocument();
  });
});
