## 1. Implement no-follow copy

- [x] 1.1 Remove `follow_symlinks` from the public copy signature, examples, generated references, and current specification.
- [x] 1.2 Add descriptor-relative no-follow traversal for regular files and directories.
- [x] 1.3 Stage beside the destination, validate the staged result, atomically publish, and clean every failure path.

## 2. Verify security and compatibility boundaries

- [x] 2.1 Cover top-level and nested in-bound/out-of-bound file and directory symlinks with exact destination preservation.
- [x] 2.2 Use a deterministic traversal barrier to prove a swapped symlink target is never read or published.
- [x] 2.3 Verify regular copy, overwrite, `info`, and `list` behavior plus signature/reference completion searches.
- [x] 2.4 Run strict OpenSpec validation, focused file tests, and repository-wide `just check`.
