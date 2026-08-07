import { Activity, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";

function percent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "0%";
  return `${Math.round(number * 100)}%`;
}

function statusTone(status) {
  return status === "pass" ? "text-[#28784c] bg-[#edf7f0] border-[#cde8d5]" : "text-[#a84632] bg-[#fff3ef] border-[#efd4cb]";
}

function flattenModels(modelProviders = []) {
  const out = [];
  for (const provider of Array.isArray(modelProviders) ? modelProviders : []) {
    const models = Array.isArray(provider?.models) ? provider.models : [];
    for (const model of models) {
      const id = String(model?.id || model?.model || model?.label || "").trim();
      if (id) out.push({ id, label: String(model?.label || id) });
    }
  }
  return out;
}

function matrixCells(matrix) {
  return Array.isArray(matrix?.cells) ? matrix.cells : [];
}

function sourceProfileRows(profile) {
  const domains = profile?.domains && typeof profile.domains === "object" ? profile.domains : {};
  return Object.entries(domains)
    .map(([domain, row]) => ({ domain, ...(row && typeof row === "object" ? row : {}) }))
    .sort((a, b) => Number(b.success_rate || 0) - Number(a.success_rate || 0) || Number(b.runs || 0) - Number(a.runs || 0))
    .slice(0, 8);
}

export default function QualityEvalPanel({ state = {}, modelProviders = [], onRefresh, onRunSnapshot, onRunLive }) {
  const cases = Array.isArray(state.cases) ? state.cases : [];
  const snapshot = state.snapshot && typeof state.snapshot === "object" ? state.snapshot : null;
  const results = Array.isArray(snapshot?.results) ? snapshot.results : [];
  const liveMatrix = state.live_matrix && typeof state.live_matrix === "object" ? state.live_matrix : null;
  const sourceRows = sourceProfileRows(state.source_profile);
  const textDiagnostics = state.text_diagnostics && typeof state.text_diagnostics === "object" ? state.text_diagnostics : null;
  const availableModels = useMemo(() => flattenModels(modelProviders), [modelProviders]);
  const categories = useMemo(() => Array.from(new Set(cases.map((item) => String(item.category || "")).filter(Boolean))), [cases]);
  const [selectedModels, setSelectedModels] = useState(() => (availableModels[0]?.id ? [availableModels[0].id] : []));
  const [selectedCategories, setSelectedCategories] = useState(() => (categories[0] ? [categories[0]] : []));
  const [confirmedLive, setConfirmedLive] = useState(false);
  const [liveNotice, setLiveNotice] = useState("");

  const effectiveModels = selectedModels.length ? selectedModels : (availableModels[0]?.id ? [availableModels[0].id] : []);
  const effectiveCategories = selectedCategories.length ? selectedCategories : (categories[0] ? [categories[0]] : []);

  const toggleValue = (items, value) => (
    items.includes(value) ? items.filter((item) => item !== value) : [...items, value]
  );

  const runLive = () => {
    if (!confirmedLive) {
      setLiveNotice("Confirm live model/API calls before running.");
      return;
    }
    setLiveNotice("");
    onRunLive?.({
      live: true,
      confirmed: true,
      models: effectiveModels,
      categories: effectiveCategories,
    });
  };

  return (
    <section className="mx-auto flex min-h-full w-full max-w-5xl flex-col gap-4 px-5 py-10 text-[#2f2f2d]">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="mb-1 flex items-center gap-2 text-[12px] uppercase tracking-[0.16em] text-[#8a877f]">
            <Activity size={15} />
            Chat quality
          </div>
          <h1 className="font-serif text-[34px] font-normal leading-tight">Evaluation snapshot</h1>
          <p className="mt-1 max-w-2xl text-[14px] leading-6 text-[#6f6b63]">
            Offline fixture checks are local. Live matrix scoring requires explicit confirmation because it calls selected models and may use credits.
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={onRefresh} className="inline-flex h-9 items-center gap-2 rounded-lg border border-[#dedbd2] bg-white px-3 text-[13px] hover:bg-[#f6f5f2]">
            <RefreshCw size={14} />
            Refresh
          </button>
          <button type="button" onClick={() => onRunSnapshot?.({ results: [] })} className="h-9 rounded-lg bg-[#2f2f2d] px-3 text-[13px] text-white hover:bg-[#1f1f1d]">
            Run snapshot
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-[#e6e2d8] bg-white p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-[13px] font-semibold">Live matrix</div>
            <div className="mt-1 text-[12px] leading-5 text-[#6f6b63]">Pick models and categories, then confirm live model/API calls before running.</div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="inline-flex h-8 items-center gap-2 rounded-lg border border-[#dedbd2] bg-[#fbfaf7] px-3 text-[12px] text-[#4a4945]">
              <input
                aria-label="Confirm live model/API calls"
                type="checkbox"
                checked={confirmedLive}
                onChange={(event) => setConfirmedLive(event.target.checked)}
              />
              Confirm live
            </label>
            <button type="button" onClick={runLive} className="h-8 rounded-lg bg-[#2f2f2d] px-3 text-[12px] text-white hover:bg-[#1f1f1d]">
              Run live matrix
            </button>
          </div>
        </div>
        {liveNotice && <div className="mt-2 text-[12px] text-[#a84632]">{liveNotice}</div>}
        {state.requires_confirmation && state.message && <div className="mt-2 text-[12px] text-[#a84632]">{state.message}</div>}
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div>
            <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-[#8a877f]">Models</div>
            <div className="flex flex-wrap gap-1.5">
              {(availableModels.length ? availableModels : [{ id: "zai:glm-4.5-flash", label: "zai:glm-4.5-flash" }]).slice(0, 12).map((model) => (
                <button
                  key={model.id}
                  type="button"
                  onClick={() => setSelectedModels((current) => toggleValue(current, model.id))}
                  className={`rounded-md border px-2 py-1 text-[11px] ${effectiveModels.includes(model.id) ? "border-[#c8bfae] bg-[#eee9de] text-[#2f2f2d]" : "border-[#e6e2d8] bg-white text-[#6f6b63]"}`}
                >
                  {model.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-[#8a877f]">Categories</div>
            <div className="flex flex-wrap gap-1.5">
              {(categories.length ? categories : ["general", "web", "thai"]).map((category) => (
                <button
                  key={category}
                  type="button"
                  onClick={() => setSelectedCategories((current) => toggleValue(current, category))}
                  className={`rounded-md border px-2 py-1 text-[11px] ${effectiveCategories.includes(category) ? "border-[#c8bfae] bg-[#eee9de] text-[#2f2f2d]" : "border-[#e6e2d8] bg-white text-[#6f6b63]"}`}
                >
                  {category}
                </button>
              ))}
            </div>
          </div>
        </div>
        {liveMatrix && (
          <div className="mt-4 overflow-hidden rounded-lg border border-[#ece8df]">
            <div className="grid gap-2 border-b border-[#ece8df] bg-[#fbfaf7] px-3 py-2 text-[12px] text-[#6f6b63] md:grid-cols-5">
              <span>Pass {percent(liveMatrix.summary?.pass_rate || 0)}</span>
              <span>Latency {liveMatrix.summary?.avg_latency_ms || 0}ms</span>
              <span>Hallucination {percent(liveMatrix.summary?.hallucination_rate || 0)}</span>
              <span>Source quality {percent(liveMatrix.summary?.source_quality_rate || 0)}</span>
              <span>Cells {liveMatrix.summary?.total_cells || matrixCells(liveMatrix).length}</span>
            </div>
            <div className="divide-y divide-[#eee9df]">
              {matrixCells(liveMatrix).map((cell) => (
                <div key={`${cell.model}-${cell.category}-${cell.prompt || ""}`} className="grid gap-2 px-3 py-2 text-[12px] md:grid-cols-[1.5fr_0.8fr_0.7fr_0.8fr]">
                  <span className="truncate font-medium">{cell.model}</span>
                  <span>{cell.category}</span>
                  <span className={cell.status === "pass" ? "text-[#28784c]" : "text-[#a84632]"}>{cell.status}</span>
                  <span className="text-[#8a877f]">{cell.latency_ms || 0}ms</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-[#e6e2d8] bg-[#fbfaf7] p-3">
          <div className="text-[12px] text-[#8a877f]">Cases</div>
          <div className="mt-1 text-[24px] font-semibold">{state.count ?? cases.length}</div>
        </div>
        <div className="rounded-lg border border-[#e6e2d8] bg-[#fbfaf7] p-3">
          <div className="text-[12px] text-[#8a877f]">Passed</div>
          <div className="mt-1 text-[24px] font-semibold">{snapshot?.passed ?? 0}</div>
        </div>
        <div className="rounded-lg border border-[#e6e2d8] bg-[#fbfaf7] p-3">
          <div className="text-[12px] text-[#8a877f]">Failed</div>
          <div className="mt-1 text-[24px] font-semibold">{snapshot?.failed ?? 0}</div>
        </div>
        <div className="rounded-lg border border-[#e6e2d8] bg-[#fbfaf7] p-3">
          <div className="text-[12px] text-[#8a877f]">Pass rate</div>
          <div className="mt-1 text-[24px] font-semibold">{snapshot ? percent((snapshot.passed || 0) / Math.max(1, snapshot.count || 1)) : "0%"}</div>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="rounded-lg border border-[#e6e2d8] bg-white">
          <div className="border-b border-[#ece8df] px-4 py-3 text-[13px] font-semibold">Web source profile</div>
          <div className="divide-y divide-[#eee9df]">
            {sourceRows.length === 0 ? (
              <div className="px-4 py-6 text-[13px] text-[#8a877f]">No live web smoke source profile yet.</div>
            ) : sourceRows.map((row) => (
              <div key={row.domain} className="grid gap-2 px-4 py-3 text-[12px] md:grid-cols-[1fr_70px_80px_70px]">
                <span className="truncate font-medium text-[#2f2f2d]">{row.domain}</span>
                <span className="text-[#6f6b63]">{Number(row.runs || 0)} runs</span>
                <span className="text-[#28784c]">{percent(row.success_rate || 0)}</span>
                <span className="text-[#8a877f]">q{Number(row.avg_quality_score || 0).toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-[#e6e2d8] bg-white">
          <div className="border-b border-[#ece8df] px-4 py-3 text-[13px] font-semibold">Thai text diagnostics</div>
          {!textDiagnostics ? (
            <div className="px-4 py-6 text-[13px] text-[#8a877f]">No text diagnostics loaded.</div>
          ) : (
            <div className="px-4 py-3 text-[12px] leading-5 text-[#6f6b63]">
              <div className={textDiagnostics.status === "warning" ? "font-medium text-[#a84632]" : "font-medium text-[#28784c]"}>
                Status: {textDiagnostics.status || "unknown"}
              </div>
              <div className="mt-1 text-[#8a877f]">
                stdout {textDiagnostics.runtime?.stdout_encoding || "unknown"} · fs {textDiagnostics.runtime?.filesystem_encoding || "unknown"}
              </div>
              {Array.isArray(textDiagnostics.findings) && textDiagnostics.findings.length > 0 && (
                <ul className="mt-2 list-disc pl-4">
                  {textDiagnostics.findings.slice(0, 4).map((finding) => (
                    <li key={`${finding.layer}-${finding.marker}`}>
                      {finding.layer}: marker {finding.marker}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="rounded-lg border border-[#e6e2d8] bg-white">
        <div className="border-b border-[#ece8df] px-4 py-3 text-[13px] font-semibold">Fixture categories</div>
        <div className="divide-y divide-[#eee9df]">
          {cases.length === 0 ? (
            <div className="px-4 py-8 text-[13px] text-[#8a877f]">No quality cases loaded.</div>
          ) : cases.map((item) => (
            <div key={`${item.category}-${item.prompt}`} className="grid gap-2 px-4 py-3 md:grid-cols-[120px_1fr]">
              <div className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[#6f6b63]">{item.category}</div>
              <div>
                <div className="text-[13px] text-[#2f2f2d]">{item.prompt}</div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {(Array.isArray(item.checks) ? item.checks : []).map((check) => (
                    <span key={check} className="rounded-md bg-[#f3f1ec] px-1.5 py-0.5 text-[11px] text-[#6f6b63]">{check}</span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {snapshot && (
        <div className="rounded-lg border border-[#e6e2d8] bg-white">
          <div className="flex items-center justify-between border-b border-[#ece8df] px-4 py-3">
            <div className="text-[13px] font-semibold">Snapshot results</div>
            <span className={`rounded-md border px-2 py-0.5 text-[12px] ${statusTone(snapshot.status)}`}>{snapshot.status}</span>
          </div>
          <div className="divide-y divide-[#eee9df]">
            {results.map((result) => (
              <div key={`${result.category}-${result.prompt}`} className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-md border px-2 py-0.5 text-[12px] ${statusTone(result.status)}`}>{result.status}</span>
                  <span className="text-[13px] font-medium">{result.category}</span>
                  <span className="text-[12px] text-[#8a877f]">score {result.score ?? 0}</span>
                </div>
                {Array.isArray(result.findings) && result.findings.length > 0 && (
                  <ul className="mt-2 list-disc pl-5 text-[12px] leading-5 text-[#6f6b63]">
                    {result.findings.map((finding) => <li key={finding}>{finding}</li>)}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
