import { useState } from "react";
import { KeyRound, RefreshCw } from "lucide-react";

// Providers whose keys the user can enter here. Order matches the model menu.
const PROVIDER_ORDER = ["openai", "deepseek", "zai", "gemini"];
const PROVIDER_LABELS = { openai: "OpenAI", deepseek: "DeepSeek", zai: "Z.ai", gemini: "Gemini" };
const PROVIDER_HINTS = {
  openai: "sk-proj-…",
  deepseek: "sk-…",
  zai: "your Z.ai key",
  gemini: "AIza…",
};

function orderedProviders(modelProviders) {
  const byId = new Map((Array.isArray(modelProviders) ? modelProviders : []).map((p) => [String(p?.id || ""), p]));
  return PROVIDER_ORDER.map((id) => ({
    id,
    label: PROVIDER_LABELS[id] || id,
    configured: Boolean(byId.get(id)?.configured),
  }));
}

function ProviderRow({ provider, onSaveProviderKey }) {
  const [keyValue, setKeyValue] = useState("");
  return (
    <div className="rounded-xl border border-[#e7e3da] bg-[#fbfaf7] p-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="text-[15px] font-medium text-[#2f2f2d]">{provider.label}</span>
        <span className={provider.configured ? "text-[12px] text-[#3f8f62]" : "text-[12px] text-[#b44b3d]"}>
          {provider.configured ? "✓ Key saved" : "No key yet"}
        </span>
      </div>
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          const value = keyValue.trim();
          if (!value) return;
          onSaveProviderKey?.(provider.id, value);
          setKeyValue("");
        }}
      >
        <input
          type="password"
          aria-label={`${provider.label} API key`}
          value={keyValue}
          onChange={(event) => setKeyValue(event.target.value)}
          placeholder={provider.configured ? `Replace key (${PROVIDER_HINTS[provider.id] || "key"})…` : `Paste ${PROVIDER_HINTS[provider.id] || "key"}…`}
          className="h-9 min-w-0 flex-1 rounded-lg border border-[#dedbd2] px-3 text-[13px] text-[#2f2f2d] outline-none focus:ring-2 focus:ring-[#d8d5cc]"
        />
        <button
          type="submit"
          aria-label={`Save ${provider.label} key`}
          disabled={!keyValue.trim()}
          className="h-9 shrink-0 rounded-lg bg-[#2f2f2d] px-4 text-[13px] font-medium text-white hover:bg-[#1f1f1d] disabled:cursor-not-allowed disabled:bg-[#d8d5cc]"
        >
          Save
        </button>
      </form>
    </div>
  );
}

export default function ProvidersPanel({ modelProviders = [], onSaveProviderKey, onRefreshProviders }) {
  const providers = orderedProviders(modelProviders);
  return (
    <section className="max-w-2xl">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2 text-[13px] font-medium uppercase tracking-wide text-[#8a877f]">
            <KeyRound size={15} />
            Model providers
          </div>
          <h2 className="font-serif text-[28px] font-normal text-[#2f2f2d]">API keys</h2>
          <p className="mt-2 max-w-xl text-[13px] leading-6 text-[#6f6b63]">
            Paste a provider key to enable its models. Keys are stored locally in your app data folder,
            never shown again, and survive updates. The key value is never sent anywhere except that provider.
          </p>
        </div>
        <button
          type="button"
          onClick={() => onRefreshProviders?.()}
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-[#dedbd2] bg-white px-3 text-[13px] text-[#3f3d38] shadow-sm hover:bg-[#f6f5f2]"
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>
      <div className="grid gap-3">
        {providers.map((provider) => (
          <ProviderRow key={provider.id} provider={provider} onSaveProviderKey={onSaveProviderKey} />
        ))}
      </div>
    </section>
  );
}
