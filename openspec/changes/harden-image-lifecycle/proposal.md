## Why

Image handles are currently short, mutable names whose metadata can redirect
storage operations, while remote downloads are buffered without a size bound
and transport failures do not have a stable tool-level contract. This leaves
the image pack exposed to collisions, path traversal, resource exhaustion, and
inconsistent errors at every public entry point.

## What Changes

- **BREAKING** Replace short, named, and bare image handles with the single
  canonical public form `#img_<64 lowercase hex>`, derived from the complete
  SHA-256 digest.
- **BREAKING** Remove the `handle` parameter and handle-passthrough behavior
  from `image.load()`; sources load by content identity and only canonical
  references are accepted by reference-oriented tools.
- Address content and metadata through validated exact direct-child paths,
  reject symlink redirection and tampered metadata, and remove legacy metadata
  fallback, directory-scan deduplication, and glob deletion.
- Stream URL responses with a fixed 20 MiB original-response limit, reject
  declared or observed overflow before image processing or persistence, and
  close responses on every outcome.
- Normalize expected HTTP and network failures into structured image-tool error
  responses while allowing unexpected programming failures to propagate.
- Require `session_cache_size` to be a positive integer and retain exact LRU
  capacity semantics, including capacity one.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ottools/tool-image`: Canonical image reference grammar, exact safe storage
  addressing, bounded URL downloads, stable expected-failure responses, and
  positive cache-capacity configuration.

## Impact

The `ot_image` public tool signature, returned handles, accepted reference
forms, storage metadata, URL behavior, configuration validation, tests,
generated tool index, and image reference documentation all change. Existing
session image entries are intentionally not migrated or accepted.
