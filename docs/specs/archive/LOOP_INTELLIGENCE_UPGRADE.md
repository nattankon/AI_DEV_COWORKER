# Loop Intelligence Upgrade — Tool-Loop & Reasoning Improvements

> Handoff spec for Codex. English throughout; Thai strings are literal data. Self-contained.
> Companion: `CONCEPT_COMPLETE_UPGRADE_PLAN.md`, `work_logs/track-a-review-log.md`.

## Design philosophy (the goal these changes serve)

Two principles drive every item below:
1. **A small model that thinks LONGER is fine** — running more steps must HELP, never crash. The loop
   should degrade gracefully and scale its budget with effort.
2. **A big model should LEAP** — the harness must not bottleneck a strong model (e.g. serialize work it
   could parallelize).

The current shared loop is `run_tool_loop` in `tool_loop.py` (used by BOTH Chat research via
`chat_research_runner.py` AND Cowork via `cowork_agent.py`). Chat research currently uses a FIXED
`max_iterations=6` and `WebResearchTools(max_fetch=5)`; on running out it RAISES
`RuntimeError("Agent loop exceeded {max_iterations}")`.

## CRITICAL cross-cutting constraint

`tool_loop.py` is SHARED with Cowork. Every change here must keep the **full Cowork test suite green**
and **not change Cowork's observable behavior** unless explicitly opted in. Risky loop changes (items 1
and 4 especially) must be OPT-IN via a parameter so Cowork keeps its current behavior unless enabled.

---

## Item 1 — Graceful max-iterations: forced best-effort answer (NOT a crash)

**Problem:** `run_tool_loop` raises when it hits `max_iterations` (`tool_loop.py` final line). A small
model that "thinks longer" until it runs out of steps gets a CRASH, not an answer — directly against
principle 1.

**Design:** when the loop reaches the last iteration and the model still wants tools (or would exceed
the cap), do ONE final turn with **tools disabled** plus a forced-answer nudge, then return that answer
through the NORMAL finalize path.
- Forced-answer nudge (system/user): *"You have reached the research limit. Provide your best answer
  using ONLY the evidence already gathered. For anything you could not find, say so explicitly — do NOT
  guess, fabricate, or fill gaps with invented values or citations."*
- Disable tools for this turn (`tools=[]`/skip schemas) so the model must answer, not search again.

**GUARD MUST NOT BE SKIPPED (answer to the key design question):** a forced answer is MORE prone to
hallucination (the model is pressured to "complete" an answer on incomplete evidence), so the guard
matters MORE here, not less. The forced answer MUST pass through the same `before_finalize` hook and the
post-loop `validate_answer` exactly like a normal answer — `validate_answer` will strip/flag any number,
year, or citation not present in the evidence actually gathered. Never add a "we're out of time, return
unchecked" shortcut.

**Opt-in:** add a param e.g. `force_final_answer: bool = False` (or `on_force_finalize` hook). Chat
research enables it; Cowork keeps its current raise unless explicitly enabled (preserve Cowork behavior).
Add `forced: bool` to `ToolLoopOutcome` for telemetry.

**Files:** `tool_loop.py` (forced-finalize path + outcome flag), `chat_research_runner.py` (enable it;
the post-loop guard already runs), `ipc_sidecar.py` (telemetry).

**Tests:** a fake model that ALWAYS returns tool_calls (never finalizes) + force_final_answer=True ->
after max_iterations, a tools-disabled forced answer is produced (NO raise); assert the forced answer
still went through the guard (a fabricated number absent from evidence is stripped/flagged). Cowork
(force off) still raises on overflow — unchanged.

---

## Item 2 — Effort-tied budgets (let small models think longer, on demand)

**Problem:** Chat research budgets are fixed (`max_iterations=6`, `max_fetch=5`), ignoring the Low/
Medium/High effort the user already picks. This is the most direct expression of principle 1.

**Design:** add per-effort research budgets to `ChatEffortConfig` (in `chat_runtime.py`):
```
Low    -> research_max_iterations=4,  research_max_fetch=3
Medium -> research_max_iterations=6,  research_max_fetch=5
High   -> research_max_iterations=12, research_max_fetch=8
```
`ipc_sidecar.py` `_run_tool_research_chat` reads the effort config and passes `max_iterations` to
`ChatResearchRunner` and `max_fetch` to the `WebResearchTools` factory (both already accept these).

**Files:** `chat_runtime.py` (ChatEffortConfig fields + defaults), `ipc_sidecar.py`
(_run_tool_research_chat wiring), `chat_research_runner.py` / `chat_web_tools.py` (already parameterized).

**Tests:** High effort -> runner built with max_iterations=12 and tools with max_fetch=8; Low -> 4/3.
Behavior unchanged at Medium (back-compat with today's 6/5).

---

## Item 3 — Repetition / stuck detection (stability; saves budget)

**Problem:** the loop never checks for repeated tool calls. A weak model can call `web_search` with the
same query, or `web_fetch` the same URL, multiple times — burning its whole budget for nothing.

**Design:** in `run_tool_loop`, track a set of seen `(tool_name, normalized_args)`. If a call repeats an
already-seen identical call, DO NOT re-execute it; instead return a short result like
`{"status":"skipped","reason":"duplicate call — you already did this; use the prior result or answer"}`.
After N (e.g. 2) duplicates in a run, optionally inject a steering user message
("You are repeating tool calls; use what you have or finalize").

**Files:** `tool_loop.py`. Must be behavior-neutral for Cowork in the non-duplicate case (a normal run
calls distinct tools, so no change). Keep this generic (works for any tool, not just web).

**Tests:** a model repeating the same `web_search` -> second call returns the "skipped/duplicate" result
without re-invoking the tool; a normal run with distinct calls is unaffected (Cowork green).

---

## Item 4 — Parallel dispatch of multiple tool_calls in one turn (big model leap)

**Problem:** `run_tool_loop` dispatches a turn's tool_calls with a sequential `for call in tool_calls`.
A strong model that fans out (e.g. fetch 3 sources in one turn) is forced to wait serially — against
principle 2.

**Design:** when a turn contains MULTIPLE tool_calls, dispatch them CONCURRENTLY (bounded
ThreadPoolExecutor), then append the tool result messages in the SAME ORDER as the calls (match by
tool_call_id). Single-tool turns stay on the simple path.

**Thread-safety (the real risk):** `WebResearchTools` shares mutable state — the `sources()` index
registry and the `max_fetch` counter. Concurrent dispatch MUST guard these with a lock so indices stay
stable and the fetch cap is honored (no race). Verify the source-index invariant under concurrency.

**Cowork preservation (important):** Cowork's per-tool hooks (`on_tool_result` -> run_state stage
recording + verification gating) assume per-tool ordering. To avoid changing Cowork behavior, make
parallel dispatch OPT-IN (e.g. `parallel_tools: bool = False`) and enable it ONLY for Chat research, OR
ensure hooks fire in call order after the concurrent batch completes. Cowork stays sequential unless
proven equivalent. Cowork suite MUST stay green.

**Files:** `tool_loop.py` (concurrent dispatch, opt-in), `chat_web_tools.py` (lock around the source
registry + fetch counter).

**Tests:** a turn with 3 tool_calls + a fake fetcher with delays -> dispatched concurrently (wall time <
sum of delays), tool results appended in call order, source indices stable (no race). Cowork path
(parallel off) unchanged.

---

## Item 5 — Unproductive-tool steering (smarter recovery)

**Problem:** when fetches keep returning blocked pages or empty evidence, the model only sees JSON error
strings and is left to guess what to do — a weak model can loop unproductively.

**Design:** track consecutive UNPRODUCTIVE tool results (blocked page, or empty evidence/tables). After
K (e.g. 2) in a row, inject a steering user message: *"Recent fetches returned no usable data. Try a
different source, or give your best answer from what you have and state what is missing."* (Pairs with
Item 1's honesty requirement.)

**Files:** `tool_loop.py` (or via a research-runner hook so it stays Chat-focused). Keep Cowork
unaffected (its tools rarely return "blocked/empty" the same way; gate to web tools or make the
"unproductive" predicate web-specific/opt-in).

**Tests:** K blocked/empty fetches in a row -> a steering user message is injected once; a productive
run is unaffected.

---

## Item 6 — Context budget for accumulated tool results (small-context stability)

**Problem:** every tool result is appended to `messages` (evidence up to 1800 chars + tables per fetch).
Long research on a SMALL-context model bloats/overflows the context, degrading quality or erroring —
against principle 1 (think longer must not break small models).

**Design:** cap the total size of tool-result content kept in the MODEL's message context. When it
exceeds a budget, compress/truncate the OLDEST tool results (keep the most recent / a short summary),
while the guard's `evidence_corpus` (sourced from `WebResearchTools.evidence_corpus()`) still retains
the FULL evidence for validation. So the model's context is bounded but grounding checks stay complete.

**Files:** `tool_loop.py` (or the runner) — trim/summarize old `role:"tool"` messages past a budget;
ensure `WebResearchTools.evidence_corpus()` is unaffected.

**Tests:** many large tool results -> total tool-message context stays under the budget; the guard still
sees full evidence (a value only in an OLD fetch is still validated correctly).

---

## Smaller add-ons (cheap, optional)

- Tell the model when evidence was TRUNCATED (the 1800-char cap) so it doesn't assume it saw everything.
- A light "plan first" line in `RESEARCH_INSTRUCTIONS` ("decide what you need, then search") — helps
  strong models structure multi-step research.

---

## Suggested sequencing (each its own commit + DoD)

1. **Item 2** (effort-tied budget) — contained, high-value, no shared-loop risk.
2. **Item 1** (graceful forced answer, guard-checked, opt-in) — the anti-crash win.
3. **Item 3** (repeat detection) — small, stability.
4. **Item 5** (unproductive steering) — small, smarter recovery.
5. **Item 6** (context budget) — small-context stability.
6. **Item 4** (parallel dispatch) — LAST: highest risk (thread-safety + Cowork), do it carefully.

## Definition of Done (per item)

1. Implement. 2. **Full backend suite green, and the COWORK suite specifically green** (shared loop) +
   frontend vitest green where touched. 3. Claude review (CLI or in-session) — for shared-loop items,
   focus on Cowork behavior-preservation; for Item 1, focus on "forced answer still passes the guard";
   for Item 4, focus on thread-safety + Cowork hook ordering. 4. Append a review entry to
   `work_logs/track-a-review-log.md`. 5. STOP and report.

## Acceptance (the philosophy, verifiable)

- A small/slow model on HIGH effort runs more steps and still returns a guard-checked best-effort answer
  (never a raw crash) even if it never "finishes" on its own.
- A strong model that fans out multiple fetches in one turn has them run concurrently.
- Repeated/blocked/empty tool calls do not silently burn the whole budget; the model is steered or the
  call is skipped.
- Long research does not overflow a small-context model, while grounding checks stay complete.
