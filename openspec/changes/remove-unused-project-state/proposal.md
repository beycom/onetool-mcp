## Why

`otpack` publicly exposes unused generic YAML state helpers whose unlocked
whole-file writes cannot provide a safe persistence contract. Removing that
surface for v3 avoids carrying an unsafe API while preserving the actively used
project-state directory primitive.

## What Changes

- **BREAKING** Remove `otpack.get_state`, `otpack.set_state`, and the
  `otpack.state` module.
- Remove the unused helper implementation, dedicated tests, package exports, and
  current documentation examples together.
- Retain `get_project_state_dir(pack)` as the supported primitive for tools that
  own project-local state.

## Capabilities

### New Capabilities

- `otpack-project-paths`: Defines the retained public project-local state
  directory helper and the removed generic state-helper surface.

### Modified Capabilities

None.

## Impact

This changes the public exports of the standalone `otpack` package and removes
its PyYAML-backed state module. Active local-history, whiteboard, and console
consumers of `get_project_state_dir` remain unchanged. Current architecture and
tool-author documentation will no longer advertise generic state reads or
writes.
