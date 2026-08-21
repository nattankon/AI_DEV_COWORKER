# Chat Context Compaction Plan

## Goal

Replace the Chat mode's fixed recent-message window with token-aware conversation
context planning. Chat retains its session transcript, fits the prompt to the
selected model's advertised context window, and summarizes older turns when the
full transcript no longer fits.

## Scope

Chat only. Cowork and Code prompts, approvals, tools, and persistence remain
unchanged.

## Steps

1. Add a pure conversation-context planner with token estimation, model-window
   lookup, safety/output reservation, and whole-turn recent-history selection.
2. Add rolling, cached summary compaction in the Chat sidecar path and keep the
   retained transcript independent of the selected effort level.
3. Surface context diagnostics, add regression coverage, and update project
   records after full backend and frontend verification.

## Acceptance Criteria

- Low effort no longer limits Chat continuity to four messages.
- The selected model's context metadata determines the usable history budget.
- Older turns are summarized rather than silently discarded once a prompt would
  exceed its budget.
- The summary is treated as untrusted historical content and is cached for an
  unchanged compacted prefix.
- Chat output, web research, attachments, and fallback behavior remain intact.
