# Console

Publish messages from tool calls to a connected onetool-console app via the signed Console outbox.

## Highlights

- `console.display` routes verbose or visual tool output to the Console and returns a one-line digest receipt — keeping large results out of the model context
- Path-based display publishes file references (`file_ref`, `file_diff_ref`): only the path crosses the wire; the Console reads the file on demand, at any size
- Inline kinds: text, markdown, code, diff, json, mermaid, yaml, or table; file kinds: file, image
- Oversized inline content is truncated to a bounded preview rather than erroring
- Publishing never requires a Console consumer to be connected — the outbox is retention-only when nothing polls it
- Retained messages are scoped to the current MCP instance and bounded by a configurable queue size

## Functions

| Function | Description |
|----------|-------------|
| `console.display(content, path, old_path, new_path, kind, title, metadata)` | Publish tool output or a file reference; return a one-line digest receipt |
| `console.show(kind, content, metadata)` | Create one inline Console message and publish it to the outbox |
| `console.list(limit, offset, kind, source)` | List retained Console message metadata, oldest-first, paginated |
| `console.read(id)` | Read one retained Console message's full payload by ID |
| `console.clear()` | Clear all retained Console messages for the current instance |

## Key Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | any (positional in `display`) | — | Evaluated value to publish; kind inferred (`table` for uniform lists of dicts, `json` for dicts/lists, `markdown`/`text` for strings) unless `kind` is set |
| `path` | str | `None` | Absolute path to display as a live file reference; kind inferred from extension (`image`, `markdown`, `diff`, `code`, `json`, `yaml`, else `file`) |
| `old_path` / `new_path` | str | `None` | Absolute paths for a file diff reference (`kind` defaults to `diff`) |
| `kind` | str | inferred | Message kind: `text`, `markdown`, `code`, `diff`, `json`, `mermaid`, `yaml`, `table`, `file`, or `image` |
| `title` | str | `None` | `display()` shorthand for `metadata["title"]` |
| `metadata` | dict[str, str] | `None` | Optional user-provided key-value metadata |
| `limit` | int | `100` | `list()` page size, 1 to 500 |
| `offset` | int | `0` | `list()` zero-based page offset |
| `source` | str | `None` | `list()` filter matching the `source` metadata key |
| `id` | str | — | Stable Console message ID returned by `console.show`/receipts |

## Configuration

### Required

- No required `tools.console` settings.

### Optional

- `console.max_queue_messages` (default `1000`) — maximum Console messages retained by the MCP producer queue before the oldest are dropped.

### Defaults

- Retained messages are scoped to the current MCP runtime instance and cleared when the instance restarts.
- Instance snapshots publish `allowed_roots` (the file pack's `allowed_dirs` plus the working directory); file references outside these roots fall back to bounded inline publication with `metadata.fallback = "outside-allowed-roots"`.

## Examples

### Route verbose output to the Console instead of context

```python
console.display(ground.search(q="mcp features 2026", count=20))
# -> 'console[a3f2c19e04d1] table: 20 items (title, url, snippet) — top: "..."'
console.display(ot.servers())
```

The receipt is what enters the model context (~40 tokens instead of the full
result). Read the full payload back later with `console.read(id)`.

### Display-then-slice: human sees everything, context pays for a fragment

```python
r = webfetch.fetch("https://example.com/changelog")
console.display(r, kind="markdown", title="changelog")
r[:500]  # keep only the lead in context
```

### Display a file or diagram by path (no content crosses the wire)

```python
console.display(path="/repo/diagrams/architecture.svg")   # renders as an image
console.display(path="/repo/src/app.py")                  # code with preview
console.display(old_path="/repo/tmp/before.py", new_path="/repo/src/app.py")
```

File references are **live views**: the Console reads the file at view time.
To record content as-it-was (e.g. a localhist diff for audit), display the
diff text as an inline value instead of paths.

### Publish and read back a message

```python
console.show(kind="text", content="build finished", metadata={"source": "ci"})
console.list(limit=10)
console.read(id="<message id from show or a display receipt>")
```

### Clear retained messages

```python
console.clear()
# {cleared: N, message_count: 0, updated_at: "..."}
```

## Notes

- `console.display` and `console.show` always succeed locally — there is no requirement for a Console consumer to be polling.
- When `direct.host.enabled` is false, nothing can ever poll the outbox, so `console.display` returns the bounded preview text (prefixed with a note) instead of a receipt — content is never silently dropped.
- Messages are delivered to a connected onetool-console app over the signed `/api/console/outbox` protocol (see [Console Outbox Protocol](../console-outbox-protocol.md)); this pack only produces messages.
- `console.read` returns an error string (not an exception) when the message has been cleared or has expired past the retention bound.
