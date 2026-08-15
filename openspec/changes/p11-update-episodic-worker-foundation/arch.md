# Episodic Worker Architecture

This feature keeps one main conversation with the user while moving substantive
work into short-lived Codex workers. A worker is an extension of the main agent:
it receives the same effective permissions, project instructions, skills, tools,
and configured MCP servers, but starts with a small record of current state
instead of inheriting an earlier worker's conversation.

This document is an architectural overview. The detailed behavior and validation
rules remain in [design.md](design.md) and the change's delta specifications.

## The idea in one sentence

The main agent coordinates, an equivalently capable fresh worker handles one
episode of work, and OneTool safely carries a small validated context file into
the next episode.

## Main components

| Component | Responsibility |
|---|---|
| Main conversation | Talks with the user and retains the returned session ID |
| `episodic-orchestrator` skill | Tells the main agent how to coordinate the workflow |
| `worker.run` | Provides the only public worker operation |
| Context store | Loads and commits one small `context.yaml` for the session |
| Console publisher | Sends user-facing content through the existing Console outbox without returning the body to the main agent |
| Change observer | Compares project files before and after an episode without storing file contents or diffs |
| History journal | Appends one MCP-authored mechanical record to `history.jsonl` after each episode |
| App-server adapter | Starts one fresh Codex thread and disposes it after the episode |
| Fresh worker | Extends the main agent with the same capabilities, performs the requested project work, and returns a strict terminal object |

## Channel model

The architecture keeps user communication, worker continuation, observable
effects, and control results in separate channels. Skills and worker instructions
teach both agents where information belongs; typed output, scoped tools, separate
storage, and runtime routing enforce the boundary.

| Channel | Writer | Reader | Storage and delivery | Automatic worker input |
|---|---|---|---|---|
| Chat | User and main agent | Current worker | Current `worker.run` prompt; the main conversation remains outside the worker | Current request or answer only |
| Context | Worker proposes; MCP validates and commits | Fresh workers in the same session | `episodic-context/<session-id>/context.yaml` | Complete current snapshot |
| Console | Worker through the Console publisher | User | Existing Console outbox and body store; the worker receives only a bounded receipt | Never |
| Local Changes | Worker through normal file tools | Project workspace and later workers | Project filesystem; the MCP observes paths changed during the episode | Through normal project-file access, never copied into context |
| Status | Worker and runtime | Main agent and user | Bounded `worker.run` terminal result | Never |
| History | MCP runtime only | User or system on explicit inspection | `episodic-context/<session-id>/history.jsonl` | Never |

Tool observations, source text, intermediate reasoning, and same-thread messages
form ephemeral working state, not another durable channel. They exist only in the
active worker thread and disappear when that thread is deleted.

Channel contents are not copied merely because another channel can reference
them. In particular:

- the main agent retains the opaque session ID but never receives or reads the
  Context body;
- Console bodies are shown to the user without being relayed through the main
  agent's conversational history;
- History records that Console output or local changes occurred but never copies
  their bodies, file contents, diffs, prompts, tool results, or agent-authored
  narrative;
- workers do not read Console or History automatically; and
- only Chat and Context enter a fresh worker prompt.

## What happens during one episode

1. The main agent calls `worker.run`. The first call has no `session_id`; later
   calls reuse the ID returned by the first call.
2. OneTool validates the execution policy and loads the entire stored context.
   Invalid YAML, schema errors, oversized context, and invalid file references
   stop the episode before a worker starts.
3. The MCP captures a project-root file baseline, excluding `.git`, OneTool
   runtime state, configured cache paths, and symlink targets outside the project.
4. The adapter checks that the installed Codex app-server can reproduce the main
   agent's effective execution permissions.
5. The adapter starts a new Codex thread and gives it the current user request
   plus the complete context. It never supplies previous worker messages.
6. The worker performs the substantive work with the main agent's effective
   permissions and the same Codex project instructions, skills, tools, and
   configured MCP servers. User-facing deliverables go to Console, while normal
   file tools apply requested Local Changes directly to the project.
7. The worker returns `completed` or `needs_input`, one bounded Status message,
   and optionally one complete replacement Context object. It does not return a
   Console body in the terminal message.
8. OneTool processes any returned Context, commits it if valid, and deletes the
   worker thread.
9. The MCP compares the final project tree with the baseline and classifies
   created, modified, and deleted project-relative paths. It records no file
   contents or diffs and does not depend on Git or Localhist.
10. The MCP appends one mechanical History record containing the episode outcome,
    Context revision transition, Console message identifiers, and Local Changes.
11. `worker.run` returns exactly `session_id`, `status`, and the bounded `message`
    to the main conversation. Console content reaches the user through the
    separate Console channel.

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
return at most one complete replacement. The main agent receives only the opaque
session ID and never receives the Context body.

## History and local-change boundary

History is a mechanical audit of observable episode facts, not agent memory. The
MCP is its sole writer; neither the main agent nor a worker composes a history
entry. Each terminal episode appends one compact UTF-8 JSON object to:

```text
.onetool/state/episodic-context/<session-id>/history.jsonl
```

Every record has a strict versioned schema and may contain the episode ID,
timestamps, terminal status, turn count, Context revisions before and after,
Console message identifiers and kinds, failure classification, and Local Changes
as project-relative path plus `created`, `modified`, or `deleted`. It contains no
Chat text, Console body, file content, diff, tool result, or semantic summary.

The MCP appends only after terminal handling and the post-episode file scan,
flushes the file, and calls `fsync`. Serialized worker execution gives the journal
one writer. Readers preserve all valid earlier records if an interrupted write
leaves a malformed final line. A history-write or change-scan failure adds a
bounded Status warning but does not undo worker side effects, Console delivery,
or a valid Context commit.

The project filesystem remains the source of truth for Local Changes. The
observer compares the pre-episode baseline with final state so it can detect an
additional edit to a file that was already dirty before the episode. It does not
follow symlinks outside the project and deliberately provides no snapshot,
rollback, or VCS integration.

## Console, status, and chat boundary

Console is the user-facing data plane. Workers publish substantial answers,
reports, evidence, previews, and file references through the existing Console
outbox. The publishing call returns only a bounded receipt to the worker; later
workers and the main agent do not automatically list or read Console bodies.

Status is the control plane. `worker.run` returns exactly `session_id`, `status`,
and one bounded `message` suitable for the main agent and user. The message may
state that a Console result is ready or contain the single `needs_input`
question, but it must not duplicate Console content.

Chat carries only the current user request or answer and the main agent's command
to the worker. A `needs_input` result terminates the episode and deletes its
thread. The user's answer becomes Chat input to a fresh episode in the same
session; the prior worker thread is never resumed.

## Execution boundary

The worker is a fresh-context extension of the main agent, not a lower-privilege
secondary agent. The main agent supplies its effective execution envelope:

- `cwd` is the absolute current project directory;
- `approval_policy` is `never` because an episode is synchronous and
  non-interactive;
- `sandbox` reproduces the main agent's effective `read-only`, `workspace-write`,
  `danger-full-access`, or `external-sandbox` boundary;
- read-only and workspace-write policies preserve the main agent's network
  access;
- workspace-write preserves every writable root and temporary-directory
  exclusion; and
- external-sandbox preserves whether externally managed network access is
  restricted or enabled.

`approval_policy: never` does not narrow the permissions already granted to the
main agent; it prevents a blocked worker from requesting additional authority
mid-episode. If the installed app-server cannot represent the supplied envelope,
the worker fails before startup rather than substituting a different policy.

The child Codex environment loads the same project instructions, skills, tools,
plugins, and configured MCP servers available through the main agent's Codex
configuration. The only intentional difference is conversational state: every
worker thread is fresh and receives the validated episodic context instead of the
main conversation or an earlier worker transcript.

Only one `worker.run` call may be active. A marked worker process cannot call
`worker.run`, so workers cannot recurse or fan out.

## Failure behavior

The system favors a clear failure over guessing or replaying work:

- Preflight failures start no worker.
- Invalid or oversized terminal context does not replace the current context.
- Failed and interrupted episodes are not retried automatically.
- A failed History append or Local Changes scan adds a bounded warning without
  reversing a known episode, Console, Context, or filesystem outcome.
- A cleanup failure adds a warning but does not change the known episode result
  or context outcome.
- A completed worker thread is never resumed.

This keeps the design small: one public operation, one fresh thread per episode,
one private Context snapshot, one mechanical History journal, and explicit
non-polluting channels for user output, filesystem effects, and control flow.
