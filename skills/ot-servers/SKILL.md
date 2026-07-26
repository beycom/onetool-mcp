---
name: ot-servers
description: Use when enabling, disabling, restarting, or diagnosing a proxied MCP server managed by OneTool, including recovery from a disconnected browser or external server. Discover status before changing runtime state.
user-invocable: false
---

# OneTool Servers

Use `ot_servers` for state-changing proxy-server operations.

## Availability

Inspect `__ot ot.status()` and `__ot ot.servers()` before using
`__ot ot.packs(pattern='ot_servers', info='min')`. If the pack, configured server, executable, or
credential is missing, stop and offer configuration guidance; do not install, configure, start,
or add credentials without a separate request.

## Workflow

1. Discover the exact server name and current state.
2. Explain the intended state change and preserve unrelated servers.
3. Enable, disable, or restart only the requested server.
4. Recheck status and retry the original operation once.

Avoid reconnect loops and do not rewrite server configuration to recover a runtime failure.
