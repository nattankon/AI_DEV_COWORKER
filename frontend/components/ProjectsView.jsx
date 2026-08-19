import { FolderOpen, Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";

export default function ProjectsView({ projects = [], onChooseFolder, onOpenProject }) {
  const [query, setQuery] = useState("");
  const visibleProjects = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return projects;
    return projects.filter((project) => project.name.toLocaleLowerCase().includes(normalized) || project.path.toLocaleLowerCase().includes(normalized));
  }, [projects, query]);

  return (
    <section className="mx-auto w-full max-w-4xl px-6 pb-12 pt-24">
      <div className="flex items-center justify-between gap-4">
        <h1 className="font-serif text-[30px] font-normal text-[#262521]">Projects</h1>
        <button
          type="button"
          onClick={onChooseFolder}
          className="inline-flex h-8 items-center gap-2 rounded-lg bg-[#252522] px-3 text-[13px] font-medium text-white hover:bg-[#11110f]"
        >
          <Plus size={14} />
          New project
        </button>
      </div>

      <label className="mt-5 flex h-11 items-center gap-2 rounded-xl border border-[#dedbd2] bg-white px-3 focus-within:border-[#8e9fe8] focus-within:ring-2 focus-within:ring-[#dfe5ff]">
        <Search size={15} className="text-[#8c887f]" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search projects..."
          className="min-w-0 flex-1 bg-transparent text-[14px] outline-none placeholder:text-[#99958c]"
        />
      </label>

      <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        {visibleProjects.map((project) => (
          <article key={project.path} className="min-h-36">
            <button
              type="button"
              aria-label={`Select project ${project.name}`}
              onClick={() => onOpenProject?.(project)}
              className="flex h-full min-h-36 w-full flex-col rounded-xl border border-[#e1ded7] bg-white p-4 text-left transition hover:border-[#c9c5bb] hover:bg-[#faf9f6] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8e9fe8]"
            >
              <span className="flex items-center gap-2 text-[14px] font-semibold text-[#302f2b]">
                <FolderOpen size={16} />
                {project.name}
              </span>
              <span className="mt-2 break-all text-[12px] leading-5 text-[#858178]">{project.path}</span>
              <span className="mt-auto pt-5 text-[12px] text-[#aaa69c]">Local workspace</span>
            </button>
          </article>
        ))}
      </div>

      <button
        type="button"
        onClick={onChooseFolder}
        className="mt-5 inline-flex h-9 items-center gap-2 rounded-lg border border-[#dedbd2] bg-white px-3 text-[13px] text-[#494742] hover:bg-[#f6f5f2]"
      >
        <FolderOpen size={15} />
        Choose a different folder
      </button>
    </section>
  );
}
