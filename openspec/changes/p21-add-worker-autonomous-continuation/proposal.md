## Why

Some workers can continue productively after a model turn without user input,
but the foundation always terminates after one turn. A bounded internal
continuation loop can improve completion while preserving one synchronous
episode and one worker.

## What Changes

- Add an internal worker-authored `continue` outcome that is never exposed as a
  public `worker.run` status.
- Reuse the same worker thread only for bounded autonomous turns inside the
  current `worker.run` call.
- Supply Chat and committed Context only on the first turn; use a fixed
  continuation instruction and ephemeral same-thread state thereafter.
- Enforce a strict maximum turn count and one total episode deadline.
- Commit Context only on terminal `completed` or `needs_input`, record the final
  turn count mechanically, and never replay earlier turns after failure.
- Preserve the fresh-episode boundary after `needs_input`, serialization,
  non-recursion, and the original execution authority.

## Capabilities

### New Capabilities

- `worker-autonomous-continuation`: Bounded same-thread continuation within one
  synchronous worker episode, including limits and terminal behavior.

### Modified Capabilities

- `serve-configuration`: Add strict maximum-turn and total-episode-deadline
  settings for worker continuation.

## Impact

- Depends on the synced `p11-update-episodic-worker-foundation` contract.
- Affects the worker terminal schema, app-server turn loop, worker configuration,
  History turn counts, tests, skill guidance, and reference documentation.
- Does not add a public continue/resume API, user-driven thread resumption,
  retries, concurrency, recursion, or authority escalation.
