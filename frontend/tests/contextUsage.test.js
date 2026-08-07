import { describe, expect, it } from "vitest";
import { buildContextUsage, estimateTextTokens, resolveContextWindow } from "../model/contextUsage";

describe("contextUsage", () => {
  it("resolves the context window from the selected provider model metadata", () => {
    const providers = [
      {
        id: "zai",
        models: [
          { id: "zai:glm-4.5-flash", label: "GLM-4.5-Flash", context_window_tokens: 131072 },
        ],
      },
    ];

    expect(resolveContextWindow("zai:glm-4.5-flash", providers)).toBe(131072);
  });

  it("estimates Thai and English session usage without requiring provider usage data", () => {
    expect(estimateTextTokens("สวัสดี hello")).toBeGreaterThan(1);
    const usage = buildContextUsage({
      modelLabel: "zai:glm-4.5-flash",
      modelProviders: [{ id: "zai", models: [{ id: "zai:glm-4.5-flash", context_window_tokens: 100 }] }],
      events: [
        { type: "message.user", payload: { text: "สวัสดีครับ" } },
        { type: "message.assistant", payload: { text: "Hello, how can I help?" } },
        { type: "agent.status", payload: { text: "busy" } },
      ],
    });

    expect(usage.usedTokens).toBeGreaterThan(1);
    expect(usage.contextWindowTokens).toBe(100);
    expect(usage.percentFull).toBeGreaterThan(0);
    expect(usage.title).toContain("Estimated from this session");
  });

  it("reports an unknown context window when the selected model lacks metadata", () => {
    const usage = buildContextUsage({
      modelLabel: "local:qwen/qwen3.5-9b",
      modelProviders: [],
      events: [{ type: "message.user", payload: { text: "test" } }],
    });

    expect(usage.contextWindowTokens).toBeNull();
    expect(usage.percentFull).toBeNull();
    expect(usage.windowLabel).toBe("unknown");
    expect(usage.title).toContain("Context window unknown");
  });
});
