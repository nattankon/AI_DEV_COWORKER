# Smartness Pipeline — Batch 2 Plan (handoff spec for Codex)

> Handoff for Codex. English throughout; Thai strings are literal data. Self-contained.
> Companions: `SMARTNESS_PIPELINE_BATCH_1.md` (what already landed),
> `work_logs/track-a-review-log.md` (2026-07-03 entries). Each item = its own commit +
> Definition of Done (test → send to Claude for in-session review → log → STOP).
> Anything that calls models/network is OPT-IN and must NEVER run in the default
> `unittest`/`vitest` suites.
>
> User decisions already made (do not re-litigate):
> - Strong-tier model to validate: `zai:glm-5.2` (already in `model_catalog.py:142`).
>   Free tier stays `zai:glm-4.5-flash`.
> - Local embedder library: **fastembed** (small, ONNX, no torch dependency).
> - Reference product shape: Claude apps — user-selectable model tiers; big model answers,
>   small model may serve background tasks LATER (explicit non-goal in this batch: no
>   background task in this codebase calls a model today, so there is nothing to wire).

## Working order

1. **Item 1 (code, offline):** make the quality runner able to run and REPORT the
   latency A/B experiment. Small, unblocks everything else.
2. **Item 2 (operational, live, needs Z.ai credit):** the GLM-5.2 validation runs. The
   user executes the commands; Codex only prepares/verifies. Results go to Claude for
   analysis.
3. **Item 3 (code, offline except one explicit first-run download):** wire fastembed into
   the semantic-memory seam.

Item 3 does not depend on 1-2 and may be built while waiting for credit, but commit and
review it separately.

## Cross-cutting constraints

- Default suites stay fully offline: no fastembed import, no model calls, no network in
  `unittest`/`vitest`. Live paths stay behind `--live` / explicit flags.
- D1: no topic/vendor names in code control flow. Model ids appear only as data
  (CLI args, catalog entries, config values).
- Behavior-preserving defaults: every new knob defaults to current behavior
  (`tool_research_routes=None`, semantic memory OFF).
- The answer guard, approval flow, and Chat's web-only tool scope are untouched.

---

## Item 1 — Quality runner: A/B routes flag + diagnostics in the report

**Problem:** Batch 1 added `ChatRuntimeConfig.tool_research_routes` and per-answer
diagnostics (`entered_tool_loop`, `research_iterations`, `research_forced`,
`answer_path_ms`), but the runner cannot use them:
- `run_chat_once` (`chat_quality_runner.py:31`) builds `IpcDependencies` WITHOUT a
  `chat_config`, so there is no way to run the gated variant.
- `run_chat_once` returns only answer/sources/evidence/latency/used_model — the new
  diagnostics fields are DROPPED, so even a default run cannot attribute latency.
- `_matrix_markdown` has no columns for them.

**Implement:**
- `run_chat_once(..., tool_research_routes: tuple[str, ...] | None = None)`: when not
  None, pass `IpcDependencies(chat_config=ChatRuntimeConfig(tool_research_routes=...))`;
  when None, construct exactly as today (byte-for-byte default behavior). Include the
  new diagnostics fields in the returned payload:
  `entered_tool_loop`, `research_iterations`, `research_forced`, `answer_path_ms`.
- `run_quality_eval_live(..., tool_research_routes=None)`: plumb through to
  `run_chat_once` (note `_run_chat_once_with_retries` must forward it) and copy the
  diagnostics fields into each cell. Add `"variant": "default" | "routes:<joined>"` to
  each cell and to the report summary so two runs are distinguishable at a glance.
- CLI: optional `--tool-research-routes web,project` (comma-separated; empty/omitted =
  None). `parser.error` if used without `--live`? Not needed — the whole command already
  requires `--live`.
- `_matrix_markdown`: add columns `Loop` (entered_tool_loop), `Iters`
  (research_iterations), `Path ms` (answer_path_ms) to the cells table, and the variant
  line in the summary block.
- IPC `chat_quality_run` (`ipc_sidecar.py` `_run_chat_quality`): accept an optional
  `tool_research_routes` list in the payload and forward it to the runner, so the
  in-app Quality panel can run the same experiment later (frontend change NOT required
  in this batch — payload plumbing only).

**Tests (fake `run_chat_once`, no live calls):** routes tuple reaches the fake; cells
carry variant + diagnostics fields; markdown includes the new columns; default path
(None) builds config identical to today (assert the fake received `None` and cells say
`variant: "default"`).

**Acceptance:** two CLI invocations (default vs `--tool-research-routes web,project`)
produce reports whose cells show, per category, whether the tool loop ran, how many
iterations, and the answer-path wall time — everything needed to attribute the ~60s
general latency.

---

## Item 2 — GLM-5.2 validation runs (operational; user executes)

**Prereq:** Z.ai credit on the account; `zai` key already configured in the app.
No code changes. Codex's only job here: verify Item 1 landed, then hand the user these
exact commands.

**Run protocol (in order, same day if possible):**

```bash
# Run A — baseline, both models, default routing
python -m chat_quality_runner --live --models zai:glm-5.2,zai:glm-4.5-flash \
  --retry-attempts 2 --retry-backoff-seconds 5

# Run B — gated variant, same models (the latency A/B)
python -m chat_quality_runner --live --models zai:glm-5.2,zai:glm-4.5-flash \
  --tool-research-routes web,project \
  --retry-attempts 2 --retry-backoff-seconds 5
```

**What the runs decide (decision rules agreed with Claude):**
1. **Model tier:** if GLM-5.2's pass rate ≥ flash AND hallucination stays 0 → GLM-5.2
   becomes the recommended strong tier; flash stays the free/default tier. If GLM-5.2
   fails on cost/latency, record why and stay on flash.
2. **Latency attribution:** compare the `general` category between Run A and Run B and
   between models. `answer_path_ms` ≈ latency with `entered_tool_loop=False` in Run B →
   loop overhead was the cause → make `("web", "project")` the DEFAULT
   `tool_research_routes` (a one-line config change, separate commit, after Claude
   review). If general stays slow with the loop off → the model is the bottleneck →
   default stays None and the tier decision (1) carries the fix.
3. **Web source quality:** confirm whether `search_provider` resolves to Brave in the
   app environment (batch 1 found the key absent from the shell env). If the web
   category still fails source quality WITH Brave active, escalate to Claude with the
   report — do not patch scoring blind.

**Deliverable:** both report paths (`work_logs/chat-quality-live-*.md/.json`) sent to
Claude for analysis + the tier/routing decision logged in `track-a-review-log.md`.

---

## Item 3 — Semantic memory: wire fastembed into the existing seam

**Current state (verified):** `ChatMemoryStore(root, embedder=None)` already supports an
injectable `Callable[[str], list[float]]`, semantic recall/dedupe when embeddings exist,
keyword fallback otherwise, and embedding redaction in public entries. The sidecar
(`ipc_sidecar.py` `_chat_memory_store`) constructs the store WITHOUT an embedder — the
seam is empty. Tests already use fake embedders.

**Implement:**
- `pyproject.toml`: optional extra `embeddings = ["fastembed>=0.4,<1"]` (mirror the
  `mcp` extra pattern).
- New `chat_embeddings.py`:
  - `create_local_embedder(*, model_name: str = "BAAI/bge-small-en-v1.5", cache_dir: str | Path | None = None) -> Callable[[str], list[float]] | None`
  - Lazy-import fastembed INSIDE the function; return `None` (never raise) when the
    package is missing.
  - Instantiate the fastembed `TextEmbedding` ONCE (module-level or lru_cache) — model
    load is expensive; embedding calls must reuse it.
  - The embedder callable: `text -> list(float)` via fastembed's embed API (first
    vector). Empty/whitespace text → return `[]` (store treats all-zero/empty as no
    embedding).
  - IMPORTANT: fastembed downloads its ONNX model (~30-130 MB) to a local cache on FIRST
    use — that is a one-time network event. Default the cache under the app data dir
    (`COWORK_USER_DATA_DIR`) so it is user-visible and persistent. After that it is
    fully offline.
- `chat_runtime.py`: `semantic_memory_enabled: bool` via env
  `COWORK_CHAT_SEMANTIC_MEMORY` (default **False** — the first-use download must be the
  user's explicit choice).
- `ipc_sidecar.py` `_chat_memory_store`: when `chat_config.semantic_memory_enabled`,
  build the embedder once (cache on the sidecar instance; `create_local_embedder()`
  returning None degrades silently to keyword recall) and pass it to `ChatMemoryStore`.
- Backfill policy (keep simple): new/updated entries get embeddings on write (already
  how `remember` works once an embedder exists). Do NOT mass-rewrite old entries; the
  existing keyword-fallback-for-unembedded-entries behavior covers them, and they
  re-embed naturally when updated.
- Optional (nice-to-have, only if trivial): MemoryManager badge "semantic recall: on"
  driven by a field in `chat_memory_state` — skip if it grows the batch.

**Tests (no fastembed in the default suite):**
- `create_local_embedder` returns None when the import fails (monkeypatch
  `builtins.__import__` or `sys.modules` to raise ImportError) — no exception escapes.
- Sidecar with `semantic_memory_enabled=False` never calls the embedder factory
  (inject a counting fake factory seam if needed).
- Sidecar with the flag on + a FAKE factory passes the embedder into the store
  (assert semantic recall path activates with the fake vectors).
- Existing `ChatMemoryStore` fake-embedder tests stay green.
- A separate OPT-IN smoke (`python -m chat_embeddings --live` or a documented manual
  step) that actually loads fastembed and embeds one string — NOT in the default suite.

**Acceptance:** with the extra installed and the env flag on, memories are recalled by
meaning (e.g. a Thai preference about food surfaces for a restaurant question that
shares no keywords); with the package missing or the flag off, behavior is exactly
today's; the default test suite never touches the network.

---

## Definition of Done (every item)

Implement → full backend (`python -m unittest discover -s test`) + frontend
(`npx vitest run`) suites green, fully offline → send to Claude for in-session review
(focus points: Item 1 default-path byte-identical; Item 3 flag-off path identical +
no import/network in default suite) → append a review entry to
`work_logs/track-a-review-log.md` → STOP and report before the next item.
