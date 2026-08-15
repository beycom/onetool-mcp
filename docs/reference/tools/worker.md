# Worker

Run one fresh Codex worker episode with small MCP-owned continuation context.

## Highlights

- One synchronous tool and one fresh Codex thread per call
- Whole-context continuation through an opaque project-local session ID
- Explicit non-interactive sandbox policy with network access disabled
- Deterministic context formatting, validation, repair, and persistence by OneTool

## Functions

| Function | Description |
|----------|-------------|
| `worker.run(prompt, execution, ...)` | Run one worker episode and return its terminal result |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | str | Complete request for this episode; must not be blank |
| `execution` | object | Exact `cwd`, `approval_policy`, and `sandbox` policy |
| `session_id` | str | Omit for a new session; reuse the returned ID for a follow-up |
| `model` | str | Optional model override for this call |
| `effort` | str | Optional reasoning-effort override for this call |

`execution.cwd` must be the absolute current project directory.
`execution.approval_policy` must be `"never"`. `execution.sandbox` must be
`"read-only"` or `"workspace-write"`. Network access is always disabled.

Every result contains exactly:

| Field | Values |
|-------|--------|
| `session_id` | Opaque project-local ID used for later episodes |
| `status` | `completed`, `needs_input`, `failed`, or `interrupted` |
| `message` | Final answer, direct question, or failure/interruption detail |

### MCP-owned context schema

OneTool stores at most one `context.yaml` per session. The worker may return a
complete replacement containing:

- `goal`: status, objective, and success criteria
- `work`: summary, next actions, and blockers
- `knowledge`: typed facts, decisions, and constraints
- `questions`: unresolved questions
- `references`: existing project-relative file paths and their purpose

OneTool owns the schema version and revision. It normalizes and validates the
complete context, checks references and file size, renders canonical YAML, and
commits atomically. Agents do not read, search, format, repair, or write this file.
If a terminal result omits context, the last valid revision is preserved.

## Requires

- An installed `codex` CLI whose app-server schema supports `thread/start`,
  `turn/start`, `turn/interrupt`, structured output, and `thread/delete`

## Configuration

### Required

None — no secrets or pack-specific settings are required.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.worker.model` | str or null | `null` | Default Codex model; a per-call value takes precedence |
| `tools.worker.effort` | str or null | `null` | Default reasoning effort; a per-call value takes precedence |
| `tools.worker.context_max_kb` | int | `16` | Positive maximum canonical UTF-8 context file size in KB |

```yaml
tools:
  worker:
    model: null
    effort: null
    context_max_kb: 16
```

### Defaults

- If `model` or `effort` is absent both per call and in configuration, Codex uses
  its installed default.
- If `context_max_kb` is omitted, OneTool accepts canonical context files up to
  16 KB.

## Examples

```python
# Analyze without allowing project writes
worker.run(
    prompt="Review the routing implementation and report correctness issues.",
    execution={
        "cwd": "/workspace/onetool-mcp",
        "approval_policy": "never",
        "sandbox": "read-only",
    },
)

# Implement an approved change in the current project
first = worker.run(
    prompt="Implement the approved OpenSpec change and run focused tests.",
    execution={
        "cwd": "/workspace/onetool-mcp",
        "approval_policy": "never",
        "sandbox": "workspace-write",
    },
)

# Answer a required-input result in a fresh episode with the same context
worker.run(
    prompt="Use the existing registry convention.",
    execution={
        "cwd": "/workspace/onetool-mcp",
        "approval_policy": "never",
        "sandbox": "workspace-write",
    },
    session_id=first["session_id"],
)
```

For coordinator-only behavior, explicitly invoke `$episodic-orchestrator`. The
skill is never selected implicitly and does not add another tool surface.
