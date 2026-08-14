# Vision Assist Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` while implementing each task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional two-stage image workflow in which a vision model extracts bounded, evidence-only observations and the user-selected primary model writes the final answer.

**Architecture:** The primary model remains authoritative and is never silently replaced. When Vision Assist is enabled and an image attachment is present, the sidecar calls a configured vision-capable helper first, then provides its textual evidence to the normal Chat/Cowork/Code request without forwarding raw image data to the primary model. A failed helper never fabricates image evidence; vision-capable primary models retain the existing direct-image fallback, and text-only models receive metadata plus a transparent limitation.

**Tech Stack:** Python 3.14, OpenAI-compatible provider client, Electron IPC JSONL, React/Vite, unittest, Vitest.

---

## File Map

- Create: `chat_vision_assist.py` - Pure, testable planning and evidence-prompt helpers.
- Create: `test/test_chat_vision_assist.py` - Unit coverage for opt-in selection, evidence handling, and safe fallback decisions.
- Modify: `model_catalog.py` - Add documented paid Z.ai vision helper choices.
- Modify: `ipc_sidecar.py` - Execute the helper, publish transient status, inject evidence into all three modes, and retain safe fallbacks.
- Modify: `test/test_ipc_sidecar.py` - Verify the two model calls, selection preservation, redaction, fallback, and no-image path.
- Modify: `frontend/CoworkApp.jsx` - Persist the per-app Vision Assist setting.
- Modify: `frontend/components/Composer.jsx` - Expose an explicit Vision Assist control and selected helper label.
- Modify: `frontend/tests/Composer.test.jsx` and/or `frontend/tests/CoworkApp.test.jsx` - Verify the control is visible and persists its setting.
- Modify: `PROJECT_STATE.md`, `work_logs/WORK_LOG.md` - Record capability, cost/consent boundary, test evidence, and remaining risks.

### Task 1: Define the safe helper contract

- [ ] Add failing tests for `vision_assist_request()` to prove that it is disabled without image data, respects explicit `off`, chooses the configured helper only when catalog metadata says it supports vision, and returns a text-only fallback reason rather than invented evidence.
- [ ] Run `python -m unittest test.test_chat_vision_assist -v` and confirm the tests fail because the module does not exist.
- [ ] Add `chat_vision_assist.py` with immutable decision data and helpers for:
  - normalized `off|auto|on` setting;
  - whether a real image data URL is available;
  - helper eligibility from catalog metadata;
  - a fixed evidence-only system instruction;
  - an evidence block tagged for internal primary-model context;
  - a bounded user-facing fallback note with no provider secret/error text.
- [ ] Re-run the focused test and confirm it passes.

### Task 2: Add verified paid vision helper catalog entries

- [ ] Add failing catalog tests for `zai:glm-4.6v-flashx` and `zai:glm-4.6v`: both must be vision-capable, paid, and expose a context window.
- [ ] Run `python -m unittest test.test_model_catalog.SaveProviderKeyTests -v` and confirm the new expectations fail.
- [ ] Add the two Z.ai models with clear paid badges. Keep `zai:glm-4.5-flash` as the existing default and do not change user-selected model routing.
- [ ] Re-run the focused catalog tests and confirm they pass.

### Task 3: Execute the secondary model without changing the primary model

- [ ] Add failing sidecar tests with a recording factory:
  - enabled Vision Assist with an image creates a helper call followed by the selected primary call;
  - the primary receives the helper evidence, never the image data URL;
  - the selected primary model ID is unchanged;
  - no raw base64 occurs in emitted IPC events;
  - helper failure falls back to direct image delivery only when the selected primary can receive images, otherwise stays metadata-only.
- [ ] Run the focused IPC tests and confirm they fail before implementation.
- [ ] In `ipc_sidecar.py`, call the helper before the normal Chat/Cowork/Code execution path. Emit a transient `cowork_status` before helper execution and normal writing/research status afterward. Include only model ID, success/failure category, and duration in audit records.
- [ ] Add the evidence system message to Chat and the temporary user-content prompt to Cowork/Code. Preserve durable histories as text-only user prompt plus final response.
- [ ] Re-run focused IPC tests and confirm they pass.

### Task 4: Make paid helper usage explicit in the UI

- [ ] Add a failing React test that opens Tool settings and finds the Vision Assist control, including its paid helper label and `Off` action.
- [ ] Run the focused Vitest command and confirm it fails.
- [ ] Add `visionAssist` and `visionModel` to persisted Chat settings. Default Vision Assist to `auto`, only causing a helper call when a real image attachment is submitted. Render a compact control with Off/Auto/On choices and helper model label.
- [ ] Pass the setting to the sidecar with the existing `web_settings` request payload and keep it inactive for no-image prompts.
- [ ] Re-run focused frontend tests and confirm they pass.

### Task 5: Verify, document, and release

- [ ] Run full backend suite: `python -m unittest discover -s test -p 'test_*.py' -v`.
- [ ] Run frontend suite from `frontend`: `npm test -- --run` (or the repository's current Vitest equivalent).
- [ ] Run `npm run build` and `npm run dist` from the project root as release verification.
- [ ] Perform one explicitly authorized live two-stage smoke call with short token limits. Record model IDs, latency, and success only; never record credentials or image payloads.
- [ ] Update state/log records and publish through the established source -> installer -> GitHub release workflow. Do not close or restart the installed app unless the user asks.

## Acceptance Checklist

- [ ] Any selected primary model can remain the final responder.
- [ ] A real image with Vision Assist enabled uses a second, configured vision model first.
- [ ] The primary model gets textual evidence only, never image data/base64 through this helper path.
- [ ] Helper failure cannot cause fabricated image claims.
- [ ] No image means no helper call and no paid vision request.
- [ ] Users can turn the helper off and see which paid model will be used.
- [ ] Existing single-vision-model delivery is retained only as a fallback when the helper fails.
