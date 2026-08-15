## Context

The current implementation already serializes `worker.run`, starts a fresh Codex
thread, persists one compact Context, and returns a small result. Its session
identity is overloaded: it selects semantic Context, groups History and future
artifacts, and is retained for the whole main Chat. Unrelated implementation,
review, research, and staging episodes therefore inherit the same semantic state.

The revised foundation treats the effective CWD as the project, a named Context
as durable workstream state, an episode as one `worker.run`, and a thread as
ephemeral model conversation. No project registry or public session exists.

## Goals / Non-Goals

**Goals:**

- Let a Chat move quickly between named Contexts while every episode keeps a
  fresh worker thread.
- Make `default` the initial Context and make new named Contexts cheap to create.
- Keep Contexts as simple editable project-local files with bounded public
  metadata and private semantic bodies.
- Preserve exact authority, channel isolation, atomic Context commits,
  serialization, and non-replay.
- Establish one deterministic Console, Local Changes, History, cleanup, and
  Status lifecycle.

**Non-Goals:**

- A project registry, project parameter, contextless mode, transcripts, resumed
  worker threads, parallel workers, recursion, queues, retries, or long-term
  cross-project memory.
- Context deletion, rename, restore, search, partial semantic-body updates,
  automatic compaction, or compatibility with session IDs.
- Automatic artifact injection, durable Console replay, or rich History queries.

## Decisions

### 1. Scope named Contexts to the effective project

The effective CWD and its loaded project instructions define the project. Context
files live at `.onetool/state/worker/contexts/<context>.md`; no project registry,
project argument, or cross-project lookup is added.

Context names use a strict lowercase filesystem-safe slug. `default` is reserved
as the initial Chat selection but otherwise uses the same file and lifecycle.
Unknown active names supplied to `run`, `select`, or `update_context` are created
atomically. An archived name remains reserved and is never recreated implicitly.

Alternative: retain opaque session IDs. Rejected because they couple Context to a
Chat lifecycle and make topic selection undiscoverable.

### 2. Keep selection in the orchestrating Chat

Every newly invoked orchestrator starts with selected Context `default`. The main
agent retains only the selected name. `worker.select(context=...)` validates or
creates the named Context and returns a bounded receipt; the orchestrator then
supplies that name on later `worker.run` calls. Selection is not project-global or
process-global state.

An explicit Context on `worker.run` is a one-episode override and does not change
the Chat selection. There is no `None` or temporary mode: a fresh perspective is
a newly named Context such as `review-feature-x`.

This coordinator-owned selection avoids one Chat mutating another while keeping
the runtime interface deterministic for direct callers.

### 3. Store metadata and semantic state in one Markdown file

Each Context is one UTF-8 Markdown file with YAML frontmatter. Runtime-owned
frontmatter fields are `schema_version`, `revision`, and `status`; user-visible
metadata fields are `description` and `tags`. The filename is the Context
identity. The Markdown body is the complete current semantic state, not a
transcript or instruction source.

`list_contexts` reads only validated frontmatter and returns names, descriptions,
tags, statuses, and revisions in stable name order. `update_context` upserts only
description and tags. Omitted fields preserve their values; explicit empty values
clear them; supplied tags replace the complete list.

Workers receive the complete active body as explicitly delimited untrusted state
and may return one complete replacement body. The runtime owns parsing,
normalization, frontmatter rendering, revisioning, reference validation, size
measurement, and beside-file atomic replacement. It binds a commit to the loaded
revision and file digest so manual edits during an episode are never overwritten.

Alternative: make Context a Chat transcript. Rejected because transcripts grow,
anchor reviewers, and defeat fresh-thread isolation.

### 4. Archive without deleting or reusing identity

`archive_context` requires an existing active Context, changes only its status to
`archived`, increments its revision, and preserves metadata and body. `default`
cannot be archived. Archived Contexts remain visible to `list_contexts`, cannot be
selected or used for a run, and block implicit recreation under the same name.

Restore, delete, and rename operations are deferred. Direct manual recovery
remains possible because the representation is an editable file, but the runtime
never silently reactivates archived state.

### 5. Treat channels as ownership boundaries

The runtime and agent instructions use this routing table:

| Channel | Writer | Reader | Durable form | Automatic worker input |
|---|---|---|---|---|
| Chat | User and main agent | Current worker | Current request | Current request only |
| Context | Worker proposes; MCP commits | Workers using that name | Named Markdown file | Complete selected body |
| Console | Worker through `console.show` | User | Existing outbox | Never |
| Local Changes | Worker file tools | Project and later workers | Project filesystem | Normal file access only |
| Status | Worker and MCP | Main agent and user | `worker.run` result | Never |
| History | MCP only | Explicit inspectors | Project `history.jsonl` | Never |

Context metadata is intentionally discoverable, but Context bodies remain absent
from list results, Status, Console, History, and the main conversation. Source
text, tool results, reasoning, and same-thread messages remain ephemeral.

### 6. Publish substantial output through Console

Workers use the existing Console publisher for answers, reports, evidence,
previews, and file references. Public `worker.run` returns exactly `context`,
`status`, and a bounded `message`; it never returns a Context or Console body.

### 7. Store History at project scope

History lives at `.onetool/state/worker/history.jsonl` rather than inside a
Context directory. Each strict MCP-authored record includes the episode ID,
selected Context name, timestamps, terminal status, turn count, Context revision
transition, Console message identifiers, Local Changes classifications, bounded
failure classification, and warning codes.

History never stores prompts, descriptions, tags, Context bodies, Console bodies,
file contents, diffs, tool results, or agent-authored summaries.

### 8. Preserve authority without a public execution object

The worker starts in the effective project and inherits the parent process's
enforced filesystem and network boundary. The adapter sets non-interactive
approval and must prove it cannot broaden the effective authority before starting
a thread. An unrepresentable boundary fails before worker startup.

Project instructions, skills, tools, plugins, and configured MCP servers are
loaded normally for that CWD. Only one call may be active, and a marked worker
cannot recurse.

### 9. Use one deterministic terminal sequence

After terminal output, the runtime validates and commits or preserves the selected
Context, deletes the worker thread, performs the final Local Changes scan, appends
History, and returns bounded Status. Context failure changes the outcome to
`failed` and preserves the last valid revision. Cleanup, scan, or History failure
adds a bounded warning without reversing known effects. Failed or interrupted
episodes are never replayed.

## Risks / Trade-offs

- **A misspelled name creates a Context** → Return the effective name, keep files
  discoverable, and never recreate an archived identity.
- **Manual edits race with a worker commit** → Bind commits to revision and digest.
- **Chat selection could leak across callers** → Keep it in orchestrator state,
  never process-global state.
- **Free-form Markdown is less mechanically semantic than the original object** →
  Keep a complete bounded replacement and validate the metadata, references,
  encoding, and storage boundary mechanically.
- **Archived Contexts accumulate** → Preserve them deliberately; deletion and
  retention require a separate explicit contract.
- **Project History mixes Contexts** → Record only the bounded Context name and
  support deterministic filtering without copying metadata or bodies.

## Migration Plan

1. Replace the active `p11` session delta specs before they are synced.
2. Remove session IDs, session directories, the public execution object, and the
   sole-tool assertion without aliases or fallbacks.
3. Implement named Context files and the five-operation worker surface.
4. Reconcile Console, History, Local Changes, and terminal lifecycle behavior.
5. Update every unimplemented dependent change to the named-Context foundation.
6. Verify and sync only the final named-Context contract to main specs.

Rollback before spec sync is a normal code and artifact revert. No migration or
legacy session reader is retained.

## Open Questions

None. Restore, delete, rename, and retention are explicitly deferred.
