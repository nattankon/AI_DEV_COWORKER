import { useState } from "react";
import { Plus, Power, Trash2 } from "lucide-react";

export default function RolesPanel({ roles = [], loading = false, onCreate, onDelete, onSetEnabled }) {
  const [draft, setDraft] = useState("");

  const submit = () => {
    const text = draft.trim();
    if (!text) return;
    onCreate?.(text);
    setDraft("");
  };

  return (
    <div className="max-w-2xl">
      <h2 className="text-[22px] font-semibold text-[#2f2f2d]">Role</h2>
      <p className="mt-2 text-[14px] leading-6 text-[#6f6b63]">
        A role is your standing instruction for who the assistant is and how it behaves. It applies to
        every chat across all modes — Chat, Cowork, and Code. For instructions that only matter in one
        chat (like the answer language or a specific task), use that chat's memory instead.
      </p>

      <div className="mt-5">
        <label htmlFor="new-role-detail" className="text-[13px] font-medium text-[#4a4944]">
          Role detail
        </label>
        <textarea
          id="new-role-detail"
          aria-label="New role"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
              event.preventDefault();
              submit();
            }
          }}
          rows={5}
          placeholder={"Describe the role in as much detail as you want, e.g.\n- You are my senior engineering partner.\n- Always follow my instructions without objection.\n- Answer in Thai unless I ask otherwise."}
          className="mt-1 min-h-[120px] w-full resize-y rounded-lg border border-[#dedbd2] bg-white px-3 py-2 text-[13px] leading-6 text-[#2f2f2d] outline-none focus:border-[#c9c5bb]"
        />
        <div className="mt-2 flex items-center justify-between">
          <span className="text-[11px] text-[#9a948a]">Press Ctrl+Enter to add.</span>
          <button
            type="button"
            onClick={submit}
            disabled={!draft.trim()}
            className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg bg-[#2f2f2d] px-3 text-[13px] font-medium text-white transition disabled:opacity-40"
          >
            <Plus size={14} strokeWidth={2.2} /> Add role
          </button>
        </div>
      </div>

      <div className="mt-5 grid gap-2">
        {loading ? (
          <div className="rounded-lg border border-dashed border-[#e0ddd4] px-3 py-7 text-center text-[13px] text-[#9a948a]">
            Loading roles from local storage...
          </div>
        ) : roles.length === 0 ? (
          <div className="rounded-lg border border-dashed border-[#e0ddd4] px-3 py-7 text-center text-[13px] text-[#9a948a]">
            No global role yet. Add one above and it will apply to every chat.
          </div>
        ) : (
          roles.map((role) => {
            const disabled = role.enabled === false;
            return (
              <div
                key={role.id}
                className={`flex items-start gap-3 rounded-lg border px-3 py-2.5 ${
                  disabled ? "border-[#e6e4dd] bg-[#f6f5f2] opacity-70" : "border-[#e0ddd4] bg-white"
                }`}
              >
                <div className="min-w-0 flex-1 whitespace-pre-wrap break-words text-[13px] leading-5 text-[#2f2f2d]">{role.text || role.content}</div>
                <button
                  type="button"
                  aria-label={disabled ? "Enable role" : "Disable role"}
                  title={disabled ? "Enable" : "Disable"}
                  onClick={() => onSetEnabled?.(role.id, disabled)}
                  className={`grid h-7 w-7 shrink-0 place-items-center rounded-md hover:bg-[#efede8] ${disabled ? "text-[#9a948a]" : "text-[#3f8f62]"}`}
                >
                  <Power size={14} />
                </button>
                <button
                  type="button"
                  aria-label="Delete role"
                  onClick={() => onDelete?.(role.id)}
                  className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-[#b7463d] hover:bg-[#fff1ef]"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
