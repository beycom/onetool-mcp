## Why

`file.copy()` validates only its top-level source and can dereference nested
symlinks outside configured allowed directories during recursive copy. V3
should expose one secure copy contract that never reads or publishes symlink
targets.

## What Changes

- **BREAKING** Remove the `follow_symlinks` parameter from `file.copy()`.
- Reject top-level and nested file or directory symlinks, including links
  introduced while traversal is in progress.
- Copy regular trees into a unique same-directory staging path and atomically
  publish only a complete link-free result.
- Preserve the separate `follow_symlinks` behavior of `file.info()` and
  `file.list()`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `otutil/tool-file`: Replace copy's follow/preserve modes with a no-follow,
  reject-all-symlinks contract and atomic destination publication.

## Impact

The `file.copy()` MCP signature, file tool implementation, generated reference
documentation, current specification, and copy-specific tests change. Callers
that intentionally want target content must pass the allowed real target path
explicitly.
