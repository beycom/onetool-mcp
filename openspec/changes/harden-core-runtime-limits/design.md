## Context

`execute_command()` currently wraps `asyncio.to_thread()` in `wait_for()`. The
waiter can time out or be cancelled, but Python cannot terminate the running
thread, and the default executor queue provides no OneTool-specific admission
bound. The Direct API similarly authenticates exact body bytes only after
`request.body()` has buffered the complete request.

Both boundaries need limits that remain correct across the MCP event loop and
the Direct API's separate event-loop thread.

## Goals / Non-Goals

**Goals:**

- Bound all admitted OneTool in-process executions, including queued and
  detached post-timeout work.
- Keep accounting attached to the actual concurrent future rather than to the
  caller coroutine.
- Define deterministic server shutdown for admitted thread work.
- Bound request-body consumption before authentication while preserving exact
  accepted bytes for HMAC verification.

**Non-Goals:**

- Hard termination or process isolation for Python execution.
- Reintroducing the removed worker/subprocess execution route.
- Adding configurable capacities, route limits, aliases, or migration paths.
- Changing valid Direct API request or response payloads.

## Decisions

### Use a dedicated eight-worker executor with admission before submission

A process-global controller owns a `ThreadPoolExecutor(max_workers=8)` and a
thread-safe set of its admitted `concurrent.futures.Future` objects. Submission
and set insertion happen under one lock. If eight futures are already admitted,
the next call receives an immediate execution-capacity error and no future is
submitted.

The future, not its awaiting coroutine, owns the slot. A completion callback
observes any exception and removes the future only after the thread actually
finishes. This works across the MCP and Direct API event loops and prevents a
timeout or cancellation from releasing capacity early.

Alternatives rejected:

- An `asyncio.Semaphore` is loop-affine and cannot safely coordinate the two
  event loops.
- `asyncio.to_thread()` uses the shared default executor and does not expose a
  stable cross-loop accounting object.
- Queueing overflow would allow callers and queued work to accumulate; immediate
  rejection keeps total admitted work equal to the numeric bound.

### Treat timeout as a soft caller deadline

Each caller wraps its admitted concurrent future for its own event loop and
waits under `asyncio.shield()`. Timeout or caller cancellation stops only that
wait. The future continues, remains accounted for, and may still perform side
effects.

### Close admission and drain admitted work during server shutdown

MCP lifespan startup opens admission. Shutdown first stops new admission and
awaits every admitted future without cancelling it, before proxy and other
runtime resources are closed. Because threads cannot be terminated safely, a
truly hung job can delay shutdown; this is preferable to reporting clean
shutdown while work still mutates runtime resources.

### Stream every Direct API body through one bounded reader

The shared reader accepts an explicit route limit, treats `Content-Length` as an
optional early-rejection hint only, and iterates `request.stream()`. It returns
the exact accumulated bytes at or below the limit and raises immediately after
the first chunk that crosses it. It never requests the remainder.

`/run` retains its 1,000,000-byte limit. `/health`, `/ready`, and
`/api/console/outbox` each use a 65,536-byte control-route limit. Valid,
non-negative `Content-Length` above the applicable limit rejects before the
first receive; absent, invalid, negative, or dishonest values cannot bypass
stream accounting.

Each route authenticates the exact returned byte sequence before performing
command, readiness, or outbox work. Oversize responses use the route's existing
response-signing key.

## Risks / Trade-offs

- **A timed-out command can still cause side effects** → The public spec and
  timeout message state this explicitly, and the job remains bounded/accounted.
- **Eight blocked commands can reject otherwise healthy work** → Immediate
  rejection is deterministic and prevents hidden queue growth; completion frees
  capacity automatically.
- **Shutdown can wait indefinitely for a truly hung thread** → This is the only
  honest non-isolated policy; hard termination requires a separate architecture.
- **An overflow crossing chunk can exceed the limit in transient transport
  memory** → The reader retains none of that chunk and stops requesting messages
  immediately afterward.
