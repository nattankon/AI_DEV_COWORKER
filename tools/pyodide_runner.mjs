import { loadPyodide } from "pyodide";

const input = await readStdin();
let payload = {};
try {
  payload = JSON.parse(input || "{}");
} catch (error) {
  emit({ status: "error", stdout: "", stderr: "", error: `Invalid JSON input: ${error.message}` });
  process.exit(0);
}

const stdout = [];
const stderr = [];

try {
  const pyodide = await loadPyodide({
    stdout: (text) => stdout.push(String(text)),
    stderr: (text) => stderr.push(String(text)),
  });
  const result = await pyodide.runPythonAsync(String(payload.code || ""));
  if (result !== undefined && result !== null) {
    stdout.push(String(result));
  }
  emit({ status: "ok", stdout: stdout.join("\n"), stderr: stderr.join("\n"), artifacts: [] });
} catch (error) {
  emit({
    status: "error",
    stdout: stdout.join("\n"),
    stderr: stderr.join("\n"),
    error: error && error.message ? error.message : String(error),
    artifacts: [],
  });
}

function emit(value) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}
