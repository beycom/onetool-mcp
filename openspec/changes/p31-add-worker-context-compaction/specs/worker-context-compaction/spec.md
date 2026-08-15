## ADDED Requirements

### Requirement: Context compaction is evidence-gated

Compaction SHALL NOT be implemented or enabled until an approved evidence
manifest identifies representative active named Context files whose concise
complete encoding reaches at least 75% of the configured limit and references a
versioned evaluation set. Passing evaluation SHALL retain every marked essential
goal, criterion, constraint, decision, blocker, question, and reference, invent
no facts or references, and achieve at least 20% median byte reduction.

Evidence and telemetry SHALL NOT contain Context names, descriptions, tags, or
semantic bodies.

#### Scenario: Evidence gate is not met
- **WHEN** evidence, coverage, essential retention, or reduction is below threshold
- **THEN** compaction SHALL remain deferred and Context behavior SHALL remain unchanged

### Requirement: Compaction explicitly targets one active named Context

The worker pack SHALL expose `context_compact` requiring an existing active
Context name. It SHALL run only on explicit invocation and SHALL NOT be triggered
by validation, startup, size rejection, normalization, archival, or maintenance.

#### Scenario: User explicitly requests compaction
- **WHEN** compaction receives an existing active Context name
- **THEN** it SHALL load the last valid revision and digest
- **AND** it SHALL evaluate one complete proposed semantic body

#### Scenario: Context is archived
- **WHEN** compaction receives an archived Context name
- **THEN** it SHALL fail without invoking a model or changing the file

### Requirement: The compaction result is bounded and body-free

Compaction SHALL return Context name, status (`compacted`, `approval_required`,
`unchanged`, or `failed`), bounded message, base/proposed byte counts,
base/result revisions, removal category counts, and an opaque approval token only
when required. It SHALL NOT return the semantic body, description, tags, removed
text, reasoning, prompts, or file contents.

#### Scenario: Proposal requires approval
- **WHEN** a valid proposal contains material removal
- **THEN** the result SHALL be `approval_required` with bounded categories/counts and an opaque token
- **AND** committed Context SHALL remain unchanged

### Requirement: Material removals require bound approval

Removing or weakening protected continuation state SHALL require a second call
with a single-use token. The token SHALL expire after 30 minutes and bind Context
name, base revision, base file digest, proposal digest, removal metadata, and
evaluation version.

#### Scenario: Valid approval is supplied
- **WHEN** an unexpired token matches the active Context, revision, digests, removals, and evaluation
- **THEN** the runtime SHALL revalidate and atomically commit the complete proposal

#### Scenario: Approval is stale or mismatched
- **WHEN** the token is expired, reused, archived, or mismatches any bound value
- **THEN** compaction SHALL fail and preserve the last valid Context file

### Requirement: Non-material compaction commits directly

A proposal removing only exact redundancy or explicitly resolved work SHALL
commit without approval when all validation and evaluation checks pass. A
proposal without meaningful semantic or byte reduction SHALL return `unchanged`
without incrementing revision.

#### Scenario: Safe reduction passes evaluation
- **WHEN** a proposal contains no material removal and passes every gate
- **THEN** the runtime SHALL preserve frontmatter metadata and atomically commit the body as the next revision

### Requirement: Every failure preserves the last valid Context

Timeout, model/protocol failure, invalid Markdown or reference, oversize,
invented or lost state, failed evaluation, archival, stale revision or digest,
invalid approval, or write failure SHALL leave the last valid Context unchanged.
The compactor SHALL have no project-write, Console, artifact, or external
side-effect tools.

#### Scenario: Manual edit occurs before commit
- **WHEN** current revision or digest differs from the proposal base
- **THEN** compaction SHALL fail rather than merge, rebase, or overwrite the edit

### Requirement: Compaction audit data never copies Context

Mechanical History SHALL record only Context name, outcome, revisions, bytes,
evaluation version, and removal category counts. Telemetry SHALL record only
identity-free aggregate latency, reduction, evaluation outcome, and retention.
Neither channel SHALL record body text, description, tags, proposal text,
removed content, reasoning, or token material.

#### Scenario: Compaction is committed
- **WHEN** a compacted body becomes the next valid Context revision
- **THEN** audit channels SHALL contain only permitted bounded metadata
- **AND** later workers using that name SHALL receive only the complete compacted body
