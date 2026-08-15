---
name: use-worker
description: Coordinate a user task through fresh Codex worker episodes backed by named project-local Contexts. Use only when the user explicitly invokes $use-worker and wants the main agent to coordinate rather than perform substantive project work itself.
---

# Use Worker

Act only as the coordinator. Delegate substantive project investigation and work
to `worker.run`; do not duplicate it in the main conversation.

## Keep one Chat-selected Context

1. At the start of every invocation, set the selected Context name to `default`.
   Keep only that name as Chat-local coordinator state. Do not persist a
   process-global or project-global selection.
2. When the user or coordinator calls `worker.select(context=...)`, retain the
   returned Context name only after the call succeeds. A failed selection leaves
   the current Chat selection unchanged.
3. An explicit Context on `worker.run` is a one-episode override. It does not
   change the selected name used by later calls.

Never read, request, reproduce, or summarize a Context body. The bounded name,
description, tags, status, and revision exposed by Context operations are
metadata, not the semantic body.

## Run an episode

1. Call `worker.run` with the complete current request and the effective Context
   name: the one-episode override when present, otherwise the Chat-selected name.
   Pass `model` or `effort` only when the user requested an override.
2. Let OneTool derive the current project and inherit its enforced filesystem and
   network boundary. Do not construct or pass an execution-policy object.
3. Do not call another episode concurrently and do not retry a failed or
   interrupted episode automatically.

One `worker.run` may consume bounded internal continuation turns synchronously.
Do not request, relay, or simulate intermediate continuation. The same worker
thread and authority remain private to that call; only its final public result is
returned.

Codex loads the same project instructions, skills, tools, plugins, and configured
MCP servers from the current working directory and installed configuration. Do
not remove or replace those capabilities for the worker.

## Use artifacts explicitly

Use `worker.artifact_create`, `worker.artifact_open`, `worker.artifact_list`, and
`worker.artifact_delete` only with an explicit Context name. Create requires an
active owner; open, list, and delete also work after archival. Text content is
UTF-8 and binary content is strict base64.

Artifact metadata and bodies are never automatic Chat, Context, Console, Status,
History, or worker input. Do not open an artifact merely because its ID appears
in Context. Keep project deliverables as normal project files, and never inspect
or modify the artifact state directory directly.

## Handle the result

- `completed`: Relay only the bounded Status receipt and stop. Substantial output
  reaches the user through Console; do not request or duplicate its body.
- `needs_input`: Ask the returned direct question. After the answer arrives, run
  a fresh episode with the same effective Context name used by the question.
- `failed`: Relay only the bounded failure Status and stop.
- `interrupted`: Relay only the bounded interruption Status and stop.

Treat the result as exactly `context`, `status`, and `message`. Do not read,
search, write, format, validate, repair, or summarize files under
`.onetool/state/worker`; explicit artifact operations are the only artifact
access path.

`continue` is not a public result status. If a call fails with `turn_limit` or
`episode_timeout` classification in its bounded message, relay that failure and
stop; do not replay the episode. A `needs_input` answer always starts a fresh
episode and thread with the same effective Context name.
