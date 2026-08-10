import { useState } from "react";
import { ArrowLeft, ArrowRight, Bot, Download, Loader2, Maximize2, Menu, Minus, PanelLeft, Search, X } from "lucide-react";
import packageInfo from "../../package.json";
import ShellMenu from "./ShellMenu";

function UpdateControl({ appUpdate, onInstallUpdate }) {
  const state = appUpdate?.state || "idle";
  if (state === "downloading" || state === "available") {
    return (
      <span
        className="app-no-drag inline-flex items-center gap-1.5 rounded-full border border-[#e6e4dd] bg-white px-2 py-1 text-[11px] text-[#77766f]"
        title="Downloading update…"
      >
        <Loader2 size={12} strokeWidth={2.2} className="animate-spin" />
        {state === "downloading" && Number(appUpdate?.percent) > 0 ? `${Math.round(appUpdate.percent)}%` : "update"}
      </span>
    );
  }
  if (state === "ready") {
    return (
      <button
        type="button"
        aria-label={`Install update${appUpdate?.version ? ` v${appUpdate.version}` : ""} and restart`}
        onClick={() => onInstallUpdate?.()}
        title={`Update to v${appUpdate?.version || ""} — installs and restarts`}
        className="app-no-drag inline-flex items-center gap-1.5 rounded-full border border-[#cfe6d5] bg-[#eef8f0] px-2 py-1 text-[11px] font-medium text-[#2f7d4f] transition hover:bg-[#e2f2e6]"
      >
        <Download size={12} strokeWidth={2.2} />
        Update{appUpdate?.version ? ` v${appUpdate.version}` : ""}
      </button>
    );
  }
  return null;
}

function callWindowControl(controlName) {
  window.electronAPI?.[controlName]?.();
}

const headerButtonClass = "app-no-drag grid h-6 w-6 place-items-center rounded-md transition hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-35";

export default function AppHeader({
  canGoBack = false,
  canGoForward = false,
  modelLabel,
  runStatus,
  workspaceLabel,
  appUpdate,
  onInstallUpdate,
  onBack,
  onForward,
  onSearch,
  onToggleSidebar,
}) {
  const isBusy = runStatus === "busy";
  const statusLabel = isBusy ? "working" : "ready";
  const [menuOpen, setMenuOpen] = useState(false);
  const appVersion = packageInfo.version ? `v${packageInfo.version}` : "";

  return (
    <header className="app-drag-region absolute inset-x-0 top-0 z-20 grid h-[38px] grid-cols-[286px_1fr_190px] items-center border-b border-black/[0.035] bg-white/85 text-[#686862] backdrop-blur-md max-lg:grid-cols-[1fr] max-lg:px-3">
      <div className="absolute left-3 top-0 flex h-full items-center gap-2 lg:static lg:gap-3 lg:pl-5">
        <button type="button" aria-label="Main menu" onClick={() => setMenuOpen((value) => !value)} className={`${headerButtonClass} hidden lg:grid`}>
          <Menu size={15} strokeWidth={2} />
        </button>
        <button type="button" aria-label="Toggle sidebar" onClick={onToggleSidebar} className={headerButtonClass}>
          <PanelLeft size={15} strokeWidth={2} />
        </button>
        <button type="button" aria-label="Search" onClick={onSearch} className={`${headerButtonClass} hidden lg:grid`}>
          <Search size={15} strokeWidth={2} />
        </button>
      </div>

      <div className="flex h-full min-w-0 items-center gap-3 px-4 text-[#aaa79f] max-lg:justify-center max-lg:px-12">
        <button type="button" aria-label="Back" onClick={onBack} disabled={!canGoBack} className={headerButtonClass}>
          <ArrowLeft size={15} strokeWidth={2} />
        </button>
        <button type="button" aria-label="Forward" onClick={onForward} disabled={!canGoForward} className={headerButtonClass}>
          <ArrowRight size={15} strokeWidth={2} />
        </button>
        <span className="app-no-drag min-w-0 truncate text-[12px] text-[#77766f]">
          {workspaceLabel || "No project selected"} / {modelLabel || "Local model"}
        </span>
      </div>

      <div className="hidden h-full items-center justify-end gap-3 pr-5 text-[#2e2d2b] lg:flex">
        <UpdateControl appUpdate={appUpdate} onInstallUpdate={onInstallUpdate} />
        {appVersion ? (
          <span className="app-no-drag text-[11px] font-medium text-[#aaa79f]" title={`AI Dev Co-worker ${appVersion}`}>
            {appVersion}
          </span>
        ) : null}
        <span className="app-no-drag inline-flex items-center gap-1.5 rounded-full border border-[#e6e4dd] bg-white px-2 py-1 text-[11px] text-[#77766f]">
          <Bot size={13} strokeWidth={2} />
          {statusLabel}
        </span>
        <button type="button" aria-label="Minimize" onClick={() => callWindowControl("minimize")} className={headerButtonClass}>
          <Minus size={14} strokeWidth={2} />
        </button>
        <button type="button" aria-label="Maximize" onClick={() => callWindowControl("maximize")} className={headerButtonClass}>
          <Maximize2 size={13} strokeWidth={2} />
        </button>
        <button type="button" aria-label="Close" onClick={() => callWindowControl("close")} className={headerButtonClass}>
          <X size={14} strokeWidth={2} />
        </button>
      </div>
      <ShellMenu open={menuOpen} />
    </header>
  );
}
