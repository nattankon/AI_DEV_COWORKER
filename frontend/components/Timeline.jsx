import TimelineEntry from "./TimelineEntry";

export default function Timeline({ events = [], mode = "Cowork", onEditUserMessage }) {
  if (events.length === 0) {
    return null;
  }

  const isChatMode = mode === "Chat";

  return (
    <div
      aria-label={isChatMode ? "Chat conversation" : "Cowork timeline"}
      className={`mx-auto w-full max-w-3xl px-4 pb-8 pt-10 ${isChatMode ? "space-y-4" : "divide-y divide-[#eee9df]"}`}
    >
      {events.map((event) => (
        <TimelineEntry event={event} key={event.id} mode={mode} onEditUserMessage={onEditUserMessage} />
      ))}
    </div>
  );
}
