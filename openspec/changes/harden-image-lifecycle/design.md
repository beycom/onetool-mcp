## Context

The image pack currently derives eight-hex handles, accepts caller-selected
names and bare references, scans metadata to deduplicate content, and trusts a
metadata `file` value when reading or deleting content. URL sources use an
eager HTTP GET with no response-size limit. These choices couple public
identity to mutable metadata and make resource and failure behavior dependent
on the call path.

The four review issues in this change share the source-to-handle lifecycle:
source resolution, transport, content identity, persistence, cache admission,
reference resolution, and deletion. They therefore need one boundary design
rather than call-site fixes.

## Goals / Non-Goals

**Goals:**

- Make the complete SHA-256 digest the only image identity.
- Validate canonical public references and internal names at their boundaries.
- Derive every storage path from validated identity and constrained format
  metadata, with symlink-aware direct-child checks.
- Bound remote originals to 20 MiB while streaming and close responses on
  success and every failure.
- Normalize only expected HTTP/network failures into the image tool's
  structured error contract.
- Reject non-positive session cache capacity through the existing Pydantic
  configuration path.

**Non-Goals:**

- Migrating or reading image entries created under the removed short/named
  handle contract.
- Adding a configurable download limit or compatibility aliases.
- Changing supported image formats, model resize behavior, or vision prompts.

## Decisions

### Complete digest identity and strict boundary parsers

The internal name is `img_<64 lowercase hex>` and the public reference is that
name prefixed by `#`. Dedicated parsers validate each form with full-match
regular expressions. `load()` derives the name directly from downloaded or
local bytes and checks the exact metadata path for deduplication; it never
scans the directory.

Using the full digest removes collision-resolution state and makes content
addressing deterministic. Retaining short or caller-selected aliases was
rejected because aliases recreate mutable identity and extra lookup paths.

### Exact paths derived from identity and constrained format

Metadata contains the validated canonical internal handle and detected
`original_format`, but no filename. The metadata path is exactly
`{handle}.meta.json`; the content path is exactly `{handle}.{mapped_extension}`.
Format-to-extension uses the supported-format map and rejects unknown metadata
formats instead of defaulting.

Every read, write, or delete validates that the lexical path is an immediate
child of the images directory and that an existing path is not a symlink or
resolved outside that directory. Directory enumeration used by list and purge
accepts only canonical metadata filenames and applies the same checks.

Trusting the legacy `file` field or globbing for content was rejected because
both make the operation target broader than the validated identity.

### One streaming transport boundary

`_fetch_url()` owns transport normalization, content-type validation, byte
limits, and response cleanup. It uses the shared client's streaming context.
A valid `Content-Length` above 20 MiB fails before body iteration; otherwise
chunks are accumulated only through the fixed limit and the first crossing
chunk causes immediate failure. Exactly 20 MiB is accepted.

Expected `httpx.HTTPError` failures become one image-source runtime error.
Validation errors already intended for callers remain structured source
errors. Other exceptions, including `AssertionError`, propagate so programming
defects are not disguised as input failures.

### Cache capacity validated at configuration construction

`session_cache_size` uses Pydantic's `gt=0` constraint. The module singleton
continues to instantiate one `Cache` from resolved configuration, so both
hosted and standalone configuration entry paths share validation and the
runtime retains exactly the configured positive number of entries.

## Risks / Trade-offs

- **Existing session entries become unreadable** → Sessions are explicitly
  ephemeral and no migration or fallback is provided.
- **A 20 MiB original may still expand substantially during decode** → Existing
  decoder safeguards remain in effect; this change bounds transport and stored
  original size, not decoded pixel memory.
- **Tampered metadata can make an entry unavailable** → Fail closed with a
  structured error rather than guessing another path.
- **Directory list/purge can encounter unrelated files** → Ignore filenames
  outside the canonical metadata grammar and never follow them.

## Migration Plan

Ship the signature, grammar, storage, tests, generated reference, and main spec
together. Existing session image files are not migrated. Rollback is the
single atomic change; no durable user data conversion is involved.

## Open Questions

None.
