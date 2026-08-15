## Context

The foundation intentionally stores one small, complete Context snapshot and
asks each worker to author current truth. Semantic compaction is warranted only
if `p24` telemetry shows representative sessions repeatedly approach the byte
limit despite concise replacements and an evaluation can detect loss of
continuation-critical state.

This change depends on synced `p11` and implemented `p24`. Creating these
artifacts does not satisfy the evidence gate or authorize implementation without
the required dataset and measurements.

## Goals / Non-Goals

**Goals:**

- Make compaction an explicit, evaluated semantic operation.
- Preserve every normal Context validation, revision, and atomic-commit boundary.
- Require approval for material removals without exposing Context to the main
  agent or History.
- Preserve the last valid revision on every failure.
- Measure continuation retention as well as bytes.

**Non-Goals:**

- Automatic truncation, deterministic repair, embeddings, retrieval,
  cross-session memory, transcript summarization, indexed History, or implicit
  reinjection of removed content.

## Decisions

### 1. Enforce an evidence and evaluation entry gate

Implementation cannot proceed until an approved evidence manifest identifies
representative sessions where canonical Context reaches at least 75% of its limit
despite concise worker-authored replacements. The manifest references a
versioned evaluation set with expected goals, success criteria, constraints,
decisions, blockers, unresolved questions, and essential file references.

Acceptance requires 100% retention of marked essential items, no invented facts
or references, valid complete Context in every passing case, and at least 20%
median byte reduction across eligible cases. If evidence or evaluation cannot
meet the gate, the change remains deferred and Context behavior is unchanged.

Alternative: compact whenever validation sees an oversized object. Rejected
because semantic judgment is not validation or deterministic repair.

### 2. Expose one explicit two-phase operation

The worker pack adds
`context_compact(session_id, approval_token=None)`. Without a token, it loads the
last valid revision, invokes a tool-free compaction model with only that Context
and fixed instructions, validates the complete proposal, compares it with the
base revision, and runs the evaluation checks.

The bounded result contains session ID, status (`compacted`,
`approval_required`, `unchanged`, or `failed`), bounded message, before/proposed
byte counts, before/after revision, removal categories and counts, and an opaque
approval token only when required. It never contains Context text or removed
content.

Alternative: let ordinary startup compact automatically. Rejected because it
silently changes trusted continuation state and makes failures hard to attribute.

### 3. Require approval for material removal

Removing or materially weakening a goal, success criterion, active constraint,
decision, blocker, unresolved question, or essential reference requires a second
call with an approval token. The token is single-use, expires after 30 minutes,
and binds session, base revision, canonical proposal digest, removal metadata,
and evaluation version. It grants no broader authority.

Non-material deduplication or removal of explicitly resolved/obsolete work may
commit on the first explicit call if every evaluation passes. If no meaningful
reduction exists, return `unchanged` without incrementing revision.

### 4. Reuse complete Context validation and atomic commit

The proposal passes the existing strict schema, reference containment, canonical
rendering, size limit, expected-revision check, and beside-file atomic replacement.
Approval rechecks the current base revision and proposal digest before commit.
Any timeout, model/protocol error, invalid or oversized proposal, hallucinated or
missing essential item, expired token, stale revision, failed evaluation, or
write failure leaves the last valid Context unchanged.

The compactor has no project-write tools, Console publisher, artifact access, or
external side-effect tools. It cannot mutate project files or other channels.

### 5. Keep audit metadata bounded and separate

History may record that explicit compaction was requested, its outcome, base and
result revisions, before/after bytes, evaluation version, and removal categories
and counts. It never records Context, proposal, removed text, model reasoning, or
approval-token material. Telemetry may aggregate size reduction, latency,
evaluation pass/fail, and retention score under its existing privacy contract.

## Risks / Trade-offs

- **A model removes essential state** → Require a versioned evaluation, strict
  category checks, and approval for material removals.
- **Approval metadata leaks Context** → Expose only category/count metadata and an
  opaque bound token, never excerpts.
- **Evaluation overfits examples** → Require representative manifests and retain
  a holdout set before default adoption changes.
- **Compaction races with a worker commit** → Bind to the loaded revision and
  reject stale approval or commit.
- **Size improves while continuation worsens** → Gate on perfect essential-item
  retention and hallucination checks before measuring reduction.

## Migration Plan

First collect and approve the evidence manifest and evaluation set. Then add the
tool-free proposer, comparison, approval tokens, validation/commit integration,
audit metadata, telemetry, and failure tests. Update `arch.md` and remove only
`Semantic Compaction or Summarization` from `next.md` after the exit gate passes.

## Open Questions

None. If the entry thresholds are not met, the prescribed outcome is to defer
implementation rather than weaken them silently.
