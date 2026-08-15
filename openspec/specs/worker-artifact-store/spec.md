# Worker Artifact Store Specification

## Purpose

Defines explicit named-Context-owned artifact creation, access, retention,
recovery, bounds, and channel isolation for worker-generated evidence and
intermediate files that are not project deliverables or semantic Context.

## Requirements

### Requirement: Artifacts are owned by a named Context

Artifact state SHALL live at
`.onetool/state/worker/artifacts/<context>/<artifact-id>/` under the effective
project. Every artifact operation SHALL require an existing valid Context name
and SHALL remain contained within that Context's artifact root.

Each final artifact directory SHALL contain exactly one immutable body and one
strict metadata object with schema version, opaque artifact ID, label, kind,
media type, byte length, SHA-256 digest, creation timestamp, and ready status.

#### Scenario: Artifact is created for an active Context
- **WHEN** create receives valid content and an existing active Context
- **THEN** it SHALL return bounded metadata with a new opaque artifact ID
- **AND** it SHALL not return the artifact body

#### Scenario: Context is unavailable
- **WHEN** an operation names an unknown or invalid Context
- **THEN** it SHALL fail without finding, creating, or modifying an artifact root

### Requirement: Artifact operations are explicit and Context-qualified

The worker pack SHALL expose `artifact_create`, `artifact_open`, `artifact_list`,
and `artifact_delete`, each requiring `context`. Create SHALL require content,
kind, media type, and label. Open and delete SHALL also require an artifact ID.
List SHALL support bounded stable oldest-first pagination and SHALL return only
metadata.

No artifact SHALL become automatic worker input. A caller SHALL explicitly open
an artifact to receive its validated body.

#### Scenario: Artifact is explicitly opened
- **WHEN** open receives a ready artifact ID and its owning Context
- **THEN** it SHALL validate metadata, digest, and size before returning the body

#### Scenario: Artifact is merely referenced by Context
- **WHEN** a worker starts with a Context body containing an artifact ID
- **THEN** the runtime SHALL NOT inject or open the artifact automatically

### Requirement: Artifact storage is bounded

The store SHALL enforce a maximum decoded body size of 8 MiB, maximum 64 ready
artifacts, and maximum 64 MiB total ready body bytes per Context. It SHALL check
limits before promoting staged content and SHALL reject unknown metadata fields,
invalid kinds, media types, encodings, lengths, and digests.

#### Scenario: Per-Context total would be exceeded
- **WHEN** creating a valid body would exceed any Context artifact limit
- **THEN** create SHALL fail without publishing a ready artifact

### Requirement: Artifact creation is atomic and recoverable

Create SHALL write and sync body and metadata in a unique staging directory under
the target Context root, then atomically rename it to the final opaque ID. It
SHALL reject symlinks and paths escaping the owned root.

Store access SHALL remove stale staging directories. A final directory with
missing or invalid metadata or mismatched body SHALL be quarantined from open and
list and reported as an orphan warning. Recovery SHALL NOT fabricate metadata or
return unvalidated bytes.

#### Scenario: Creation is interrupted before promotion
- **WHEN** a crash leaves a stale staging directory
- **THEN** later store access SHALL remove it
- **AND** list SHALL never report it as ready

#### Scenario: Final artifact is inconsistent
- **WHEN** body size or digest differs from metadata
- **THEN** open and list SHALL exclude it and report an orphan warning

### Requirement: Archived Contexts retain inspectable artifacts

Artifact creation SHALL require an active owning Context. Context archival SHALL
preserve all artifact bodies and metadata. Open, list, and delete SHALL remain
available when the owning Context is archived.

#### Scenario: Artifact creation targets archived Context
- **WHEN** create names an archived Context
- **THEN** it SHALL fail without staging content

#### Scenario: Existing artifact owner is archived
- **WHEN** an active Context with ready artifacts is archived
- **THEN** its artifacts SHALL remain listable, openable, and explicitly deletable

### Requirement: Artifact deletion is explicit

Delete SHALL require an existing artifact ID in its owning Context and SHALL
remove its body and metadata as one store operation. Unknown IDs SHALL fail rather
than report idempotent success. No Context archival operation SHALL cascade into
artifact deletion, and V1 SHALL NOT expire artifacts by time.

#### Scenario: Existing artifact is deleted
- **WHEN** delete receives an existing artifact ID and owning Context
- **THEN** later list and open SHALL not return it

#### Scenario: Unknown artifact is deleted
- **WHEN** delete receives an unknown ID
- **THEN** it SHALL fail without modifying other artifacts

### Requirement: Artifact channels remain isolated

Artifact bodies and metadata SHALL NOT be injected automatically, copied into
Console, Context files, Status, telemetry, or mechanical History. Project
deliverables SHALL remain normal Local Changes rather than artifact copies.

History MAY record only Context name, artifact ID, and mechanical operation kind.
It SHALL NOT record label, media type, summary, path, metadata object, or body.

#### Scenario: History records an artifact operation
- **WHEN** History observes artifact creation, open, or deletion
- **THEN** it SHALL contain only bounded identity and operation metadata
- **AND** it SHALL contain no artifact content or descriptive metadata
