import { Check, ChevronDown, ChevronRight } from "lucide-react";
import { useRef, useState } from "react";
import useClickOutside from "../lib/useClickOutside";

const MODEL_OPTIONS = ["qwen/qwen3.5-9b", "qwen2.5-7b-instruct"];
const EFFORT_OPTIONS = ["Low", "Medium", "High"];

function modelBadge(model) {
  return model?.badge || model?.tier || model?.billing || "model";
}

function modelTitle(model) {
  return model?.label || model?.id || "";
}

function flattenProviderModels(providerGroups) {
  return providerGroups.flatMap((provider) => (provider.models || []).map((model) => ({ ...model, provider })));
}

function recommendedLabel(model) {
  if (model.default_model || model.default) return "Free default";
  if ((model.strengths || []).includes("coding")) return "Coding";
  if ((model.strengths || []).includes("reasoning")) return "Reasoning";
  if ((model.strengths || []).includes("long-context")) return "Long context";
  return modelBadge(model);
}

export default function ModelMenu({ effort, modelLabel, modelProviders = [], onEffortChange, onModelChange, onManageKeys }) {
  const [open, setOpen] = useState(false);
  const [activeProviderId, setActiveProviderId] = useState("");
  const rootRef = useRef(null);
  const openProvider = (id) => {
    setActiveProviderId(id);
  };
  useClickOutside(rootRef, open, () => {
    setOpen(false);
    setActiveProviderId("");
  });
  const providerGroups = Array.isArray(modelProviders)
    ? modelProviders.filter((provider) => Array.isArray(provider?.models) && provider.models.length > 0)
    : [];
  const providerModels = flattenProviderModels(providerGroups);
  const selectedModel = providerModels.find((model) => model.id === modelLabel);
  const selectedText = modelLabel === "auto" ? "Auto" : modelTitle(selectedModel) || modelLabel || "Local model";
  const recommendedModels = providerModels.filter((model) => model.recommended || model.default_model || model.default).slice(0, 5);
  const activeProvider = providerGroups.find((provider) => provider.id === activeProviderId);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-label="Model and effort"
        onClick={() => {
          setOpen((value) => !value);
          setActiveProviderId("");
        }}
        className="flex h-8 max-w-[240px] items-center gap-1.5 truncate rounded-lg px-2 text-[13px] text-[#4a4945] transition hover:bg-[#efede8]"
      >
        <span className="truncate">{selectedText}</span>
        <span className="text-[#8a877f]">{effort}</span>
        <ChevronDown size={13} />
      </button>
      {open && (
        <div
          role="menu"
          aria-label="Model choices"
          className="absolute bottom-10 right-0 z-40 w-64 rounded-xl border border-[#dedbd2] bg-white p-1.5 shadow-[0_14px_38px_rgba(0,0,0,0.16)]"
        >
          {providerGroups.length > 0 ? (
            activeProvider ? (
              <div className="py-1">
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => openProvider("")}
                  className="flex h-8 w-full items-center gap-2 rounded-lg px-2 text-left text-[13px] hover:bg-[#f0efeb]"
                >
                  <ChevronDown size={13} className="rotate-90 text-[#8a877f]" />
                  <span className="font-medium">{activeProvider.label}</span>
                </button>
                <div className="mb-1 flex items-center justify-between border-b border-[#ebe8df] px-2 pb-2 pt-1">
                  <span className={activeProvider.configured ? "text-[11px] text-[#3f8f62]" : "text-[11px] text-[#b44b3d]"}>
                    {activeProvider.configured ? "✓ Key saved" : "No key yet"}
                  </span>
                  {onManageKeys && (
                    <button
                      type="button"
                      aria-label="Manage API keys in settings"
                      onClick={() => {
                        setOpen(false);
                        setActiveProviderId("");
                        onManageKeys();
                      }}
                      className="rounded-md px-1.5 py-0.5 text-[11px] text-[#6f6b63] hover:bg-[#f0efeb]"
                    >
                      Manage keys
                    </button>
                  )}
                </div>
                <div role="menu" aria-label={`${activeProvider.label} models`} className="pt-1">
                  {activeProvider.models.map((model) => (
                    <button
                      key={model.id}
                      type="button"
                      role="menuitemradio"
                      aria-checked={model.id === modelLabel}
                      onClick={() => onModelChange?.(model.id)}
                      className="flex min-h-8 w-full items-center justify-between gap-2 rounded-lg px-2 text-left text-[13px] hover:bg-[#f0efeb]"
                    >
                      <span className="min-w-0 truncate">{modelTitle(model)}</span>
                      <span className="ml-auto shrink-0 rounded-md bg-[#f0efeb] px-1.5 py-0.5 text-[11px] text-[#77746d]">
                        {modelBadge(model)}
                      </span>
                      {model.id === modelLabel && <Check size={14} className="shrink-0 text-[#4d73df]" />}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {recommendedModels.length > 0 && (
                  <div className="py-1">
                    <div className="px-2 py-1 text-[11px] font-medium text-[#99958c]">Recommended</div>
                    <button
                      type="button"
                      role="menuitemradio"
                      aria-checked={modelLabel === "auto"}
                      onClick={() => onModelChange?.("auto")}
                      className="flex min-h-8 w-full items-center justify-between gap-2 rounded-lg px-2 text-left text-[13px] hover:bg-[#f0efeb]"
                    >
                      <span className="w-24 shrink-0 text-[12px] text-[#8a877f]">Router</span>
                      <span className="min-w-0 flex-1 truncate">Auto</span>
                      {modelLabel === "auto" && <Check size={14} className="shrink-0 text-[#4d73df]" />}
                    </button>
                    {recommendedModels.map((model) => (
                      <button
                        key={model.id}
                        type="button"
                        role="menuitemradio"
                        aria-checked={model.id === modelLabel}
                        onClick={() => onModelChange?.(model.id)}
                        className="flex min-h-8 w-full items-center justify-between gap-2 rounded-lg px-2 text-left text-[13px] hover:bg-[#f0efeb]"
                      >
                        <span className="w-24 shrink-0 text-[12px] text-[#8a877f]">{recommendedLabel(model)}</span>
                        <span className="min-w-0 flex-1 truncate">{modelTitle(model)}</span>
                        {model.id === modelLabel && <Check size={14} className="shrink-0 text-[#4d73df]" />}
                      </button>
                    ))}
                  </div>
                )}
                <div className="my-1 border-t border-[#ebe8df]" />
                <div className="px-2 py-1 text-[11px] font-medium text-[#99958c]">Providers</div>
                {providerGroups.map((provider) => (
                  <button
                    key={provider.id}
                    type="button"
                    role="menuitem"
                    aria-label={`${provider.label} ${provider.configured ? "ready" : "no key"}`}
                    onClick={() => openProvider(provider.id)}
                    className="flex h-8 w-full items-center justify-between gap-2 rounded-lg px-2 text-left text-[13px] hover:bg-[#f0efeb]"
                  >
                    <span className="min-w-0 truncate">{provider.label}</span>
                    <span className={provider.configured ? "text-[11px] text-[#3f8f62]" : "text-[11px] text-[#b44b3d]"}>
                      {provider.configured ? "ready" : "no key"}
                    </span>
                    <ChevronRight size={13} className="shrink-0 text-[#8a877f]" />
                  </button>
                ))}
              </>
            )
          ) : (
            <>
              <div className="px-2 py-1 text-[11px] font-medium text-[#99958c]">Models</div>
              <button
                type="button"
                role="menuitemradio"
                aria-checked={modelLabel === "auto"}
                onClick={() => onModelChange?.("auto")}
                className="flex min-h-8 w-full items-center justify-between rounded-lg px-2 text-left text-[13px] hover:bg-[#f0efeb]"
              >
                <span>Auto</span>
                {modelLabel === "auto" && <Check size={14} className="text-[#4d73df]" />}
              </button>
              {MODEL_OPTIONS.map((model) => (
                <button
                  key={model}
                  type="button"
                  role="menuitemradio"
                  aria-checked={model === modelLabel}
                  onClick={() => onModelChange?.(model)}
                  className="flex min-h-8 w-full items-center justify-between rounded-lg px-2 text-left text-[13px] hover:bg-[#f0efeb]"
                >
                  <span>{model}</span>
                  {model === modelLabel && <Check size={14} className="text-[#4d73df]" />}
                </button>
              ))}
            </>
          )}
          <div className="my-1 border-t border-[#ebe8df]" />
          <div className="px-2 py-1 text-[11px] font-medium text-[#99958c]">Effort</div>
          {EFFORT_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              role="menuitemradio"
              aria-label={`Effort ${option}`}
              aria-checked={option === effort}
              onClick={() => onEffortChange?.(option)}
              className="flex h-8 w-full items-center justify-between rounded-lg px-2 text-left text-[13px] hover:bg-[#f0efeb]"
            >
              {option}
              {option === effort && <Check size={14} className="text-[#4d73df]" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
