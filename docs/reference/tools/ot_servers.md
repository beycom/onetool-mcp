# OT Servers

Runtime proxy server control tools.

Use this pack for state-changing server operations. Discovery remains read-only in `ot.servers()` and `ot.packs()`.

Short alias: `srv`

## Functions

| Function | Description |
|----------|-------------|
| `ot_servers.enable(name)` | Enable a disabled proxy server and connect it |
| `ot_servers.disable(name)` | Disable an enabled proxy server and disconnect it |
| `ot_servers.restart(name)` | Disconnect and reconnect a proxy server |
| `ot_servers.status(name)` | Show detailed status for one proxy server |

## Requires

- No required `tools.ot_servers` settings.
- Servers must exist in `servers.yaml`.

## Examples

```python
# Enable on demand for this session
ot_servers.enable(name="github")

# Inspect one server
ot_servers.status(name="github")

# Reconnect after failure
ot_servers.restart(name="github")

# Disable when done
ot_servers.disable(name="github")
```

## Notes

- All changes are in-memory only and reset when OneTool restarts.
- If you don't know the server name, use `ot.servers()` first.
- After `ot_servers.enable(name="...")`, the server pack is available immediately in the same command block.
