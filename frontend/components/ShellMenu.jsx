export default function ShellMenu({ open }) {
  if (!open) return null;

  return (
    <div
      role="menu"
      aria-label="Application menu"
      className="app-no-drag absolute left-2 top-9 z-50 w-28 rounded-xl border border-[#dedbd2] bg-white p-1.5 text-[13px] text-[#353431] shadow-[0_12px_34px_rgba(0,0,0,0.16)]"
    >
      {["File", "Edit", "View", "Help"].map((label) => (
        <button
          key={label}
          type="button"
          role="menuitem"
          aria-label={label}
          className="flex h-7 w-full items-center justify-between rounded-lg px-2 text-left hover:bg-[#f0efeb]"
        >
          {label}
          <span className="text-[#aaa79f]">›</span>
        </button>
      ))}
    </div>
  );
}
