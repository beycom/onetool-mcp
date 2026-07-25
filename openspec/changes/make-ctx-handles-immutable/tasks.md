## 1. Immutable storage

- [x] 1.1 Replace flat content/metadata files with immutable per-handle record
  directories and unique same-parent staging
- [x] 1.2 Publish complete records atomically and exclusively, retrying forced
  handle collisions without replacement
- [x] 1.3 Make discovery, reads, purge, and deletion operate only on complete
  published record directories

## 2. Contract reduction

- [x] 2.1 Delete `ctx.append`, its exports, and all same-handle update helpers
- [x] 2.2 Remove access-count state, read-side writes, and response fields
- [x] 2.3 Synchronize the ctx main spec and current tool reference documentation

## 3. Verification

- [x] 3.1 Test independent concurrent creation, forced collisions, and reader
  observations around the publication boundary
- [x] 3.2 Inject serialization, content-write, metadata-write, and publication
  failures and prove no visible or staging residue remains
- [x] 3.3 Prove repeated reads preserve stored bytes and mtimes, and successful
  deletion removes the complete record
- [x] 3.4 Run focused ctx, registry, and docs-generation tests plus strict
  OpenSpec/docs validation

## 4. Repository validation

- [x] 4.1 Run `just check` and resolve every substantive batch review finding
