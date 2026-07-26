<!-- Generated from skills/ot-runtime/SKILL.md; do not edit. -->
# OneTool Runtime

## Capability boundary

This skill owns ongoing operation of the root OneTool process after setup. Use `ot-ref` for call
syntax and tool discovery, `ot-setup` for installation or persistent configuration changes, and
`ot-mcp-proxy` for outbound MCP server configuration and connection lifecycle.

### Establish the runtime boundary

Identify whether the caller uses MCP stdio, root streamable HTTP, or the authenticated Direct API
attached to an already running OneTool process. Do not confuse the root runtime with a proxied MCP
server listed by `ot.servers()`.

Root HTTP has no built-in authentication. Prefer loopback binding; require an explicitly secured
deployment boundary before recommending any non-loopback exposure. Direct API authentication does
not make the root MCP HTTP transport authenticated.

## Workflow

### Observe before acting

1. Start with `ot.status()` for readiness and degraded components.
2. Use `ot.debug()` only for the narrower diagnostic detail needed.
3. Inspect `ot.stats()` and configured telemetry for measured behavior, not guessed causes.
4. Retrieve a stored large output with `ot.result(...)`; use service logs at the resolved runtime
   location when status is insufficient.

### Operate

Use the current documented CLI/host command for the selected transport. `onetool direct run`
targets an already running Direct host; do not claim removed Direct lifecycle or discovery
subcommands. After a reload, verify readiness and the exact affected pack or server rather than
assuming all state refreshed.

## Safety and side effects

Starting/stopping a host, binding a port, changing log/telemetry settings, reloading config, and
retrieving sensitive logs/results are operational side effects. Root Streamable HTTP has no
built-in authentication; keep loopback or require a separately secured deployment. Direct API is
HMAC-authenticated, loopback-bound, size-limited, and owned by the already-running MCP process.
The current Direct CLI exposes `onetool direct run`, not lifecycle/list/search/log commands.

## Verification and recovery

Classify bind, config, dependency, worker, proxy, and result-handle failures separately. Attempt one
bounded corrective action, then surface the exact sanitized error. Hand persistent config,
installation, or secrets changes to `ot-setup`, and named outbound server recovery to
`ot-mcp-proxy`; do not loop reloads or reconnect unrelated services. Verify status/readiness, the
affected pack/server, log/result access, and measured stats after the action.
