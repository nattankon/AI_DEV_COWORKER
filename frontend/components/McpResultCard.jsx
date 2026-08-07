function formatPayload(value) {
  if (typeof value === "undefined" || value === null || value === "") return "No result payload.";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export default function McpResultCard({ event }) {
  const payload = event?.payload || {};
  const status = String(payload.status || "error");
  const isOk = status === "ok";
  const isDenied = status === "denied";
  const tone = isOk
    ? "border-[#d8e9dc] bg-[#f5faf6] text-[#315f3d]"
    : isDenied
      ? "border-[#ead9c8] bg-[#fff8ef] text-[#83552a]"
      : "border-[#ecd6d2] bg-[#fff4f1] text-[#9b3f34]";
  const body = isOk ? formatPayload(payload.result) : (payload.error || "MCP tool did not complete.");
  const args = payload.arguments && typeof payload.arguments === "object" ? payload.arguments : {};
  const hasArgs = Object.keys(args).length > 0;

  return (
    <article className="py-4">
      <div className={`rounded-xl border px-4 py-3 text-[13px] shadow-sm ${tone}`}>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">MCP</span>
          <span className="min-w-0 truncate font-mono text-[12px]">
            {payload.server || "connector"}/{payload.tool || "tool"}
          </span>
          <span className="rounded-md bg-white/70 px-1.5 py-0.5 text-[10px] uppercase tracking-wide">
            {payload.readOnly ? "read-only" : "approval"}
          </span>
          <span className="rounded-md bg-white/70 px-1.5 py-0.5 text-[10px] uppercase tracking-wide">
            {payload.origin || "manual"}
          </span>
          {payload.durationMs > 0 && (
            <span className="ml-auto text-[11px] opacity-75">{payload.durationMs} ms</span>
          )}
        </div>
        {hasArgs && (
          <details className="mt-2">
            <summary className="cursor-pointer text-[11px] font-medium opacity-75">Arguments</summary>
            <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg border border-black/5 bg-white/70 p-2 text-[11px] leading-4 text-[#33302b]">
              {formatPayload(args)}
            </pre>
          </details>
        )}
        <pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap rounded-lg border border-black/5 bg-white/70 p-3 text-[12px] leading-5 text-[#33302b]">
          {body}
        </pre>
      </div>
    </article>
  );
}
