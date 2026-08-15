## Context

The foundation distinguishes small semantic Context, user-facing Console, normal
project Local Changes, bounded Status, and mechanical History. None is suitable
for session-scoped evidence or intermediate files that should outlive one episode
without becoming a project deliverable or automatic model input.

This change depends on the synced `p11` storage and channel boundaries.

## Goals / Non-Goals

**Goals:**

- Give each episodic session an explicit, bounded artifact namespace.
- Support safe create, open, list, and delete operations with stable IDs.
- Define crash recovery, retention, cleanup, and channel isolation.

**Non-Goals:**

- Copying project files, automatic memory, semantic indexing, cross-session
  sharing, durable Console replay, or storing bodies in Context or History.
- Replacing normal project deliverables or the Console data plane.

## Decisions

### 1. Store artifacts beside session Context

Artifacts live under
`episodic-context/<session-id>/artifacts/<artifact-id>/` in the same
project-scoped state root. Each directory contains one immutable body and one
atomically written strict metadata JSON object. IDs are opaque and collision
checked. Metadata contains schema version, ID, nonblank label, kind (`text` or
`binary`), validated media type, byte length, SHA-256 digest, creation timestamp,
and status (`ready`). Unknown fields are rejected.

The initial limits are 8 MiB per body, 64 artifacts, and 64 MiB total per
session. Limits apply to decoded bytes and are checked before durable promotion.

Alternative: place artifacts in the project. Rejected because non-deliverable
state would pollute Local Changes and project ownership.

### 2. Add explicit worker artifact operations

The worker pack adds `artifact_create`, `artifact_open`, `artifact_list`, and
`artifact_delete`. Every call requires an existing project-scoped `session_id`.
Create accepts content, kind, media type, and label; it returns metadata without
echoing the body. Open requires an artifact ID and returns its validated body and
metadata. List is metadata-only with stable oldest-first pagination. Delete is
idempotent only for an existing artifact ID; an unknown ID fails through current
validation rather than pretending success.

Artifacts are never injected at worker startup. A worker or explicit inspector
must call open. Context may carry a compact artifact ID and purpose in an existing
reference field only when needed for continuation; it never carries metadata or
body copies.

Alternative: expose the artifact directory as ordinary file paths. Rejected
because it bypasses containment, metadata, size, and lifecycle enforcement.

### 3. Use staged atomic creation and conservative recovery

Create writes to a unique staging directory inside the session artifact root,
flushes and `fsync`s the body, writes and syncs metadata, then atomically renames
the directory to its final ID. It never follows caller-controlled symlinks.

On store access, stale staging directories are removed. A final directory missing
valid metadata or whose body digest/size does not match is quarantined from list
and open and reported as an orphan warning. Recovery never guesses metadata or
returns unvalidated content.

### 4. Tie retention to the episodic session

Artifacts persist until explicit artifact deletion or session cleanup. Deleting
an artifact removes metadata and body as one store operation; failure returns an
error and never reports success. Session cleanup removes all artifacts only when
the owning session is explicitly removed. V1 has no time-based expiry.

History may record only artifact IDs and mechanical operation kinds when useful;
it never records labels, media types, summaries, paths, or bodies. Artifact
metadata and bodies are never automatic input to any agent.

## Risks / Trade-offs

- **Binary content can consume storage** → Enforce decoded per-artifact, count,
  and total-session limits before promotion.
- **Crashes split body and metadata writes** → Stage inside the target filesystem,
  atomically rename, and quarantine inconsistent final directories.
- **IDs in Context become stale after deletion** → Open fails clearly; the store
  does not mutate semantic Context behind the worker's back.
- **Explicit open adds a tool call** → Preserve that friction because automatic
  injection would turn artifacts into hidden memory.

## Migration Plan

Add the store and operations behind the existing worker pack, then test limits,
containment, symlinks, collisions, pagination, deletion, session cleanup, and
crash recovery. After verification, document the channel, update `arch.md`, and
remove only `Session Artifact Store` from `next.md`.

## Open Questions

None.
