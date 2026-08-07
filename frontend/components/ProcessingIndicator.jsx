import { useEffect, useState } from "react";

function formatElapsed(totalSeconds) {
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
}

export default function ProcessingIndicator({ active = false, waitingForApproval = false, statusText = "" }) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const cleanStatusText = String(statusText || "").trim();

  useEffect(() => {
    if (!active || waitingForApproval || cleanStatusText) {
      setElapsedSeconds(0);
      return undefined;
    }

    const startedAt = Date.now();
    setElapsedSeconds(0);
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [active, waitingForApproval, cleanStatusText]);

  if (!active || waitingForApproval) return null;

  return (
    <div role="status" aria-live="polite" className="mb-3 flex min-h-6 items-center gap-2 px-1 text-[13px] text-[#929089]">
      <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#9c9991]" />
      <span>{cleanStatusText || (elapsedSeconds <= 10 ? "Thinking" : `Working for ${formatElapsed(elapsedSeconds)}`)}</span>
    </div>
  );
}
