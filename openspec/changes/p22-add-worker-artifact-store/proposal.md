## Why

Workers sometimes create evidence or intermediate files that should survive an
episode without becoming project deliverables, semantic Context, or automatic
model input. The named-Context foundation needs an explicit artifact namespace
whose lifecycle remains separate from the editable Context file.

## What Changes

- Add a project-local artifact namespace owned by each named Context.
- Add explicit create, open, list, and delete operations requiring a Context name.
- Keep artifact bodies out of automatic worker startup, Context files, Console,
  Status, and mechanical History.
- Enforce bounded metadata, byte/count limits, containment, digest validation,
  staged atomic creation, and conservative orphan recovery.
- Permit creation only for active Contexts while preserving artifact inspection
  and explicit deletion after Context archival.

## Capabilities

### New Capabilities

- `worker-artifact-store`: Named-Context-owned artifact creation, access,
  retention, recovery, and channel isolation.

### Modified Capabilities

None.

## Impact

- Depends on the synced named-Context contract from
  `p11-update-episodic-worker-foundation`.
- Affects project-local worker state, worker-facing tool discovery, path
  validation, archival retention, tests, skill guidance, and documentation.
- Does not copy project files, inject artifacts automatically, create semantic
  memory, retain Console output, or provide cross-Context search.
