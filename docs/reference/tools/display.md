# Display

Bounded MCP-side producer for rich, user-visible artifacts consumed by the separate OneTool Console App.

Short alias: `d`

## Highlights

- Creates display messages in the current OneTool MCP process without starting a browser service or returning a browser URL.
- Publishes `display.message.created` events to the signed Console outbox when `display.show(...)` creates a message.
- Keeps a bounded MCP-side producer queue controlled by `display.max_queue_messages`.
- Keeps MCP-local introspection through `display.status`, `display.list`, `display.read`, `display.focus`, and `display.clear`.
- Leaves browser read models, file previews, rich rendering, and disposable UI cache ownership to `onetool-console`.

## Functions

| Function | Description |
|----------|-------------|
| `display.status()` | Return current display instance status, MCP instance ID, message count, and timestamps |
| `display.show(...)` | Create one typed display message and return its path, kind, stable ID, and metadata |
| `display.show_clip(...)` | Resolve a clipboard image or existing clipboard file path into a path-backed display message |
| `display.read(id)` | Return message metadata and bounded preview only |
| `display.focus(id)` | Queue a local focus request for MCP-local display clients |
| `display.clear()` | Clear messages from the current MCP display instance |
| `display.list(...)` | Return a paginated metadata-only message list |
| `display.seed_mock_messages(...)` | TEST ONLY: seed representative fixture messages |

## Console App

Launch the browser-facing OneTool Console App from the separate TypeScript project:

```bash
onetool-console serve --ot-dir ~/.onetool
```

`onetool-mcp` must have `direct.host.enabled: true` for Console ingestion. Console reads `~/.onetool/auth/console-outbox.key` by default and consumes:

- `GET /api/console/outbox`
- `POST /api/console/outbox/ack`

The Console outbox key is scoped only to those endpoints. It does not authorize `/run`.

## Configuration

```yaml
direct:
  host:
    enabled: true
    port: 8765

display:
  max_queue_messages: 1000
```

## Payload Modes

Display events use Console protocol payload modes:

- `inline` for text, markdown, code, diff, JSON, YAML, Mermaid, and table content.
- `file_ref` for local file and image references.
- `file_diff_ref` for local diff files or generated diffs with structured old/new paths.

## Limits

- Message IDs are stable 12-character lowercase hex strings.
- Preview text is bounded to 64 KiB windows.
- Inline list payload views are bounded to the first 500 items.
- Generated file diffs are skipped when either input is larger than 1 MiB.
- MCP producer retention is FIFO bounded by `display.max_queue_messages`, capped by the implementation maximum.

## Security And Persistence

File payloads must use workspace-local paths. Image payloads may also reference OneTool-owned session image paths produced by clipboard image loading. Remote URLs, untrusted `file://` URLs, path traversal outside allowed roots, HTML kinds, and terminal/log kinds are rejected.

Display producer state is in-session only. A OneTool MCP process restart creates fresh display state. Console owns browser-facing state after it ingests outbox events.

## Examples

```python
display.status()
display.show(kind="markdown", metadata={"title": "Run summary"}, content="# Result\n\n- passed")
display.show(kind="json", metadata={"title": "Result", "task": "smoke"}, content={"ok": True})
display.show(kind="file", metadata={"title": "Test output"}, path="tmp/test-output.txt")
display.show(kind="table", metadata={"title": "Scores"}, content=[{"name": "Ada", "score": 10}])
display.show_clip()
display.focus(id="a1b2c3d4e5f6")
display.clear()
```
