## Context

The named-Context foundation stores one small complete Markdown body for each
project-local workstream and asks workers to author current truth. Semantic
compaction is warranted only if privacy-bounded `p24` telemetry shows
representative Contexts repeatedly approach the byte limit despite concise
replacements and an evaluation detects loss of continuation-critical state.

This change depends on synced `p11` and implemented `p24`. Creating these
artifacts does not satisfy the evidence gate or authorize implementation.

## Goals / Non-Goals

**Goals:**

- Make compaction an explicit evaluated operation for one active Context name.
- Preserve frontmatter metadata and normal revision, digest, validation, and
  atomic-commit boundaries.
- Require approval for material removals without exposing semantic bodies.
- Preserve the last valid file on every failure.
- Measure continuation retention as well as bytes.

**Non-Goals:**

- Automatic truncation, deterministic repair, embeddings, retrieval,
  cross-Context memory, transcript summarization, indexed History, archived-
  Context compaction, or implicit reinjection of removed content.

## Decisions

### 1. Enforce an evidence and evaluation entry gate

Implementation cannot proceed until an approved manifest identifies
representative active Context files where the complete encoded file reaches at
least 75% of its limit despite concise worker-authored bodies. The manifest
references a versioned evaluation set with expected goals, criteria, constraints,
decisions, blockers, questions, and essential project-contained references.

Acceptance requires 100% retention of marked essential items, no invented facts
or references, valid bounded Markdown in every passing case, and at least 20%
median byte reduction across eligible cases. Context names, descriptions, and
tags remain excluded from telemetry and the evidence manifest.

### 2. Expose one explicit two-phase operation

The worker pack adds `context_compact(context, approval_token=None)`. Without a
token, it requires an existing active Context, loads its last valid revision and
digest, invokes a tool-free model with only the semantic body and fixed
instructions, validates one complete proposal body, compares it with the base,
and runs the evaluation.

The bounded result contains Context name, status (`compacted`,
`approval_required`, `unchanged`, or `failed`), message, before/proposed bytes,
before/after revision, removal category counts, and an opaque approval token only
when required. It never contains body text, frontmatter description or tags, or
removed content.

### 3. Require approval for material removal

Removing or weakening a goal, criterion, active constraint, decision, blocker,
question, or essential reference requires a second call with a single-use token.
The token expires after 30 minutes and binds Context name, base revision, base
digest, proposal digest, removal metadata, and evaluation version. It grants no
broader authority.

Non-material deduplication or removal of explicitly resolved work may commit on
the first explicit call if every evaluation passes. No meaningful reduction
returns `unchanged` without revision increment.

### 4. Reuse named-Context validation and atomic commit

The proposal passes UTF-8, Markdown, reference containment, canonical frontmatter,
complete-file size, expected revision/digest, and beside-file atomic replacement.
Description, tags, name, and active status are preserved unchanged. Approval
rechecks current status, revision, base digest, and proposal digest before commit.

Timeout, model/protocol error, invalid or oversized body, lost or invented item,
archival, expired token, stale revision/digest, failed evaluation, or write
failure leaves the last valid file unchanged.

The compactor has no project-write tools, Console publisher, artifact access, or
external side-effect tools.

### 5. Keep audit metadata bounded and separate

History may record Context name, request/outcome, revisions, bytes,
evaluation version, and removal category counts. It never records the semantic
body, description, tags, proposal, removed text, reasoning, or token material.
Telemetry may aggregate reduction, latency, evaluation outcome, and retention
score without Context identity under the `p24` privacy contract.

## Risks / Trade-offs

- **A model removes essential state** → Require evaluation and approval.
- **Approval metadata leaks state** → Expose categories/counts and opaque token only.
- **Evidence identifies Contexts** → Exclude names and frontmatter metadata.
- **Compaction races with worker or manual edit** → Bind revision and digest.
- **Context is archived during approval** → Recheck active status before commit.
- **Bytes improve while continuation worsens** → Require perfect essential retention first.

## Migration Plan

Collect and approve evidence and evaluation, then add the tool-free proposer,
comparison, approval tokens, named-Context validation/commit integration, audit
metadata, telemetry, and failure tests. Update `plans/episodic-worker/arch.md`
and remove only the compaction section from `plans/episodic-worker/next.md`
after the exit gate passes.

## Open Questions

None. If thresholds are not met, implementation remains deferred.
