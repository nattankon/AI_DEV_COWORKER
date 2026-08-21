import { useRef, useState } from "react";
import { Check, ChevronUp, Hand, ShieldAlert, ShieldCheck } from "lucide-react";
import useClickOutside from "../lib/useClickOutside";


const PERMISSION_PROFILES = [
  {
    id: "manual",
    label: "Manual control",
    description: "Ask before every write, verification, code run, and side-effecting MCP tool.",
    Icon: Hand,
  },
  {
    id: "trusted",
    label: "Approvals only",
    description: "Allow routine project writes and verification. Ask for external MCP writes, code, destructive, and unknown actions.",
    Icon: ShieldCheck,
  },
  {
    id: "full",
    label: "Full access",
    description: "Allow every supported action without a prompt. Project and secret boundaries still apply.",
    Icon: ShieldAlert,
  },
];

function activeProfile(mode) {
  return PERMISSION_PROFILES.find((profile) => profile.id === mode) ?? PERMISSION_PROFILES[0];
}

export default function PermissionModeMenu({ mode = "manual", workspaceLabel = "", onChange }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const profile = activeProfile(mode);
  useClickOutside(rootRef, open, () => setOpen(false));

  return (
    <div ref={rootRef} className="pointer-events-auto relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Permission mode: ${profile.label}`}
        title="Permission mode"
        onClick={() => setOpen((current) => !current)}
        className="inline-flex h-[29px] items-center gap-2 rounded-full border border-[#e6e4dd] bg-white/90 px-3 text-[#77736b] shadow-[0_4px_15px_rgba(0,0,0,0.04)] transition hover:bg-white"
      >
        <profile.Icon size={13} strokeWidth={1.8} />
        <span>{profile.label}</span>
        <ChevronUp size={12} className={`transition ${open ? "rotate-0" : "rotate-180"}`} />
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Permission mode"
          className="absolute bottom-10 right-0 z-50 w-[360px] overflow-hidden rounded-lg border border-[#dedbd2] bg-white p-2 text-[#34332f] shadow-[0_18px_50px_rgba(0,0,0,0.18)]"
        >
          <div className="px-2 pb-2 pt-1 text-[11px] font-medium uppercase text-[#9a958a]">Permission mode</div>
          {PERMISSION_PROFILES.map(({ id, label, description, Icon }) => (
            <button
              key={id}
              type="button"
              role="menuitemradio"
              aria-checked={profile.id === id}
              aria-label={label}
              onClick={() => {
                onChange?.(id);
                setOpen(false);
              }}
              className={`grid w-full grid-cols-[24px_1fr_18px] gap-2 rounded-md px-2 py-2.5 text-left transition hover:bg-[#f5f4f1] ${profile.id === id ? "bg-[#f1f0ec]" : ""}`}
            >
              <Icon size={16} className={id === "full" ? "text-[#c35b3f]" : "text-[#67635b]"} />
              <span className="min-w-0">
                <span className="block text-[13px] font-medium">{label}</span>
                <span className="mt-0.5 block text-[11px] leading-4 text-[#89847a]">{description}</span>
              </span>
              {profile.id === id && <Check size={15} className="mt-0.5 text-[#c35b3f]" />}
            </button>
          ))}
          <div className="mx-2 mt-2 border-t border-[#ece9e2] px-0 pb-1 pt-2 text-[11px] leading-4 text-[#8b867c]">
            Project boundary: {workspaceLabel || "No project selected"}. Workspace path and Secret Guard remain enforced in every mode.
          </div>
        </div>
      )}
    </div>
  );
}
