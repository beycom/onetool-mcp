# Episodic Worker Architecture

This feature keeps one main conversation with the user while moving substantive
work into short-lived Codex workers. Each worker starts with a small record of
current state instead of inheriting an earlier worker's conversation.

This document is an architectural overview. The detailed behavior and validation
rules remain in [design.md](design.md) and the change's delta specifications.

## The idea in one sentence

The main agent coordinates, a fresh worker handles one episode of work, and
OneTool safely carries a small validated context file into the next episode.

## Main components

| Component | Responsibility |
|---|---|
| Main conversation | Talks with the user and retains the returned session ID |
| `episodic-orchestrator` skill | Tells the main agent how to coordinate the workflow |
| `worker.run` | Provides the only public worker operation |
| Context store | Loads and commits one small `context.yaml` for the session |
| App-server adapter | Starts one fresh Codex thread and disposes it after the episode |
| Fresh worker | Performs the requested project work and returns a strict terminal object |

## What happens during one episode

1. The main agent calls `worker.run`. The first call has no `session_id`; later
   calls reuse the ID returned by the first call.
2. OneTool validates the execution policy and loads the entire stored context.
   Invalid YAML, schema errors, oversized context, and invalid file references
   stop the episode before a worker starts.
3. The adapter checks that the installed Codex app-server can enforce the
   requested restrictions.
4. The adapter starts a new Codex thread and gives it the current user request
   plus the complete context. It never supplies previous worker messages.
5. The worker performs the substantive work with normal Codex project
   instructions, skills, tools, and configured MCP servers.
6. The worker returns `completed` or `needs_input`, a message, and optionally one
   complete replacement context object.
7. OneTool processes any returned context, commits it if valid, and deletes the
   worker thread.
8. `worker.run` returns exactly `session_id`, `status`, and `message` to the main
   conversation.

Every later episode repeats this process with another fresh thread.

## Context boundary

The context file stores current operational truth, not conversation history. It
lives at `.onetool/state/episodic-context/<session-id>/context.yaml` in the
current project, so session IDs cannot silently cross projects. It contains only:

- the current goal and success criteria;
- current work, next actions, and blockers;
- durable facts, decisions, and constraints;
- unresolved questions; and
- references to useful files inside the project.

The worker authors this meaning as a typed object. OneTool—not an agent—then
performs the mechanical work:

- normalize permitted whitespace and path forms;
- remove blank strings and exact duplicates;
- validate the strict schema and project-relative references;
- render canonical UTF-8 YAML;
- enforce `context_max_kb`, which defaults to 16 KB;
- manage the revision number; and
- replace the file atomically.

There is no public context read, write, search, patch, or repair tool. The full
validated context is automatically supplied at worker startup, and the worker can
return at most one complete replacement.

## Execution boundary

V1 accepts a deliberately small execution policy:

- `cwd` is the absolute current project directory;
- `approval_policy` is always `never`;
- `sandbox` is `read-only` or `workspace-write`;
- network access is disabled; and
- workspace writes are limited to `cwd`.

Only one `worker.run` call may be active. A marked worker process cannot call
`worker.run`, so workers cannot recurse or fan out.

## Failure behavior

The system favors a clear failure over guessing or replaying work:

- Preflight failures start no worker.
- Invalid or oversized terminal context does not replace the current context.
- Failed and interrupted episodes are not retried automatically.
- A cleanup failure adds a warning but does not change the known episode result
  or context outcome.
- A completed worker thread is never resumed.

This keeps the design small: one public operation, one fresh thread per episode,
one context file per session, and one deterministic persistence path.
