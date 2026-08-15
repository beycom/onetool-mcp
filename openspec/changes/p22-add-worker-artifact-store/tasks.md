## 1. Confirm the Named-Context Foundation

- [x] 1.1 Confirm revised `p11` is implemented, verified, and synced before
  integrating this change.
- [x] 1.2 Reuse strict Context name and status validation; do not add session IDs,
  project registries, aliases, or separate Context discovery.

## 2. Implement Context-Owned Artifact Storage

- [x] 2.1 Add the contained Context-qualified artifact root, opaque collision-
  checked IDs, strict metadata, immutable bodies, and path/symlink validation.
- [x] 2.2 Enforce 8 MiB per body, 64 ready artifacts, and 64 MiB total body bytes
  per Context before promotion.
- [x] 2.3 Implement staged write, flush, `fsync`, atomic rename, stale staging
  cleanup, inconsistent-final quarantine, and bounded orphan warnings.

## 3. Add Explicit Artifact Operations

- [x] 3.1 Add Context-qualified create with active-owner enforcement and bounded
  metadata-only result.
- [x] 3.2 Add open with owner, metadata, size, and digest validation before body return.
- [x] 3.3 Add stable bounded metadata-only list for active and archived owners.
- [x] 3.4 Add explicit delete that requires an existing artifact and cannot affect
  another Context root.

## 4. Enforce Archival and Channel Boundaries

- [x] 4.1 Preserve artifacts when a Context is archived; reject new creation while
  permitting explicit open, list, and delete.
- [x] 4.2 Keep artifacts out of automatic worker input, Context files, Console,
  Status, telemetry, and project Local Changes.
- [x] 4.3 Restrict History observation to Context name, artifact ID, and operation
  kind without descriptive metadata or body.

## 5. Verify and Promote

- [x] 5.1 Test validation, limits, containment, symlinks, collisions, atomicity,
  recovery, pagination, deletion, active/archive behavior, and channel isolation.
- [x] 5.2 Update skill and worker references for explicit Context-qualified access.
- [x] 5.3 Update `plans/episodic-worker/arch.md`, remove only the artifact-store
  section from `plans/episodic-worker/next.md`, and update plan status after
  verified implementation.
- [x] 5.4 Run focused tests, strict OpenSpec validation, and `just check` before
  syncing or archiving this change.
