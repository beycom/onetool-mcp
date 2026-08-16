# Semantic Context Compaction

## Status

Optional, evidence-gated, and non-normative. Draft OpenSpec change
`p31-add-worker-context-compaction` must not be implemented merely because its
artifacts exist.

## Opportunity

Over long-lived Contexts, workers may repeatedly preserve facts that are valid
but no longer useful. Mechanical validation cannot determine relevance,
supersession, or the smallest adequate explanation.

## Possible design

- Treat compaction as an explicit semantic operation, never deterministic
  validation, repair, or silent truncation.
- Compare proposed compact state with prior state and surface important removals
  for audit or approval.
- Consider a dedicated model call only if normal workers cannot keep complete
  replacements concise.
- Preserve the last valid Context on every failure.
- Measure continuation quality, not only bytes or tokens.

## Adoption criteria

- Representative long-lived Contexts reach the configured limit despite concise
  worker-authored replacements.
- A versioned evaluation detects loss of goals, constraints, decisions, blockers,
  unresolved questions, and essential references.
- Compaction demonstrates useful reduction without losing required state or
  inventing facts.
