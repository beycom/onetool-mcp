# Worker

Run fresh Codex worker episodes with named project-local Contexts and bounded
control Status.

## Highlights

- One fresh Codex thread per synchronous episode, with no recursion or fan-out
- Complete current state in strict `.onetool/state/worker/contexts/<name>.md` files
- Five operations for running, selecting, listing, updating, and archiving Contexts
- Substantial output through Console; exact bounded `context`, `status`, and
  `message` results from `worker.run`
- Current project, instructions, capabilities, and enforced authority inherited
  without a public execution-policy parameter

## Functions

| Function | Description |
|----------|-------------|
| `worker.run(prompt, context?, model?, effort?)` | Run one fresh worker episode |
| `worker.select(context)` | Create or validate an active Context for caller-owned selection |
| `worker.list_contexts(status?)` | List body-free Context metadata in name order |
| `worker.update_context(context, description?, tags?)` | Create a Context or replace supplied metadata |
| `worker.archive_context(context)` | Archive an active non-default Context |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | str | Current request or required-input answer; must not be blank |
| `context` | str | Lowercase Context slug; `run` defaults to `default` |
| `model` | str | Optional direct Codex model override for this call |
| `effort` | str | Optional installed Codex reasoning-effort override |
| `status` | `active`, `archived`, or null | Optional `list_contexts` filter |
| `description` | str or omitted | Complete replacement description; empty clears it |
| `tags` | list[str] or omitted | Complete ordered replacement tag list; empty clears it |

Context names use lowercase letters, digits, and single hyphens. A missing valid
name used by `run`, `select`, or `update_context` is created atomically. Archived
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

`select`, `list_contexts`, `update_context`, and `archive_context` return bounded
receipts or frontmatter metadata only. Selection is caller-owned: a coordinator
retains the selected name for its current Chat and passes it explicitly to later
runs. No process-global or project-global selection is stored.

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
  `turn/start`, `turn/interrupt`, structured output, inherited external sandboxing,
  and `thread/delete`

## Configuration

### Required

None - no secrets or pack-specific settings are required.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.worker.model` | str or null | `null` | Default Codex model; a per-call value takes precedence |
| `tools.worker.effort` | str or null | `null` | Default reasoning effort; a per-call value takes precedence |
| `tools.worker.context_max_kb` | int | `16` | Positive maximum complete UTF-8 Context file size in KB |

```yaml
tools:
  worker:
    model: null
    effort: null
    context_max_kb: 16
```

### Defaults

- If `model` or `effort` is absent both per call and in configuration, the
  installed Codex default applies.
- If `context_max_kb` is omitted, complete Context files may be at most 16 KB.

## Examples

```python
# Start with the default Context.
worker.run(prompt="Inspect the routing implementation and publish a review.")

# Create metadata, then run in a named implementation Context.
worker.update_context(
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
worker.list_contexts(status="active")
worker.archive_context(context="review-feature-x")
```

For coordinator-only behavior, explicitly invoke `$use-worker`. The
skill starts each invoked Chat with `default`, retains one selected name, and
treats an explicit run Context as a one-episode override.
