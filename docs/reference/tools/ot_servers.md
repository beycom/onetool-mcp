# OT Servers

Runtime proxy server control tools.

Use this pack for state-changing server operations. Discovery remains read-only in `ot.servers()` and `ot.packs()`.

Short alias: `srv`

## Functions

| Function | Description |
|----------|-------------|
| `ot_servers.enable(name)` | Enable a disabled proxy server and connect it |
| `ot_servers.disable(name)` | Disable an enabled proxy server and disconnect it |
| `ot_servers.restart(name)` | Reconnect a proxy server with its current on-disk config |
| `ot_servers.status(name)` | Show detailed status for one proxy server |

## Requires

- No required `tools.ot_servers` settings.
- Servers must exist in `servers.yaml`.

## Examples

```python
# Enable on demand for this session
ot_servers.enable(name="playwright")

# Inspect one server
ot_servers.status(name="playwright")

# Reconnect after failure, or to apply a servers.yaml edit
ot_servers.restart(name="playwright")

# Disable when done
ot_servers.disable(name="playwright")
```

## Notes

- Enable/disable changes are in-memory only and reset when OneTool restarts.
- `restart(name=...)` re-reads that server's entry from `servers.yaml`, so edits to `command`, `args`, `env`, `timeout`, or `tool_prefix` take effect on restart (use `ot.reload()` to reload everything).
- If you don't know the server name, use `ot.servers()` first.
- After `ot_servers.enable(name="...")`, the server pack is available immediately in the same command block.
