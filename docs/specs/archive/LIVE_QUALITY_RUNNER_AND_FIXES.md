# Live Quality Runner + Review Fixes (handoff spec)

> Handoff for Codex. English throughout; Thai strings are literal data. Self-contained.
> Source: the 2026-07-01 big review in `work_logs/track-a-review-log.md`. Do the two small fixes
> (A, B) first so the Live Runner (C) measures clean, real quality — not surface format.

## Why this order

The review found the Chat foundation solid, with two things to address before the next phase:
- A regression: `chat_research_strategy.py` re-hardcodes topic verticals (the oil/fuel branch you
  removed in D1 came back).
- A gap: the quality eval scores FORMAT (cited? Thai? latency?) but NOT hallucination — the exact
  failure mode you care about most.

Fixing A + B makes the Live Model Quality Runner (C) trustworthy: it will answer, with numbers,
"does the strategy help?", "which model fits which task?", and "did hallucination drop?".

Each item is its own commit + Definition of Done (test → Claude review → log → STOP).

---

## Item A — De-hardcode `chat_research_strategy.py` (remove the oil vertical)

**Problem:** `build_research_plan` uses `if _matches_any(...)` branches; the fuel/น้ำมัน branch
(lines ~25-32) is the exact topic vertical removed in D1, re-introduced. Topic-specific code will
re-grow (a new topic = new code) and re-couples the connector to test-fixture domains.

**Change:**
1. **Delete the oil/fuel branch entirely.** The model forms its own queries for fuel like any topic;
   the generic type-profiles below cover the "official/pricing" intent without naming fuel.
2. **Refactor the remaining branches into a DATA-DRIVEN registry** of query-TYPE profiles (type = kind
   of question, NOT topic). Example shape:
   ```python
   _QUERY_TYPE_PROFILES = (
       {"keywords": ("api","sdk","documentation","docs","openai","gemini","deepseek","z.ai","zai"),
        "query_templates": ("{q} official documentation",),
        "source_hints": ({"source_type":"official-docs","hint":"Prefer official API/model docs over blogs."},)},
       {"keywords": ("price","pricing","cost","quota","rate limit","billing","credit","subscription"),
        "query_templates": ("{q} official pricing","{q} official status quota limits"),
        "source_hints": ({"source_type":"pricing","hint":"Prefer official pricing/billing/quota/status pages."},)},
       {"keywords": ("github","repo","repository","readme","release notes","changelog","issue","pull request"),
        "query_templates": ("{q} site:github.com",),
        "source_hints": ({"source_type":"repository","hint":"Prefer the repo README/releases/changelog/issues/PRs."},)},
       {"keywords": ("news","latest","today","current","ล่าสุด","วันนี้","ปัจจุบัน"),
        "query_templates": ("{q} latest news",),
        "source_hints": ({"source_type":"news","hint":"Prefer recent primary sources or reputable news."},)},
       # adding a new query-type is DATA here, not code
   )
   ```
   `build_research_plan` iterates the registry, matching keywords, expanding `{q}` in templates, and
   collecting `source_hints`. Keep `answer_language` detection and `_clean_query` as-is.
3. Keep `source_preferences` as SOFT HINTS injected as instructions (they are — good; they carry no
   concrete values, so they do not open a date/price guessing channel).

**Constraints:** no topic name (fuel, oil, EPPO, Bangchak, gold, etc.) in code control flow — only
generic query-TYPE keywords as data. Behavior-preserving for the generic types.

**Files:** `chat_research_strategy.py`; update `test/test_chat_research_strategy.py`.

**Tests:** a docs/pricing/github/news query resolves via the registry (query templates + hints); a fuel
query no longer triggers a fuel-specific branch (it just flows as a normal query, optionally matching
"price"/"news" generically); adding a dummy profile entry works through the same path.

---

## Item B — Grounding / hallucination metric in the eval (reuse the guard)

**Problem:** `evaluate_case_result` (in `chat_quality_eval.py`) checks format/keywords/latency, not
whether numbers/dates/citations are grounded. The thing you care about most (guessing dates/prices) is
not measured.

**Change:**
1. Add an `evidence` parameter to `evaluate_case_result(case, *, answer, sources=None, evidence="",
   latency_ms=None)`.
2. Inside, call `chat_answer_guard.validate_answer(answer, evidence_corpus=evidence, sources=sources or [],
   allow=<current-date + prompt numbers>)`. If the guard returns violations, add a
   `"hallucinated: <joined violations>"` finding and force `status="fail"` (grounding is a hard gate,
   like "missing sources").
   - When `evidence` is blank (general/parametric answers), the guard is already a no-op (Phase 3 fix) —
     so general-knowledge answers are NOT penalized. Correct behavior.
3. Thread `evidence` through `run_quality_eval_snapshot` (accept `evidence` per supplied result) so the
   snapshot scorer can grade grounding too.

**Constraints:** grounding only bites when there IS evidence; do not penalize parametric answers.
Reuse the existing guard — do not reimplement number/date checks.

**Files:** `chat_quality_eval.py`; update `test/test_chat_quality_eval.py`.

**Tests:** an answer with a year/price NOT in the supplied evidence → `hallucinated` finding + fail; the
same value present in evidence → pass; a general case with empty evidence + a year → NOT flagged.

---

## Item C — Live Model Quality Runner (the main next work)

**Goal:** run the real fixture cases against REAL models and produce scored results, so quality is
measured, not guessed. Must answer: does strategy help, which model fits which task, did hallucination
drop, is latency acceptable, is Thai quality kept.

**Design:**
1. A thin headless entry to the Chat pipeline: `run_chat_once(prompt, *, model, effort, web_settings)
   -> {answer, sources, evidence_corpus, latency_ms, used_model}`. Reuse the existing pipeline
   (`IpcSidecar._run_plain_chat` / `ChatResearchRunner`); capture `sources` and `evidence_corpus` from
   the `ChatResearchResult`, and measure wall-clock latency. For non-web answers, `evidence_corpus` is
   "" (guard no-op). Inject the pipeline callable so tests use a fake (NO live model in the test suite).
2. `run_quality_eval_live(*, models, run_chat_once, categories=None) -> matrix`:
   - For each fixture case (optionally filtered by category) × each model in `models`, call
     `run_chat_once`, then score with `evaluate_case_result(case, answer=..., sources=..., evidence=...,
     latency_ms=...)` (grounding via Item B).
   - Produce a MATRIX: per (category × model) → {score, status, findings, latency_ms, hallucinated:bool,
     used_source:bool, thai_ok:bool}. Aggregate per model (pass rate, avg latency, hallucination rate)
     and per category — this directly answers "which model fits which task".
3. Expose it as a CLI/command gated behind a flag (needs model + network); it must NOT run in the
   default `unittest` suite. Save a JSON/markdown report under `work_logs/` for comparison over time.

**Constraints:** live model calls are OPT-IN (flag/CLI), never in the default test suite; the runner
must bound each call (reuse the model timeout); a single model/case failure records a "failed" cell and
continues (does not abort the matrix). Reuse the guard for grounding (Item B).

**Files:** new `chat_quality_runner.py` (`run_chat_once` + `run_quality_eval_live`); a small CLI hook;
`test/test_chat_quality_runner.py` (fake pipeline only).

**Tests (fake pipeline, no network):** a fake `run_chat_once` returning canned answers/sources/evidence
per model → the matrix scores each cell; a hallucinated cell (value not in evidence) → flagged; a model
that errors on one case → that cell is "failed", others still scored; category filter works.

**Acceptance:** running the live runner (with real models + flag on) yields a per-model × per-category
scorecard with pass rate, latency, hallucination rate, and source usage — a real answer to "which model
is best for which task" and "did quality improve".

---

## Minor carry-forward (from the review; not required for C)

- **MCP timeout cleanup:** `_call_with_timeout` (`chat_mcp_client.py`) unblocks the caller on timeout but
  the underlying thread/subprocess may linger (Python can't kill threads). When wiring the live stdio
  SDK, ensure the spawned connector process is terminated on timeout.
- **Frontend base64 persistence:** verify the frontend session persistence does NOT write image
  `data_url` base64 to disk (backend logs are already clean; this is a client-side check).
- **Code-exec network isolation:** the "no-network" string blocklist is best-effort/bypassable — keep
  code-exec off + approval-gated until a real sandbox (Pyodide/container) provides network isolation.

## Sequencing + Definition of Done

Order: **A → B → C** (fixes first so the runner measures clean quality). Each: implement → full backend
suite + frontend vitest green (Cowork suite green for any shared change) → Claude review (A: no topic in
code; B: grounding only bites with evidence; C: opt-in, bounded, fake-pipeline tests) → append a review
entry to `work_logs/track-a-review-log.md` → STOP and report. Do not start the next until confirmed.
