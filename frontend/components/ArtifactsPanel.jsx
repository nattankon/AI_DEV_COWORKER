import { useMemo, useState } from "react";

function latestVersion(artifact) {
  const versions = Array.isArray(artifact?.versions) ? artifact.versions : [];
  return versions.at(-1) ?? {};
}

function artifactAttachment(artifact) {
  const version = latestVersion(artifact);
  return {
    label: String(artifact?.title || "Untitled artifact"),
    source: "artifact",
    kind: String(artifact?.type || "text"),
    content: String(version.content ?? artifact?.content ?? "").slice(0, 12000),
    artifactId: String(artifact?.id || ""),
    version: version.version ?? 1,
  };
}

function artifactFileName(artifact, version) {
  const title = String(artifact?.title || "artifact").trim().replace(/[\\/:*?"<>|]+/g, "-") || "artifact";
  const type = String(artifact?.type || "txt").trim().toLowerCase();
  const extension = type === "html" ? "html" : type === "markdown" ? "md" : type === "javascript" ? "js" : type === "python" ? "py" : "txt";
  return `${title}-v${version?.version ?? 1}.${extension}`;
}

function downloadArtifact(artifact, version, content) {
  if (typeof document === "undefined" || typeof URL === "undefined") return;
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = artifactFileName(artifact, version);
  anchor.click();
  URL.revokeObjectURL(href);
}

export default function ArtifactsPanel({ artifacts = [], onAttachArtifact }) {
  const [selectedId, setSelectedId] = useState("");
  const shownArtifacts = Array.isArray(artifacts) ? artifacts : [];
  const selected = useMemo(
    () => shownArtifacts.find((artifact) => artifact.id === selectedId) ?? shownArtifacts[0],
    [shownArtifacts, selectedId],
  );
  const version = latestVersion(selected);
  const content = String(version.content ?? selected?.content ?? "");
  const type = String(selected?.type ?? "text");

  return (
    <section className="mx-auto grid min-h-full w-full max-w-6xl grid-cols-[280px_1fr] gap-5 px-6 py-12">
      <aside className="min-h-0 rounded-xl border border-[#e1ded7] bg-[#fbfaf6] p-3">
        <div className="mb-3 flex items-center justify-between">
          <h1 className="text-[22px] font-semibold text-[#2f2f2d]">Artifacts</h1>
          <span className="text-[12px] text-[#8a877f]">{shownArtifacts.length}</span>
        </div>
        <div className="grid gap-1">
          {shownArtifacts.length === 0 ? (
            <p className="px-2 py-3 text-[13px] leading-5 text-[#7d786e]">
              Generated code, HTML, and documents will appear here.
            </p>
          ) : shownArtifacts.map((artifact) => (
            <button
              key={artifact.id}
              type="button"
              onClick={() => setSelectedId(artifact.id)}
              className={`min-h-10 rounded-lg px-2 py-1.5 text-left text-[13px] ${
                artifact.id === selected?.id ? "bg-[#e9e6df] text-[#2f2f2d]" : "hover:bg-[#f0efeb]"
              }`}
            >
              <span className="block truncate font-medium">{artifact.title || "Untitled artifact"}</span>
              <span className="text-[11px] text-[#8a877f]">{artifact.type || "text"} · v{latestVersion(artifact).version ?? 1}</span>
            </button>
          ))}
        </div>
      </aside>
      <main className="min-h-0 rounded-xl border border-[#e1ded7] bg-white">
        {!selected ? (
          <div className="grid h-full min-h-[460px] place-items-center text-[14px] text-[#8a877f]">
            No artifact selected
          </div>
        ) : (
          <div className="flex h-full min-h-[460px] flex-col">
            <div className="flex min-h-14 items-center justify-between border-b border-[#ebe8df] px-4">
              <div>
                <h2 className="text-[15px] font-semibold text-[#2f2f2d]">{selected.title}</h2>
                <p className="text-[12px] text-[#8a877f]">{type} · version {version.version ?? 1}</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => onAttachArtifact?.(artifactAttachment(selected))}
                  className="h-8 rounded-lg border border-[#dedbd2] px-3 text-[13px] hover:bg-[#f7f6f2]"
                >
                  Attach to Chat
                </button>
                <button
                  type="button"
                  onClick={() => navigator.clipboard?.writeText(content)}
                  className="h-8 rounded-lg border border-[#dedbd2] px-3 text-[13px] hover:bg-[#f7f6f2]"
                >
                  Copy
                </button>
                <button
                  type="button"
                  onClick={() => downloadArtifact(selected, version, content)}
                  className="h-8 rounded-lg border border-[#dedbd2] px-3 text-[13px] hover:bg-[#f7f6f2]"
                >
                  Download
                </button>
              </div>
            </div>
            {type === "html" ? (
              <iframe
                title={selected.title || "HTML artifact"}
                sandbox=""
                srcDoc={content}
                className="min-h-0 flex-1 bg-white"
              />
            ) : (
              <pre className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap p-4 text-[13px] leading-6 text-[#2f2f2d]">
                {content}
              </pre>
            )}
          </div>
        )}
      </main>
    </section>
  );
}
