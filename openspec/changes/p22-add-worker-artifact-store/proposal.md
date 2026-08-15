## Why

Workers sometimes create evidence or intermediate files that should survive an
episode but are neither small continuation Context nor project deliverables. A
session-owned artifact store gives that material an explicit, isolated lifecycle.

## What Changes

- Add a project-scoped `artifacts/` root beside each session's Context and
  History, with opaque stable IDs and bounded typed metadata.
- Add explicit create, open, list, and delete operations; artifacts are never
  injected automatically into worker startup.
- Enforce containment, symlink safety, atomic metadata updates, media/kind and
  size validation, collision handling, retention, cleanup, and orphan recovery.
- Keep artifact bodies and summaries out of Context, History, Console, and
  Status; Context may hold only an operationally necessary compact reference.
- Keep project deliverables in Local Changes and user-facing content in Console.

## Capabilities

### New Capabilities

- `worker-artifact-store`: Explicit session-scoped artifact creation, access,
  metadata, retention, recovery, deletion, and channel isolation.

### Modified Capabilities


## Impact

- Depends on the synced `p11-update-episodic-worker-foundation` contract.
- Affects session-state storage, worker-facing tool discovery, path validation,
  cleanup, tests, skill guidance, and reference documentation.
- Does not copy project files into managed storage, create automatic memory,
  retain Console output, or provide semantic indexing or cross-session storage.
