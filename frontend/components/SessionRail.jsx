import { useState } from "react";
import { Activity, Bot, ChevronDown, Code2, FolderOpen, Globe2, HelpCircle, LayoutPanelTop, LogOut, MessageSquare, MoreVertical, Palette, Pin, Plug, Plus, Search, Settings, Sparkles, Trash2 } from "lucide-react";

function formatSessionMeta(session) {
  const eventCount = Number.isFinite(session?.eventCount) ? session.eventCount : 0;
  return `${eventCount} event${eventCount === 1 ? "" : "s"}`;
}

const modeTabs = [
  { label: "Chat", icon: MessageSquare },
  { label: "Cowork", icon: Bot },
  { label: "Code", icon: Code2 },
];

export default function SessionRail({
  activeMode = "Chat",
  sessions = [],
  activeSessionId,
  visible = true,
  workspaceLabel,
  onCustomize,
  onDeleteSession,
  onNewSession,
  onOpenArtifacts,
  onOpenConnectors,
  onOpenQuality,
  onOpenProjects,
  onOpenSettings,
  onOpenWorkspace,
  onPinSession,
  onRenameSession,
  onSelectMode,
  onSelectSession,
}) {
  const shownSessions = sessions.length > 0 ? sessions : [{ id: "empty", title: "New chat", eventCount: 0 }];
  const [sessionMenuId, setSessionMenuId] = useState("");
  const [renameSessionId, setRenameSessionId] = useState("");
  const [renameDraft, setRenameDraft] = useState("");
  const [searchDraft, setSearchDraft] = useState("");
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const filteredSessions = searchDraft.trim()
    ? shownSessions.filter((session) => String(session.title || "").toLowerCase().includes(searchDraft.trim().toLowerCase()))
    : shownSessions;

  return (
    <aside
      aria-label="Session sidebar"
      data-state={visible ? "open" : "closed"}
      className={`min-h-0 w-[286px] shrink-0 grid-rows-[auto_auto_1fr_auto] border-r border-[#e6e4dd] bg-[#f7f7f5] pt-[50px] ${
        visible ? "fixed inset-y-0 left-0 z-10 grid shadow-[8px_0_24px_rgba(0,0,0,0.08)] lg:static lg:z-auto lg:shadow-none" : "hidden"
      }`}
    >
      <div className="mx-3 mb-3 grid grid-cols-3 gap-1 rounded-xl border border-[#e1ded7] bg-[#ecebe7] p-1">
        {modeTabs.map(({ label, icon: Icon }) => {
          const active = label === activeMode;
          return (
          <button
            key={label}
            type="button"
            aria-label={`Mode ${label}`}
            aria-pressed={active}
            onClick={() => onSelectMode?.(label)}
            className={`flex h-[30px] items-center justify-center gap-1.5 rounded-[9px] text-[13px] transition ${
              active ? "bg-white text-[#2f2f2d] shadow-[0_1px_4px_rgba(0,0,0,0.08)]" : "text-[#77746d] hover:bg-white/60"
            }`}
          >
            <Icon size={14} strokeWidth={1.9} />
            {label}
          </button>
          );
        })}
      </div>

      <div className="px-3 pb-4">
        <button
          type="button"
          onClick={onNewSession}
          className="flex h-[30px] w-full items-center gap-2 rounded-lg px-2 text-left text-[13px] text-[#4c4b47] transition hover:bg-[#e6e5df]"
        >
          <Plus size={15} strokeWidth={2} />
          New chat
        </button>
        <button
          type="button"
          onClick={onOpenProjects}
          className="mt-1 flex h-[30px] w-full items-center gap-2 rounded-lg px-2 text-left text-[13px] text-[#4c4b47] transition hover:bg-[#e6e5df]"
        >
          <FolderOpen size={15} strokeWidth={2} />
          Projects
        </button>
        <button
          type="button"
          onClick={onOpenWorkspace}
          className="mt-1 flex h-[30px] w-full items-center gap-2 rounded-lg px-2 text-left text-[13px] text-[#4c4b47] transition hover:bg-[#e6e5df]"
        >
          <LayoutPanelTop size={15} strokeWidth={2} />
          Workspace
        </button>
        <button
          type="button"
          onClick={onOpenArtifacts}
          className="mt-1 flex h-[30px] w-full items-center gap-2 rounded-lg px-2 text-left text-[13px] text-[#4c4b47] transition hover:bg-[#e6e5df]"
        >
          <Sparkles size={15} strokeWidth={2} />
          Artifacts
        </button>
        <button
          type="button"
          onClick={onOpenQuality}
          className="mt-1 flex h-[30px] w-full items-center gap-2 rounded-lg px-2 text-left text-[13px] text-[#4c4b47] transition hover:bg-[#e6e5df]"
        >
          <Activity size={15} strokeWidth={2} />
          Quality
        </button>
        <button
          type="button"
          onClick={onOpenConnectors}
          className="mt-1 flex h-[30px] w-full items-center gap-2 rounded-lg px-2 text-left text-[13px] text-[#4c4b47] transition hover:bg-[#e6e5df]"
        >
          <Plug size={15} strokeWidth={2} />
          Connectors
        </button>
        <button
          type="button"
          onClick={onCustomize}
          className="mt-1 flex h-[30px] w-full items-center gap-2 rounded-lg px-2 text-left text-[13px] text-[#4c4b47] transition hover:bg-[#e6e5df]"
        >
          <Palette size={15} strokeWidth={2} />
          Customize
        </button>
      </div>

      <div className="min-h-0 overflow-y-auto px-3 pb-3">
        <label className="mb-2 flex h-8 items-center gap-2 rounded-lg border border-[#e3e0d8] bg-white px-2 text-[12px] text-[#8a877f]">
          <Search size={14} />
          <input
            aria-label="Search chat history"
            value={searchDraft}
            onChange={(event) => setSearchDraft(event.target.value)}
            placeholder="Search history"
            className="min-w-0 flex-1 bg-transparent text-[12px] text-[#2f2f2d] outline-none placeholder:text-[#aaa69c]"
          />
        </label>
        <div className="px-2 pb-2 pt-1 text-[12px] text-[#aaa69c]">Recents</div>
        <div className="grid gap-0.5">
          {filteredSessions.map((session) => {
            const active = session.id === activeSessionId;
            return (
              <div key={session.id} className="relative flex min-w-0 items-center">
                {renameSessionId === session.id ? (
                  <input
                    aria-label="Rename session"
                    autoFocus
                    value={renameDraft}
                    onChange={(event) => setRenameDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key !== "Enter") return;
                      onRenameSession?.(session.id, renameDraft.trim());
                      setRenameSessionId("");
                      setSessionMenuId("");
                    }}
                    className="h-8 min-w-0 flex-1 rounded-lg border border-[#c9c5bb] bg-white px-2 text-[13px] outline-none"
                  />
                ) : (
                  <button
                    type="button"
                    onClick={() => session.id !== "empty" && onSelectSession?.(session.id)}
                    className={`min-h-[28px] min-w-0 flex-1 truncate rounded-lg px-2 py-1.5 text-left text-[13px] leading-snug transition ${
                      active ? "bg-[#e6e5df] text-[#2f2f2d]" : "text-[#3d3c39] hover:bg-[#e9e8e3]"
                    }`}
                    title={`${session.title || "Untitled chat"} - ${formatSessionMeta(session)}`}
                  >
                    {session.pinned ? "• " : ""}
                    {session.title || "Untitled chat"}
                  </button>
                )}
                {session.id !== "empty" && (
                  <button
                    type="button"
                    aria-label={`Session actions for ${session.title || "Untitled chat"}`}
                    onClick={() => setSessionMenuId((value) => (value === session.id ? "" : session.id))}
                    className="ml-1 grid h-7 w-7 shrink-0 place-items-center rounded-lg text-[#8b877f] hover:bg-[#e6e5df]"
                  >
                    <MoreVertical size={14} />
                  </button>
                )}
                {sessionMenuId === session.id && (
                  <div role="menu" aria-label={`Actions for ${session.title}`} className="absolute right-0 top-8 z-40 w-44 rounded-xl border border-[#dedbd2] bg-white p-1.5 shadow-[0_12px_32px_rgba(0,0,0,0.16)]">
                    <button type="button" role="menuitem" onClick={() => onPinSession?.(session.id)} className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left text-[13px] hover:bg-[#f0efeb]">
                      <Pin size={14} /> Pin
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setRenameSessionId(session.id);
                        setRenameDraft(session.title || "");
                      }}
                      className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left text-[13px] hover:bg-[#f0efeb]"
                    >
                      Rename
                    </button>
                    <button type="button" role="menuitem" onClick={onOpenProjects} className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left text-[13px] hover:bg-[#f0efeb]">
                      <FolderOpen size={14} /> Add to project
                    </button>
                    <button type="button" role="menuitem" onClick={() => onDeleteSession?.(session.id)} className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left text-[13px] text-[#b7463d] hover:bg-[#fff1ef]">
                      <Trash2 size={14} /> Delete
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid gap-3 px-3 pb-3">
        <div className="flex h-[39px] items-center gap-2.5 rounded-xl border border-[#e6e4dd] bg-white px-3 text-[12px] text-[#827f78] shadow-[0_3px_12px_rgba(0,0,0,0.04)]">
          <span className="h-[15px] w-[15px] rounded-full border-2 border-[#d7d5ce] border-t-[#8f8b82]" />
          CLI contracts ready
        </div>
        <div className="relative">
          {accountMenuOpen && (
            <div
              role="menu"
              aria-label="Account menu"
              className="absolute bottom-10 left-0 z-50 w-[262px] rounded-xl border border-[#dedbd2] bg-white p-1.5 text-[13px] shadow-[0_14px_38px_rgba(0,0,0,0.18)]"
            >
              <div className="px-2 py-1.5 text-[12px] font-medium text-[#8a877f]">Local workspace</div>
              <button
                type="button"
                role="menuitem"
                aria-label="Settings"
                onClick={() => {
                  setAccountMenuOpen(false);
                  onOpenSettings?.("developer");
                }}
                className="flex h-8 w-full items-center justify-between rounded-lg px-2 text-left hover:bg-[#f0efeb]"
              >
                <span className="flex items-center gap-2"><Settings size={14} /> Settings</span>
                <span className="text-[11px] text-[#8a877f]">Ctrl,</span>
              </button>
              <button type="button" role="menuitem" className="flex h-8 w-full items-center justify-between rounded-lg px-2 text-left hover:bg-[#f0efeb]">
                <span className="flex items-center gap-2"><Globe2 size={14} /> Language</span>
                <span className="text-[#8a877f]">›</span>
              </button>
              <button type="button" role="menuitem" className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]">
                <HelpCircle size={14} /> Get help
              </button>
              <div className="my-1 border-t border-[#ebe8df]" />
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setAccountMenuOpen(false);
                  onOpenSettings?.("extensions");
                }}
                className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]"
              >
                <Plug size={14} /> Get apps and extensions
              </button>
              <button type="button" role="menuitem" className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]">
                <Activity size={14} /> View changelog
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setAccountMenuOpen(false);
                  onOpenSettings?.("developer");
                }}
                className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]"
              >
                <Plug size={14} /> Developer
              </button>
              <div className="my-1 border-t border-[#ebe8df]" />
              <button type="button" role="menuitem" className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left hover:bg-[#f0efeb]">
                <LogOut size={14} /> Log out
              </button>
            </div>
          )}
          <button
            type="button"
            aria-label="Account and settings"
            onClick={() => setAccountMenuOpen((value) => !value)}
            className="flex h-8 w-full items-center gap-2 rounded-lg text-[13px] text-[#4b4a45] hover:bg-[#e6e5df]"
          >
            <span className="grid h-[22px] w-[22px] place-items-center rounded-full bg-[#dedbd2] text-[11px] text-[#4e4c47]">C</span>
            <span className="min-w-0 flex-1 truncate text-left">{workspaceLabel || "Local workspace"}</span>
            <span className="h-1.5 w-1.5 rounded-full bg-[#3f8f62]" />
            <ChevronDown size={13} className="text-[#8a877f]" />
          </button>
        </div>
      </div>
    </aside>
  );
}
