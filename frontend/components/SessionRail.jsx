import { useState } from "react";
import { Activity, Bot, ChevronDown, Code2, Folder, FolderOpen, Globe2, HelpCircle, LayoutPanelTop, LogOut, MessageSquare, MoreVertical, Palette, Pin, Plug, Plus, Search, Settings, Sparkles, Trash2 } from "lucide-react";

function formatSessionMeta(session) {
  const eventCount = Number.isFinite(session?.eventCount) ? session.eventCount : 0;
  return `${eventCount} event${eventCount === 1 ? "" : "s"}`;
}

const modeTabs = [
  { label: "Chat", icon: MessageSquare },
  { label: "Cowork", icon: Bot },
  { label: "Code", icon: Code2 },
];

function groupSessionsByProject(sessions, activeProjectName, projects = []) {
  const registeredProjects = Array.isArray(projects) ? projects.filter((project) => project?.path && project?.name) : [];
  const hasProjects = registeredProjects.length > 0 || sessions.some((session) => session.project?.name);
  if (!hasProjects) {
    return [{ key: "__recents__", name: "Recents", isProject: false, sessions }];
  }
  const byProject = new Map();
  const noProject = [];
  for (const project of registeredProjects) {
    byProject.set(project.path, { project, sessions: [] });
  }
  for (const session of sessions) {
    const name = session.project?.name;
    if (!name) {
      noProject.push(session);
      continue;
    }
    const project = session.project;
    const key = project.path || `name:${name}`;
    if (!byProject.has(key)) byProject.set(key, { project, sessions: [] });
    byProject.get(key).sessions.push(session);
  }
  const projectGroups = [...byProject.entries()]
    .map(([key, entry]) => ({
      key: `project:${key}`,
      name: entry.project.name,
      isProject: true,
      project: entry.project,
      sessions: entry.sessions,
    }))
    .sort((left, right) => {
      if (left.name === activeProjectName) return -1;
      if (right.name === activeProjectName) return 1;
      return left.name.localeCompare(right.name);
    });
  if (noProject.length) {
    projectGroups.push({ key: "__no_project__", name: "No project", isProject: false, sessions: noProject });
  }
  return projectGroups;
}

export default function SessionRail({
  activeMode = "Chat",
  activeProjectName = "",
  sessions = [],
  projects = [],
  activeSessionId,
  visible = true,
  workspaceLabel,
  onCustomize,
  onDeleteSession,
  onNewSession,
  onNewSessionInProject,
  onOpenArtifacts,
  onOpenConnectors,
  onOpenQuality,
  onOpenProjects,
  onOpenSettings,
  onOpenWorkspace,
  onPinSession,
  onRenameSession,
  onSelectMode,
  onSelectProject,
  onSelectSession,
}) {
  const shownSessions = sessions.length > 0 ? sessions : [{ id: "empty", title: "New chat", eventCount: 0 }];
  const [sessionMenuId, setSessionMenuId] = useState("");
  const [renameSessionId, setRenameSessionId] = useState("");
  const [renameDraft, setRenameDraft] = useState("");
  const [searchDraft, setSearchDraft] = useState("");
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState(() => new Set());
  const filteredSessions = searchDraft.trim()
    ? shownSessions.filter((session) => String(session.title || "").toLowerCase().includes(searchDraft.trim().toLowerCase()))
    : shownSessions;
  const sessionGroups = groupSessionsByProject(filteredSessions, activeProjectName, projects);
  const toggleGroup = (key) =>
    setCollapsedGroups((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

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
        {sessionGroups.map((group) => {
          const collapsed = collapsedGroups.has(group.key);
          return (
            <div key={group.key} className="group/head mb-1">
              <div className="flex items-center gap-0.5 rounded-md pr-1 text-[12px] text-[#8a877f] transition hover:bg-[#ecece7]">
                {group.isProject ? (
                  <>
                    <button
                      type="button"
                      aria-label={`${collapsed ? "Expand" : "Collapse"} project ${group.name}`}
                      aria-expanded={!collapsed}
                      onClick={() => toggleGroup(group.key)}
                      className="grid h-6 w-6 shrink-0 place-items-center rounded-md hover:bg-[#deddd6]"
                    >
                      <ChevronDown size={12} strokeWidth={2} className={`transition-transform ${collapsed ? "-rotate-90" : ""}`} />
                    </button>
                    <button
                      type="button"
                      aria-label={`Open project ${group.name}`}
                      onClick={() => onSelectProject?.(group.project)}
                      className="flex min-w-0 flex-1 items-center gap-1 py-1 text-left"
                    >
                      <Folder size={12} strokeWidth={2} className="shrink-0 text-[#a5906a]" />
                      <span className="min-w-0 flex-1 truncate">{group.name}</span>
                      <span className="shrink-0 text-[11px] text-[#b6b3aa]">{group.sessions.length}</span>
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    aria-expanded={!collapsed}
                    onClick={() => toggleGroup(group.key)}
                    className="flex min-w-0 flex-1 items-center gap-1 px-2 py-1 text-left"
                  >
                    <ChevronDown size={12} strokeWidth={2} className={`shrink-0 transition-transform ${collapsed ? "-rotate-90" : ""}`} />
                    <span className="min-w-0 flex-1 truncate">{group.name}</span>
                    <span className="shrink-0 text-[11px] text-[#b6b3aa]">{group.sessions.length}</span>
                  </button>
                )}
                {group.isProject ? (
                  <button
                    type="button"
                    aria-label={`New chat in ${group.name}`}
                    title={`New chat in ${group.name}`}
                    onClick={() => onNewSessionInProject?.(group.project)}
                    className="grid h-6 w-6 shrink-0 place-items-center rounded-md text-[#8b877f] opacity-0 transition hover:bg-[#deddd6] focus-visible:opacity-100 group-hover/head:opacity-100"
                  >
                    <Plus size={13} strokeWidth={2} />
                  </button>
                ) : null}
              </div>
              {collapsed ? null : (
                <div className="grid gap-0.5">
                  {group.sessions.map((session) => {
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
              )}
            </div>
          );
        })}
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
