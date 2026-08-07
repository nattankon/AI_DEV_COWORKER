export default function ToolCallEntry({ event }) {
  const toolName = event.payload?.toolName ?? event.payload?.tool_name ?? "unknown_tool";
  const duration = Number.isFinite(event.payload?.durationMs) ? `${event.payload.durationMs}ms` : "";
  const summary = event.payload?.resultSummary ?? event.payload?.result ?? "";

  return (
    <article className="py-4">
      <div className="rounded-xl border border-[#ebe8df] bg-[#f8f7f3] p-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md bg-[#e7f2eb] px-2 py-1 font-mono text-[10px] text-[#3f8f62]">
            {toolName}
          </span>
          <span className="font-mono text-[10px] text-[#aaa79f]">{event.status ?? "complete"}</span>
          {duration && <span className="font-mono text-[10px] text-[#aaa79f]">{duration}</span>}
        </div>
        {summary && <div className="mt-2 text-xs leading-5 text-[#77766f]">{summary}</div>}
      </div>
    </article>
  );
}
