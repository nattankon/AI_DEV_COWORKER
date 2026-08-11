import { AlertTriangle, CheckCircle2, ShieldAlert, XCircle } from "lucide-react";

const STATUS_META = {
  passed: { label: "passed", icon: CheckCircle2, className: "text-[#2f7d4f]" },
  failed: { label: "failed", icon: XCircle, className: "text-[#c0492f]" },
  denied: { label: "denied", icon: ShieldAlert, className: "text-[#b0872f]" },
  timeout: { label: "timed out", icon: AlertTriangle, className: "text-[#b0872f]" },
  error: { label: "error", icon: XCircle, className: "text-[#c0492f]" },
};

function runMeta(status) {
  return STATUS_META[String(status || "").toLowerCase()] || { label: status || "unknown", icon: AlertTriangle, className: "text-[#77766f]" };
}

export default function VerificationPanel({ evidence }) {
  if (!evidence || !evidence.writesPerformed) return null;

  const runs = Array.isArray(evidence.verificationRuns) ? evidence.verificationRuns : [];
  const passed = Boolean(evidence.verificationPassed);
  const observed = Boolean(evidence.verificationObserved);
  const testFilesModified = Array.isArray(evidence.testFilesModified) ? evidence.testFilesModified : [];

  const headline = passed
    ? "Verified — changes passed verification"
    : observed
      ? "Files changed — verification did not pass"
      : "Files changed — not verified";

  const tone = passed
    ? { border: "border-[#cfe6d5]", bg: "bg-[#f2f9f4]", icon: CheckCircle2, iconClass: "text-[#2f7d4f]" }
    : { border: "border-[#eadfc2]", bg: "bg-[#fbf6ea]", icon: AlertTriangle, iconClass: "text-[#b0872f]" };
  const HeadlineIcon = tone.icon;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`mb-3 rounded-lg border ${tone.border} ${tone.bg} px-3 py-2.5 text-[12px] text-[#4a4944]`}
    >
      <div className="flex items-center gap-2 font-medium">
        <HeadlineIcon size={14} strokeWidth={2.2} className={tone.iconClass} />
        <span>{headline}</span>
      </div>
      {runs.length > 0 ? (
        <ul className="mt-2 flex flex-col gap-1">
          {runs.map((run, index) => {
            const meta = runMeta(run?.status);
            const RunIcon = meta.icon;
            return (
              <li key={`${run?.name ?? "run"}-${index}`} className="flex items-center gap-2">
                <RunIcon size={13} strokeWidth={2.2} className={meta.className} />
                <span className="font-mono text-[11px] text-[#5c5b55]">{run?.name || "verification"}</span>
                <span className={`text-[11px] ${meta.className}`}>{meta.label}</span>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mt-1 text-[11px] text-[#77766f]">
          No verification preset was run. Ask the agent to run one before trusting the change.
        </p>
      )}
      {testFilesModified.length > 0 ? (
        <div className="mt-2 flex items-start gap-2 border-t border-black/[0.06] pt-2 text-[11px] text-[#b0872f]">
          <ShieldAlert size={13} strokeWidth={2.2} className="mt-px shrink-0" />
          <span>
            Test files were changed this run ({testFilesModified.map((file) => file.split(/[\\/]/).pop()).join(", ")}) —
            confirm the fix is in the implementation, not the tests.
          </span>
        </div>
      ) : null}
    </div>
  );
}
