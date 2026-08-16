# Worker

Run fresh Codex worker episodes with named project-local Contexts and bounded
control Status.

## Highlights

- One fresh Codex thread per synchronous episode, with up to 3 turns by default
  and no recursion or fan-out
- Complete current state in strict `.onetool/state/worker/contexts/<name>.md` files
- Nine operations for episodes, Context management, and explicit artifact access
- Substantial output through Console; exact bounded `context`, `status`, and
  `message` results from `worker.run`
- Current project, instructions, capabilities, and enforced authority inherited
  without a public execution-policy parameter
- Optional exact-keyed app-server reuse with a fresh deleted thread every episode

## Functions

| Function | Description |
|----------|-------------|
| `worker.run(prompt, context?, model?, effort?)` | Run one fresh worker episode |
| `worker.ctx_select(context)` | Create or validate an active Context for caller-owned selection |
| `worker.ctx_list(status?)` | List body-free Context metadata in name order |
| `worker.ctx_update(context, description?, tags?)` | Create a Context or replace supplied metadata |
| `worker.ctx_archive(context)` | Archive an active non-default Context |
| `worker.asset_create(context, content, kind, media_type, label)` | Create an immutable artifact for an active Context |
| `worker.asset_open(context, artifact_id)` | Open and validate one artifact explicitly |
| `worker.asset_list(context, limit?, offset?)` | List bounded metadata oldest-first |
| `worker.asset_delete(context, artifact_id)` | Delete one existing artifact explicitly |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | str | Current request or required-input answer; must not be blank |
| `context` | str | Lowercase Context slug; `run` defaults to `default` |
| `model` | str | Optional direct Codex model override for this call |
| `effort` | str | Optional installed Codex reasoning-effort override |
| `status` | `active`, `archived`, or null | Optional `ctx_list` filter |
| `description` | str or omitted | Complete replacement description; empty clears it |
| `tags` | list[str] or omitted | Complete ordered replacement tag list; empty clears it |
| `content` | str | UTF-8 text, or strict base64 for binary artifacts |
| `kind` | `text` or `binary` | Artifact content encoding kind |
| `media_type` | str | Lowercase `type/subtype` without parameters |
| `label` | str | Nonblank artifact label of at most 256 UTF-8 bytes |
| `artifact_id` | str | Opaque ID returned by artifact create or list |
| `limit`, `offset` | int | Artifact page size 1–64 and zero-based offset |

Context names use lowercase letters, digits, and single hyphens. A missing valid
name used by `run`, `ctx_select`, or `ctx_update` is created atomically. Archived
names remain reserved and cannot be run, selected, updated, or recreated.
`default` cannot be archived.

## Results and channels

Every `worker.run` result contains exactly:

| Field | Values |
|-------|--------|
| `context` | Effective Context name for the episode |
| `status` | `completed`, `needs_input`, `failed`, or `interrupted` |
| `message` | Status receipt, direct question, or diagnostic, at most 1024 UTF-8 bytes |

Workers publish substantial answers, reports, evidence, previews, and file
references through Console. The run result does not duplicate Console content or
return a Context body. Project deliverables remain normal project files. Mechanical
episode facts and created, modified, or deleted paths go to project History at
`.onetool/state/worker/history.jsonl` without file content or diffs.

`ctx_select`, `ctx_list`, `ctx_update`, and `ctx_archive` return bounded
receipts or frontmatter metadata only. Selection is caller-owned: a coordinator
retains the selected name for its current Chat and passes it explicitly to later
runs. No process-global or project-global selection is stored.

Within one `worker.run`, a worker may internally request another turn by naming
one concrete autonomous action. OneTool consumes that outcome; `continue` is
never a public status. The same thread, model, effort, project, approval policy,
and sandbox authority are reused. The first turn alone receives Chat and the
complete selected Context; later turns receive only a fixed continuation
instruction and the preceding action.

Context is committed once, only from final `completed` or `needs_input`. A turn
limit, episode deadline, interruption, or later failure leaves it at the
pre-episode revision. Earlier project, Console, and external effects remain and
are never replayed or claimed as rolled back. History records the actual number
of turns started without storing continuation instructions, actions, or thread
messages. `needs_input` deletes the thread; the answer starts a fresh episode and
thread with the same named Context.

Warm runtime is enabled by default. The worker reuses at most one
healthy initialized app-server process for the exact same project, inherited
execution boundary, environment, and Codex/MCP credential configuration identity.
A bounded protocol health check precedes reuse, idle processes expire, and server
shutdown closes owned resources. Every episode still creates and deletes a fresh
thread. A pre-turn health failure may create one cold replacement; work is never
replayed after a turn starts.

Operational logging distinguishes cold and warm startup and records initialization,
first-event, thread-start, and total pre-turn duration without prompts, Context,
Console bodies, file contents, tool results, or secrets. See the
[repeatable benchmark and baseline](../../../dev/benchmarks/worker-warm-runtime.md).

## Context-owned artifacts

Artifacts hold evidence or intermediate files that should survive an episode but
are neither semantic Context nor project deliverables. They live under
`.onetool/state/worker/artifacts/<context>/<artifact-id>/` as one immutable body
and one strict metadata object. IDs are opaque and collision checked.

Creation requires an existing active Context and returns metadata without the
body. Open, list, and delete require the owning Context explicitly and remain
available after archival. Open validates metadata, byte length, SHA-256 digest,
media type, and text encoding before returning content. List returns metadata
only in stable oldest-first pages. Unknown IDs fail; deletion is not idempotent.

Each decoded body is limited to 8 MiB. One Context may retain at most 64 ready
artifacts and 64 MiB of ready body bytes. Creation uses synced staging and atomic
rename. Later access removes stale staging and excludes inconsistent finals with
bounded orphan warnings. Path escape and symlinked state components are rejected.

Artifact bodies and metadata are never automatic worker input and never copied
into Context, Console, Status, History, telemetry, or project Local Changes.
Workers and explicit inspectors use the four artifact operations; they never
read or modify the state directory directly. Project deliverables remain normal
project files.

## Context files

Each Context is one bounded UTF-8 Markdown file:

```markdown
---
schema_version: 1
revision: 3
status: active
description: Implement feature X
tags:
- feature
- active
---

# Goal

Complete current semantic state, not a transcript.
```

OneTool strictly validates frontmatter, encoding, local Markdown references, and
complete-file size. It owns canonical rendering, revisions, digest conflict
checks, and beside-file atomic replacement. A worker may propose one complete
Markdown body replacement; omitted replacement preserves the current revision.
Agents must not directly modify OneTool worker state.

Metadata updates preserve the semantic body. Omitted values preserve metadata,
explicit empty values clear it, and supplied tags replace the complete list.
Archival preserves the file, description, tags, and body while incrementing the
revision.

## Requires

- An installed `codex` CLI whose app-server schema supports `thread/start`,
  `thread/list`, `turn/start`, `turn/interrupt`, structured output, inherited
  external sandboxing, and `thread/delete`

## Configuration

### Required

None - no secrets or pack-specific settings are required.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.worker.model` | str or null | `null` | Default Codex model; a per-call value takes precedence |
| `tools.worker.effort` | str or null | `null` | Default reasoning effort; a per-call value takes precedence |
| `tools.worker.context_max_kb` | int | `16` | Positive maximum complete UTF-8 Context file size in KB |
| `tools.worker.max_turns` | int | `3` | Strict maximum episode turn count, from 1 through 10 |
| `tools.worker.episode_timeout_seconds` | int | `900` | Strict total episode deadline in seconds, from 1 through 3600 |
| `tools.worker.warm_runtime_enabled` | bool | `true` | Reuse one healthy exact-keyed app-server process between serialized episodes |
| `tools.worker.warm_runtime_idle_seconds` | int | `300` | Close an idle warm runtime after 1 through 3600 seconds |

```yaml
tools:
  worker:
    model: null
    effort: null
    context_max_kb: 16
    max_turns: 3
    episode_timeout_seconds: 900
    warm_runtime_enabled: true
    warm_runtime_idle_seconds: 300
```

### Defaults

- If `model` or `effort` is absent both per call and in configuration, the
  installed Codex default applies.
- If `context_max_kb` is omitted, complete Context files may be at most 16 KB.
- The turn count and deadline defaults are 3 turns and 900 total seconds. The
  deadline is monotonic and does not reset between turns.
- Warm reuse defaults on with a 300-second monotonic idle expiry. Set
  `warm_runtime_enabled: false` for explicit cold/debug operation.

## Examples

```python
# Start with the default Context.
worker.run(prompt="Inspect the routing implementation and publish a review.")

# Create metadata, then run in a named implementation Context.
worker.ctx_update(
    context="feature-x",
    description="Implement feature X",
    tags=["feature", "active"],
)
worker.run(
    prompt="Implement the approved change and run focused tests.",
    context="feature-x",
    effort="high",
)

# Use a fresh review Context for one episode without changing Chat selection.
worker.run(
    prompt="Review the current project independently and publish findings.",
    context="review-feature-x",
)

# Discover and archive completed Contexts.
worker.ctx_list(status="active")
worker.ctx_archive(context="review-feature-x")

# Preserve evidence outside Context and project deliverables.
created = worker.asset_create(
    context="feature-x",
    content="Focused test output",
    kind="text",
    media_type="text/plain",
    label="Focused tests",
)
worker.asset_open(
    context="feature-x",
    artifact_id=created["artifact"]["id"],
)
```

For coordinator-only behavior, explicitly invoke `$use-worker`. The
skill starts each invoked Chat with `default`, retains one selected name, and
treats an explicit run Context as a one-episode override.
