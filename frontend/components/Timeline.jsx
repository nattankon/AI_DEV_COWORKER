import TimelineEntry from "./TimelineEntry";

// Only render the most recent slice so a very long session stays responsive.
const MAX_RENDERED_EVENTS = 300;

export default function Timeline({ events = [], mode = "Cowork", onEditUserMessage }) {
  if (events.length === 0) {
    return null;
  }

  const isChatMode = mode === "Chat";
  const hiddenCount = Math.max(0, events.length - MAX_RENDERED_EVENTS);
  const visibleEvents = hiddenCount > 0 ? events.slice(-MAX_RENDERED_EVENTS) : events;

  return (
    <div
      aria-label={isChatMode ? "Chat conversation" : "Cowork timeline"}
      className={`mx-auto w-full max-w-3xl px-4 pb-8 pt-10 ${isChatMode ? "space-y-4" : "divide-y divide-[#eee9df]"}`}
    >
      {hiddenCount > 0 ? (
        <div className="mb-4 rounded-lg border border-dashed border-[#e0ddd4] px-3 py-2 text-center text-[12px] text-[#9a948a]">
          {hiddenCount} earlier {hiddenCount === 1 ? "message" : "messages"} hidden to keep this chat fast. Start a new chat for a clean slate.
        </div>
      ) : null}
      {visibleEvents.map((event) => (
        <TimelineEntry event={event} key={event.id} mode={mode} onEditUserMessage={onEditUserMessage} />
      ))}
    </div>
  );
}
