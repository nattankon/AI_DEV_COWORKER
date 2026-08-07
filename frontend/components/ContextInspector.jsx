import { selectChangedFiles, selectPendingApprovals } from "../model/coworkSelectors";

export default function ContextInspector({ modelLabel, state, workspaceLabel }) {
  const pendingApprovals = selectPendingApprovals(state);
  const changedFiles = selectChangedFiles(state);

  return (
    <aside className="hidden w-60 shrink-0 border-l border-line bg-[#151619] p-4 xl:block">
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">Run context</div>
      <dl className="mt-4 space-y-3 text-xs">
        <div>
          <dt className="font-mono text-[9px] uppercase tracking-[0.14em] text-dim">Provider</dt>
          <dd className="mt-1 text-muted">LM Studio / local</dd>
        </div>
        <div>
          <dt className="font-mono text-[9px] uppercase tracking-[0.14em] text-dim">Model</dt>
          <dd className="mt-1 truncate text-muted">{modelLabel || "No model selected"}</dd>
        </div>
        <div>
          <dt className="font-mono text-[9px] uppercase tracking-[0.14em] text-dim">Working directory</dt>
          <dd className="mt-1 truncate text-muted">{workspaceLabel || "Not selected"}</dd>
        </div>
        <div>
          <dt className="font-mono text-[9px] uppercase tracking-[0.14em] text-dim">Approvals</dt>
          <dd className="mt-1 text-muted">{pendingApprovals.length} pending</dd>
        </div>
        <div>
          <dt className="font-mono text-[9px] uppercase tracking-[0.14em] text-dim">Changed files</dt>
          <dd className="mt-1 text-muted">{changedFiles.length}</dd>
        </div>
      </dl>
    </aside>
  );
}
