# Documentation Index

> Organized 2026-07-03. Three tiers: root = living documents that tools/agents depend on;
> `docs/` = everything else; `work_logs/` = generated records. When a spec is finished
> AND reviewed, move it from `docs/specs/active/` to `docs/specs/archive/`.

## Tier 1 — Root (living; do NOT move; agents depend on these paths)

| File | Role |
|---|---|
| `README.md` | Entry point + CLI setup. (Some sections stale — frontend is no longer "paused".) |
| `AGENTS.md` | Mandatory dev rules for Codex/agents: verify, log to `work_logs/WORK_LOG.md`, update `PROJECT_STATE.md`. |
| `PROJECT_STATE.md` | THE living capability/state document. Most important single file for onboarding. |

## Tier 2 — `work_logs/` (living records; append-only)

| Path | Role |
|---|---|
| `work_logs/track-a-review-log.md` | Review log: every implement→review→verdict cycle since Track A. Primary continuity artifact. |
| `work_logs/WORK_LOG.md` | Codex's dated development log. |
| `work_logs/chat-quality-live-*.md/.json` | Live model×category scorecards (2026-07-03 pair = GLM-5.2 baseline vs gated A/B). |
| `work_logs/chat-web-smoke-*.md/.json` | Live web fallback-chain reports. |
| `work_logs/model-performance-profile.json`, `chat-web-source-profile.json` | Machine-readable profiles fed back into routing/source hints. |
| `work_logs/test-runs/` | Raw test/verification logs (moved from root). |
| `work_logs/probes/` | Raw HTML probes captured during the EPPO/Bangchak investigation. |
| `work_logs/sessions/` | JSONL runtime session records. |

## Tier 3 — `docs/reference/` (stable reference)

| File | Role |
|---|---|
| `reference/ARCHITECTURE.md` | 3-layer architecture (Chat → Cowork → Code CLI). |
| `reference/CONTEXT.md` | Project context snapshot. |
| `reference/INSTALL_AND_UPDATE.md` | Install/update steps. |

## Tier 4 — `docs/specs/active/` (specs still being executed or awaiting review)

| File | Status |
|---|---|
| `specs/active/SMARTNESS_PIPELINE_BATCH_2_PLAN.md` | Items 1-3 implemented + live A/B runs executed; awaiting Claude review + decision log (routes default, model tier). |

## Tier 5 — `docs/specs/archive/` (completed handoff specs, historical order)

| File | What it delivered |
|---|---|
| `TRACK_A_RESEARCH_FOUNDATION_DESIGN.md` | Shared tool loop + Chat web research foundation (Steps 1-6). |
| `CONCEPT_COMPLETE_UPGRADE_PLAN.md` | Search API, relevance gate, production stability round. |
| `LOOP_INTELLIGENCE_UPGRADE.md` | Forced-final-answer + loop intelligence items. |
| `CHAT_CAPABILITY_ROADMAP.md` | CompositeToolProvider, MCP foundation, code-exec, artifacts, router, memory. |
| `LIVE_QUALITY_RUNNER_AND_FIXES.md` | De-hardcoded strategy, grounding metric, live quality runner. |
| `CHAT_REMAINING_WORK_PLAN.md` | Web smoke, MCP phases, semantic memory seam, quality panel, UI polish. |
| `MCP_LIVE_CONNECTOR_PLAN.md` | MCP live connector completion plan (items 1-5). |
| `MCP_FIXES_IMPLEMENTED.md` | Claude-implemented MCP fixes (deadlock, payload, consent model) — Codex-reviewed. |
| `SMARTNESS_PIPELINE_BATCH_1.md` | Preset merge, exposed_tools, latency instrumentation, first live smoke. |
| `DEVELOPMENT_ROADMAP.md` | Early full-program roadmap (superseded by PROJECT_STATE + batch plans). |
| `HANDOFF.md` | Early handoff notes (2026-06-12, historical). |
| `2026-06-12-cowork-ui-rebuild.md` | Early Cowork UI rebuild plan (moved from `plans/`). |

## Other

| Path | Role |
|---|---|
| `docs/chat-completion-phase-plan.md` | Chat completion phase plan (phases A-…), partially executed. |
| `docs/superpowers/plans/` | Dated per-feature implementation plans written during development. |
| `.claude/`, `.agents/` | Tooling configuration for Claude Code / agent skills. |
