# Chat Completion Phase Plan

**Goal:** Continue the Chat-first roadmap toward a polished GPT/Gemini-like experience while preserving Chat/Cowork/Code boundaries.

**Phase A - User-visible controls**
- Memory Manager can create typed memories manually and keep edit/delete behavior.
- Chat assistant answers can be copied without copying hidden tool output.
- Session rail can search Chat history locally without changing persisted sessions.
- Quality evaluation fixtures can score answer/source/latency metadata for local smoke checks.

**Phase B - Research quality**
- Extend source-profile data by topic type and keep source strategy data-driven.
- Add result classification for official docs, news/current facts, GitHub, and pricing/status pages.
- Add tests that answers distinguish fetched evidence from inferred analysis.

**Phase C - Attachment depth**
- Improve attachment previews and extraction for PDF/Doc/Excel using explicit user attachments only.
- Keep workspace reads outside Chat unless the user switches to Cowork/Code.

**Phase D - MCP live depth**
- Add packaged MCP SDK path and HTTP/SSE transport support after bounded connection tests are in place.
- Keep write/destructive MCP tools approval-gated.

This round implements Phase A first because it is small, reversible, testable, and immediately visible in the Chat UI.
