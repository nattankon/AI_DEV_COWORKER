const CONTEXT_WINDOW_FIELDS = [
  "context_window_tokens",
  "contextWindowTokens",
  "context_window",
  "contextWindow",
  "max_context_tokens",
  "maxContextTokens",
  "input_token_limit",
  "inputTokenLimit",
];

function normalizeModelId(modelLabel = "") {
  const value = String(modelLabel || "").trim();
  if (!value) return "";
  return /^(local|openai|deepseek|zai|gemini):/.test(value) ? value : `local:${value}`;
}

function compactTokens(value) {
  const tokens = Math.max(0, Math.round(Number(value) || 0));
  if (tokens >= 1_000_000) return `${Number((tokens / 1_000_000).toFixed(1))}m`;
  if (tokens >= 1000) return `${Math.round(tokens / 1000)}k`;
  return String(tokens);
}

function numericField(source, fields) {
  for (const field of fields) {
    const value = Number(source?.[field]);
    if (Number.isFinite(value) && value > 0) return Math.round(value);
  }
  return null;
}

export function estimateTextTokens(text = "") {
  const value = String(text || "");
  if (!value) return 0;
  const thaiChars = (value.match(/[\u0E00-\u0E7F]/g) || []).length;
  const nonWhitespaceChars = (value.match(/\S/g) || []).length;
  const thaiEstimate = Math.ceil(thaiChars / 1.6);
  const remainingEstimate = Math.ceil(Math.max(0, nonWhitespaceChars - thaiChars) / 4);
  return Math.max(1, thaiEstimate + remainingEstimate);
}

export function estimateTimelineTokens(events = []) {
  if (!Array.isArray(events)) return 0;
  return events.reduce((total, event) => {
    const type = String(event?.type || "");
    if (!type.startsWith("message.")) return total;
    const text = event?.payload?.text;
    if (typeof text !== "string" || !text.trim()) return total;
    return total + estimateTextTokens(text);
  }, 0);
}

export function resolveContextWindow(modelLabel, modelProviders = []) {
  const normalized = normalizeModelId(modelLabel);
  const raw = String(modelLabel || "").trim();
  const providers = Array.isArray(modelProviders) ? modelProviders : [];
  for (const provider of providers) {
    for (const model of Array.isArray(provider?.models) ? provider.models : []) {
      const modelIds = [model?.id, normalizeModelId(model?.id), model?.label].map((item) => String(item || "").trim());
      if (!modelIds.includes(normalized) && !modelIds.includes(raw)) continue;
      return numericField(model, CONTEXT_WINDOW_FIELDS);
    }
  }
  return null;
}

export function buildContextUsage({ events = [], modelLabel = "", modelProviders = [] } = {}) {
  const usedTokens = estimateTimelineTokens(events);
  const contextWindowTokens = resolveContextWindow(modelLabel, modelProviders);
  const percentFull = contextWindowTokens
    ? Math.min(999, Math.round((usedTokens / contextWindowTokens) * 100))
    : null;
  const usedLabel = compactTokens(usedTokens);
  const windowLabel = contextWindowTokens ? compactTokens(contextWindowTokens) : "unknown";
  const title = contextWindowTokens
    ? `Context window:\n${percentFull}% full\n${usedLabel} / ${windowLabel} tokens used\nEstimated from this session; actual provider tokenization may differ.`
    : `Context window unknown for ${modelLabel || "selected model"}.\n${usedLabel} tokens estimated from this session.\nAdd context_window_tokens to model metadata for an exact window.`;

  return {
    contextWindowTokens,
    percentFull,
    usedTokens,
    usedLabel,
    windowLabel,
    title,
  };
}
