function formatCoworkTime(timestamp) {
  const date = new Date(timestamp);
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

export function normalizeCoworkRole(role) {
  const upperRole = (role ?? "AI").toUpperCase();
  if (upperRole === "USER") {
    return "user";
  }
  if (upperRole === "SYSTEM") {
    return "system";
  }
  return "ai";
}

export function createCoworkMessage(role, text, timestamp = new Date().toISOString(), modelLabel) {
  return {
    role,
    text,
    time: formatCoworkTime(timestamp),
    timestamp,
    modelLabel: typeof modelLabel === "string" && modelLabel.trim() ? modelLabel.trim() : undefined,
  };
}

export function buildCoworkPrompt(prompt, workingDirectory) {
  if (!workingDirectory) {
    return prompt;
  }

  return `[Target Working Directory: ${workingDirectory}]\n${prompt}`;
}

export function buildCoworkTranscript(messages) {
  return messages.map((message) => `[${message.time}] ${message.role.toUpperCase()}: ${message.text}`).join("\n\n");
}
