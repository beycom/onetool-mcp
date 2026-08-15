## 1. Confirm Foundation and Freeze Contracts

- [ ] 1.1 Confirm the verified `p11` specs are synced before integrating the
  artifact store and preserve every foundation channel-isolation rule.
- [ ] 1.2 Add strict artifact metadata, operation input/result, pagination, and
  error models with unknown-field, enum, media, and decoded-size tests.

## 2. Implement Safe Session Storage

- [ ] 2.1 Resolve the session artifact root through project-state utilities and
  enforce opaque IDs, containment, no caller filenames, and symlink rejection.
- [ ] 2.2 Implement staged body/metadata writes, flush and `fsync`, digest and size
  verification, atomic directory promotion, and collision handling.
- [ ] 2.3 Enforce 8 MiB per body, 64 artifacts, and 64 MiB total session limits
  before durable creation.
- [ ] 2.4 Implement stale-staging cleanup, orphan quarantine, explicit artifact
  deletion, and complete owning-session cleanup without guessed recovery.

## 3. Add Explicit Artifact Operations

- [ ] 3.1 Add `artifact_create` returning body-free metadata and `artifact_open`
  returning only the explicitly requested validated artifact.
- [ ] 3.2 Add stable oldest-first, metadata-only `artifact_list` pagination and
  strict `artifact_delete` behavior for existing IDs.
- [ ] 3.3 Keep artifacts out of startup and all other automatic-input paths; allow
  only compact operational IDs in Context and body-free operation facts in History.

## 4. Verify Lifecycle and Channel Isolation

- [ ] 4.1 Test containment, traversal, symlinks, collisions, text encoding, binary
  content, media validation, all limits, pagination, and cross-project/session IDs.
- [ ] 4.2 Test interruption at each creation phase, recovery, corrupt metadata,
  digest mismatch, delete failures, orphan handling, and session cleanup.
- [ ] 4.3 Prove artifact bodies/metadata are never automatic worker/main input and
  never copied into Context, Console, Status, History, or Local Changes observation.

## 5. Promote and Validate

- [ ] 5.1 Verify implementation against the proposal, design, and delta specs.
- [ ] 5.2 Update program `arch.md` with the verified store and channel routing,
  then remove only `Session Artifact Store` and supporting-only text from
  program `next.md`.
- [ ] 5.3 Update worker skill/reference documentation and the delivery plan status
  if an execution record or status field has been added.
- [ ] 5.4 Run focused tests, strict OpenSpec validation, and `just check`; resolve
  every failure before syncing or archiving the change.
