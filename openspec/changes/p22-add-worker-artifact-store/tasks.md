## 1. Confirm the Named-Context Foundation

- [ ] 1.1 Confirm revised `p11` is implemented, verified, and synced before
  integrating this change.
- [ ] 1.2 Reuse strict Context name and status validation; do not add session IDs,
  project registries, aliases, or separate Context discovery.

## 2. Implement Context-Owned Artifact Storage

- [ ] 2.1 Add the contained Context-qualified artifact root, opaque collision-
  checked IDs, strict metadata, immutable bodies, and path/symlink validation.
- [ ] 2.2 Enforce 8 MiB per body, 64 ready artifacts, and 64 MiB total body bytes
  per Context before promotion.
- [ ] 2.3 Implement staged write, flush, `fsync`, atomic rename, stale staging
  cleanup, inconsistent-final quarantine, and bounded orphan warnings.

## 3. Add Explicit Artifact Operations

- [ ] 3.1 Add Context-qualified create with active-owner enforcement and bounded
  metadata-only result.
- [ ] 3.2 Add open with owner, metadata, size, and digest validation before body return.
- [ ] 3.3 Add stable bounded metadata-only list for active and archived owners.
- [ ] 3.4 Add explicit delete that requires an existing artifact and cannot affect
  another Context root.

## 4. Enforce Archival and Channel Boundaries

- [ ] 4.1 Preserve artifacts when a Context is archived; reject new creation while
  permitting explicit open, list, and delete.
- [ ] 4.2 Keep artifacts out of automatic worker input, Context files, Console,
  Status, telemetry, and project Local Changes.
- [ ] 4.3 Restrict History observation to Context name, artifact ID, and operation
  kind without descriptive metadata or body.

## 5. Verify and Promote

- [ ] 5.1 Test validation, limits, containment, symlinks, collisions, atomicity,
  recovery, pagination, deletion, active/archive behavior, and channel isolation.
- [ ] 5.2 Update skill and worker references for explicit Context-qualified access.
- [ ] 5.3 Update `plans/episodic-worker/arch.md`, remove only the artifact-store
  section from `plans/episodic-worker/next.md`, and update plan status after
  verified implementation.
- [ ] 5.4 Run focused tests, strict OpenSpec validation, and `just check` before
  syncing or archiving this change.
