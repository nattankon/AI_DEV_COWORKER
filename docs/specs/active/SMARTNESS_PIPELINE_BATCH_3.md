# Smartness Pipeline — Batch 3 (implemented by Claude, pending Codex review)

> Goal set by the user: push the app toward world-class quality. This batch converts the
> 2026-07-03 A/B evidence into defaults, closes the gaps that made those defaults unsafe,
> fixes the real mojibake, and formally reviews Batch 2.
> Verification: backend **367/367**, frontend **134/134** (both run after all changes).

## 1. Batch 2 formal review — PASS

Read the implementation directly:
- `chat_embeddings.py`: matches spec exactly — lazy fastembed import returning `None` on
  failure, `lru_cache`d model instance, cache dir under `COWORK_USER_DATA_DIR`, opt-in
  `--live` smoke CLI. No network in the default suite.
- Runner A/B plumbing: proven by the REAL reports (`chat-quality-live-20260703-115752`
  baseline vs `-120123` gated) — variant labels and Loop/Iters/Path-ms columns all
  populated.
- Sidecar: `semantic_memory_enabled` flag-gated embedder wiring (lazy, cached);
  `chat_quality_run` accepts `tool_research_routes`.
- Verdict: PASS, no rework. One design gap found and fixed below (mcp reachability).

## 2. Gated tool-research routes are now the DEFAULT (data-backed)

`ChatRuntimeConfig.tool_research_routes` default changed `None` →
`("web", "project", "mixed", "mcp")`. Evidence (same-day A/B, both models): pass rate
0.786 → 0.857, directness 0.93 → 1.0, general-route latency for flash 9.2s → 6.0s and
fail → pass. `None` remains supported as the legacy escape hatch (everything except
memory) and is covered by tests.

## 3. MCP stays reachable under the gated default (the trap the A/B exposed)

In the gated run, mcp-category cells "passed" with `Loop=False` — the model answered
MCP questions WITHOUT tools (fixture weakness + dead tools). Three-part fix:

- **Router:** new `"mcp"` route category driven by generic data terms
  (`mcp`, `connector`, `connectors`) — `chat_router.py`. MCP-intent prompts now enter
  the loop via the default tuple. (Terms are generic tech words, not vendor names — D1.)
- **Runtime bypass:** `_should_run_tool_research` returns True whenever the request's
  MCP toggle is on and `mcp_enabled` is set, regardless of route — available tools must
  be reachable even when the prompt has no MCP keywords (e.g. "มีพาร์ทกี่ชิ้นใน Workspace").
  Memory route stays excluded always.
- **Fixture hardening:** the mcp eval case now carries `requires_tool_loop: True` and its
  own `web_settings: {"mcp": "on"}`; the runner merges per-case settings over the base
  and passes `entered_tool_loop` into `evaluate_case_result`, which HARD-FAILS a
  tools-required case answered without the loop (None = unknown = not penalized, so old
  callers are safe).

## 4. Bangchak source adapter now covers the main page

`chat_source_adapters.py`: adapter host substring `oil-price.bangchak.co.th` →
`bangchak.co.th` (matches both the www page and the subdomain; same JSON API endpoint).
The 2026-07-03 smoke showed the main page falling through to raw HTML at quality 2 —
next smoke run should show it at adapter quality. Test added using the existing JSON
fixture against the main-page URL.

## 5. Mojibake FOUND and fixed (Codex review item 3, previously unreproducible)

It was never in the UI: `test/test_ipc_sidecar.py`'s guard-stream test had its Thai
literals double-encoded into CJK garbage (`喔｀覆喔勦覆…`) — evidence text, both stream
payloads, and the prompt. Restored to the intended strings ("Price table updated 26
มิ.ย.", "ราคาล่าสุด 26 มิ.ย. 2569 [web:1]", corrected form, prompt "ราคาน้ำมันล่าสุด").
Bonus: the restored prompt correctly classifies as a web route, so the test also
exercises the new default routing honestly.

## 6. Existing tests updated to match the new default (intent preserved)

- Chat scope test: prompt now web-routed ("what is the latest chatbot news?") so the
  loop's tool list is still asserted (web + MCP diagnostics + artifacts, NO workspace
  tools).
- General-question no-double-complete test: pinned to legacy routing
  (`tool_research_routes=None`) — that path still exists and must stay covered.
- Routes-gating test rewritten for the new default + a dedicated MCP-bypass test +
  router category test (Thai and English connector questions → `"mcp"`; plain question →
  `"general"`).

## 7. Also in this session (recorded for completeness)

- Documentation reorganized: root reduced to `README.md` / `AGENTS.md` /
  `PROJECT_STATE.md`; everything else under `docs/reference/`, `docs/specs/active/`,
  `docs/specs/archive/` with `docs/INDEX.md` as the map; stray root logs → `work_logs/
  test-runs/`; probe HTML → `work_logs/probes/`. Backend suite re-run after moves.

## Files touched (this batch)

| File | Change |
|---|---|
| `chat_runtime.py` | gated default `("web","project","mixed","mcp")` + rationale comment |
| `ipc_sidecar.py` | memory-first exclusion + MCP-toggle bypass in `_should_run_tool_research` |
| `chat_router.py` | `_MCP_TERMS` + `"mcp"` category |
| `chat_quality_eval.py` | `requires_tool_loop` + per-case `web_settings` on the mcp case; `entered_tool_loop` param; hard-fail finding |
| `chat_quality_runner.py` | per-case web_settings merge; passes `entered_tool_loop` |
| `chat_source_adapters.py` | bangchak substring broadened |
| `test/test_ipc_sidecar.py` | mojibake restored; 2 tests re-anchored; gating + bypass tests |
| `test/test_chat_router.py` | mcp category test |
| `test/test_chat_quality_eval.py` | +2 loop-gate tests |
| `test/test_chat_quality_runner.py` | +2 merge/fail tests |
| `test/test_chat_source_adapters.py` | +1 main-page adapter test |

## What Codex should verify hardest

1. The gated default cannot strand any real capability: search for other code paths that
   assumed general/memory prompts enter the loop (artifacts? code-exec? — both ride the
   same `web_tools_factory`, so a general-route prompt with artifacts enabled now skips
   them too. Claude judged this acceptable — artifacts trigger on answer DETECTION, not
   loop tools — but double-check `detect_artifacts` still fires on the legacy path).
2. Router `"mcp"` terms: confirm "connector" does not misroute unrelated prompts in real
   usage (e.g. electrical connectors) — acceptable false-positive cost is one tool loop
   entry, but flag if you disagree.
3. The mojibake restoration matches the original test intent (partial-date guard repair
   with stream replacement).

## Review outcome (Opus 4.8, 2026-07-03) — all findings closed

Independent read-only review by Opus 4.8 (Codex unavailable): PASS-with-findings, 12 findings,
2 HIGH. All fixed in-session; backend 370/370, frontend 134/134. Highlights:
- Mojibake was only 1/3 fixed (overclaim) — now fully restored; repo scan clean except intentional
  detector/relevance fixtures.
- Code-exec toggle was stranded on the general route exactly like the mcp bug this batch fixed — now
  bypassed identically, with a test.
- The showcase guard test asserted nothing (passed even with the guard deleted) — now asserts the year
  is stripped and exactly one repair runs.
- Bangchak adapter over-broadened to the whole corporate domain — narrowed to price paths only.
- CLI legacy variant + label collision fixed (LEGACY_ROUTES sentinel, "default:gated" label).
- Added tool_loop_attempted so a crashing loop is not misdiagnosed as "routing skipped".
- Tightened router "connector" matching (word boundary + app-context term).
Full finding-by-finding record: `work_logs/track-a-review-log.md` (2026-07-03 Opus entry).

## Next (not in this batch)

- Live re-run of smoke + scorecard to confirm bangchak quality jump and mcp-cell honesty
  (needs network/credits — user's call).
- Web category remains the weakest scorecard area: glm-5.2 under-searches (1 iteration,
  no sources), flash finds low-quality sources. Next lever after this batch lands:
  effort-based search-persistence steering + Brave key verification in the app env.
- Roblox prefetch redesign decision still queued (delete vs data-driven profile) — now
  measurable via the hardened mcp fixture.
