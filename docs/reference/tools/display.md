# Display

Local browser display service for rich, user-visible artifacts.

## Highlights

- Starts lazily on the first `display.*` call and binds to `127.0.0.1`
- Returns a per-running-MCP-process URL from `display.status()`
- Stores messages in memory for the current process only
- Loads payloads lazily in a t3code-derived React timeline UI with well-maintained renderers
- Restricts file previews and open actions to the current workspace root

## Functions

| Function | Description |
|----------|-------------|
| `display.status()` | Start or check the local display service and return the current instance URL and metadata |
| `display.show(...)` | Create one typed display message and return its stable ID |
| `display.read(id)` | Return message metadata, payload references, and bounded preview only |
| `display.focus(id)` | Ask connected display clients to scroll to a message |
| `display.list(...)` | Return a paginated metadata-only message list |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `kind` | str | One of `text`, `markdown`, `code`, `file`, `diff`, `file_diff`, `image`, `json`, `mermaid`, `yaml`, or `table` |
| `content` | str\|dict\|list | Inline payload for text-like, structured, diff, and table messages |
| `path` | str | Workspace-local path for file, image, or file-diff payloads |
| `old_path` / `new_path` | str | Workspace-local paths used to generate a file diff |
| `title` | str | Optional display title for the timeline row |
| `summary` | str | Optional lightweight timeline summary |
| `source` | str | Optional producer or workflow label |
| `expand` | str | Initial browser expansion mode: `auto`, `collapsed`, or `expanded` |
| `id` | str | Stable display message ID returned by `display.show(...)` |
| `limit` / `offset` | int | Pagination controls for `display.list(...)`; `limit` is bounded to 1-500 |

## Requires

None - no secrets or external services required. The browser UI build uses the local `packages/onetool-display-ui` React/TypeScript project during development.

## Configuration

### Required

None - no secrets required.

### Optional

No `tools.display` configuration keys are supported in V1.

```yaml
tools: {}
```

### Defaults

- The display server binds to `127.0.0.1` on an ephemeral local port.
- Display state is in-memory and scoped to the current running MCP process.
- File access is limited to the effective OneTool cwd.

## Supported Kinds

V1 accepts `text`, `markdown`, `code`, `file`, `diff`, `file_diff`, `image`, `json`, `mermaid`, `yaml`, and `table`.

The browser UI uses a t3code-derived React architecture: `@legendapp/list` for the virtualized timeline, `react-markdown` with GFM for markdown, `@pierre/diffs` for diff parsing/rendering, Mermaid for in-browser diagram rendering, `yaml` for YAML formatting, and renderer-specific lazy payload expansion. Large payloads use bounded previews and raw fallbacks.

## Limits

Display keeps memory bounded during long sessions:

- Retains up to 1,000 message metadata records per running MCP process.
- Returns file, inline string, and generated preview text in 64 KiB windows.
- Keeps inline list payload views to the first 500 items.
- Skips generated file diffs when either input file is larger than 1 MiB.
- Keeps up to 100 lazily loaded payload views in the browser cache.
- Renders table previews as a bounded grid of up to 200 rows by 80 columns.

## Security And Persistence

The service is local-only and binds to `127.0.0.1`. Browser and API routes are scoped by the generated MCP instance ID plus an instance token in the returned URL.

File and image payloads must use workspace-local paths. Remote URLs, untrusted `file://` URLs, path traversal outside the workspace, HTML kinds, and terminal/log kinds are rejected.

Display state is in-session only. A OneTool MCP process restart creates fresh display state; there is no V1 persistence guarantee.

## Examples

```python
# Get the current display URL
display.status()

# Show markdown in the display timeline
display.show(kind="markdown", title="Run summary", content="# Result\n\n- passed")

# Start a short payload expanded, collapsed, or in automatic mode
display.show(kind="json", title="Result", content={"ok": True}, expand="expanded")

# Show a workspace file by reference
display.show(kind="file", title="Test output", path="tmp/test-output.txt")

# Show a table with bounded browser rendering
display.show(kind="table", title="Scores", content=[{"name": "Ada", "score": 10}])

# Focus an existing display message
display.focus(id="msg_...")
```

## V1 Exclusions

`display.search(...)`, `display.create(...)`, update tools, and delete tools are not exposed in V1. HTML, remote URL, terminal, and log renderers are also excluded.

## Based on

The display browser UI is based on [t3code](https://github.com/pingdotgg/t3code) by T3 Tools Inc., licensed under MIT.
