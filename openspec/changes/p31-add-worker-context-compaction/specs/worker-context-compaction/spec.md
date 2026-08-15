## ADDED Requirements

### Requirement: Context compaction is evidence-gated

Context compaction SHALL NOT be implemented or enabled until an approved
evidence manifest identifies representative sessions whose concise canonical
Context reaches at least 75% of its configured limit and references a versioned
evaluation set. Passing evaluation SHALL retain 100% of marked essential goals,
success criteria, constraints, decisions, blockers, unresolved questions, and
file references, SHALL invent no facts or references, and SHALL achieve at least
20% median byte reduction across eligible cases.

#### Scenario: Evidence gate is not met
- **WHEN** representative evidence, evaluation coverage, essential-item retention, or measured reduction is below its threshold
- **THEN** compaction SHALL remain deferred and current Context behavior SHALL remain unchanged

#### Scenario: Evidence gate is met
- **WHEN** an approved manifest and evaluation satisfy every threshold
- **THEN** the entry gate SHALL permit implementation against that versioned evidence contract

### Requirement: Compaction is an explicit semantic operation

The worker pack SHALL expose `context_compact` requiring an existing
project-scoped session ID. It SHALL run only on explicit invocation and SHALL NOT
be triggered by Context validation, startup, size rejection, deterministic
normalization, or background maintenance.

#### Scenario: Context is oversized during normal validation
- **WHEN** ordinary Context validation finds an oversized replacement
- **THEN** it SHALL reject that replacement and preserve the last valid Context
- **AND** it SHALL NOT invoke compaction automatically

#### Scenario: User explicitly requests compaction
- **WHEN** `context_compact` receives an existing session ID
- **THEN** it SHALL load the last valid revision and evaluate one complete semantic proposal

### Requirement: The compaction result is bounded and body-free

`context_compact` SHALL return session ID, status (`compacted`,
`approval_required`, `unchanged`, or `failed`), bounded message, base/proposed
byte counts, base/result revisions, removal category counts, and an opaque
approval token only when required. It SHALL NOT return Context, removed text,
model reasoning, prompts, or file contents.

#### Scenario: Proposal requires approval
- **WHEN** a valid proposal contains a material removal
- **THEN** the result SHALL be `approval_required` with only bounded category/count metadata and an opaque token
- **AND** committed Context SHALL remain unchanged

### Requirement: Material removals require bound approval

Removing or materially weakening a goal, success criterion, active constraint,
decision, blocker, unresolved question, or essential file reference SHALL require
a second call with a single-use approval token. The token SHALL expire after 30
minutes and bind the session, base revision, canonical proposal digest, removal
metadata, and evaluation version.

#### Scenario: Valid approval is supplied
- **WHEN** an unexpired token matches the current session, revision, proposal, removals, and evaluation
- **THEN** the runtime SHALL revalidate and atomically commit the complete proposal

#### Scenario: Approval is stale or mismatched
- **WHEN** the token is expired, reused, or does not match any bound value
- **THEN** compaction SHALL fail and preserve the last valid Context

### Requirement: Non-material compaction commits directly

An explicit compaction proposal that removes only exact redundancy or explicitly
resolved/obsolete work SHALL commit without a second approval when all validation
and evaluation checks pass. A proposal without meaningful semantic or byte
reduction SHALL return `unchanged` without incrementing revision.

#### Scenario: Safe reduction passes evaluation
- **WHEN** a proposal contains no material removal and passes every gate
- **THEN** the runtime SHALL atomically commit it as the next complete Context revision

#### Scenario: No meaningful reduction exists
- **WHEN** the proposal is equivalent or does not reduce Context materially
- **THEN** the result SHALL be `unchanged` and the revision SHALL not increment

### Requirement: Every failure preserves the last valid Context

Timeout, model or protocol failure, invalid schema, invalid reference, oversized
proposal, invented content, lost essential content, failed evaluation, stale
revision, invalid approval, or atomic-write failure SHALL leave the last valid
Context unchanged. The compactor SHALL have no project-write, Console, artifact,
or external side-effect tools.

#### Scenario: Proposal loses essential state
- **WHEN** evaluation detects any missing marked essential item or invented fact
- **THEN** compaction SHALL return `failed`
- **AND** no Context revision or other channel SHALL change

#### Scenario: Base revision changes before commit
- **WHEN** committed Context no longer matches the revision bound to the proposal
- **THEN** compaction SHALL fail rather than merge, rebase, or overwrite it

### Requirement: Compaction audit data never copies Context

When compaction is observed, mechanical History SHALL record only request/outcome,
base and result revisions, before/after bytes, evaluation version, and removal
categories/counts. When telemetry is enabled, it SHALL record only aggregate
latency, size reduction, evaluation outcome, and retention score. Neither channel
SHALL record Context text, proposal text, removed content, model reasoning, or
approval-token material.

#### Scenario: Compaction is committed
- **WHEN** a compacted Context becomes the next valid revision
- **THEN** audit channels SHALL contain only the bounded permitted metadata
- **AND** later workers SHALL receive only the complete committed compact Context automatically
