## Why

Starting a new app-server process and reconnecting transports for every episode
may dominate worker latency even though conversational isolation requires only a
fresh thread. Measured, policy-partitioned runtime reuse can reduce that cost
without weakening the episodic boundary.

## What Changes

- Measure and document cold-start latency before selecting reusable state.
- Reuse only app-server process and eligible transport/connection infrastructure;
  create and delete a fresh Codex thread for every episode.
- Partition warm state by project and the exact effective execution/security
  envelope so credentials, permissions, caches, and MCP sessions cannot cross
  boundaries.
- Add health checking, idle expiry, reconnect, clean shutdown, stale-process
  recovery, and distinct cold/warm measurements.
- Surface lifecycle failures without automatically replaying worker work.

## Capabilities

### New Capabilities

- `worker-warm-runtime`: Safe process and transport reuse with fresh-thread,
  project, authority, health, expiry, recovery, and measurement boundaries.

### Modified Capabilities

- `serve-configuration`: Add strict warm-runtime enablement and idle-expiry
  settings.

## Impact

- Depends on the synced `p11-update-episodic-worker-foundation` contract.
- Affects the app-server adapter lifecycle, transport ownership, worker
  configuration, shutdown handling, instrumentation, tests, and documentation.
- Does not pool or resume worker threads, preload shared Context, enable
  concurrency, change permissions, or replay failed work.
