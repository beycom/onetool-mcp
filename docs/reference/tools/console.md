# Console

Publish inline messages from tool calls to a connected onetool-console app via the signed Console outbox.

## Highlights

- Inline-only in 3.0: text, markdown, code, diff, json, mermaid, yaml, or table content
- Oversized content is truncated to a bounded preview rather than erroring
- Publishing never requires a Console consumer to be connected — the outbox is retention-only when nothing polls it
- Retained messages are scoped to the current MCP instance and bounded by a configurable queue size
- File-backed payload modes (`file`, `image`, `file_diff`) ship with the full display pack in 3.1

## Functions

| Function | Description |
|----------|-------------|
| `console.show(kind, content, metadata)` | Create one inline Console message and publish it to the outbox |
| `console.list(limit, offset, kind, source)` | List retained Console message metadata, oldest-first, paginated |
| `console.read(id)` | Read one retained Console message's full payload by ID |
| `console.clear()` | Clear all retained Console messages for the current instance |

## Key Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `kind` | str | — | Message kind: `text`, `markdown`, `code`, `diff`, `json`, `mermaid`, `yaml`, or `table` |
| `content` | str \| dict \| list | — | Inline content; truncated to the configured inline payload limit rather than erroring |
| `metadata` | dict[str, str] | `None` | Optional user-provided key-value metadata |
| `limit` | int | `100` | `list()` page size, 1 to 500 |
| `offset` | int | `0` | `list()` zero-based page offset |
| `source` | str | `None` | `list()` filter matching the `source` metadata key |
| `id` | str | — | Stable Console message ID returned by `console.show` |

## Configuration

### Required

- No required `tools.console` settings.

### Optional

- `console.max_queue_messages` (default `1000`) — maximum Console messages retained by the MCP producer queue before the oldest are dropped.

### Defaults

- Retained messages are scoped to the current MCP runtime instance and cleared when the instance restarts.

## Examples

### Publish and read back a message

```python
console.show(kind="text", content="build finished", metadata={"source": "ci"})
console.list(limit=10)
console.read(id="<message id from show>")
```

### Clear retained messages

```python
console.clear()
# {cleared: N, message_count: 0, updated_at: "..."}
```

## Notes

- `console.show` always succeeds locally — there is no requirement for a Console consumer to be polling.
- Messages are delivered to a connected onetool-console app over the signed `/api/console/outbox` protocol (see [Console Outbox Protocol](../console-outbox-protocol.md)); this pack only produces messages.
- `console.read` returns an error string (not an exception) when the message has been cleared or has expired past the retention bound.
