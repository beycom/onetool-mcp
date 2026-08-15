## Context

The foundation starts a new Codex app-server process for each episode so process,
transport, and thread lifetime coincide. Only the thread must be conversationally
fresh. Process and eligible MCP transport setup can be reused if measurements
show startup is material and reuse is partitioned by every security boundary.

This change depends on synced `p11`; it does not depend on autonomous
continuation and does not permit concurrent `worker.run` calls.

## Goals / Non-Goals

**Goals:**

- Reuse safe process and transport infrastructure between serialized episodes.
- Preserve a new and deleted thread for every episode, including after input.
- Partition reusable state by project, authority, and effective MCP configuration.
- Provide health, idle expiry, shutdown, reconnect, and stale-process recovery.
- Measure cold and warm startup separately.

**Non-Goals:**

- Thread or transcript pooling, shared preloaded Context, concurrency, changed
  permissions, automatic work replay, or hidden lifecycle failures.

## Decisions

### 1. Gate reuse on a cold-start benchmark

Before enabling reuse by default, capture a repeatable cold-start benchmark over
representative projects and report process initialization, first protocol event,
thread start, and total pre-turn latency. Implementation proceeds only if process
or transport setup is a material share and the warm path has a documented target.

Alternative: implement pooling before measurement. Rejected because added
lifecycle state is unjustified without a demonstrated latency bottleneck.

### 2. Cache one runtime per exact isolation key

The runtime manager's key is a canonical project root plus a deterministic digest
of the effective approval/sandbox/network/writable-root envelope and effective
configured MCP server/credential identities. The digest contains no secret values.
Different keys never share a process or transport session.

The serialized worker lock means at most one cached runtime is leased. A key
change retires the previous runtime rather than migrating its live state.

Alternative: key only by project. Rejected because permission and MCP changes
could broaden authority across episodes.

### 3. Reuse processes and eligible transports, never threads

Initialization and capability preflight occur once per healthy cached process.
Every episode still calls `thread/start`, performs its bounded turn lifecycle,
and calls `thread/delete` before the lease returns to idle. No thread ID,
messages, developer input, Chat, or Context survives in reusable state.

Only transports whose protocol and server lifecycle explicitly support reuse are
eligible. Ineligible transports reconnect per episode inside the warm process.

### 4. Use explicit health and lifecycle state

The manager has `starting`, `ready`, `leased`, `idle`, `unhealthy`, and `closed`
states. Before reuse it performs a bounded protocol health check. Failed health,
unexpected process exit, protocol desynchronization, or stale ownership closes
the runtime and permits one cold replacement only before substantive execution.
Failure after a worker turn starts returns through normal episode failure and is
never replayed.

Idle runtimes expire after `tools.worker.warm_runtime_idle_seconds`, default 300.
Server shutdown closes transports, terminates the process with a bounded grace
period, and force-terminates only that resolved child if needed.

### 5. Make warm reuse opt-in until evidence is verified

`tools.worker.warm_runtime_enabled` is a strict boolean defaulting to `false`.
Disabled mode preserves one process per episode. Operational records distinguish
`cold` and `warm`, measure initialization and pre-turn duration, and exclude
prompts, Context, Console, paths beyond the project partition digest, and secrets.
`p24` may later consume the measurements through its separate telemetry channel.

## Risks / Trade-offs

- **Cached credentials become stale** → Include credential identity in the key,
  health-check before lease, and reconnect rather than replay.
- **A process leaks state between threads** → Reuse only documented process and
  transport state; assert fresh/deleted thread IDs on every episode.
- **Shutdown leaves a child process** → Use owned process handles, bounded graceful
  close, and verified targeted termination.
- **Warm mode hides cold-path regressions** → Keep separate measurements and test
  both modes.

## Migration Plan

Land the benchmark first, add the disabled-by-default manager and configuration,
then verify project/policy switching, expiry, crash, reconnect, cleanup, and
shutdown. Enable only after the measured benefit and isolation gate pass. Update
`plans/episodic-worker/arch.md` and remove only `Warm Runtime and Connection
Reuse` from `plans/episodic-worker/next.md`.

## Open Questions

None.
