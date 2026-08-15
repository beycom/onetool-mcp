## Why

Compaction is justified only when representative telemetry shows that concise
named Context files approach their configured limit and an evaluation can detect
loss of continuation-critical information. When that gate is met, compaction
must be an explicit semantic operation rather than hidden truncation or repair.

## What Changes

- Gate implementation on representative `p24` evidence and a versioned evaluation
  set for goals, constraints, decisions, blockers, questions, and references.
- Add explicit compaction for one existing active named Context.
- Compare a compact Markdown body with the current revision and expose bounded
  audit metadata about important removals without copying Context into History or
  Status.
- Validate and atomically commit the complete compacted body through the named-
  Context revision and digest path while preserving frontmatter metadata.
- Preserve the last valid Context on timeout, model failure, invalid or oversized
  output, archival, concurrent edit, or failed evaluation.

## Capabilities

### New Capabilities

- `worker-context-compaction`: Evidence-gated explicit semantic compaction for a
  named Context, approval metadata, failure preservation, and evaluation.

### Modified Capabilities

None.

## Impact

- Depends on the synced named-Context `p11` foundation and completed `p24`
  telemetry evidence.
- Affects Context lifecycle, model invocation, audit metadata, evaluation assets,
  tests, skill guidance, and documentation.
- Does not add silent truncation, embeddings, retrieval, cross-Context memory,
  transcript summarization, indexed History, or implicit reinjection of removals.
