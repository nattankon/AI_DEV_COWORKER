import MessageEntry from "./MessageEntry";
import McpResultCard from "./McpResultCard";

export default function TimelineEntry({ event, mode = "Cowork", onEditUserMessage }) {
  if (event.type.startsWith("message.")) {
    return <MessageEntry event={event} mode={mode} onEditUserMessage={onEditUserMessage} />;
  }
  if (event.type.startsWith("tool.")) {
    return null;
  }
  if (event.type === "mcp.result") {
    return <McpResultCard event={event} />;
  }
  if (event.type === "approval.resolved") {
    const approved = event.payload?.answer === "allow";
    return (
      <article className="py-4">
        <div className={`rounded-lg border px-3 py-2 text-[13px] ${approved ? "border-[#d7e8dc] bg-[#f2f8f4] text-[#35764e]" : "border-[#ecd8d4] bg-[#fff4f2] text-[#a4483e]"}`}>
          {approved ? "Approved" : "Denied"} {event.payload?.approvalId}
        </div>
      </article>
    );
  }
  if (event.type === "approval.requested" || event.type === "agent.status") {
    return null;
  }
  return (
    <article className="py-4">
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-dim">{event.type}</div>
      <pre className="mt-2 whitespace-pre-wrap rounded-lg border border-line bg-[#111214] p-3 text-xs text-muted">
        {JSON.stringify(event.payload ?? {}, null, 2)}
      </pre>
    </article>
  );
}
