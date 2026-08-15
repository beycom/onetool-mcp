---
name: episodic-orchestrator
description: Coordinate a user task through fresh Codex worker episodes backed by small MCP-owned continuation context. Use only when the user explicitly invokes $episodic-orchestrator and wants the main agent to coordinate rather than perform substantive project work itself.
---

# Episodic Orchestrator

Act only as the coordinator. Delegate substantive project investigation and work to
`worker.run`; do not duplicate it in the main conversation.

## Run an episode

1. Build `execution` with the absolute current project directory, approval policy
   `never`, and either `read-only` or `workspace-write`. Use `workspace-write` only
   when the task requires edits and the current session permits them. Never grant
   broader access than the current session.
2. For the first episode, call `worker.run` with the complete current request and no
   `session_id`. Pass `model` or `effort` only when the user requested an override.
3. Retain the returned `session_id`. For a user answer or follow-up, call
   `worker.run` again with that same ID and only the new request or answer. The MCP
   supplies the complete validated continuation context to each fresh worker.
4. Do not call another episode concurrently and do not retry a failed or interrupted
   episode automatically.

## Handle the result

- `completed`: Relay the worker's message and stop.
- `needs_input`: Ask the user the worker's question. After the answer arrives, run a
  new episode with the same `session_id`.
- `failed`: Relay the failure and stop.
- `interrupted`: Relay the interruption and stop.

Treat the result as exactly `session_id`, `status`, and `message`. Do not look for or
invent context-management tools. Never read, search, write, format, validate, repair,
or summarize `context.yaml`; those operations belong to the MCP.
