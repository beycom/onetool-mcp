## Why

The foundation's mechanical History cannot answer performance and capacity
questions without becoming an unsafe memory channel. A distinct, privacy-bounded
telemetry contract is needed before evaluating runtime reuse or Context
compaction.

## What Changes

- Define worker metrics by name, unit, source, aggregation, consumer, retention,
  privacy classification, and availability semantics.
- Record provider-reported tokens when reliable, first-event and total latency,
  turn count, terminal status, Context bytes/revisions/validation failures, and
  rejected sizes.
- Separate cold/warm runtime and per-turn/whole-episode measurements.
- Store and expose telemetry independently from History, Context, Console, Chat,
  and Status; it is never automatic agent input.
- Exclude prompts, Console bodies, file contents, diffs, tool results, secrets,
  and sensitive high-cardinality labels by default.
- Mark unavailable and estimated measurements explicitly and prohibit treating
  Context size as total model input.

## Capabilities

### New Capabilities

- `worker-advanced-telemetry`: Privacy-bounded episodic-worker measurement,
  retention, availability, and channel-isolation behavior.

### Modified Capabilities

- `serve-configuration`: Add strict worker-telemetry enablement, retention, and
  record-limit controls.

## Impact

- Depends on the synced `p11-update-episodic-worker-foundation` contract and
  provides the evidence contract required by `p31`.
- Affects worker lifecycle instrumentation, telemetry storage/query surfaces,
  privacy controls, tests, and documentation.
- Does not capture transcripts, prompts, Console content, semantic memory, or
  agent-authored History, and does not silently alter worker behavior.
