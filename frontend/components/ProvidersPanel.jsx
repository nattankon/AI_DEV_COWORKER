import { useEffect, useState } from "react";
import { Eye, EyeOff, KeyRound, RefreshCw } from "lucide-react";

// Providers whose keys the user can enter here. Order matches the model menu.
const PROVIDER_ORDER = ["openai", "anthropic", "deepseek", "zai", "gemini"];
const PROVIDER_LABELS = {
  openai: "OpenAI",
  anthropic: "Anthropic / Claude",
  deepseek: "DeepSeek",
  zai: "Z.ai",
  gemini: "Gemini",
};
const PROVIDER_HINTS = {
  openai: "sk-proj-…",
  anthropic: "sk-ant-…",
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
  const [showKey, setShowKey] = useState(false);
  const helpId = `${provider.id}-key-help`;
  return (
    <div className="rounded-xl border border-[#e7e3da] bg-[#fbfaf7] p-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="text-[15px] font-medium text-[#2f2f2d]">{provider.label}</span>
        <span className={provider.configured ? "text-[12px] text-[#3f8f62]" : "text-[12px] text-[#b44b3d]"}>
          {provider.configured ? "✓ Key saved" : "No key yet"}
        </span>
      </div>
      <form
        className="grid grid-cols-[minmax(0,1fr)_auto] gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          const value = keyValue.trim();
          if (!value) return;
          onSaveProviderKey?.(provider.id, value);
          setKeyValue("");
        }}
      >
        <div className="relative min-w-0">
          <input
            type={showKey ? "text" : "password"}
            aria-label={`${provider.label} API key`}
            aria-describedby={helpId}
            autoComplete="new-password"
            autoCapitalize="none"
            spellCheck={false}
            value={keyValue}
            onChange={(event) => setKeyValue(event.target.value)}
            placeholder={provider.configured ? `Replace key (${PROVIDER_HINTS[provider.id] || "key"})…` : `Paste ${PROVIDER_HINTS[provider.id] || "key"}…`}
            className="h-9 w-full rounded-lg border border-[#dedbd2] px-3 pr-10 text-[13px] text-[#2f2f2d] outline-none focus:ring-2 focus:ring-[#d8d5cc]"
          />
          <button
            type="button"
            aria-label={`${showKey ? "Hide" : "Show"} ${provider.label} key`}
            onClick={() => setShowKey((value) => !value)}
            className="absolute right-1 top-1 inline-flex h-7 w-7 items-center justify-center rounded-md text-[#77736b] hover:bg-[#efede7] hover:text-[#2f2f2d]"
            title={showKey ? "Hide key" : "Show key"}
          >
            {showKey ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        </div>
        <button
          type="submit"
          aria-label={`Save ${provider.label} key`}
          disabled={!keyValue.trim()}
          className="h-9 shrink-0 rounded-lg bg-[#2f2f2d] px-4 text-[13px] font-medium text-white hover:bg-[#1f1f1d] disabled:cursor-not-allowed disabled:bg-[#d8d5cc]"
        >
          Save
        </button>
        <p id={helpId} className="col-span-2 text-[11px] leading-5 text-[#8a877f]">
          Stored locally. Saving replaces only this provider's key.
        </p>
      </form>
    </div>
  );
}

function CustomAnthropicProvider({ provider, result, onSave, onImport }) {
  const [baseUrl, setBaseUrl] = useState(String(provider?.base_url || ""));
  const [keyValue, setKeyValue] = useState("");
  const [showKey, setShowKey] = useState(false);
  const models = Array.isArray(provider?.models) ? provider.models : [];

  useEffect(() => {
    setBaseUrl(String(provider?.base_url || ""));
  }, [provider?.base_url]);

  const payload = () => ({ baseUrl: baseUrl.trim(), key: keyValue.trim() });
  const canSubmit = Boolean(baseUrl.trim() && (keyValue.trim() || provider?.configured));
  return (
    <div className="mt-6 border-t border-[#dedbd2] pt-5">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-[15px] font-medium text-[#2f2f2d]">Custom Anthropic-compatible</h3>
          <p className="mt-1 text-[12px] leading-5 text-[#77736b]">
            Connect an endpoint that implements Anthropic Messages API. This third-party endpoint receives your API key and requests.
          </p>
        </div>
        <span className={provider?.configured ? "text-[12px] text-[#3f8f62]" : "text-[12px] text-[#b44b3d]"}>
          {provider?.configured ? "✓ Configured" : "Not configured"}
        </span>
      </div>
      <div className="grid gap-3">
        <label className="grid gap-1 text-[12px] text-[#6f6b63]">
          Base URL
          <input
            aria-label="Custom Anthropic-compatible Base URL"
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
            placeholder="https://provider.example.com/v1"
            autoCapitalize="none"
            spellCheck={false}
            className="h-9 rounded-lg border border-[#dedbd2] px-3 text-[13px] text-[#2f2f2d] outline-none focus:ring-2 focus:ring-[#d8d5cc]"
          />
        </label>
        <label className="grid gap-1 text-[12px] text-[#6f6b63]">
          API key
          <span className="relative block">
            <input
              type={showKey ? "text" : "password"}
              aria-label="Custom Anthropic-compatible API key"
              value={keyValue}
              onChange={(event) => setKeyValue(event.target.value)}
              placeholder={provider?.configured ? "Use saved key or enter a replacement…" : "Paste API key…"}
              autoComplete="new-password"
              autoCapitalize="none"
              spellCheck={false}
              className="h-9 w-full rounded-lg border border-[#dedbd2] px-3 pr-10 text-[13px] text-[#2f2f2d] outline-none focus:ring-2 focus:ring-[#d8d5cc]"
            />
            <button
              type="button"
              aria-label={`${showKey ? "Hide" : "Show"} custom Anthropic-compatible key`}
              onClick={() => setShowKey((value) => !value)}
              className="absolute right-1 top-1 grid h-7 w-7 place-items-center rounded-md text-[#77736b] hover:bg-[#efede7]"
            >
              {showKey ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </span>
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            aria-label="Save custom Anthropic-compatible provider"
            disabled={!baseUrl.trim() || (!keyValue.trim() && !provider?.configured)}
            onClick={() => {
              onSave?.(payload());
              setKeyValue("");
            }}
            className="h-9 rounded-lg border border-[#d8d4ca] bg-white px-3 text-[13px] text-[#3f3d38] hover:bg-[#f6f5f2] disabled:cursor-not-allowed disabled:opacity-45"
          >
            Save
          </button>
          <button
            type="button"
            aria-label="Test and import custom Anthropic-compatible models"
            disabled={!canSubmit}
            onClick={() => {
              onImport?.(payload());
              setKeyValue("");
            }}
            className="h-9 rounded-lg bg-[#2f2f2d] px-3 text-[13px] font-medium text-white hover:bg-[#1f1f1d] disabled:cursor-not-allowed disabled:bg-[#d8d5cc]"
          >
            Test & import models
          </button>
          <span className="text-[12px] text-[#77736b]">
            {models.length} imported model{models.length === 1 ? "" : "s"}
          </span>
        </div>
        {result?.message ? (
          <p className={result.ok ? "text-[12px] text-[#3f8f62]" : "text-[12px] text-[#b44b3d]"} role="status">
            {result.message}
          </p>
        ) : null}
      </div>
    </div>
  );
}

export default function ProvidersPanel({
  modelProviders = [],
  customProviderResult,
  onSaveProviderKey,
  onSaveCustomProvider,
  onImportCustomModels,
  onRefreshProviders,
}) {
  const providers = orderedProviders(modelProviders);
  const customProvider = (Array.isArray(modelProviders) ? modelProviders : []).find((provider) => provider?.id === "anthropic_compatible") || {};
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
      <CustomAnthropicProvider
        provider={customProvider}
        result={customProviderResult}
        onSave={onSaveCustomProvider}
        onImport={onImportCustomModels}
      />
    </section>
  );
}
