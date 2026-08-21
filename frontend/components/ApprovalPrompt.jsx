import { ShieldCheck, ShieldX } from "lucide-react";

function formatJson(value) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value ?? "");
  }
}

export default function ApprovalPrompt({ event, onDecision }) {
  if (!event) return null;
  const proposal = event.payload?.proposal ?? {};
  const approvalKind = event.payload?.approvalKind ?? "";
  const isVerification = approvalKind === "run_verification";
  const title = event.payload?.title || (isVerification ? "Approve verification run" : "Approve file write");
  const details = proposal.details && typeof proposal.details === "object" ? proposal.details : {};
  const fullPayload = proposal.full_payload && typeof proposal.full_payload === "object" ? proposal.full_payload : {};
  const pathLabel = proposal.subject || proposal.relative_path || proposal.name || details.tool || "Pending action";
  const command = Array.isArray(details.argv) ? details.argv.join(" ") : Array.isArray(proposal.argv) ? proposal.argv.join(" ") : "";
  const riskLevel = String(proposal.risk_level || "").trim();
  const riskSummary = String(proposal.risk_summary || "").trim();
  const defaultDecision = String(proposal.default_decision || "").trim();
  const detailText = Object.keys(details).length > 0 ? formatJson(details) : "";
  const fullPayloadText = Object.keys(fullPayload).length > 0 ? formatJson(fullPayload) : "";
  const diff = proposal.diff || details.diff;
  const originLabel = proposal.origin === "web_chat" ? "Web Chat" : "Cowork";

  return (
    <section
      aria-label="Approval prompt"
      className="mx-auto mb-4 w-full max-w-3xl rounded-xl border border-[#ead8c8] bg-[#fff9f4] p-4 shadow-[0_14px_42px_rgba(80,45,21,0.12)]"
    >
      <div className="flex items-start gap-3">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#f4e2d6] text-[#a34d2f]">
          <ShieldCheck size={17} strokeWidth={2} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-1 text-[12px] font-medium text-[#a34d2f]">{originLabel} is waiting for your decision.</div>
          <div className="text-[14px] font-semibold text-[#2f2f2d]">{title}</div>
          <div className="mt-1 text-[13px] leading-5 text-[#6f6a61]">{event.payload?.question}</div>
          {(riskLevel || riskSummary || defaultDecision) && (
            <div className="mt-3 rounded-lg border border-[#eadfd4] bg-[#fffdf9] p-3 text-[12px] leading-5 text-[#5e5a52]">
              {riskLevel && <div className="font-semibold text-[#8f4d30]">Risk: {riskLevel}</div>}
              {riskSummary && <div className="mt-1">{riskSummary}</div>}
              {defaultDecision && <div className="mt-1 text-[#8a857a]">Default: {defaultDecision}</div>}
            </div>
          )}
          <div className="mt-3 rounded-lg border border-[#eadfd4] bg-white p-3">
            <div className="text-[12px] font-semibold text-[#4d4a45]">{pathLabel}</div>
            {command && <div className="mt-1 font-mono text-[11px] text-[#77736b]">{command}</div>}
            {detailText && (
              <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-[#f8f7f3] p-2 font-mono text-[11px] leading-5 text-[#4b4943]">
                {detailText}
              </pre>
            )}
            {fullPayloadText && (
              <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap rounded-md bg-[#f3f2ee] p-2 font-mono text-[11px] leading-5 text-[#4b4943]">
                {fullPayloadText}
              </pre>
            )}
            {diff && (
              <pre className="mt-2 max-h-44 overflow-auto whitespace-pre-wrap rounded-md bg-[#f8f7f3] p-2 font-mono text-[11px] leading-5 text-[#4b4943]">
                {diff}
              </pre>
            )}
          </div>
        </div>
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          onClick={() => onDecision?.("deny")}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-[#dedbd2] bg-white px-3 text-[13px] text-[#5d5a53] transition hover:bg-[#f6f5f2]"
        >
          <ShieldX size={14} strokeWidth={2} />
          Deny
        </button>
        <button
          type="button"
          onClick={() => onDecision?.("allow")}
          className="h-8 rounded-lg bg-[#2f2f2d] px-3 text-[13px] font-medium text-white transition hover:bg-[#1f1f1d]"
        >
          Approve
        </button>
      </div>
    </section>
  );
}
