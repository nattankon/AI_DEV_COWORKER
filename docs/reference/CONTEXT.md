# Cowork Domain Context

## Standalone CLI

The command-line application that owns its Local AI connection, agent loop, workspace tools, approvals, conversation history, and session records. It must run without importing, spawning, packaging, or reading application code from the legacy Blender AI Studio host.

## Workspace

The single directory explicitly selected for a Cowork CLI session. All filesystem tool targets must resolve inside this directory after canonical path normalization.

## Tool Approval

The user decision required before a filesystem mutation is applied. Read-only tools do not require approval. A denied mutation returns a structured denial to the model and leaves the filesystem unchanged.

## Secret Guard

The policy applied before workspace metadata, contents, or write diffs are exposed. It blocks high-confidence secret paths such as environment files, private keys, SSH material, and credential-store directories while allowing explicit templates such as `.env.example`.

## Local AI

An OpenAI-compatible server selected explicitly by the user, normally LM Studio at `http://127.0.0.1:1234/v1`. Cloud fallback is outside the first standalone CLI milestone.
