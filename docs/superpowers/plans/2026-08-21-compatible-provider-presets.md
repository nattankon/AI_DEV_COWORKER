# Compatible Provider Presets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven development to implement this plan task-by-task.

**Goal:** Replace the single free-form Custom Anthropic-compatible setup with a data-driven compatible-provider selector that supports verified presets and fully custom endpoints without coupling runtime behavior to provider names.

**Architecture:** Keep the existing `anthropic_compatible` credential slot and model prefix for backward compatibility, but persist a generic compatible-provider profile containing preset, protocol, authentication scheme, API root, and imported model IDs. Runtime dispatch is driven only by the persisted protocol/authentication fields. Provider presets are inert data returned to the UI, so adding another provider does not add provider-specific control flow.

**Tech Stack:** Python 3.11, `httpx`, OpenAI-compatible SDK adapter, React 19, Vitest, Python unittest.

---

### Task 1: Profile schema and preset registry

**Files:**
- Modify: `custom_anthropic_provider.py`
- Test: `test/test_custom_anthropic_provider.py`

- [ ] Add failing tests for preset metadata, legacy-profile migration, protocol/auth validation, and secret-free provider status.
- [ ] Run `python -m unittest test.test_custom_anthropic_provider -v` and confirm the new tests fail because the schema is missing.
- [ ] Add a data-only preset registry for MWAPI, OpenRouter, Groq, Together AI, DeepInfra, LiteLLM, and Custom.
- [ ] Persist `preset_id`, `protocol`, `auth_scheme`, `models_auth_scheme`, `base_url`, and `models`, while continuing to load old profiles as Anthropic Messages + x-api-key.
- [ ] Re-run the focused backend tests until green.

### Task 2: Compatible HTTP transport and protocol runtime

**Files:**
- Modify: `custom_anthropic_provider.py`
- Modify: `anthropic_chat_model.py`
- Modify: `ipc_sidecar.py`
- Modify: `pyproject.toml`
- Test: `test/test_custom_anthropic_provider.py`
- Test: `test/test_anthropic_chat_model.py`
- Test: `test/test_ipc_sidecar.py`

- [ ] Add failing tests proving model import uses the configured authentication scheme and Anthropic requests support x-api-key or Bearer authentication through `httpx`.
- [ ] Add a failing sidecar test proving OpenAI-compatible profiles use the OpenAI chat adapter while Anthropic Messages profiles use the Anthropic adapter.
- [ ] Run the focused tests and confirm failures are caused by missing protocol routing.
- [ ] Replace `urllib` calls on this provider path with bounded `httpx` calls and sanitized errors.
- [ ] Route runtime by profile `protocol`, never by preset/provider name.
- [ ] Re-run focused backend tests until green.

### Task 3: Provider preset and custom-entry UI

**Files:**
- Modify: `frontend/components/ProvidersPanel.jsx`
- Test: `frontend/tests/ProvidersPanel.test.jsx`

- [ ] Add failing UI tests for selecting a preset, automatic field population, switching to Custom, protocol/auth controls, and complete save/import payloads.
- [ ] Run `npm test -- --run frontend/tests/ProvidersPanel.test.jsx` and confirm the new assertions fail.
- [ ] Replace the Custom Anthropic-only form with a Compatible API provider form using accessible selects and editable fields.
- [ ] Keep API keys masked, never hydrate saved values, and clearly identify which endpoint receives requests.
- [ ] Re-run the focused frontend test until green.

### Task 4: Verification, live check, and records

**Files:**
- Modify: `PROJECT_STATE.md`
- Modify: `work_logs/WORK_LOG.md`

- [ ] Run the complete backend unittest suite.
- [ ] Run the complete frontend Vitest suite.
- [ ] Run the production frontend build.
- [ ] Run a transient MWAPI model-list and short Messages request through the new transport without persisting or printing the supplied key.
- [ ] Append capability, migration, verification, and known third-party gateway caveats to the project records.
- [ ] Do not bump the desktop version or publish an update unless the user separately requests a release batch.
