# Retry and Recovery Policies

## Status

Optional and non-normative. Current episodes are never replayed automatically.

## Opportunity

Transient app-server or MCP failures may occur before a worker performs an
external side effect.

## Possible design

- Classify failures into provably pre-execution transport failures and
  potentially side-effecting failures.
- Permit bounded retry only for the former, with a new thread and the same
  committed Context revision.
- Never infer idempotency from missing output; require runtime evidence that
  substantive execution did not begin.
- Record retry reason and attempt count in the terminal result.

## Adoption criteria

- Transport-only failures are frequent enough to harm usability.
- The runtime can prove that a retry cannot duplicate project or external state.
