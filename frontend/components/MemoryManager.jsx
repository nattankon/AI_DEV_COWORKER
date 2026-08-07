import { useState } from "react";
import { Power, Trash2, X } from "lucide-react";

const KIND_LABELS = {
  do_not_remember: "Do not remember",
  identity: "Identity",
  long_term_goal: "Long-term goal",
  memory: "Memory",
  preference: "Preference",
  profile: "Profile",
  role: "Role",
  writing_style: "Writing style",
};
const MODE_LABELS = {
  Chat: "Chat",
  Cowork: "Cowork",
  Code: "Code",
};

function memoryKindLabel(kind) {
  const normalized = String(kind || "memory").trim() || "memory";
  return KIND_LABELS[normalized] || normalized.replace(/[_-]+/g, " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function normalizeMode(mode) {
  const normalized = String(mode || "").trim();
  return MODE_LABELS[normalized] || "Chat";
}

export default function MemoryManager({ activeMode = "Chat", activeSessionId = "", entries = [], open = false, onClose, onCreate, onDelete, onSetEnabled, onUpdate }) {
  const [editingId, setEditingId] = useState("");
  const [draft, setDraft] = useState("");
  const [newKind, setNewKind] = useState("preference");
  const [newMemory, setNewMemory] = useState("");
  const mode = normalizeMode(activeMode);
  const visibleEntries = entries.filter((entry) => {
    if (String(entry?.kind || "") !== "role") return true;
    const entrySessionId = String(entry?.source?.session_id || "");
    const entryMode = normalizeMode(entry?.mode || entry?.source?.mode || "Chat");
    if (entryMode !== mode) return false;
    return !entrySessionId || !activeSessionId || entrySessionId === activeSessionId;
  });

  if (!open) return null;

  const startEdit = (entry) => {
    setEditingId(entry.id);
    setDraft(entry.text || entry.content || "");
  };

  const commitEdit = () => {
    const text = draft.trim();
    if (!editingId || !text) return;
    onUpdate?.(editingId, text);
    setEditingId("");
    setDraft("");
  };

  const commitCreate = () => {
    const text = newMemory.trim();
    if (!text) return;
    onCreate?.({ kind: newKind, ...(newKind === "role" ? { mode } : {}), text });
    setNewMemory("");
    setNewKind("preference");
  };

  return (
    <div className="absolute right-5 top-14 z-50 w-[min(420px,calc(100%-32px))] rounded-xl border border-[#dedbd2] bg-white p-3 text-[13px] shadow-[0_18px_48px_rgba(0,0,0,0.16)]">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <h2 className="text-[14px] font-semibold text-[#2f2f2d]">{mode} memory</h2>
          <p className="text-[12px] text-[#8a877f]">{visibleEntries.length} saved</p>
        </div>
        <button type="button" aria-label="Close memory manager" onClick={onClose} className="grid h-7 w-7 place-items-center rounded-lg hover:bg-[#f0efeb]">
          <X size={15} />
        </button>
      </div>
      <div className="mb-3 rounded-lg border border-[#ebe8df] bg-[#fbfaf7] p-2">
        <div className="grid grid-cols-[130px_1fr_auto] gap-2">
          <label className="text-[11px] text-[#6f6b63]">
            Memory kind
            <select
              aria-label="Memory kind"
              value={newKind}
              onChange={(event) => setNewKind(event.target.value)}
              className="mt-1 h-8 w-full rounded-lg border border-[#dedbd2] bg-white px-2 text-[12px] text-[#2f2f2d] focus:outline-none focus:ring-2 focus:ring-[#d8d5cc]"
            >
              <option value="preference">Preference</option>
              <option value="profile">Profile</option>
              <option value="writing_style">Writing style</option>
              <option value="identity">Identity</option>
              <option value="long_term_goal">Long-term goal</option>
              <option value="role">Role</option>
              <option value="do_not_remember">Do not remember</option>
              <option value="memory">Memory</option>
            </select>
          </label>
          <label className="text-[11px] text-[#6f6b63]">
            New memory
            <input
              aria-label="New memory"
              value={newMemory}
              onChange={(event) => setNewMemory(event.target.value)}
              className="mt-1 h-8 w-full rounded-lg border border-[#dedbd2] bg-white px-2 text-[12px] text-[#2f2f2d] focus:outline-none focus:ring-2 focus:ring-[#d8d5cc]"
            />
          </label>
          <button
            type="button"
            onClick={commitCreate}
            disabled={!newMemory.trim()}
            className="mt-[17px] h-8 rounded-lg bg-[#2f2f2d] px-3 text-[12px] text-white hover:bg-[#1f1f1d] disabled:bg-[#d8d5cc]"
          >
            {newKind === "role" ? "Add role" : newKind === "do_not_remember" ? "Do not remember" : "Remember"}
          </button>
        </div>
      </div>
      <div className="max-h-[360px] space-y-2 overflow-y-auto pr-1">
        {visibleEntries.length === 0 ? (
          <div className="rounded-lg border border-[#ebe8df] bg-[#faf9f6] px-3 py-4 text-[#8a877f]">No saved Chat memories.</div>
        ) : visibleEntries.map((entry) => (
          <div key={entry.id} className={`rounded-lg border border-[#ebe8df] p-2 ${entry.enabled === false ? "bg-[#f1f0ec] opacity-75" : "bg-[#faf9f6]"}`}>
            {editingId === entry.id ? (
              <>
                <textarea
                  aria-label={`Edit memory ${entry.id}`}
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  rows={3}
                  className="w-full resize-none rounded-lg border border-[#dedbd2] bg-white px-2 py-1.5 text-[13px] leading-5 text-[#2f2f2d] focus:outline-none focus:ring-2 focus:ring-[#d8d5cc]"
                />
                <div className="mt-2 flex justify-end gap-2">
                  <button type="button" onClick={() => setEditingId("")} className="h-7 rounded-lg border border-[#dedbd2] px-2 text-[12px] hover:bg-white">Cancel</button>
                  <button type="button" onClick={commitEdit} className="h-7 rounded-lg bg-[#2f2f2d] px-2 text-[12px] text-white hover:bg-[#1f1f1d]">Save</button>
                </div>
              </>
            ) : (
              <>
                <button type="button" onClick={() => startEdit(entry)} className="block w-full rounded-md px-1 py-1 text-left text-[#2f2f2d] hover:bg-white">
                  {entry.text || entry.content}
                </button>
                <div className="mt-1 flex items-center justify-between px-1 text-[11px] text-[#8a877f]">
                  <div className="flex flex-wrap items-center gap-1">
                    <span className="rounded-md bg-white px-1.5 py-0.5 text-[#6f6b63]">{memoryKindLabel(entry.kind)}</span>
                    {entry.kind === "role" && (
                      <>
                        <span className="rounded-md bg-[#2f2f2d] px-1.5 py-0.5 text-white">Persona role</span>
                        <span className="rounded-md bg-white px-1.5 py-0.5 text-[#6f6b63]">This chat</span>
                        <span className="rounded-md bg-white px-1.5 py-0.5 text-[#6f6b63]">{entry.enabled === false ? "Paused" : "Active"}</span>
                      </>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    {entry.kind === "role" && (
                      <button
                        type="button"
                        aria-label={`${entry.enabled === false ? "Enable" : "Pause"} role ${entry.id}`}
                        onClick={() => onSetEnabled?.(entry.id, entry.enabled === false)}
                        className="grid h-6 w-6 place-items-center rounded-md text-[#5d5a53] hover:bg-white"
                      >
                        <Power size={13} />
                      </button>
                    )}
                    <button type="button" aria-label={`Delete memory ${entry.id}`} onClick={() => onDelete?.(entry.id)} className="grid h-6 w-6 place-items-center rounded-md text-[#a84632] hover:bg-white">
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
