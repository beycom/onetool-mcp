## Context

The foundation separates small semantic Context, Console, Local Changes, Status,
and project-scoped mechanical History. None is suitable for bounded evidence or
intermediate files that should outlive an episode without entering the project or
automatic model input.

Named Context replaces the earlier opaque session as the durable workstream
identity. Artifact ownership must follow that identity without turning the
Context Markdown file into a manifest or making Context archival destructive.

## Goals / Non-Goals

**Goals:**

- Give each named Context an explicit bounded artifact namespace.
- Support safe create, open, list, and delete with stable opaque artifact IDs.
- Define crash recovery, limits, archival retention, and channel isolation.

**Non-Goals:**

- Copying project files, automatic memory, semantic indexing, cross-Context
  search, durable Console replay, or storing artifact bodies in Context or History.
- Context deletion, cascading cleanup, automatic expiry, or project deliverables.

## Decisions

### 1. Store artifacts under named Context ownership

Artifacts live at
`.onetool/state/worker/artifacts/<context>/<artifact-id>/`. Each directory
contains one immutable body and one atomically written strict metadata JSON
object. The owning Context file must exist. Artifact IDs are opaque and collision
checked; the Context name is validated through the foundation contract.

Metadata contains schema version, ID, nonblank label, kind (`text` or `binary`),
validated media type, byte length, SHA-256 digest, creation timestamp, and status
`ready`. Unknown fields are rejected.

Initial limits are 8 MiB per body, 64 artifacts, and 64 MiB total per Context.

Alternative: place artifacts beside project deliverables. Rejected because
non-deliverable evidence would pollute Local Changes and project ownership.

### 2. Add explicit Context-qualified operations

The worker pack adds `artifact_create`, `artifact_open`, `artifact_list`, and
`artifact_delete`. Every operation requires an existing Context name. Create also
requires that Context to be active. Open, list, and delete remain available for an
archived Context so users can inspect or clean retained evidence.

Create accepts content, kind, media type, and label and returns metadata without
echoing the body. Open requires an artifact ID and returns validated body and
metadata. List is metadata-only with stable oldest-first pagination. Delete
requires an existing artifact and never treats an unknown ID as success.

Artifacts are never injected at worker startup. A worker or explicit inspector
must open one deliberately. The Context body may carry a compact artifact ID and
purpose when needed, but never an artifact body or copied metadata.

### 3. Use staged atomic creation and conservative recovery

Create writes to a unique staging directory inside the owning Context artifact
root, flushes and `fsync`s the body, writes and syncs metadata, then atomically
renames the directory to its final ID. It never follows caller-controlled
symlinks.

On store access, stale staging directories are removed. A final directory with
missing or invalid metadata or mismatched body digest/size is quarantined from
list and open and reported as an orphan warning. Recovery never guesses metadata.

### 4. Preserve artifacts when a Context is archived

Context archival changes semantic lifecycle, not artifact retention. Existing
artifacts remain listable, openable, and deletable. New artifact creation fails
while the owner is archived. No context-archive operation recursively deletes
artifact bodies or metadata.

Artifacts persist until explicit artifact deletion. Because the foundation has
no Context delete operation, this change adds no cascading Context cleanup or
time-based expiry.

History may record only owning Context name, artifact ID, and mechanical operation
kind. It never records labels, media types, summaries, paths, or bodies.

## Risks / Trade-offs

- **Binary content consumes storage** → Enforce per-body, count, and total-Context limits.
- **Crashes split body and metadata** → Stage, sync, atomically rename, and quarantine inconsistencies.
- **Archived Contexts retain bytes** → Allow explicit inspection and deletion; do not make archive destructive.
- **Artifact IDs in Context become stale** → Open fails clearly and never rewrites semantic Context.
- **Explicit open adds a tool call** → Preserve the friction because automatic injection becomes hidden memory.

## Migration Plan

Add the Context-qualified store and operations after the named-Context foundation
is synced. Test active and archived ownership, limits, containment, symlinks,
collisions, pagination, deletion, and recovery. After verification, update
`plans/episodic-worker/arch.md`, references, and remove only the artifact-store
section from `plans/episodic-worker/next.md`.

## Open Questions

None.
