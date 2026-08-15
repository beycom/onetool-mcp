## Context

The `p11` foundation treats one `worker.run` call as one episode with one fresh
thread and one model turn. A Codex turn already supports multiple tool calls, so
continuation is reserved for cases where the worker reaches the end of a turn,
requires no user input, and can name concrete remaining work.

This change depends on the synced `p11` channel contract. It must not change
public terminal statuses, automatic-input rules, execution authority, or the
fresh episode required after user input.

## Goals / Non-Goals

**Goals:**

- Permit a small number of autonomous turns on the same thread within one call.
- Bound the entire episode by turn count and one monotonic deadline.
- Commit Context once, only at a public terminal outcome.
- Preserve deterministic cleanup, History, Status, and non-replay behavior.

**Non-Goals:**

- A public continue/resume API or user-driven thread resumption.
- Parallel workers, recursion, queues, retries, Context checkpoints, or authority
  escalation.
- Using continuation instead of normal within-turn tool use.

## Decisions

### 1. Add one internal-only continuation variant

The strict worker output becomes a discriminated union. `completed` and
`needs_input` retain bounded Status plus optional complete Context. Internal
`continue` contains only a nonblank bounded `next_action`; it contains no Context,
Console body, public message, changed permissions, or user question.

The adapter consumes `continue` and never returns it through `worker.run`.

Alternative: expose `continue` publicly and require another main-agent call.
Rejected because that would make orchestration stateful and expose thread reuse.

### 2. Reuse one thread only within the current episode

The first turn receives the current Chat request and committed Context. Each
later turn uses the same thread and execution policy and receives one fixed
developer-controlled continuation instruction plus `next_action`. Chat and
Context are not repeated. Same-thread messages remain ephemeral and disappear
when the thread is deleted.

`needs_input` is always terminal: commit valid Context, delete the thread, finish
observation and History, and return the question. Its answer starts a fresh
episode and fresh thread.

### 3. Apply one count limit and one total deadline

`tools.worker.max_turns` defaults to `3` and accepts strict integers from 1 to 10.
`tools.worker.episode_timeout_seconds` defaults to `900` and accepts strict
integers from 1 to 3600. The deadline begins before the first turn and is never
reset. Each app-server request receives only the remaining time.

A `continue` at the turn limit or deadline returns public `failed` with bounded
classification `turn_limit` or `episode_timeout`. No returned Context is
committed. Project and external effects from earlier turns are preserved and not
replayed.

Alternative: one timeout per turn. Rejected because total work could then grow
without an episode bound.

### 4. Finalize once

Context commit/preservation, thread deletion, final Local Changes observation,
History append, and Status return run only after a public terminal result or a
loop failure. History records the actual positive turn count. Console and Local
Changes created during any turn belong to the one episode.

Later-turn protocol, process, validation, cancellation, or timeout failures map
through the existing failure lifecycle. Earlier turns are neither replayed nor
rolled back.

## Risks / Trade-offs

- **Workers overuse continuation** → Require concrete `next_action`, low defaults,
  and fixed instructions that prefer normal tool use within a turn.
- **Long episodes delay user control** → Enforce one monotonic total deadline and
  keep caller interruption active across the loop.
- **Later failure follows side effects** → Preserve mechanical observations and
  explicitly prohibit replay or rollback claims.
- **Same-thread state is less isolated** → Permit it only within one synchronous
  episode; always delete the thread at terminal handling.

## Migration Plan

Add configuration with defaults matching the bounded behavior, extend the
internal schema and adapter loop, then update tests, skill guidance, History turn
count coverage, `arch.md`, and reference documentation. Remove only `Bounded
Autonomous Same-Thread Continuation` from `next.md` after verification.

## Open Questions

None.
