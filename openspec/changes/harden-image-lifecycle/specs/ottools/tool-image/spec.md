## ADDED Requirements

### Requirement: Canonical image references and safe storage

The image pack SHALL use the complete content SHA-256 digest as image identity.
The only public reference form SHALL be `#img_<64 lowercase hexadecimal
characters>`, and the only internal storage-name form SHALL be the same value
without `#`. Public reference boundaries SHALL reject short, uppercase, bare,
named, traversal, separator-containing, and otherwise malformed references
before storage or model I/O.

Metadata and content operations SHALL use exact direct-child paths derived from
validated identity and a supported detected format. They SHALL NOT trust a
metadata filename, scan by hash, glob for lifecycle targets, follow symlink
redirection, or accept legacy session entries. Metadata whose handle or format
does not match its addressed entry SHALL fail closed.

#### Scenario: Deterministic full-digest identity

- **WHEN** an image with SHA-256 digest `<64 lowercase hex>` is loaded
- **THEN** its public handle SHALL be exactly `#img_<64 lowercase hex>`
- **AND** repeat loading of the same bytes SHALL address the same metadata path
  directly without a directory scan

#### Scenario: Invalid reference forms fail at every public boundary

- **WHEN** `ask`, `summary`, or `delete` receives a short, uppercase, bare,
  named, traversal, separator-containing, or otherwise malformed handle
  reference
- **THEN** it SHALL return a structured invalid-reference error before storage
  or model I/O

#### Scenario: Load accepts sources only

- **WHEN** `image.load()` receives any handle reference as its `img` source
- **THEN** it SHALL return a structured error and SHALL NOT access image storage

#### Scenario: Exact path and tamper protection

- **WHEN** metadata or content paths are symlinks, resolve outside the images
  directory, or metadata contains a mismatched handle, unsupported format, or
  arbitrary filename
- **THEN** `ask`, `summary`, `list`, `delete`, and `purge` SHALL NOT read,
  write, or delete the redirected target
- **AND** direct reference operations SHALL return a structured error

#### Scenario: Exact deletion

- **WHEN** a canonical image reference is deleted
- **THEN** only its exact derived content path and exact metadata path SHALL be
  removed
- **AND** similarly prefixed or unrelated files SHALL remain untouched

### Requirement: Bounded URL downloads and expected failure semantics

The image pack SHALL stream remote image responses and enforce a fixed maximum
of 20 MiB (20 × 1024 × 1024 bytes) for the original response. The source
boundary SHALL own HTTP status handling, network and timeout normalization,
content-type validation, limit enforcement, and response cleanup.

Expected `httpx` HTTP, connection, DNS/request, and timeout failures SHALL
become structured error results through `load`, each `load_batch` item, and
the automatic source-loading paths of `ask` and `summary`. Unexpected
programming failures, including `AssertionError`, SHALL propagate.

#### Scenario: Declared oversize response

- **WHEN** a remote image declares a valid `Content-Length` greater than 20 MiB
- **THEN** loading SHALL fail before reading a body chunk
- **AND** image decoding, persistence, cache admission, and background work
  SHALL not run

#### Scenario: Streaming limit with absent or dishonest length

- **WHEN** `Content-Length` is absent or does not exceed the limit but streamed
  bytes cross 20 MiB
- **THEN** loading SHALL stop at the crossing chunk and return a structured
  size-limit error
- **AND** image decoding, persistence, cache admission, and background work
  SHALL not run

#### Scenario: Exact limit succeeds

- **WHEN** a valid image response contains exactly 20 MiB
- **THEN** it SHALL be accepted by the download boundary

#### Scenario: Response is always closed

- **WHEN** a remote response succeeds or fails due to status, content type,
  declared size, or streamed overflow
- **THEN** the response SHALL be closed before the operation returns or raises

#### Scenario: Expected transport failures are structured

- **WHEN** a URL source raises an HTTP status, connection/request, DNS, or
  timeout failure
- **THEN** `load`, the corresponding `load_batch` item, and automatic loading
  from `ask` or `summary` SHALL return an error dict instead of raising
- **AND** `load_batch` SHALL continue processing later sources

#### Scenario: Unexpected failure propagates

- **WHEN** the URL source boundary raises `AssertionError`
- **THEN** the public call SHALL propagate it unchanged

## MODIFIED Requirements

### Requirement: Load a single image into session storage

`image.load()` SHALL accept one file, HTTP/HTTPS URL, or clipboard source,
derive the canonical handle from the complete SHA-256 digest, save the original
verbatim to `.onetool/images/` under the exact canonical content path, populate
the session LRU cache, and return handle and image metadata. It SHALL have no
custom-handle parameter and SHALL not accept a handle as a source.

#### Scenario: Load from file path

- **WHEN** `image.load(img="~/screenshots/ui.png")` is called
- **THEN** it SHALL return `{"handle": "#img_<64hexchars>", "source": "<path>", "dims": [W, H], "resized": bool, "dedup": false}`
- **AND** the original SHALL be saved verbatim as
  `.onetool/images/img_<64hexchars>.<detected extension>`
- **AND** canonical metadata SHALL be created without a stored filename field
- **AND** if `model` is configured, a background daemon thread SHALL persist a
  summary without blocking `load()`

#### Scenario: Stored extension matches detected format

- **WHEN** image content is loaded
- **THEN** its exact content extension SHALL use PNG→`.png`, JPEG→`.jpg`,
  GIF→`.gif`, WebP→`.webp`, TIFF→`.tiff`, HEIC→`.heic`, AVIF→`.avif`,
  or SVG→`.svg` according to detected bytes

#### Scenario: Background summary skipped when no vision model

- **WHEN** `image.load()` is called and `model` is empty
- **THEN** no background thread SHALL be spawned

#### Scenario: Load from clipboard

- **WHEN** `image.load(img="clip")` is called on Windows or macOS with an image
- **THEN** it SHALL store the captured PNG with source `"clipboard"` and return
  its canonical handle

#### Scenario: Load from URL

- **WHEN** `image.load(img="https://...")` receives a valid bounded image
- **THEN** it SHALL store the original with the URL as source and return its
  canonical handle

#### Scenario: Dedup by exact content address

- **GIVEN** an image has already been loaded
- **WHEN** the identical bytes are loaded again
- **THEN** `load()` SHALL return the same canonical handle with `dedup: true`
- **AND** it SHALL use the exact digest-derived metadata path without scanning
  or rewriting files

#### Scenario: Glob rejected by load

- **WHEN** `image.load(img="~/screenshots/*.png")` is called
- **THEN** it SHALL return an error directing the caller to `load_batch()`

#### Scenario: Linux clipboard not supported

- **WHEN** `image.load(img="clip")` is called on Linux
- **THEN** it SHALL return a structured unsupported-clipboard error

#### Scenario: Image resize

- **WHEN** an image exceeds `max_edge`
- **THEN** the original SHALL remain full resolution on disk
- **AND** only model-upload bytes SHALL be resized
- **AND** metadata SHALL record original and model dimensions

### Requirement: Ask questions about a loaded image

`image.ask()` SHALL accept canonical image references, file paths, URLs, or
`"clip"` for each image input. Non-reference sources SHALL be auto-loaded.
Every handle reference SHALL use the canonical public grammar.

#### Scenario: Canonical handle question

- **WHEN** `image.ask(img="#img_<64 lowercase hex>", q="What is shown?")` is
  called for a loaded image
- **THEN** it SHALL return ordered question/answer pairs and that exact handle

#### Scenario: Multiple questions use one structured call

- **WHEN** multiple questions are supplied
- **THEN** they SHALL be sent in one structured model call and returned in input
  order
- **AND** existing per-question fallback SHALL preserve complete answers when
  the structured response cannot be parsed

#### Scenario: Multi-image ask

- **WHEN** up to eight canonical references or auto-loadable sources are passed
- **THEN** all SHALL be resolved before one model call and returned in input
  order under `handles`

#### Scenario: Multi-image response shape keyed by input type

- **WHEN** `img` is a list
- **THEN** the response SHALL use `handles`
- **WHEN** `img` is a plain string
- **THEN** the response SHALL use `handle`

#### Scenario: Multi-image resolution failure fails fast

- **WHEN** any image reference or source cannot be resolved
- **THEN** the result SHALL identify that input and no model call SHALL run

#### Scenario: Empty image list

- **WHEN** `img=[]`
- **THEN** an error dict SHALL be returned without a model call

#### Scenario: Multi-image cap

- **WHEN** more than eight images are provided
- **THEN** an error naming the limit SHALL be returned without a model call

#### Scenario: Clipboard refresh

- **WHEN** `"clip"` is used on successive calls
- **THEN** current clipboard bytes SHALL be loaded each time and content-address
  deduplication SHALL select the canonical handle

#### Scenario: Vision model not configured

- **WHEN** no model is configured
- **THEN** a structured `Error:` result SHALL be returned rather than raised

### Requirement: Extract and cache a structured image summary

`image.summary()` SHALL accept a canonical image reference, file path, URL, or
`"clip"`, auto-load sources, run generic extraction once per image, and cache
the result in canonical metadata.

#### Scenario: First canonical call triggers model

- **WHEN** a loaded canonical handle has no summary
- **THEN** the model SHALL run, the result SHALL be saved, and `cached` SHALL be
  false

#### Scenario: Repeat call is cached

- **WHEN** the same canonical handle is summarized again
- **THEN** the saved result SHALL return with `cached: true` and no model call

#### Scenario: Clipboard refresh

- **WHEN** `"clip"` is summarized successively
- **THEN** current clipboard bytes SHALL be loaded and addressed by content each
  time

#### Scenario: clip_view delegates

- **WHEN** `image.clip_view()` is called
- **THEN** it SHALL behave as `image.summary(img="clip")`

#### Scenario: Summary JSON keys

- **WHEN** a summary succeeds
- **THEN** it SHALL contain exactly `type`, `mode`, `colours`, `description`,
  and `content`, with valid mode and non-null content

### Requirement: List loaded images

`image.list()` SHALL return metadata only for valid canonical entries currently
in the session images directory and SHALL not follow or report malformed or
redirected metadata paths.

#### Scenario: Basic list

- **WHEN** two canonical images are loaded
- **THEN** list SHALL return their canonical handles and metadata fields

#### Scenario: Invalid entry is not followed

- **WHEN** the directory contains malformed filenames, symlink metadata, or
  metadata whose handle does not match its filename
- **THEN** list SHALL not follow or report those entries

#### Scenario: Empty store

- **WHEN** no valid canonical images are loaded
- **THEN** list SHALL return `[]`

### Requirement: Delete a loaded image

`image.delete()` SHALL require a canonical public reference and remove only the
exact derived content path, exact metadata path, and matching session-cache
entry.

#### Scenario: Successful exact delete

- **WHEN** a valid loaded canonical handle is deleted
- **THEN** its exact content and metadata files and cache entry SHALL be removed
- **AND** similarly prefixed and unrelated files SHALL remain

#### Scenario: Invalid or unknown handle

- **WHEN** the handle is malformed or no valid canonical entry exists
- **THEN** a structured error SHALL be returned without deleting other paths

### Requirement: Purge images by age

`image.purge()` SHALL delete valid canonical entries older than a positive
number of minutes, or all valid canonical entries when `all=True`. It SHALL not
follow malformed, tampered, or symlink entries.

#### Scenario: Purge with minutes

- **WHEN** `image.purge(minutes=120)` is called
- **THEN** valid canonical entries older than 120 minutes SHALL be exactly
  deleted and counted

#### Scenario: Purge default

- **WHEN** `image.purge()` is called
- **THEN** valid canonical entries older than 15 minutes SHALL be deleted

#### Scenario: Purge all

- **WHEN** `image.purge(all=True)` is called
- **THEN** all valid canonical entries and only those entries SHALL be deleted

#### Scenario: Invalid minutes raises

- **WHEN** minutes is zero or negative and `all` is false
- **THEN** `ValueError` SHALL be raised

### Requirement: Session cache is bounded

The in-memory session LRU cache SHALL enforce exactly the configured positive
entry count.

#### Scenario: Capacity one

- **GIVEN** `session_cache_size=1`
- **WHEN** two distinct images are admitted
- **THEN** exactly the most recently used image SHALL remain

#### Scenario: Positive capacity

- **GIVEN** `session_cache_size=N` for positive `N`
- **WHEN** more than `N` distinct images are admitted
- **THEN** exactly the `N` most recently used images SHALL remain
- **AND** evicted originals SHALL remain on disk

#### Scenario: Re-access after eviction

- **WHEN** an evicted canonical image is asked about
- **THEN** its exact content path SHALL be read and the cache repopulated

### Requirement: Configuration via `tools.image` block

The `ot_image` pack SHALL be configurable under `tools.ot_image`, and
`session_cache_size` SHALL be a positive integer. Hosted and standalone pack
configuration SHALL use the same Pydantic field validation and failure
semantics.

#### Scenario: Non-positive cache size rejected

- **WHEN** `session_cache_size` is zero or negative through hosted or standalone
  configuration
- **THEN** configuration SHALL fail for the `session_cache_size` field

#### Scenario: Model required for ask and summary

- **WHEN** no image or top-level LLM model is configured
- **THEN** `ask` and `summary` SHALL return a structured model-setting error

#### Scenario: Inherit LLM values

- **WHEN** image model or base URL is empty
- **THEN** configured top-level LLM values SHALL be inherited
- **AND** the API key SHALL use `OPENAI_API_KEY` when present, otherwise
  `OT_LLM_API_KEY`

#### Scenario: max_edge override

- **WHEN** `tools.ot_image.max_edge` is configured
- **THEN** model-upload resizing SHALL honor that value
