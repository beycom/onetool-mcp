# Named-Context Worker Architecture

This feature keeps one main Chat with the user while moving substantive work into
short-lived Codex workers. Each worker starts with the active project and one
small named Context instead of inheriting the main Chat or an earlier worker
transcript.

This file is an architectural overview. Normative behavior remains in the change
design and delta specifications; implementation tasks promote only verified
behavior here.

## The idea in one sentence

The main agent coordinates, a fresh worker handles one episode, and OneTool
carries one explicitly selected project-local Context into that episode.

## Identity model

| Concept | Meaning |
|---|---|
| Project | The effective CWD with its project instructions and current files |
| Chat | The user/main-agent conversation and its selected Context name |
| Context | Durable current semantic state for one named project workstream |
| Episode | One synchronous `worker.run` invocation |
| Thread | Fresh ephemeral Codex conversation used by an episode |

There is no project registry, public worker session, or contextless episode.
Every newly invoked orchestrator selects `default`. A Chat can switch Contexts,
and an explicit run name can override the selection for one episode.

## Main components

| Component | Responsibility |
|---|---|
| Main Chat | Talks with the user and retains one selected Context name |
| `use-worker` skill | Defaults selection, resolves overrides, and delegates work |
| Worker pack | Runs episodes and selects, lists, updates, or archives Contexts |
| Context store | Validates and atomically commits named Markdown files |
| Console publisher | Delivers substantial worker output without returning its body |
| Change observer | Classifies project-file effects without storing contents or diffs |
| History journal | Appends project-scoped mechanical episode facts |
| App-server adapter | Starts and deletes one fresh Codex thread per episode |

## Worker surface

```text
worker.run(prompt, context?, model?, effort?)
worker.select(context)
worker.list_contexts(status?)
worker.update_context(context, description?, tags?)
worker.archive_context(context)
```

Missing active names used by run, select, or update are created automatically.
Archive preserves a file but prevents later run, select, update, or implicit
recreation. `default` cannot be archived.

The orchestrator owns Chat selection. `worker.select` returns a bounded receipt,
and the main agent retains that name and supplies it on later calls. Selection is
never process-global or project-global state.

## Channel model

| Channel | Writer | Reader | Storage/delivery | Automatic worker input |
|---|---|---|---|---|
| Chat | User and main agent | Current worker | Current request | Current request only |
| Context | Worker proposes; MCP commits | Workers using that name | `contexts/<name>.md` | Complete selected body |
| Console | Worker publisher | User | Existing outbox/body store | Never |
| Local Changes | Worker file tools | Project and later workers | Project filesystem | Normal file access only |
| Status | Worker and runtime | Main agent and user | Bounded operation result | Never |
| History | MCP runtime | Explicit inspectors | Project `history.jsonl` | Never |

Context name, description, tags, status, and revision are discoverable metadata.
The semantic Markdown body is not returned to the main agent or copied across
channels. Tool observations, source text, reasoning, and thread messages remain
ephemeral.

## One episode

1. The orchestrator resolves the Chat-selected or explicit Context name.
2. OneTool validates or atomically creates the active Context and loads its
   complete file, revision, and digest.
3. The runtime captures a project-tree baseline with state/cache exclusions.
4. The adapter proves the child cannot broaden the effective authority.
5. The adapter starts a fresh thread in the effective project.
6. The worker receives the current request and selected semantic body as
   explicitly delimited untrusted state.
7. The worker performs work; substantial output goes to Console and project
   deliverables go through normal file operations.
8. The worker returns terminal Status and optionally one complete replacement
   semantic body.
9. OneTool validates and atomically commits or preserves the Context, then
   deletes the thread.
10. The runtime observes final Local Changes and appends project History.
11. `worker.run` returns exactly Context name, status, and bounded message.

Every later episode repeats this sequence with another fresh thread. Selecting
the same name carries current semantic state; selecting a newly created review
name carries no state from the implementation Context while still seeing the
same project files and instructions.

## Context files

Context files live at:

```text
.onetool/state/worker/contexts/
├── default.md
├── feature-x.md
└── review-feature-x.md
```

Each file contains strict YAML frontmatter followed by a complete Markdown body:

```markdown
---
schema_version: 1
revision: 3
status: active
description: Implement feature X
tags: [feature, active]
---

# Goal

Current semantic state, not a transcript.
```

The runtime validates names, frontmatter, encoding, references, and complete-file
size; manages revision; and replaces files atomically. A worker replacement is
bound to the loaded revision and digest, so a manual edit during an episode is
never overwritten.

`update_context` changes only description and tags. Omitted values preserve;
explicit empty values clear; supplied tags replace the list. `archive_context`
changes only status and revision and preserves all other content.

## History and Local Changes

Project History lives at:

```text
.onetool/state/worker/history.jsonl
```

Each record may contain episode ID, Context name, timestamps, terminal status,
turn count, Context revisions, Console identifiers, failure classification,
warnings, and sorted created/modified/deleted paths. It contains no prompts,
Context description, tags or body, Console body, file content, diff, tool result,
or semantic summary.

The project filesystem remains the source of truth for Local Changes. Pre/post
comparison detects further edits to already dirty files without invoking Git or
storing snapshots.

## Console, Status, and Chat

Console is the user-facing data plane for answers, reports, evidence, previews,
and file references. Status is the bounded control plane. Chat carries the
current request or answer and coordinator selection only.

A `needs_input` result ends the episode and deletes its thread. The answer starts
a fresh episode using the same effective Context name.

## Authority and isolation

The worker starts in the effective project and inherits the caller's enforced
filesystem and network boundary. Approval remains non-interactive. The adapter
must fail before startup if it cannot ensure the child cannot broaden authority.

The child loads the same project instructions, skills, tools, plugins, and
configured MCP servers. One call may be active, and the marked child cannot call
worker operations recursively.

## Failure behavior

- Invalid Context name/frontmatter/body prevents startup or commit as applicable.
- Revision or digest conflict preserves the manual or competing edit.
- Archived names fail rather than reactivate or create replacements.
- Invalid or oversized replacement preserves the prior file.
- Failed and interrupted episodes are never replayed.
- Cleanup, final-scan, or History failures add bounded warnings without reversing
  known worker, Console, Context, or filesystem effects.
- A completed worker thread is never resumed.

The result is a small model: one project, one Chat-selected named Context per
episode, one fresh thread, and explicit non-polluting channels for output,
filesystem effects, and control flow.
