import { useEffect, useMemo, useState } from "react";
import {
  ChevronRight,
  FileCode2,
  Folder,
  GitBranch,
  History,
  Play,
  RefreshCw,
} from "lucide-react";

const verificationPresets = ["python-tests", "frontend-tests", "frontend-build"];

function requestId(action) {
  const suffix = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${action}-${suffix}`;
}

function joinWorkspacePath(parent, child) {
  return parent === "." ? child : `${parent}/${child}`;
}

export default function WorkspacePanel({ bridge, mode, workspacePath }) {
  const [activeTab, setActiveTab] = useState("Files");
  const [currentDirectory, setCurrentDirectory] = useState(".");
  const [entriesByDirectory, setEntriesByDirectory] = useState({});
  const [selectedFile, setSelectedFile] = useState("");
  const [fileContent, setFileContent] = useState("");
  const [inspection, setInspection] = useState({ git_status: {}, git_diff: {}, backups: [] });
  const [verification, setVerification] = useState(null);
  const [notice, setNotice] = useState("");
  const [pendingAction, setPendingAction] = useState("");

  const entries = entriesByDirectory[currentDirectory] ?? [];
  const workspaceName = useMemo(
    () => workspacePath.split(/[\\/]/).filter(Boolean).at(-1) || "No project selected",
    [workspacePath],
  );

  const sendAction = (action, payload = {}) => {
    const requestIdValue = requestId(action);
    setPendingAction(action);
    void bridge.workspaceAction?.({ requestId: requestIdValue, action, ...payload });
    return requestIdValue;
  };

  const refreshWorkspace = () => {
    if (!workspacePath) return;
    sendAction("list_directory", { path: currentDirectory });
    sendAction("inspect");
  };

  useEffect(() => bridge.subscribeWorkspace?.((event) => {
    const result = event?.result ?? {};
    if (event?.action === "list_directory") {
      setEntriesByDirectory((current) => ({
        ...current,
        [result.path || currentDirectory]: Array.isArray(result.entries) ? result.entries : [],
      }));
    } else if (event?.action === "read_file") {
      setSelectedFile(result.path || selectedFile);
      setFileContent(String(result.content ?? ""));
    } else if (event?.action === "inspect") {
      setInspection(result);
    } else if (event?.action === "run_verification") {
      setVerification(result);
    } else if (event?.action === "restore_backup") {
      setNotice(result.status === "restored" ? `Restored ${result.path}` : result.error || `Restore ${result.status}`);
      sendAction("inspect");
    }
    setPendingAction("");
  }), [bridge, currentDirectory, selectedFile]);

  useEffect(() => {
    setCurrentDirectory(".");
    setEntriesByDirectory({});
    setSelectedFile("");
    setFileContent("");
    setVerification(null);
    setNotice("");
    if (!workspacePath) return;
    sendAction("list_directory", { path: "." });
    sendAction("inspect");
  }, [workspacePath]);

  const openEntry = (entry) => {
    const isDirectory = entry.endsWith("/");
    const name = isDirectory ? entry.slice(0, -1) : entry;
    const path = joinWorkspacePath(currentDirectory, name);
    if (isDirectory) {
      setCurrentDirectory(path);
      sendAction("list_directory", { path });
      return;
    }
    setSelectedFile(path);
    sendAction("read_file", { path });
  };

  if (!workspacePath) {
    return (
      <section className="grid min-h-full place-items-center px-6">
        <div className="text-center">
          <Folder className="mx-auto mb-3 text-[#8d8981]" size={26} />
          <h1 className="text-xl font-semibold text-[#34332f]">{mode} workspace</h1>
          <p className="mt-2 text-sm text-[#8d8981]">Choose a project folder to inspect files and verification evidence.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="flex min-h-full flex-col" aria-label={`${mode} workspace panel`}>
      <div className="flex min-h-16 items-center justify-between border-b border-[#e4e1d9] px-6">
        <div className="min-w-0">
          <h1 className="text-[18px] font-semibold text-[#34332f]">{mode} workspace</h1>
          <p className="truncate text-[12px] text-[#8d8981]">{workspaceName} · {workspacePath}</p>
        </div>
        <button type="button" aria-label="Refresh workspace" onClick={refreshWorkspace} className="grid h-8 w-8 place-items-center rounded-md hover:bg-[#f0efeb]">
          <RefreshCw size={15} />
        </button>
      </div>

      <div className="flex h-11 items-end gap-1 border-b border-[#e4e1d9] px-5" role="tablist" aria-label="Workspace views">
        {["Files", "Changes", "Verification", "Backups"].map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            onClick={() => setActiveTab(tab)}
            className={`h-10 border-b-2 px-3 text-[13px] ${activeTab === tab ? "border-[#d96b4a] text-[#302f2b]" : "border-transparent text-[#807c74] hover:text-[#302f2b]"}`}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        {activeTab === "Files" && (
          <div className="grid h-full min-h-[480px] grid-cols-[260px_minmax(0,1fr)]">
            <aside className="overflow-y-auto border-r border-[#e4e1d9] bg-[#faf9f6] p-3" aria-label="Workspace files">
              <div className="mb-2 flex items-center gap-1 text-[12px] text-[#8d8981]">
                <Folder size={13} /> {currentDirectory}
              </div>
              {currentDirectory !== "." && (
                <button type="button" onClick={() => setCurrentDirectory(currentDirectory.split("/").slice(0, -1).join("/") || ".")} className="mb-1 flex h-8 w-full items-center gap-2 rounded-md px-2 text-left text-[13px] hover:bg-[#eceae4]">
                  <ChevronRight className="rotate-180" size={14} /> Parent folder
                </button>
              )}
              {entries.map((entry) => {
                const directory = entry.endsWith("/");
                const label = directory ? entry.slice(0, -1) : entry;
                return (
                  <button key={entry} type="button" onClick={() => openEntry(entry)} className="flex h-8 w-full items-center gap-2 rounded-md px-2 text-left text-[13px] hover:bg-[#eceae4]">
                    {directory ? <Folder size={14} /> : <FileCode2 size={14} />}
                    <span className="truncate">{label}</span>
                  </button>
                );
              })}
            </aside>
            <div className="min-w-0 overflow-auto bg-white p-5">
              <div className="mb-3 flex h-7 items-center gap-2 border-b border-[#ebe8e0] text-[12px] text-[#77736b]">
                <FileCode2 size={14} /> {selectedFile || "Select a file"}
              </div>
              <pre className="whitespace-pre-wrap break-words font-mono text-[13px] leading-6 text-[#34332f]">{fileContent}</pre>
            </div>
          </div>
        )}

        {activeTab === "Changes" && (
          <div className="grid h-full min-h-[480px] grid-cols-[280px_minmax(0,1fr)]">
            <aside className="overflow-y-auto border-r border-[#e4e1d9] bg-[#faf9f6] p-4">
              <div className="mb-4 flex items-center gap-2 text-sm font-medium"><GitBranch size={15} /> {inspection.git_status?.branch || "No Git branch"}</div>
              {(inspection.git_status?.changes ?? []).map((change) => (
                <div key={`${change.code}-${change.path}`} className="flex min-h-8 items-center gap-2 border-t border-[#ebe8e0] py-2 text-[13px]">
                  <span className="font-mono text-[#b45b43]">{change.code}</span><span className="break-all">{change.path}</span>
                </div>
              ))}
            </aside>
            <pre className="overflow-auto whitespace-pre-wrap p-5 font-mono text-[12px] leading-5 text-[#34332f]">{inspection.git_diff?.stdout || inspection.git_diff?.error || "No unstaged changes."}</pre>
          </div>
        )}

        {activeTab === "Verification" && (
          <div className="mx-auto max-w-4xl p-6">
            <div className="flex flex-wrap gap-2">
              {verificationPresets.map((preset) => (
                <button key={preset} type="button" disabled={pendingAction === "run_verification"} onClick={() => sendAction("run_verification", { name: preset })} className="flex h-9 items-center gap-2 rounded-md border border-[#dcd8cf] px-3 text-[13px] hover:bg-[#f5f3ee] disabled:opacity-50">
                  <Play size={14} /> Run {preset}
                </button>
              ))}
            </div>
            <div className="mt-5 border-t border-[#e4e1d9] pt-4">
              <div className="text-[13px] font-medium text-[#34332f]">{verification ? `${verification.name}: ${verification.status}` : "No verification run selected"}</div>
              <pre className="mt-3 max-h-[420px] overflow-auto whitespace-pre-wrap bg-[#faf9f6] p-4 font-mono text-[12px] leading-5">{verification?.stdout || verification?.stderr || ""}</pre>
            </div>
          </div>
        )}

        {activeTab === "Backups" && (
          <div className="mx-auto max-w-4xl p-6">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium"><History size={15} /> Rollback backups</div>
            {notice && <div className="mb-3 text-[13px] text-[#4f7442]">{notice}</div>}
            {(inspection.backups ?? []).map((backup) => (
              <div key={backup.backup_path} className="flex min-h-14 items-center justify-between gap-4 border-t border-[#e4e1d9] py-3">
                <div className="min-w-0">
                  <div className="truncate text-[13px] font-medium">{backup.target_path}</div>
                  <div className="truncate text-[11px] text-[#8d8981]">{backup.backup_path}</div>
                </div>
                <button type="button" onClick={() => sendAction("restore_backup", { backupPath: backup.backup_path })} className="h-8 shrink-0 rounded-md border border-[#dcd8cf] px-3 text-[12px] hover:bg-[#f5f3ee]">
                  Restore {backup.target_path}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
