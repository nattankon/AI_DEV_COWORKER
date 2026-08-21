import { describe, expect, it } from "vitest";
import {
  CHATGPT_WEB_URL,
  WEB_CHAT_PARTITION,
  normalizeWebChatBounds,
  sanitizeWebChatCommand,
} from "../../electron/webChatSurface.js";

describe("webChatSurface", () => {
  it("uses the real ChatGPT URL and a dedicated persistent partition", () => {
    expect(CHATGPT_WEB_URL).toBe("https://chatgpt.com/");
    expect(WEB_CHAT_PARTITION).toBe("persist:web-chat");
  });

  it("rounds and clamps renderer bounds before applying them to a native view", () => {
    expect(normalizeWebChatBounds({ x: 286.4, y: 82.6, width: 900.8, height: 600.2 })).toEqual({
      x: 286,
      y: 83,
      width: 901,
      height: 600,
    });
    expect(normalizeWebChatBounds({ x: -5, y: -2, width: 0, height: -4 })).toEqual({
      x: 0,
      y: 0,
      width: 1,
      height: 1,
    });
  });

  it("allows only the fixed navigation command set", () => {
    expect(sanitizeWebChatCommand("reload")).toBe("reload");
    expect(sanitizeWebChatCommand("back")).toBe("back");
    expect(sanitizeWebChatCommand("read-cookies")).toBe("");
    expect(sanitizeWebChatCommand("https://example.com")).toBe("");
  });
});
