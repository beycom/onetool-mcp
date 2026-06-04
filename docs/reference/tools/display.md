# Display

Local admin dashboard route for rich, user-visible artifacts.

Short alias: `d`

## Highlights

- Starts a Starlette-backed local admin service lazily on the first `display.*` call and binds to `127.0.0.1`
- Returns a compact high-entropy per-running-MCP-process browser URL from `display.status()`
- Keeps bounded hot and cold message windows for the current process, with cold records cached under project-local display state
- Loads payloads lazily in a t3code-derived React timeline UI with fixed row previews, a side inspector, content-aware markdown, code, diff, JSON/YAML tree/source, Mermaid render/source, table, and file renderers
- Loads the latest timeline page on browser startup in high-volume sessions while preserving oldest-to-newest visual order within the loaded page
- Restricts file previews and open actions to the current workspace root

## Functions

| Function | Description |
|----------|-------------|
| `display.status()` | Start or check the local display service and return the current instance URL and metadata |
| `display.show(...)` | Create one typed display message and return its path, kind, stable ID, URL, and metadata |
| `display.show_clip(...)` | Resolve a clipboard image or existing clipboard file path into a path-backed display message |
| `display.read(id)` | Return message metadata, payload references, and bounded preview only |
| `display.focus(id)` | Ask connected display clients to scroll to a message |
| `display.clear()` | Clear all messages from the current display instance timeline |
| `display.list(...)` | Return a paginated metadata-only message list |
| `display.seed_mock_messages(...)` | TEST ONLY: seed representative UI fixture messages for every V1 kind |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `kind` | str | One of `text`, `markdown`, `code`, `file`, `diff`, `file_diff`, `image`, `json`, `mermaid`, `yaml`, or `table` |
| `content` | str\|dict\|list | Inline payload for text-like, structured, diff, and table messages |
| `path` | str | Workspace-local path for file, image, or file-diff payloads |
| `old_path` / `new_path` | str | Workspace-local paths used to generate a file diff |
| `metadata` | dict[str, str] | Optional key-value metadata; it does not control rendering, validation, or routing |
| `id` | str | Stable 12-character lowercase hex display message ID returned by `display.show(...)` |
| `limit` / `offset` | int | Pagination controls for `display.list(...)`; `limit` must be 1-500 and `offset` must be 0 or greater |

## Requires

None - no secrets or external services required. The browser UI build uses the local `packages/onetool-display-ui` Vite + React + TypeScript project during development.

## Configuration

### Required

None - no secrets required.

### Optional

No `tools.display` configuration keys are supported in V1.

```yaml
tools: {}
```

### Defaults

- The admin server binds to `127.0.0.1` on an ephemeral local port.
- Display hot state is in-memory and scoped to the current running MCP process; a bounded cold message window may be cached under the project-local display state directory.
- File access is limited to the effective OneTool cwd.

## Supported Kinds

V1 accepts `text`, `markdown`, `code`, `file`, `diff`, `file_diff`, `image`, `json`, `mermaid`, `yaml`, and `table`.

The browser UI uses the local admin frontend foundation: Vite, React, TypeScript, TanStack Router, TanStack Query, TanStack Table, Radix-compatible primitives, Tailwind as the styling foundation, Recharts availability, and lucide icons. Display keeps its t3code-derived architecture: `@legendapp/list` for the virtualized timeline, `react-markdown` with GFM for markdown, `@pierre/diffs` for code/diff rendering, Mermaid for in-browser diagram rendering, `yaml` for YAML parsing, and renderer-specific lazy payload loading. File messages route through markdown, JSON, YAML, code, or raw text viewers based on metadata and extension hints, with a compact filename header above file-backed payloads and full paths kept in message info/actions instead of footer metadata. Message info actions are available from timeline rows and the side panel, and show core message fields, payload references, and caller-provided key-value metadata except `summary`. File-backed source renderers do not duplicate the filename inside the payload body, and footer message IDs show the full 12-character display ID. Browser-rendered timestamps use `HH:mm, dd-Mon` format, such as `23:01, 03-Jun`. Large payloads use bounded row previews, side-panel inspection, bounded previews, and raw fallbacks; table previews render directly as a bounded grid without row/column truncation status text. Structured JSON/YAML tree/source toggles size to their content instead of stretching across the message body. Text messages render as plain content by default, not as code-style raw blocks. Display does not generate default `summary` metadata. The Line Wrapping setting applies to plain text, raw text, code/source, structured source, and diff renderers; when disabled, long text/source lines remain horizontally scrollable instead of clipping. Inline timeline rows expose copy content, message info, and side-panel open actions; openable file-backed timeline rows add an open action after those controls. File side-panel rows expose the overflow menu, message info, and open-file. Secondary actions such as path copy and rich/raw view controls live behind a text-labeled overflow menu. The side panel uses the same compact message layout as timeline rows, with floating actions and no separate inspector header band. Recent messages are loaded first in the browser, a scroll-to-bottom control appears when the user is away from the latest messages, and renderer failures are isolated to the affected message card or inspector payload.

Generated `file_diff` messages keep old and new source paths as separate payload metadata fields. File-backed diff payloads use `path` for the referenced diff file.

## Limits

Display keeps memory bounded during long sessions:

- Keeps only the hot message window in memory while allowing a bounded cold message window to be read from project-local display cache state.
- Returns file, inline string, and generated preview text in 64 KiB windows.
- Keeps inline list payload views to the first 500 items.
- Skips generated file diffs when either input file is larger than 1 MiB.
- Keeps up to 100 lazily loaded payload views in the browser cache.
- Renders table previews as a bounded grid of up to 200 rows by 80 columns.
- Keeps the browser inspector panel resizable locally, with long payloads using the panel height rather than nested vertical scroll caps.

## Security And Persistence

The service is local-only and binds to `127.0.0.1`. `display.status()` returns a compact high-entropy browser route such as `/display/0821a4b75d1e8c31`; the browser page bootstraps full API credentials for that page. Display API routes live under `/api/display/instances/{instance_id}/...` and remain scoped by the generated MCP instance ID plus an instance token. The admin service also exposes `/api/admin/health`.

File payloads must use workspace-local paths. Image payloads may also reference OneTool-owned session image paths produced by clipboard image loading. Remote URLs, untrusted `file://` URLs, path traversal outside allowed roots, HTML kinds, and terminal/log kinds are rejected.

Display state is in-session only. A OneTool MCP process restart creates fresh display state; cached cold-message records are an internal memory-pressure detail, not durable storage or a V1 recovery guarantee.

## Examples

```python
# Get the current display URL
display.status()

# Show markdown in the display timeline
display.show(kind="markdown", metadata={"title": "Run summary"}, content="# Result\n\n- passed")

# Add arbitrary metadata without affecting rendering
display.show(kind="json", metadata={"title": "Result", "task": "smoke"}, content={"ok": True})

# Show a workspace file by reference
display.show(kind="file", metadata={"title": "Test output"}, path="tmp/test-output.txt")

# Show a table with bounded browser rendering
display.show(kind="table", metadata={"title": "Scores"}, content=[{"name": "Ada", "score": 10}])

# Show a clipboard image or existing clipboard file path
display.show_clip()

# Focus an existing display message
display.focus(id="a1b2c3d4e5f6")

# Clear the current display timeline
display.clear()

# TEST ONLY: seed UI fixture messages during display/admin development
display.seed_mock_messages()
```

## V1 Exclusions

`display.search(...)`, `display.create(...)`, update tools, and individual message delete tools are not exposed in V1. HTML, remote URL, terminal, and log renderers are also excluded.

## Based on

The display browser UI is based on [t3code](https://github.com/pingdotgg/t3code) by T3 Tools Inc., licensed under MIT.
