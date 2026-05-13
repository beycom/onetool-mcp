# OneTool IDE Bridge

VS Code IDE integration for [OneTool MCP](https://github.com/beycom/onetool-mcp).

This extension exposes read-only VS Code state to the OneTool `ide` tool pack through an authenticated local loopback bridge. It lets an MCP agent understand the workspace and active editor without requiring file-path guessing or manual copy/paste.

## What It Provides

- A workspace-derived IDE connection id.
- Read-only workspace metadata, including folders and `.code-workspace` file.
- Active editor document metadata, dirty state, and visible ranges.
- Current selection ranges and selected text.
- Auto-port binding on `127.0.0.1`.
- Authenticated `/health` and `/state` bridge endpoints.

The bridge is intentionally read-only. It does not edit files, run terminal commands, or mutate your editor state.

## Requirements

- OneTool MCP with the `[dev]` extra installed.
- VS Code 1.85 or newer.

Install OneTool:

```bash
uv tool install 'onetool-mcp[dev]'
onetool init --config ~/.onetool
```

See the full project docs at [onetool.beycom.online](https://onetool.beycom.online).

## Usage

The status bar shows the active connection id and selected port:

```text
OneTool IDE: your-workspace-name :58764
```

In OneTool, connect to that id and read IDE state:

```python
ide.connect(id="your-workspace-name")
ide.state()
```

Useful focused helpers return plain text:

```python
ide.sel()
ide.file()
ide.editor()
ide.workspace()
ide.paths()
```

To copy the connection id, run **OneTool IDE: Show or Copy Connection ID** or click the status bar item.

## Configuration

The extension exposes these VS Code settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `onetoolIde.portStart` | `58764` | First loopback HTTP port to try for the bridge. |
| `onetoolIde.portCount` | `10` | Number of loopback HTTP ports to try. |

The OneTool side uses the same defaults:

```yaml
tools:
  ide:
    port_start: 58764
    port_count: 10
    timeout: 3.0
```

Set `tools.ide.base_url` only as an explicit debug override. When it is set, OneTool skips port discovery.

## Security

The extension and Python pack share `~/.onetool/ide/auth.key`. Requests and responses are signed with HMAC-SHA256, the key is never sent over HTTP, and replayed request nonces are rejected.

## Links

- [OneTool MCP repository](https://github.com/beycom/onetool-mcp)
- [OneTool documentation](https://onetool.beycom.online)
- [IDE tool reference](https://onetool.beycom.online/reference/tools/ide/)
- [Issues](https://github.com/beycom/onetool-mcp/issues)

## License

GPL-3.0. See the OneTool MCP repository license for details.
