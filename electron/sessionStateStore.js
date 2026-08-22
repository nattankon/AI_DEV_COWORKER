import fs from "node:fs";
import path from "node:path";

const SESSION_STATE_FILE = "session-history.json";
const SESSION_STATE_BACKUP_FILE = "session-history.json.bak";

function validateEnvelope(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  if (value.schemaVersion !== 4 || typeof value.savedAt !== "string" || Number.isNaN(Date.parse(value.savedAt))) return null;
  if (!value.state || typeof value.state !== "object" || Array.isArray(value.state)) return null;
  if (!Array.isArray(value.state.sessions)) return null;
  if (!value.state.eventsBySessionId || typeof value.state.eventsBySessionId !== "object") return null;
  return value;
}

function readEnvelope(filePath) {
  try {
    return validateEnvelope(JSON.parse(fs.readFileSync(filePath, "utf8")));
  } catch {
    return null;
  }
}

export function createSessionStateStore({ directory }) {
  if (typeof directory !== "string" || !directory.trim()) {
    throw new TypeError("Session state directory is required.");
  }
  const primaryPath = path.join(directory, SESSION_STATE_FILE);
  const backupPath = path.join(directory, SESSION_STATE_BACKUP_FILE);
  const temporaryPath = path.join(directory, `${SESSION_STATE_FILE}.tmp`);

  return {
    load() {
      const primary = readEnvelope(primaryPath);
      if (primary) return { ok: true, envelope: primary, source: "primary" };
      const backup = readEnvelope(backupPath);
      if (backup) return { ok: true, envelope: backup, source: "backup" };
      return { ok: true, envelope: null, source: "none" };
    },

    save(candidate) {
      const envelope = validateEnvelope(candidate);
      if (!envelope) return { ok: false, error: "Invalid session state envelope." };
      try {
        fs.mkdirSync(directory, { recursive: true });
        fs.writeFileSync(temporaryPath, JSON.stringify(envelope), "utf8");
        const current = readEnvelope(primaryPath);
        if (current) fs.copyFileSync(primaryPath, backupPath);
        fs.rmSync(primaryPath, { force: true });
        fs.renameSync(temporaryPath, primaryPath);
        if (!readEnvelope(backupPath)) fs.copyFileSync(primaryPath, backupPath);
        return { ok: true };
      } catch (error) {
        try {
          fs.rmSync(temporaryPath, { force: true });
        } catch {
          // Keep the original error; cleanup is best-effort.
        }
        return { ok: false, error: error instanceof Error ? error.message : String(error) };
      }
    },
  };
}
