# OT Direct

Manage the onetool execution host from within a tool session.

Short alias: `direct`

## Highlights

- Start, stop, and restart the local HTTP execution host
- Check host status and uptime
- Tail the execution host log
- Works alongside the `onetool direct` CLI — both manage the same host

## Functions

| Function | Description |
|----------|-------------|
| `ot_direct.stop(port)` | Stop the running host |
| `ot_direct.status(port)` | Show host status (PID, uptime, log path) |
| `ot_direct.restart(config, port)` | Stop and restart, reusing saved config |
| `ot_direct.logs(port, lines)` | Return the last N lines of the host log |

## Key Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config` | str | `None` | Path to `onetool.yaml`; host starts with no tools if omitted |
| `secrets` | str | `None` | Path to secrets file (optional) |
| `port` | int | MCP-bound host port (or `8765` fallback) | Port the host listens on |
| `lines` | int | `50` | Number of log lines to return (`logs()` only) |

## Configuration

### Required

- No required `tools.ot_direct` settings.

### Optional

- This pack does not define any pack-specific keys under `tools.ot_direct`.
- When called inside an MCP process with `direct.host.enabled: true`, omitted `port` resolves to that process's bound direct-host port.
- Outside MCP auto mode, omitted `port` falls back to `8765`.

## Examples

### Check status and tail the log

```python
# Check uptime
ot_direct.status()

# Stop when done
ot_direct.stop()
```

### Restart after config changes

```python
ot_direct.restart()  # reuses saved config from previous start
```

### Tail the log

```python
ot_direct.logs(lines=20)
```

### Multiple hosts on different ports

```python
ot_direct.start(config='project-a.yaml', port=8765)
ot_direct.start(config='project-b.yaml', port=9000)

ot_direct.status(port=8765)
ot_direct.status(port=9000)

ot_direct.stop(port=9000)
```

## Notes

- `restart()` inherits the saved `config` and `secrets` from the previous CLI `onetool direct start` — pass them explicitly to override; spins up a fresh host if none is running
- The same PID and log files used by `onetool direct start` are used here (`~/.onetool/direct-server-{port}.pid` and `.log`)
- Use `onetool direct` CLI for interactive use; use `ot_direct` when driving the host from within a tool session
