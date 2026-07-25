## Why

OneTool's supported Forge workflow creates in-process extensions, but a stale
PEP 723 worker route remains reachable and contradicts current templates and
guidance. V3 should expose one extension architecture and remove the unused
subprocess protocol before it becomes a release contract.

## What Changes

- **BREAKING** Remove PEP 723-based worker classification, dependency
  installation, subprocess execution, and the worker-only public contract.
- Load every configured extension in-process with dependencies supplied by the
  installed OneTool environment.
- Treat inline PEP 723 blocks as ordinary Python comments with no OneTool
  routing semantics.
- Delete worker-only implementation, tests, specification, and current
  documentation while retaining generic static extension analysis.
- Reconcile current install, security, extension, architecture, and
  specification-index guidance with the single in-process model.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `serve-tools-packages`: Configured extensions use the same in-process loading
  route regardless of inline comment metadata.
- `ottools/tool-forge`: Remove the obsolete SDK migration warning from the
  current extension validator contract.
- `tool-execution`: Retire the obsolete worker-only capability and all of its
  subprocess, PEP 723, and worker classification requirements.

## Impact

This removes worker modules and branches across the executor, registry,
metadata, CLI, and docs generator; deletes worker-only tests and the
`tool-execution` main spec; and updates current user/developer documentation and
the canonical spec index. Existing extension files must have their dependencies
installed in the OneTool environment.
