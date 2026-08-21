import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export const WEB_CHAT_PERMISSION_MODES = Object.freeze(["manual", "trusted", "full"]);

const permissionModes = new Set(WEB_CHAT_PERMISSION_MODES);

function emptyDocument(revision = 0) {
  return { version: 1, revision, grant: null };
}

function publicState(document) {
  return {
    revision: document.revision,
    grant: document.grant ? { ...document.grant } : null,
    toolsEnabled: false,
    tunnelConnected: false,
  };
}

function normalizePermissionMode(value) {
  const mode = String(value || "").trim().toLowerCase();
  if (!permissionModes.has(mode)) throw new TypeError("Unsupported Web Chat permission profile.");
  return mode;
}

function normalizeWorkspaceName(value, workspacePath) {
  const name = String(value || "").trim().slice(0, 160);
  return name || path.basename(workspacePath) || workspacePath;
}

function normalizeStoredDocument(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return emptyDocument();
  const revision = Number.isSafeInteger(value.revision) && value.revision >= 0 ? value.revision : 0;
  const grant = value.grant;
  if (!grant || typeof grant !== "object" || Array.isArray(grant)) return emptyDocument(revision);
  const workspacePath = String(grant.workspacePath || "").trim();
  const permissionMode = String(grant.permissionMode || "").trim();
  if (!workspacePath || !permissionModes.has(permissionMode)) return emptyDocument(revision);
  try {
    if (!fs.statSync(workspacePath).isDirectory()) return emptyDocument(revision);
  } catch {
    return emptyDocument(revision);
  }
  return {
    version: 1,
    revision,
    grant: {
      id: String(grant.id || ""),
      workspacePath,
      workspaceName: normalizeWorkspaceName(grant.workspaceName, workspacePath),
      permissionMode,
      grantedAt: String(grant.grantedAt || ""),
    },
  };
}

export class WebChatGrantStore {
  constructor({ filePath }) {
    if (!filePath) throw new TypeError("Web Chat grant store requires a file path.");
    this.filePath = path.resolve(filePath);
  }

  _read() {
    try {
      return normalizeStoredDocument(JSON.parse(fs.readFileSync(this.filePath, "utf8")));
    } catch {
      return emptyDocument();
    }
  }

  _write(document) {
    fs.mkdirSync(path.dirname(this.filePath), { recursive: true });
    const temporaryPath = `${this.filePath}.${process.pid}.${Date.now()}.tmp`;
    fs.writeFileSync(temporaryPath, `${JSON.stringify(document, null, 2)}\n`, "utf8");
    try {
      fs.renameSync(temporaryPath, this.filePath);
    } catch {
      fs.copyFileSync(temporaryPath, this.filePath);
      fs.rmSync(temporaryPath, { force: true });
    }
    return document;
  }

  getState() {
    return publicState(this._read());
  }

  setGrant(payload) {
    const input = payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
    const permissionMode = normalizePermissionMode(input.permissionMode);
    const requestedPath = String(input.workspacePath || "").trim();
    if (!requestedPath) throw new TypeError("Workspace directory is required.");

    let workspacePath;
    try {
      workspacePath = fs.realpathSync(path.resolve(requestedPath));
      if (!fs.statSync(workspacePath).isDirectory()) throw new TypeError("Workspace path is not a directory.");
    } catch (error) {
      if (error instanceof TypeError) throw error;
      throw new TypeError("Workspace path must be a real directory.");
    }

    const workspaceName = normalizeWorkspaceName(input.workspaceName, workspacePath);
    let document = this._read();
    if (
      document.grant?.workspacePath === workspacePath
      && document.grant?.workspaceName === workspaceName
      && document.grant?.permissionMode === permissionMode
    ) {
      return publicState(document);
    }

    // Persist revocation first so a crash cannot leave two logical grants active.
    if (document.grant) {
      document = this._write(emptyDocument(document.revision + 1));
    }
    document = this._write({
      version: 1,
      revision: document.revision + 1,
      grant: {
        id: crypto.randomUUID(),
        workspacePath,
        workspaceName,
        permissionMode,
        grantedAt: new Date().toISOString(),
      },
    });
    return publicState(document);
  }

  revoke() {
    const document = this._read();
    if (!document.grant) return publicState(document);
    return publicState(this._write(emptyDocument(document.revision + 1)));
  }
}
