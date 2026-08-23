import fs from "node:fs";
import path from "node:path";

export function readDevToolsPort(profile) {
  const activePortPath = path.join(profile, "DevToolsActivePort");
  try {
    const [line] = fs.readFileSync(activePortPath, "utf8").split(/\r?\n/);
    const port = Number.parseInt(line, 10);
    return Number.isInteger(port) && port > 0 && port <= 65_535 ? port : null;
  } catch {
    return null;
  }
}
