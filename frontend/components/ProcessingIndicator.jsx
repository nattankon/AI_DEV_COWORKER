import { useEffect, useState } from "react";

const GENERIC_PROGRESS = [
  "Thinking through your request...",
  "Preparing the response...",
  "Reviewing the details...",
  "Keeping this task active...",
];

function formatElapsed(totalSeconds) {
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
}

function timestampFor(startedAt) {
  const parsed = Date.parse(String(startedAt || ""));
  return Number.isFinite(parsed) ? parsed : Date.now();
}

export default function ProcessingIndicator({ active = false, waitingForApproval = false, statusText = "", startedAt = "" }) {
  const [now, setNow] = useState(() => Date.now());
  const cleanStatusText = String(statusText || "").trim();
  const startedAtMs = timestampFor(startedAt);
  const elapsedSeconds = Math.max(0, Math.floor((now - startedAtMs) / 1000));

  // The timer belongs to the whole request, not a status step. Status text can change
  // from "Searching" to "Writing" without making a slow request look newer than it is.
  useEffect(() => {
    if (!active || waitingForApproval) {
      setNow(Date.now());
      return undefined;
    }

    setNow(Date.now());
    const timer = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);
    return () => window.clearInterval(timer);
  }, [active, waitingForApproval, startedAt]);

  if (!active || waitingForApproval) return null;

  const label = cleanStatusText || GENERIC_PROGRESS[Math.floor(elapsedSeconds / 4) % GENERIC_PROGRESS.length];

  return (
    <div role="status" aria-live="polite" className="mb-3 flex min-h-6 items-center gap-2 px-1 text-[13px] text-[#929089]">
      <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#9c9991]" />
      <span>{`Working for ${formatElapsed(elapsedSeconds)} · ${label}`}</span>
    </div>
  );
}
