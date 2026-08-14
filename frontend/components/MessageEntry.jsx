import MarkdownMessage from "./MarkdownMessage";
import { Copy } from "lucide-react";

const MESSAGE_LABELS = {
  "message.user": "You",
  "message.assistant": "Cowork",
  "message.system": "System",
};

function labelFor(event, mode) {
  if (mode === "Chat" && event.type === "message.assistant") return "Chat";
  return MESSAGE_LABELS[event.type] ?? "Message";
}

function sourceBadgeLabel(sourceType) {
  const type = String(sourceType || "").trim();
  if (type === "fetched-page") return "fetched";
  if (type === "search-result") return "snippet";
  if (type === "fetch-blocked") return "blocked";
  if (type === "trusted-hint") return "hint";
  return type || "source";
}

function domainForSource(source) {
  if (source?.domain) return String(source.domain);
  try {
    return new URL(String(source?.url || "")).hostname;
  } catch {
    return String(source?.url || "source");
  }
}

function sourceQualityScore(source) {
  const value = Number(source?.quality_score ?? source?.qualityScore);
  if (!Number.isFinite(value)) return null;
  return Math.max(0, Math.min(5, Math.round(value)));
}

function SourceQuality({ source }) {
  const score = sourceQualityScore(source);
  if (score === null) return null;
  return (
    <span className="flex items-center gap-1" aria-label={`Source quality ${score} of 5`}>
      <span className="text-[10px] text-[#8a877f]">quality</span>
      <span className="flex gap-0.5" aria-hidden="true">
        {[0, 1, 2, 3, 4].map((index) => (
          <span
            key={index}
            className={`h-1.5 w-1.5 rounded-full ${index < score ? "bg-[#4f8f5d]" : "bg-[#ded8ca]"}`}
          />
        ))}
      </span>
    </span>
  );
}

function SourceCards({ sources = [] }) {
  if (!sources.length) return null;
  return (
    <div className="mt-1 flex max-w-full flex-wrap gap-2" aria-label="Web sources">
      {sources.map((source) => {
        const index = source?.index ?? "";
        const title = source?.title || source?.url || `Source ${index}`;
        return (
          <a
            className="flex max-w-[260px] flex-col gap-1 rounded-xl border border-[#ddd6c8] bg-[#fbfaf6] px-3 py-2 text-[11px] text-[#4b4943] no-underline shadow-[0_1px_2px_rgba(0,0,0,0.03)] transition hover:border-[#cfc5b4] hover:bg-white"
            href={source?.url}
            id={`source-web-${index}`}
            key={`${index}-${source?.url || title}`}
            rel="noreferrer noopener"
            target="_blank"
          >
            <span className="flex items-center justify-between gap-2">
              <span className="truncate text-[#6d695f]">{domainForSource(source)}</span>
              <span className="shrink-0 rounded-full bg-[#eee9de] px-2 py-0.5 text-[10px] font-medium text-[#6b6255]">
                {sourceBadgeLabel(source?.source_type)}
              </span>
            </span>
            <span className="line-clamp-2 font-medium text-[#2f2f2d]">{title}</span>
            <SourceQuality source={source} />
          </a>
        );
      })}
    </div>
  );
}

function imagePreviewUrl(attachment) {
  const value = attachment?.thumbnailDataUrl || attachment?.dataUrl || attachment?.previewUrl;
  if (typeof value !== "string") return "";
  return value.startsWith("data:image/") ? value : "";
}

function AttachmentPreviews({ attachments = [], align = "end" }) {
  if (!attachments.length) return null;
  return (
    <div className={`flex max-w-full flex-wrap ${align === "start" ? "justify-start" : "justify-end"} gap-1.5`} aria-label="Attached context">
      {attachments.map((attachment, index) => {
        const previewUrl = imagePreviewUrl(attachment);
        if (attachment?.kind === "image" && previewUrl) {
          return (
            <div
              key={`${attachment.label || "attachment"}-${index}`}
              className="flex max-w-[180px] flex-col gap-1 rounded-xl border border-[#dedbd2] bg-[#f7f6f2] p-1.5 text-[11px] text-[#4a4945]"
            >
              <img
                alt={`${attachment.label || "image"} attachment`}
                src={previewUrl}
                className="h-20 w-28 rounded-lg border border-[#ebe8df] bg-white object-cover"
              />
              <div className="flex min-w-0 items-center gap-1 px-1">
                <span className="truncate font-medium">{attachment.label || "attached-image"}</span>
                <span className="shrink-0 text-[#8a877f]">{attachment.source || "attached"}</span>
              </div>
            </div>
          );
        }
        return (
          <span
            key={`${attachment.label || "attachment"}-${index}`}
            className="inline-flex max-w-[220px] items-center gap-1 rounded-lg border border-[#dedbd2] bg-[#f7f6f2] px-2 py-1 text-[11px] text-[#4a4945]"
          >
            <span className="truncate font-medium">{attachment.label || "attached-context"}</span>
            <span className="shrink-0 text-[#8a877f]">{attachment.source || "attached"}</span>
            {attachment.kind && <span className="shrink-0 text-[#aaa79f]">{attachment.kind}</span>}
          </span>
        );
      })}
    </div>
  );
}

export default function MessageEntry({ event, mode = "Cowork", onEditUserMessage }) {
  const isChatMode = mode === "Chat";
  const isUser = event.type === "message.user";
  const align = isChatMode && isUser ? "right" : "left";
  const label = labelFor(event, mode);
  const time = new Date(event.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const attachments = Array.isArray(event.payload?.attachments) ? event.payload.attachments : [];
  const useMarkdown = isChatMode && event.type === "message.assistant";
  const webSources = isChatMode && event.type === "message.assistant" && Array.isArray(event.payload?.webSources)
    ? event.payload.webSources
    : [];

  if (isChatMode) {
    return (
      <article className={`flex py-1 ${isUser ? "justify-end" : "justify-start"}`} data-align={align}>
        <div className={`max-w-[78%] ${isUser ? "items-end" : "items-start"} flex flex-col gap-1`}>
          <div className={`flex items-center gap-2 ${isUser ? "flex-row-reverse" : ""}`}>
            <span className="text-[11px] font-medium text-[#6f6b63]">{label}</span>
            <span className="text-[10px] text-[#aaa79f]">{time}</span>
          </div>
          <div
            className={`${useMarkdown ? "" : "whitespace-pre-wrap"} break-words rounded-2xl px-4 py-2.5 text-[14px] leading-6 shadow-[0_1px_2px_rgba(0,0,0,0.04)] ${
              isUser
                ? "rounded-br-md bg-[#2f2f2d] text-white"
                : event.type === "message.system"
                  ? "rounded-bl-md border border-[#ead7d2] bg-[#fff4f2] text-[#9d3e39]"
                  : "rounded-bl-md border border-[#e7e2d8] bg-[#f7f5f0] text-[#3d3c39]"
            }`}
          >
            {useMarkdown ? (
              <MarkdownMessage text={event.payload?.text ?? ""} webSources={webSources} />
            ) : (
              event.payload?.text ?? ""
            )}
          </div>
          {webSources.length > 0 && <SourceCards sources={webSources} />}
          {isUser && attachments.length > 0 && <AttachmentPreviews attachments={attachments} />}
          {isUser && typeof onEditUserMessage === "function" && (
            <button
              type="button"
              onClick={() => onEditUserMessage(event)}
              className="text-[11px] font-medium text-[#8a877f] hover:text-[#2f2f2d]"
            >
              Edit
            </button>
          )}
          {!isUser && event.type === "message.assistant" && (
            <button
              type="button"
              aria-label="Copy answer"
              onClick={() => navigator.clipboard?.writeText(String(event.payload?.text ?? ""))}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-[#8a877f] hover:text-[#2f2f2d]"
            >
              <Copy size={12} /> Copy
            </button>
          )}
        </div>
      </article>
    );
  }

  return (
    <article className="py-5">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-xs font-semibold text-[#2f2f2d]">{label}</span>
        <span className="text-[10px] text-[#aaa79f]">{time}</span>
      </div>
      <div className="whitespace-pre-wrap break-words text-[14px] leading-6 text-[#3d3c39]">
        {event.payload?.text ?? ""}
      </div>
      {isUser && attachments.length > 0 && <AttachmentPreviews attachments={attachments} align="start" />}
    </article>
  );
}
