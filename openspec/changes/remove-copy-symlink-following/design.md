## Context

`file.copy()` currently validates a resolved top-level path and delegates
directory traversal to `shutil.copytree(..., symlinks=False)`. Nested links are
therefore dereferenced without validating their targets, and a prewalk would
still leave a check/use race. The destination is also written directly, so a
late rejection can publish a partial tree.

## Goals / Non-Goals

**Goals:**

- Reject every top-level or nested symlink without reading target bytes.
- Close traversal races by opening each source entry without following links.
- Publish a complete regular file or tree atomically from a unique
  same-directory staging path.
- Preserve destination bytes and remove staging residue on every failure.

**Non-Goals:**

- Preserving or dereferencing links.
- Changing the separate symlink options on `file.info()` or `file.list()`.
- Adding a compatibility parameter or migration-specific error branch.

## Decisions

1. Remove `follow_symlinks` from the public function rather than hardening two
   modes. One no-follow contract is auditable and callers can pass an allowed
   real target explicitly when they intend to copy its content.
2. Traverse directories through no-follow file-descriptor opens. Each entry is
   opened relative to its already-open parent and classified with `fstat`, so a
   regular entry swapped to a symlink fails before target bytes are read.
3. Copy into an exclusively created path beside the destination. The staged
   result is checked to contain no links and is published with atomic rename
   only after traversal succeeds.
4. Refuse an existing directory destination and require `overwrite=True` for an
   existing file, preserving the current destination policy.

## Risks / Trade-offs

- [No-follow descriptor flags vary by platform] → Require the platform
  primitives needed for the security guarantee and fail closed when they are
  unavailable.
- [Source mutates during copy] → Descriptor-relative no-follow opens ensure
  replacements cannot redirect reads; ordinary concurrent content changes have
  normal file-copy snapshot semantics.
- [Process stops before cleanup] → Unique hidden staging names prevent
  publication; normal error paths remove all residue.
