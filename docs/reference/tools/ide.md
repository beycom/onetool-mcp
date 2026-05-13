# IDE

Read-only VS Code state retrieval through the local OneTool IDE Bridge extension.

## Highlights

- Connect once to a VS Code workspace id, then call state helpers without repeating the id
- Persists the selected default id in `.onetool/state.yaml` for the current project
- Auto-discovers the active bridge across a small loopback port range
- Authenticates local bridge traffic with `ide/auth.key` under the active OneTool directory
- Retrieves live active-editor, selection, workspace, and viewport state
- Warns on workspace mismatch while still returning absolute paths

## Functions

| Function | Description |
|----------|-------------|
| `ide.connect(id)` | Select, validate, and persist the default VS Code connection |
| `ide.state(id=None)` | Return validated structured IDE state |
| `ide.sel(id=None)` | Return the active selection as plain text |
| `ide.file(id=None)` | Return active document metadata as plain text |
| `ide.editor(id=None)` | Return active editor metadata and visible ranges as plain text |
| `ide.workspace(id=None)` | Return workspace metadata as plain text |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | str | Optional connection id. Overrides the default from `ide.connect(id=...)` for one call. |

## Requires

- `onetool-mcp[dev]`
- The local OneTool IDE Bridge VS Code `.vsix` companion extension

## Configuration

No `tools.ide` settings are required.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.ide.port_start` | int | `58764` | First loopback port scanned for the bridge. |
| `tools.ide.port_count` | int | `10` | Number of ports scanned. Maximum: `10`. |
| `tools.ide.base_url` | str or null | `null` | Explicit loopback URL override for debugging. When set, discovery is skipped. |
| `tools.ide.timeout` | float | `3.0` | Bridge request timeout in seconds. Range: `0.1-30.0`. |

```yaml
tools:
  ide:
    port_start: 58764
    port_count: 10
    timeout: 3.0
```

## Examples

```python
# Select the default IDE connection once
ide.connect(id="onetool-mcp")

# Return the full structured IDE state snapshot
ide.state()

# Override the connection for one call
ide.sel(id="docs")
```

Example `ide.sel()` output:

```text
"selected code" from "/repo/src/app.py"
range: 0:0-2:10
```

For multiple selections, each selected text/range pair is returned as a separate
block using the same format.

Example state shape:

```json
{
  "connection": {
    "id": "onetool-mcp"
  },
  "workspace": {
    "name": "onetool-mcp",
    "workspace_folders": ["/repo"],
    "workspace_file": null
  },
  "active_editor": {
    "visible_ranges": [
      {"start_line": 0, "end_line": 40}
    ],
    "document": {
      "path": "/repo/src/app.py",
      "dirty": false,
      "untitled": false
    }
  },
  "selection": {
    "path": "/repo/src/app.py",
    "ranges": [
      {
        "start_line": 0,
        "start_character": 0,
        "end_line": 2,
        "end_character": 10,
        "text": "selected code"
      }
    ],
    "text": "selected code"
  }
}
```

## Companion Extension

Build the local `.vsix` from the repo:

```bash
just build-ide-vscode
```

Install the generated `.vsix` from `dist/` in VS Code with **Extensions: Install from VSIX...** or:

```bash
code --install-extension dist/onetool-ide-vscode-*.vsix
```

The extension derives its connection id from the workspace name, such as `onetool-mcp`, and shows the chosen port in the status bar. If the default port is busy, it binds the first available port in `onetoolIde.portStart..portStart + portCount - 1`.

Python discovers bridges through authenticated `GET /health` checks and connects to the first bridge whose `connection.id` matches. Duplicate connection ids use first-match semantics.

Set the VS Code `onetoolIde.otDir` setting to the OneTool directory that should
share `ide/auth.key` with the Python pack. If unset, the extension uses
`~/.onetool`.

The extension artifact version is independent from the `onetool-mcp` Python package version. Its base version is `1.0.0`; local builds use generated `1.0.0-dev.<build>` versions so repeated local installs replace earlier local builds without `--force`.

The bridge protocol version is separate from the extension artifact version. Python and TypeScript both require protocol `1`; mismatches fail clearly instead of falling back to older bridge shapes.

## Caveats

- The bridge is read-only and exposes only authenticated `/health` and `/state` endpoints.
- The auth key is stored at `ide/auth.key` under the active OneTool directory and is not stored in `.onetool/state.yaml` or `onetool.yaml`.
- Discovered ports are runtime-only and are not persisted.
- The v1 bridge does not expose terminal state, diagnostics, full file contents, editor mutation, or WebSocket streaming.
- If `active_editor.document.dirty` is `true`, `selection.text` reflects the live editor buffer, but later file reads from disk may be stale for non-selected content.
