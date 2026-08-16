# Durable Console Retention and Replay

## Status

Optional and non-normative. The existing Console channel is sufficient for
testing the episodic-worker concept.

## Opportunity

The Console outbox keeps user-facing worker content out of the main agent's
conversation, but message bodies are scoped to one runtime instance. Users may
eventually need to reconnect, replay, or retain selected results across runtime
restarts.

## Possible design

- Extend the existing Console protocol and body store rather than adding a
  `console.md`, event log, or second transport.
- Associate retained messages with Context and episode identifiers using
  runtime-owned metadata while keeping bodies out of `history.jsonl`.
- Add explicit retention, deletion, reconnect, and replay controls.
- Preserve bounded receipts and never inject retained bodies into later workers
  or the main agent automatically.
- If streaming is added, define incomplete-message markers and crash recovery
  without changing terminal Status semantics.

## Adoption criteria

- Users demonstrably need Console results after the producing runtime exits.
- Retention and deletion can be specified without turning Console into History,
  Context, or long-term memory.
