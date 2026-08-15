## Why

Compaction is justified only when representative telemetry shows that concise
whole-state Context approaches its configured limit and an evaluation can detect
loss of continuation-critical information. When that gate is met, compaction
must be an explicit semantic operation rather than hidden truncation or repair.

## What Changes

- Gate implementation on representative `p24` evidence and an evaluation set for
  goals, constraints, decisions, blockers, unresolved questions, and essential
  file references.
- Add an explicit semantic compaction operation with a defined trigger,
  initiator, model/runtime boundary, and approval policy for material removals.
- Compare proposed compact Context with the last valid revision and expose
  bounded audit metadata about important removals without copying Context into
  History or Status.
- Validate and atomically commit the complete compacted object through the
  existing Context schema and revision path.
- Preserve the last valid Context on timeout, model failure, invalid or oversized
  output, or failed evaluation, and measure continuation quality as well as size.

## Capabilities

### New Capabilities

- `worker-context-compaction`: Evidence-gated explicit semantic Context
  compaction, review metadata, validation, failure preservation, and evaluation.

### Modified Capabilities


## Impact

- Depends on the synced `p11` foundation and completed `p24` telemetry evidence.
- Affects Context lifecycle, model invocation, audit metadata, evaluation assets,
  tests, skill guidance, and documentation.
- Does not add silent truncation, embeddings, retrieval, cross-session memory,
  transcript summarization, indexed History, or implicit reinjection of removed
  material.
