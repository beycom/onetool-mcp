## Context

Foundation History records bounded mechanical episode facts for audit and
recovery. It intentionally cannot answer token, latency, Context pressure, or
warm-runtime questions, and expanding it would create a second memory channel.
Telemetry therefore needs independent collection, storage, retention, and query
semantics before it can support `p31` evaluation.

This change depends on synced `p11`. It can consume `p21` turn counts and `p23`
runtime mode when those changes are present, but neither is required to store a
one-turn cold episode.

## Goals / Non-Goals

**Goals:**

- Define a small stable metric catalog with units and availability metadata.
- Separate per-turn observations from whole-episode aggregates.
- Bound retention and provide explicit aggregate query and clear operations.
- Exclude sensitive bodies and prevent telemetry from becoming agent input.

**Non-Goals:**

- Prompts, transcripts, Console retention, file contents, diffs, tool results,
  secrets, semantic memory, or agent-authored History.
- Silent policy changes or claims based on unavailable provider measurements.

## Decisions

### 1. Use a fixed versioned metric catalog

Version 1 records whole-episode duration, first-event latency, turn count,
terminal status, runtime start mode, Context bytes before/after, Context revisions
before/after, validation-failure count, and rejected Context bytes. Per turn it
records duration and provider-reported input, output, and cached tokens.

Each optional measurement has `value`, fixed unit, and availability of `measured`,
`estimated`, or `unavailable`. Unavailable values have no numeric value or
fabricated zero. Context bytes are explicitly labeled as persisted Context size,
not total prompt or model input.

### 2. Store telemetry outside every semantic and audit channel

Telemetry uses a project-scoped, append-oriented store under a dedicated
`episodic-telemetry/` state root. Records use opaque random observation IDs and
low-cardinality dimensions only: schema version, timestamps, status, turn ordinal,
runtime mode, model family when explicitly safe, and metric values. Session IDs,
prompts, paths, labels, error text, Console identifiers/bodies, Context bodies,
file contents, diffs, tool results, credentials, and secrets are prohibited.

Telemetry is never supplied automatically to a worker or main agent and is never
copied into History, Context, Console, Chat, or Status.

Alternative: add metrics to History. Rejected because retention, consumers, and
privacy differ and History must stay a small mechanical journal.

### 3. Make collection opt-in and retention bounded

`tools.worker.telemetry.enabled` defaults to `false`.
`retention_days` defaults to 30 and accepts 1–365; `max_records` defaults to
10,000 and accepts 100–1,000,000. Collection prunes oldest records when either
bound is crossed. Disabling collection stops new writes but does not silently
delete existing records; explicit clear owns deletion.

### 4. Expose only explicit bounded aggregate access

The worker pack adds `telemetry_query` and `telemetry_clear`. Query accepts a
bounded UTC interval and optional low-cardinality status/runtime-mode filters and
returns counts, availability counts, min/max/mean, and fixed histogram buckets.
It never returns raw observation rows or high-cardinality labels. Clear requires
an explicit interval and reports the deleted record count.

This access is never invoked automatically by orchestration. `p31` evidence
collection is an explicit project activity.

### 5. Fail telemetry independently

Collection and pruning occur after the episode outcome is known. A telemetry
write failure emits a bounded operational warning but does not alter worker,
Console, Context, Local Changes, Status, or History outcomes. Query detects a
malformed store and returns a diagnostic rather than fabricating aggregates.

## Risks / Trade-offs

- **Metrics can become identifying** → Use low-cardinality dimensions, no Context
  names, descriptions, tags, paths, or reconstructable identities, opt-in
  collection, and bounded local retention.
- **Provider token fields differ** → Record provenance and availability; never
  infer measured tokens from Context bytes.
- **Append storage can grow** → Enforce age and count bounds during collection and
  provide explicit clear.
- **Telemetry failure obscures evidence** → Report unavailability explicitly and
  never alter the product outcome.

## Migration Plan

Add disabled-by-default configuration, catalog models, collection hooks, bounded
storage, query/clear operations, and privacy tests. Update
`plans/episodic-worker/arch.md` and remove only `Advanced Telemetry` from
`plans/episodic-worker/next.md` after verification. The resulting catalog and
queries become the required evidence source for `p31`.

## Open Questions

None.
