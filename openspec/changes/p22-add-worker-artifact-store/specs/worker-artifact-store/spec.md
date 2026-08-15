## ADDED Requirements

### Requirement: Artifacts are session-owned and bounded

Each artifact SHALL belong to one existing episodic session under the current
project-state root and SHALL have an opaque stable ID, immutable body, and strict
versioned metadata. The store SHALL allow at most 8 MiB per decoded body, 64
artifacts, and 64 MiB of artifact bodies per session.

#### Scenario: Artifact is within all limits
- **WHEN** a create request targets an existing session and remains within body, count, and total limits
- **THEN** the store SHALL create one artifact and return body-free metadata with its stable ID

#### Scenario: A limit would be exceeded
- **WHEN** decoded content, artifact count, or session bytes would exceed its limit
- **THEN** creation SHALL fail without committing a body or metadata entry

### Requirement: Artifact metadata and media are strictly validated

Metadata SHALL contain exactly schema version, ID, nonblank label, `text` or
`binary` kind, valid media type, decoded byte length, SHA-256 digest, UTC creation
time, and `ready` status. Text bodies SHALL be valid UTF-8. Unknown fields,
unsupported media, blank labels, and metadata/body mismatches SHALL be rejected.

#### Scenario: Metadata matches the body
- **WHEN** a stored body has the declared kind, size, and digest
- **THEN** open SHALL return the validated metadata and body

#### Scenario: Metadata or body is inconsistent
- **WHEN** metadata is invalid or its size or digest differs from the body
- **THEN** open SHALL fail and list SHALL exclude that artifact as an orphan

### Requirement: Artifact access is explicit

The worker pack SHALL expose `artifact_create`, `artifact_open`, `artifact_list`,
and `artifact_delete`. Each operation SHALL require an existing project-scoped
session ID. Artifacts and metadata SHALL NOT be injected automatically into
worker startup, Context, Chat, Console, Status, or the main conversation.

#### Scenario: Later worker starts
- **WHEN** a session contains artifacts and a fresh worker starts
- **THEN** the worker SHALL receive no artifact body or metadata automatically
- **AND** it SHALL use an explicit artifact operation to access one

#### Scenario: Artifacts are listed
- **WHEN** a caller lists artifacts with a valid page limit and cursor
- **THEN** it SHALL receive stable oldest-first body-free metadata and a bounded next cursor

#### Scenario: Unknown session or artifact is supplied
- **WHEN** an operation references a session or artifact outside the current project-scoped store
- **THEN** it SHALL fail rather than create, infer, or alias the missing value

### Requirement: Artifact paths are contained and symlink-safe

All staging, metadata, and body paths SHALL resolve within the owning session's
artifact root. The store SHALL reject absolute paths, traversal, caller-controlled
filenames, symlink components, and collision with an existing artifact ID.

#### Scenario: Path escapes through traversal or symlink
- **WHEN** an artifact operation would resolve outside the session artifact root
- **THEN** the operation SHALL fail before reading or writing the target

### Requirement: Creation and recovery preserve complete artifacts

Creation SHALL durably write body and metadata in a unique in-root staging
directory and atomically promote the complete directory. Recovery SHALL remove
stale staging directories and quarantine inconsistent final directories without
inventing metadata or exposing bodies.

#### Scenario: Creation is interrupted before promotion
- **WHEN** the process stops with only a staging directory
- **THEN** the artifact SHALL not appear in list or open
- **AND** later recovery SHALL remove the stale staging directory

#### Scenario: Final artifact is orphaned
- **WHEN** a final artifact directory lacks valid matching metadata and body
- **THEN** recovery SHALL exclude it and report an orphan warning

### Requirement: Deletion and session cleanup own retention

Artifacts SHALL persist until explicit deletion or explicit cleanup of their
owning session. Deletion SHALL remove the artifact body and metadata; session
cleanup SHALL remove every artifact owned by that session. V1 SHALL NOT expire
artifacts by time.

#### Scenario: Artifact is deleted
- **WHEN** delete receives an existing artifact ID in its owning session
- **THEN** later list and open SHALL not return that artifact

#### Scenario: Owning session is cleaned up
- **WHEN** explicit session cleanup succeeds
- **THEN** all artifact bodies, metadata, staging directories, and quarantined orphans for that session SHALL be removed

### Requirement: Artifact content remains isolated from other channels

Artifact bodies, labels, media types, summaries, and filesystem paths SHALL NOT
be copied into mechanical History. Project deliverables SHALL remain normal Local
Changes, and user-facing output SHALL remain Console content.

#### Scenario: Artifact operation is observed
- **WHEN** History records an artifact operation
- **THEN** it SHALL record only the opaque artifact ID and mechanical operation kind
- **AND** it SHALL contain no artifact body, label, media type, summary, or path
