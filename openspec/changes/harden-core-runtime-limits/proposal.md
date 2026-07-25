## Why

In-process execution timeouts currently stop only the caller while allowing
unbounded detached thread work, and Direct API routes can buffer oversized
unauthenticated request bodies before rejecting them. The public contracts need
explicit resource bounds that match what the runtime can actually enforce.

## What Changes

- Define soft-timeout semantics: caller timeout does not terminate the underlying
  Python thread and post-timeout side effects may still occur.
- Admit at most eight in-process execution jobs globally, including work whose
  caller has timed out or been cancelled, and reject overflow immediately.
- Keep admitted work counted until its underlying thread finishes and make server
  shutdown stop admission and wait for all admitted work.
- Incrementally consume every Direct API request body using explicit per-route
  limits, stopping after the first chunk that crosses the applicable limit.
- Preserve exact accepted bytes for HMAC verification and return the existing
  signed `413` overload response before route work on oversized requests.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `serve-run-tool`: Reconcile soft timeout, bounded admission, accounting, and
  shutdown behavior for in-process execution.
- `direct-api`: Apply bounded incremental request-body consumption to every
  authenticated Direct API route.

## Impact

The executor runner and MCP lifespan gain bounded admission and shutdown
accounting. Direct API health, readiness, run, and Console outbox routes share an
incremental body reader. Focused executor, server-lifecycle, and raw-ASGI request
tests are updated; no configuration keys or dependencies are added.
