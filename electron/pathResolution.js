import path from "node:path";

export function getPythonEntryCandidates({ appRoot, resourcesPath, env = process.env }) {
  return [
    env.COWORK_PYTHON_ENTRY,
    resourcesPath ? path.join(resourcesPath, "cowork-sidecar", "AI_DEV_COWORKER", "ipc_sidecar.py") : undefined,
    path.join(appRoot, "ipc_sidecar.py"),
  ].filter(Boolean);
}

export function getSidecarPythonPathCandidates({ appRoot, resourcesPath }) {
  return [
    resourcesPath ? path.join(resourcesPath, "cowork-sidecar") : undefined,
    path.resolve(appRoot, ".."),
  ].filter(Boolean);
}
