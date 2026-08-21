export const CHATGPT_WEB_URL = "https://chatgpt.com/";
export const WEB_CHAT_PARTITION = "persist:web-chat";

const WEB_CHAT_COMMANDS = new Set(["back", "forward", "reload", "home", "open-external"]);

function finiteNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

export function normalizeWebChatBounds(bounds) {
  const source = bounds && typeof bounds === "object" && !Array.isArray(bounds) ? bounds : {};
  return {
    x: Math.max(0, Math.round(finiteNumber(source.x))),
    y: Math.max(0, Math.round(finiteNumber(source.y))),
    width: Math.max(1, Math.round(finiteNumber(source.width, 1))),
    height: Math.max(1, Math.round(finiteNumber(source.height, 1))),
  };
}

export function sanitizeWebChatCommand(command) {
  const normalized = String(command || "").trim().toLowerCase();
  return WEB_CHAT_COMMANDS.has(normalized) ? normalized : "";
}

export function isSafeExternalWebUrl(url) {
  try {
    const parsed = new URL(String(url || ""));
    return parsed.protocol === "https:" || parsed.protocol === "http:";
  } catch {
    return false;
  }
}
