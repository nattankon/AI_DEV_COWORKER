# Track A — Research Foundation Design (handoff for Codex)

> **Audience:** an implementer (Codex) with no prior conversation context. Everything needed is in this file plus the referenced source files. Read the "Current State" section before writing code.
>
> **Language:** This document and all handoff communication are in English (planning-dev → dev). Thai strings in examples/tests (e.g. `26 มิ.ย.`, `เบนซิน 95`) are literal input/output **data** the system must handle — keep them verbatim; do not translate data literals.
>
> **Process:** This is a multi-step effort (Section 8). After each step, request a **Claude Code review** and log it (Section 9) before advancing. Codex can invoke Claude Code directly for this.

---

## 0. Context & Why

`AI_DEV_COWORKER` is a 3-layer product: **(1) Chatbot → (2) Cowork → (3) Code CLI**. The chatbot is being built first because strong code assistance depends on strong **research/retrieval** — so retrieval built for Chat is the reusable foundation for all three layers. The capability bar is **Claude chat (claude.ai)**: agentic, tool-driven web research with grounded, cited answers.

Today, **Chat does retrieval the wrong way for that goal**: it runs the model *tool-less* (`complete(messages, tools=[], ...)`) and does a fixed Python pre-fetch pipeline with keyword heuristics and hardcoded verticals (Thai oil prices). That fights the model's intelligence and does not generalize.

**Track A turns retrieval into model-driven tools + a model-agnostic correctness guard + generic extraction.** Intelligence is expected to come from capable tier models (GPT-5.4 / GPT-4.0 / Gemini 3.1 Flash); our job is the orchestration so a capable model performs well, while a weaker test model (currently GLM-4.5 free) still degrades gracefully.

Track A has 3 parts:
- **A1** — Web research as tools + a model-driven loop (with fallback to today's pipeline for weak models).
- **A2** — Deterministic evidence/citation guard (post-answer, model-agnostic).
- **A3** — Generic extraction (table-aware; de-hardcode the oil vertical).

**Out of scope (Track B, do NOT do here):** streaming output, markdown rendering, source-card UI.

---

## 1. Invariants / Constraints (do not violate)

1. **Chat is web-only.** Chat must NOT get filesystem/workspace/git/run_verification tools. The Chat/Cowork separation is intentional: Chat never reads local files, never creates approval prompts. New Chat tools are limited to `web_search` and `web_fetch`.
2. **Shared agent loop; Cowork behavior preserved.** Extract the tool-calling loop into a shared core (`tool_loop.py`) that BOTH Cowork and Chat use — this matches the target architecture (one agent loop; Chat/Cowork/Code-CLI differ only by toolset + prompt + policy). Refactoring `CoworkAgent` onto the shared core is a **behavior-preserving** change, gated by the existing Cowork test suite (must stay green, currently 105/105). Do not change Cowork's observable behavior in this refactor.
3. **Model-agnostic.** No prompt tuning to GLM-4.5 quirks. Correctness is enforced in code (A2), not by trusting the model.
4. **Graceful fallback.** If the model does not drive tools (weak model emits zero `tool_calls`), fall back to the existing one-shot pipeline (`_search_web_for_chat` + `_format_chat_web_context`). Never regress today's behavior.
5. **Keep existing tests green.** `test/test_chat_web_connector.py` (currently 13 focused / 105 full backend) must keep passing or be updated only where behavior intentionally changes. Add new tests (Section 5).
6. **Tool-result contract = JSON string**, matching the existing convention: `dispatch()` returns `json.dumps(payload, ensure_ascii=False)` where payload has a `status` field (`ok` | `error` | `denied`). Mirror `WorkspaceTools.dispatch` (`workspace_tools.py:407`).

---

## 2. Current State (read these before coding)

| Concern | Location | Notes |
|---|---|---|
| Chat entrypoint | `ipc_sidecar.py` → `_run_plain_chat` (~L250) | builds messages, calls `_search_web_for_chat`, `_format_chat_web_context`, then `_complete_plain_chat_with_fallback` |
| Tool-less completion | `ipc_sidecar.py` → `_complete_plain_chat_with_fallback` (~L369) | calls `complete(messages, tools=[], generation=...)`, walks `_model_candidates` for fallback |
| Web pipeline | `chat_web_connector.py` → `ChatWebConnector.search()` (L39) | returns `WebSearchResponse(query, results, error, analysis)` |
| Result type | `chat_web_connector.py` → `WebSearchResult` (L16) | frozen: `title,url,snippet,evidence,source_type,quality_score` |
| Page fetch | `chat_web_connector.py` → `_fetch_text` (L555), `_extract_page_evidence` (L220), `_is_blocked_page` (L244) | `_ReadableTextParser` (L261) flattens `<tr>/<td>` → table data lost |
| Routing | `chat_router.py` → `classify_chat_prompt` (L79) | keyword router → `ChatRoute(needs_web_context=...)` |
| Tool loop (reuse pattern) | `cowork_agent.py` → `CoworkAgent.run()` L122-212 | the proven complete→tool_calls→dispatch→append loop |
| Model tool support | `cowork_agent.py` → `OpenAIChatModel.complete()` L50-73 | already accepts `tools`, returns `tool_calls:[{id,name,arguments}]` |
| Tool schema/contract shape | `workspace_tools.py` → `schemas` (L61), `dispatch` (L407), `_tool_schema` (L440) | OpenAI function format, `strict:True`, `additionalProperties:False` |

**Key fact:** the tool-calling machinery already exists. A1 reuses the *pattern*, not the cowork-specific semantics (`run_state`, verification gating, workspace memory).

---

## 3. Part A1 — Web research as tools + model-driven loop

### A1.1 New tool provider: `WebResearchTools`

New file `chat_web_tools.py`. Mirror the `WorkspaceTools` contract exactly (`.schemas` property + `.dispatch(name, args) -> str`), so the loop is interchangeable.

```python
# chat_web_tools.py
class WebResearchTools:
    def __init__(self, connector: ChatWebConnector | None = None, *, max_fetch: int = 5):
        self._connector = connector or ChatWebConnector()
        self._sources: list[dict] = []   # ordered registry: index -> {url,title,source_type}
        self._max_fetch = max_fetch

    @property
    def schemas(self) -> list[dict]: ...
    def dispatch(self, tool_name: str, arguments: dict) -> str: ...
    def sources(self) -> list[dict]:   # for guard (A2) + future UI (Track B)
        return list(self._sources)
```

**Tools exposed (web-only):**

`web_search`
- params: `{"query": string, "max_results": integer(optional, default 5, cap 8)}` — but per `strict:True` schemas, keep `required:["query"]` and clamp `max_results` in code.
- behavior: call `self._connector.search(query, max_results)`; register each result into `self._sources` with a stable `index` (1-based, continues across calls); return:
```json
{"status":"ok","results":[
  {"index":1,"title":"...","url":"https://...","snippet":"...","source_type":"search-result"}
]}
```
- Do NOT auto-fetch here. The model decides what to open (agentic).

`web_fetch`
- params: `{"url": string}` required.
- behavior: fetch via connector internals (`_fetch_text`), block-check (`_is_blocked_page`), extract (A3 generic extractor). Register/locate the URL in `self._sources`. Return:
```json
{"status":"ok","index":1,"url":"https://...","title":"...","blocked":false,
 "evidence":"...","tables":[{"caption":"...","rows":[["label","value"],...]}]}
```
- On block: `{"status":"ok","index":N,"url":...,"blocked":true,"evidence":""}` (do not raise; let the model pick another source).
- Cap total fetches at `self._max_fetch` (return `{"status":"error","error":"fetch limit reached"}` beyond it) to bound latency.

Use `_tool_schema(...)`-style helpers (copy the small helpers from `workspace_tools.py:436-454`, or import them if you choose to expose them; copying keeps modules decoupled).

### A1.2 The `index` contract (critical for citations)

`self._sources` is the single source of truth mapping `[web:N] → url/title/source_type`. Both A2 (guard) and Track B (UI) consume `WebResearchTools.sources()`. Indices are assigned on first appearance (search or fetch) and never reused. The model is instructed to cite using these `index` values.

### A1.3 Shared loop core: `tool_loop.py` (extract first), then `ChatResearchRunner`

**Step 1 — Extract the core (behavior-preserving refactor).** Pull the loop body from `CoworkAgent.run()` L122-212 into a new `tool_loop.py`:

```python
@dataclass(frozen=True)
class ToolLoopOutcome:
    answer: str
    used_tools: bool
    iterations: int

def run_tool_loop(*, model, messages, tools, max_iterations,
                  on_event=lambda *_: None, hooks: "LoopHooks | None" = None) -> ToolLoopOutcome:
    """complete -> if tool_calls: dispatch each, append {"role":"tool",...} -> else final content.
    Includes the one-shot empty-response recovery (L176-186)."""
```

The cowork-specific behavior (run_state stage recording, "verification-before-report" gate at L188-197) must NOT live in the core. Expose it via optional `hooks` callbacks the core calls at defined points:
- `hooks.before_finalize(content) -> str | None` — return a "repair" user message to continue the loop instead of finalizing (this is exactly how Cowork's verification gate works); `None` = allow finalize.
- `hooks.on_tool_result(tool_name, arguments, result)` — for stage/state recording.

`CoworkAgent.run()` keeps its `run_state` and passes hooks that implement the verification gate + stage recording, so **observable Cowork behavior is identical**. Verify by running the full Cowork suite — it must stay green.

**Step 2 — `ChatResearchRunner`** (new file `chat_research_runner.py`): a thin wrapper that calls `run_tool_loop` with web tools, `max_iterations=6` (Chat research is shallower than Cowork builds; bounds latency), and **no hooks** (no verification, no run_state). Returns the `ToolLoopOutcome`.

- `used_tools` drives the fallback decision (Invariant 4).
- Reuse `OpenAIChatModel` as-is (already returns `tool_calls`). Create the model the same way as `_complete_plain_chat_with_fallback`.
- Keep the per-provider error fallback: walk `_model_candidates` like `_complete_plain_chat_with_fallback` does today. Factor the candidate-walk into one helper both call.

### A1.4 Integration in `_run_plain_chat`

Replace the current "search → format → complete(tools=[])" for the web/mixed routes with a decision:

```
route = classify_chat_prompt(prompt)
if route.needs_web_context and _tool_research_enabled(model):
    tools = WebResearchTools()
    messages = [system, route_block(has_web_context=True), memory?, attachments?,
                RESEARCH_INSTRUCTIONS, *history, user]   # NOTE: no pre-fetched web block
    outcome = run_research(model=.., messages=messages, tools=tools, ...)
    if outcome.used_tools:
        answer = guard(outcome.answer, tools.sources(), evidence_corpus_from(tools))  # A2
        web_sources = tools.sources()
    else:
        # weak model ignored tools -> fall back to today's pipeline
        answer, web_sources = _legacy_web_chat(prompt, model, ...)
else:
    answer, web_sources = _legacy_web_chat(prompt, model, ...)  # today's path unchanged
```

- `_legacy_web_chat(...)` = today's exact behavior: `_search_web_for_chat` + `_format_chat_web_context` + `_complete_plain_chat_with_fallback`. Extract it into a helper so both branches and non-web routes stay identical to current output. **Non-web routes (general/memory/project) are unchanged.**
- `RESEARCH_INSTRUCTIONS` (new system block): tells the model it has `web_search`/`web_fetch`, to search → open the most relevant sources → ground every external fact in fetched evidence → cite `[web:N]` using the `index` from tool results → end with a Sources list → and the existing grounding rules (no inferred values; partial dates stay partial; do not convert BE/CE unless the year is in evidence). Reuse the wording already in `_format_chat_web_context` (`ipc_sidecar.py:339-347`) so behavior is consistent.

### A1.5 `_tool_research_enabled(model)`

Gate tool-mode by provider to avoid wasting a round-trip on models that reliably can't tool-call:
- Default **on** for `openai:`, `gemini:`, `anthropic:`/`claude`, and **`zai:`** (GLM-4.5, accessed via z.ai, supports function/tool calling natively — including the free tier used for testing).
- Default **off** (use legacy pipeline) only for `local:`/unknown providers where tool support is uncertain. Make it a config value on `ChatRuntimeConfig` (e.g. `tool_research_providers: tuple[str,...] = ("openai","gemini","anthropic","zai")`) so it's data, not a buried constant.
- Even when on, Invariant 4 fallback still applies at runtime (`outcome.used_tools is False`) — this covers a free/smaller `zai:` variant that occasionally ignores tools.

---

## 4. Part A2 — Deterministic evidence/citation guard

New file `chat_answer_guard.py`. **Pure, model-agnostic, no network.** This is the backstop that makes correctness independent of model strength.

```python
@dataclass(frozen=True)
class GuardResult:
    ok: bool
    violations: list[str]          # human-readable, for logging/telemetry
    corrected_answer: str | None   # set only when an automatic correction was applied

def validate_answer(answer: str, *, evidence_corpus: str, sources: list[dict]) -> GuardResult: ...
```

**`evidence_corpus`** = concatenation of all fetched `evidence` + `tables` text from `WebResearchTools` (the only text the model was allowed to ground on).

**Checks (all string/regex-level, deterministic):**
1. **Numbers/prices:** every numeric token in the answer that looks like a *factual figure* (price `\d[\d,]*\.?\d*`, with currency/unit context) must appear in `evidence_corpus`. Allow obvious non-evidence numbers (list indices, years in the user's own question echoed back) via a small allowlist; be conservative — only flag figures presented as retrieved facts.
2. **Years / full dates:** any 4-digit year (`20\d\d`, `25\d\d` for BE) or full date in the answer must appear in `evidence_corpus`. This directly kills the `26 มิ.ย. → 2561/2018` hallucination.
3. **Partial-date integrity:** if a day+month appears in evidence with no year, and the answer attaches a year to it, that's a violation (covered by check 2, but assert explicitly with a test).
4. **Citation validity:** every `[web:N]` in the answer must have a matching `index` in `sources`. Flag dangling citations.

**Action policy:** re-ask once, then annotate.
- On violation, append a correction `user` turn to the loop messages: *"Your answer contained values/citations not present in the fetched evidence: <violations>. Rewrite using only fetched evidence; keep partial dates partial; remove or fix invalid citations."* Re-run one model turn (no new tools needed).
- If the re-asked answer still violates: return it but set `corrected_answer` to a version with the offending unsupported figures/years annotated (e.g. append `(ไม่พบปี/ค่าในแหล่ง)`) OR strip them — pick stripping of the specific unsupported year only, to avoid mangling prose. Record a `chat_answer_guard` telemetry event either way (`record_cowork_event`).

**Where called:** inside the tool-mode branch of `_run_plain_chat` (A1.4), after `run_research`. Legacy path may optionally call it too (cheap, same signature) — recommended but gate behind the same enablement to limit blast radius.

---

## 5. Part A3 — Generic extraction (de-hardcode the oil vertical)

### A3.1 Table-aware extraction (the real fix for "numbers from tables")

In `chat_web_connector.py`, the current `_ReadableTextParser` (L261) flattens `<tr>/<td>` and loses row→value binding. Add a generic table extractor used by `web_fetch` (A1.1) and available to `_extract_page_evidence`:

```python
def _extract_tables(html: str, *, max_tables=8, max_rows=40) -> list[dict]:
    """Return [{caption, headers:[...], rows:[[cell,...],...]}] preserving row structure."""
```
- Parse `<table>` blocks; keep each row's cells in order; capture an optional caption/preceding heading.
- Serialize for evidence as `label: value` lines (e.g. `เบนซิน 95: 39.50`), so a grounded model can quote per-type values. This is **domain-agnostic** — works for fuel, specs, comparison tables, anything.
- `web_fetch` returns both `evidence` (prose) and `tables` (structured) so the model/guard can use whichever fits.

### A3.2 Demote oil-specific code to a thin, optional fallback

The oil paths exist only because the tool-less pipeline needed heuristics. In tool-mode the model forms queries and picks sources, so most heuristics become unnecessary.
- Keep `_trusted_source_hints` / `_international_source_hints` usable **only in the legacy pipeline** path. Do not extend them.
- In tool-mode, `web_search` passes the model's query through with no oil special-casing.
- Remove the mojibake constants `"喔權箟喔赤浮喔编笝"` in `_is_thai_oil_query` (L516) and `_has_oil_relevance` (L540) — corrupted Thai that never matches (cleanup, no behavior change).
- **Thai relevance note:** generic token relevance (`_relevance_terms` L482) is weak for Thai (no word boundaries; regex is ASCII-only). In tool-mode this no longer matters (the model decides relevance), so do **not** invest more in Thai heuristic relevance — let it ride the legacy path only.

---

## 6. Data contracts (summary)

- **Tool result JSON:** always `{"status": "ok"|"error", ...}`, serialized with `ensure_ascii=False`.
- **`web_search.results[]`:** `{index,title,url,snippet,source_type}`.
- **`web_fetch`:** `{status,index,url,title,blocked,evidence,tables}`.
- **`WebResearchTools.sources()`:** `[{index,url,title,source_type}]` — consumed by guard (A2) and Track B UI.
- **`GuardResult`:** `{ok,violations,corrected_answer}`.

---

## 7. Test plan (add under `test/`)

1. `test_chat_web_tools.py`
   - `web_search` registers indices and returns expected shape (inject a fake `ChatWebConnector` via constructor).
   - `web_fetch` on a blocked page → `blocked:true`, no raise.
   - `web_fetch` table page → `tables` preserves rows; `evidence` contains `label: value`.
   - fetch cap enforced.
2. `test_chat_research_runner.py`
   - Fake model that emits a `web_search` call then a final answer → `used_tools=True`, answer returned.
   - Fake model that emits no tool calls → `used_tools=False` (drives fallback).
   - empty-response recovery path.
3. `test_chat_answer_guard.py`
   - Evidence has `26 มิ.ย.` (no year); answer says `26 มิ.ย. 2561` → violation; corrected answer drops the year. **(the headline regression test)**
   - Answer cites `[web:3]` with only 2 sources → dangling-citation violation.
   - Price not in evidence → violation; price present → ok.
4. `test_chat_web_connector.py` (extend)
   - `_extract_tables` row-preservation unit test.
   - Existing 13 tests stay green (legacy pipeline unchanged).
5. Integration (in `ipc_sidecar` tests): tool-enabled provider with a fake tool-driving model → guarded answer + `web_sources` populated; weak provider → legacy path, output identical to today.

---

## 8. Rollout order (suggested commits)

1. **Extract `tool_loop.run_tool_loop` from `CoworkAgent` (behavior-preserving) + refactor Cowork onto it with `hooks`. GATE: full Cowork test suite stays green (105/105).** This is the only step with refactor risk; the tests are the safety net. No new behavior.
2. A3.1 `_extract_tables` + wire into `_extract_page_evidence` (safe, additive) + cleanup mojibake. Tests.
3. A1.1 `WebResearchTools` + schemas/dispatch + tests (no integration yet).
4. A1.3 Step 2 `ChatResearchRunner` on the shared core + tests (fake model).
5. A2 `chat_answer_guard` + tests (standalone, the regression-killer).
6. A1.4/A1.5 integrate into `_run_plain_chat` behind `_tool_research_enabled`, with legacy fallback. Integration tests.
7. Telemetry: `record_cowork_event("chat_research", {...})` and `("chat_answer_guard", {...})`.

Each step is independently testable and leaves the app shippable. Step 1 changes structure but not behavior (tests prove it); steps 2-5 don't change runtime behavior; step 6 is the switch-on with fallback.

**Every step above ends with the Definition of Done in Section 9 (tests → Claude Code review → log → proceed).**

---

## 9. Definition of Done & review workflow (Codex ⇄ Claude Code)

Codex can invoke Claude Code directly for review. Treat each rollout step (Section 8) as a unit of work with this Definition of Done — do not advance to the next step until all five are met:

1. **Implement** the step.
2. **Test.** Run the relevant tests. For Step 1 the gate is the full Cowork suite green (105/105). Never proceed on red.
3. **Request a Claude Code review** of the step's diff — focused on: correctness, behavior-preservation (critical for Step 1), adherence to the contracts in this doc (tool-result JSON, `index` mapping, web-only toolset), and test adequacy.
4. **Record the review** in `work_logs/track-a-review-log.md` (create if missing; append-only). Each entry:
   - date, step id/name, files touched
   - test result (e.g. `Cowork 105/105 green`; new tests added + passing)
   - review findings: each issue raised → how it was resolved (or deferred, with reason)
   - decision: `proceed` or `rework`
5. **Resolve blocking findings**, then advance.

Keep entries concise and factual (what changed, what the review found, what was done). This log is the audit trail for Track A and the handoff record for the next layer (Code-CLI).

---

## 10. Explicit non-goals (Track B / later)

- Streaming output over IPC (perceived speed) — separate track.
- Markdown rendering in `frontend/components/MessageEntry.jsx` — separate track.
- Source-card UI — separate track, but A1.2 `sources()` is the data source it will consume.
- Code-CLI layer (layer 3) — future; but `tool_loop.run_tool_loop` (Section A1.3) is built as the shared core it will reuse, so no second extraction is needed later. Cowork is brought onto the shared core *now* (Section 8 step 1).
