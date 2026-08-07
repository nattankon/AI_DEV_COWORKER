import { useState } from "react";
import { BarChart3, BriefcaseBusiness, Code2, CreditCard, Download, Globe2, HelpCircle, Monitor, Plug, Settings, Shield, SlidersHorizontal, UserCircle, Wrench, X } from "lucide-react";
import ConnectorsPanel from "./ConnectorsPanel";

const settingsGroups = [
  {
    label: "Settings",
    items: [
      { key: "general", label: "General", icon: Settings },
      { key: "account", label: "Account", icon: UserCircle },
      { key: "privacy", label: "Privacy", icon: Shield },
      { key: "billing", label: "Billing", icon: CreditCard },
      { key: "usage", label: "Usage", icon: BarChart3 },
      { key: "capabilities", label: "Capabilities", icon: BriefcaseBusiness },
      { key: "connectors", label: "Connectors", icon: Plug },
      { key: "code", label: "Code", icon: Code2 },
      { key: "cowork", label: "Cowork", icon: SlidersHorizontal },
    ],
  },
  {
    label: "Desktop app",
    items: [
      { key: "desktop-general", label: "General", icon: Monitor },
      { key: "extensions", label: "Extensions", icon: Download },
      { key: "developer", label: "Developer", icon: Wrench },
    ],
  },
];

function PlaceholderSettings({ title }) {
  return (
    <div className="max-w-2xl">
      <h2 className="text-[22px] font-semibold text-[#2f2f2d]">{title}</h2>
      <p className="mt-2 text-[14px] leading-6 text-[#6f6b63]">
        This settings section is reserved for app-level configuration. Developer settings currently owns the local MCP server registry.
      </p>
    </div>
  );
}

export default function SettingsModal({
  open = false,
  initialSection = "developer",
  connectorState,
  connectorTestResult,
  connectorDiscoveryResult,
  onClose,
  onRefreshConnectors,
  onSaveConnectors,
  onTestConnector,
  onDiscoverConnector,
}) {
  const [activeSection, setActiveSection] = useState(initialSection || "developer");
  if (!open) return null;

  const activeItem = settingsGroups.flatMap((group) => group.items).find((item) => item.key === activeSection);
  const activeLabel = activeItem?.label || "Developer";
  const showDeveloperConnectors = activeSection === "developer" || activeSection === "connectors";

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/35 px-5 py-8 backdrop-blur-[1px]">
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        className="grid h-[min(760px,calc(100vh-48px))] w-[min(1040px,calc(100vw-48px))] overflow-hidden rounded-xl border border-[#d8d4ca] bg-white shadow-[0_24px_80px_rgba(0,0,0,0.28)] md:grid-cols-[192px_1fr]"
      >
        <aside className="min-h-0 border-r border-[#e6e2d8] bg-[#fbfaf7] p-3">
          <label className="mb-5 flex h-9 items-center gap-2 rounded-lg border border-[#e1ded7] bg-white px-2 text-[13px] text-[#8a877f]">
            <HelpCircle size={15} />
            <input aria-label="Search settings" placeholder="Search" className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-[#aaa69c]" />
          </label>
          <nav className="space-y-5">
            {settingsGroups.map((group) => (
              <div key={group.label}>
                <div className="mb-2 px-2 text-[12px] text-[#9a948a]">{group.label}</div>
                <div className="grid gap-1">
                  {group.items.map(({ key, label, icon: Icon }) => {
                    const active = key === activeSection;
                    return (
                      <button
                        key={key}
                        type="button"
                        aria-pressed={active}
                        onClick={() => setActiveSection(key)}
                        className={`flex h-8 items-center gap-2 rounded-lg px-2 text-left text-[13px] transition ${
                          active ? "bg-[#e7e5df] font-medium text-[#2f2f2d]" : "text-[#5f5a52] hover:bg-[#efede8]"
                        }`}
                      >
                        <Icon size={15} strokeWidth={1.9} />
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
        </aside>
        <div className="relative min-h-0 overflow-y-auto p-6">
          <button
            type="button"
            aria-label="Close settings"
            onClick={onClose}
            className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-lg text-[#4f4a42] hover:bg-[#efede8]"
          >
            <X size={17} />
          </button>
          {showDeveloperConnectors ? (
            <ConnectorsPanel
              embedded
              connectorState={connectorState}
              connectorTestResult={connectorTestResult}
              connectorDiscoveryResult={connectorDiscoveryResult}
              onRefresh={onRefreshConnectors}
              onSaveConnectors={onSaveConnectors}
              onTestConnector={onTestConnector}
              onDiscoverConnector={onDiscoverConnector}
            />
          ) : (
            <PlaceholderSettings title={activeLabel} />
          )}
        </div>
      </section>
    </div>
  );
}
