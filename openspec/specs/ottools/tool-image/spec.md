# tool-image Specification

## Purpose

Defines the `ot_image` pack for bounded image loading, canonical
content-addressed session storage, lifecycle management, and vision querying.

## Requirements

### Requirement: Supported image formats

`image.load()` SHALL accept PNG, JPEG, GIF, WebP, TIFF, HEIC, HEIF, AVIF, and
SVG. Missing optional HEIC/HEIF/AVIF, SVG, or clipboard dependencies SHALL
produce a structured error naming the install requirement.

#### Scenario: Supported raster format loads

- **WHEN** a supported raster image is loaded
- **THEN** it SHALL be accepted and stored

#### Scenario: Missing optional decoder

- **WHEN** a required optional decoder is absent
- **THEN** `load()` SHALL return an error dict naming that dependency

### Requirement: Canonical image references and safe storage

The complete SHA-256 digest SHALL identify an image. The only public reference
form SHALL be `#img_<64 lowercase hexadecimal characters>` and the internal
storage name SHALL be the same value without `#`. Public reference boundaries
SHALL reject short, uppercase, bare, named, traversal, separator-containing, or
otherwise malformed references before storage or model I/O.

Metadata and content operations SHALL use exact direct-child paths derived from
validated identity and a supported detected format. They SHALL NOT trust a
metadata filename, scan by hash, glob for lifecycle targets, follow symlink
redirection, or accept legacy session entries. Metadata whose handle, hash, or
format does not match the addressed entry SHALL fail closed.

#### Scenario: Deterministic full-digest identity

- **WHEN** bytes with a given SHA-256 digest are loaded
- **THEN** the handle SHALL be exactly `#img_<complete digest>`
- **AND** repeat loading SHALL check the exact metadata path without a scan

#### Scenario: Invalid reference forms fail at public boundaries

- **WHEN** `ask`, `summary`, or `delete` receives a noncanonical reference
- **THEN** it SHALL return an invalid-reference error before storage or model I/O

#### Scenario: Load accepts sources only

- **WHEN** `load()` receives any handle reference as `img`
- **THEN** it SHALL return a structured error without accessing image storage

#### Scenario: Tamper protection

- **WHEN** a metadata or content path is a symlink, resolves outside the image
  directory, or metadata identity or format is inconsistent
- **THEN** the redirected target SHALL not be read, written, or deleted

#### Scenario: Exact deletion

- **WHEN** a canonical image is deleted
- **THEN** only its exact content and metadata paths SHALL be removed

### Requirement: Load a single image into session storage

`image.load()` SHALL accept one file, HTTP/HTTPS URL, or clipboard source,
derive a canonical handle, save the original verbatim under the detected
extension, populate the session LRU cache, and return image metadata. It SHALL
have no custom-handle parameter and SHALL not accept a handle as a source.

#### Scenario: Load from file

- **WHEN** a supported file is loaded
- **THEN** the result SHALL include its canonical handle, source, dimensions,
  resize status, and `dedup: false`
- **AND** canonical metadata SHALL be stored without a filename field

#### Scenario: Stored extension matches detected format

- **WHEN** content is stored
- **THEN** its extension SHALL use PNG→`.png`, JPEG→`.jpg`, GIF→`.gif`,
  WebP→`.webp`, TIFF→`.tiff`, HEIC→`.heic`, AVIF→`.avif`, or SVG→`.svg`
  according to detected bytes

#### Scenario: Dedup by exact content address

- **WHEN** identical bytes are loaded again
- **THEN** the same handle SHALL return with `dedup: true`
- **AND** files SHALL not be rewritten

#### Scenario: Background summary

- **WHEN** a vision model is configured
- **THEN** `load()` SHALL start nonblocking summary work
- **WHEN** no model is configured
- **THEN** it SHALL not create a summary thread

#### Scenario: Clipboard

- **WHEN** clipboard loading is supported and contains an image
- **THEN** captured PNG bytes SHALL be stored with source `"clipboard"`

#### Scenario: Linux clipboard unsupported

- **WHEN** clipboard loading is requested on Linux
- **THEN** a structured unsupported error SHALL return

#### Scenario: Glob rejected by load

- **WHEN** `load()` receives a glob
- **THEN** it SHALL return an error directing the caller to `load_batch()`

#### Scenario: Model resize preserves original

- **WHEN** an image exceeds `max_edge`
- **THEN** the disk original SHALL remain full resolution
- **AND** only model-upload bytes SHALL be resized

### Requirement: Bounded URL downloads and expected failure semantics

Remote responses SHALL be streamed with a fixed maximum of 20 MiB
(20 × 1024 × 1024 bytes). The source boundary SHALL own status handling,
network and timeout normalization, content-type validation, limit enforcement,
and response cleanup.

Expected `httpx` HTTP, connection/request, DNS, and timeout failures SHALL
become structured errors through `load`, each `load_batch` item, and automatic
loading from `ask` and `summary`. Unexpected failures such as `AssertionError`
SHALL propagate.

#### Scenario: Declared oversize response

- **WHEN** valid `Content-Length` exceeds 20 MiB
- **THEN** loading SHALL fail before body iteration or downstream image work

#### Scenario: Observed oversize response

- **WHEN** streamed bytes cross 20 MiB
- **THEN** loading SHALL stop at the crossing chunk
- **AND** decoding, persistence, caching, and background work SHALL not run

#### Scenario: Exact limit

- **WHEN** a valid image response contains exactly 20 MiB
- **THEN** the transport boundary SHALL accept it

#### Scenario: Response cleanup

- **WHEN** a response succeeds or fails due to status, content type, declared
  size, or streamed overflow
- **THEN** it SHALL be closed

#### Scenario: Batch continuation

- **WHEN** one source has an expected transport failure
- **THEN** its batch item SHALL be an error and later sources SHALL still run

#### Scenario: Unexpected failure propagates

- **WHEN** the source boundary raises `AssertionError`
- **THEN** the public call SHALL propagate it unchanged

### Requirement: Load multiple images in batch

`image.load_batch()` SHALL accept a glob or ordered list of sources and return
one `load()`-shaped result per source.

#### Scenario: Glob load

- **WHEN** a glob matches supported image files
- **THEN** each SHALL be loaded in sorted path order

#### Scenario: Ordered source list

- **WHEN** a list of sources is supplied
- **THEN** results SHALL preserve input order and failures SHALL not stop later items

#### Scenario: Empty glob

- **WHEN** a glob matches no files
- **THEN** `[]` SHALL return

### Requirement: Ask questions about a loaded image

`image.ask()` SHALL accept canonical references, file paths, URLs, or `"clip"`
for one image or a list of up to eight. Sources SHALL be auto-loaded, all
references SHALL resolve before one vision call, and questions and answers
SHALL preserve order.

#### Scenario: Canonical handle question

- **WHEN** a loaded canonical handle and question are passed
- **THEN** ordered question/answer pairs and that handle SHALL return

#### Scenario: Multiple questions

- **WHEN** multiple questions are passed
- **THEN** one structured model call SHALL be attempted
- **AND** an unparseable structured response SHALL fall back to complete
  per-question calls in input order

#### Scenario: Multiple images

- **WHEN** a list of up to eight references or sources is passed
- **THEN** all images SHALL be included in one model call in input order
- **AND** the response SHALL use `handles`

#### Scenario: Response shape follows input type

- **WHEN** `img` is a string
- **THEN** the response SHALL use `handle`
- **WHEN** `img` is a list, including one item
- **THEN** the response SHALL use `handles`

#### Scenario: Resolution failure is fail-fast

- **WHEN** any reference or source cannot resolve
- **THEN** that input SHALL be identified and no model call SHALL run

#### Scenario: Empty list and cap

- **WHEN** the list is empty or contains more than eight inputs
- **THEN** an error SHALL return without a model call

#### Scenario: Clipboard refresh

- **WHEN** `"clip"` is used successively
- **THEN** current clipboard bytes SHALL be loaded each time and deduplicated by
  content

#### Scenario: Model not configured

- **WHEN** no vision model is configured
- **THEN** a structured `Error:` result SHALL return

### Requirement: Extract and cache a structured image summary

`image.summary()` SHALL accept a canonical reference, file path, URL, or
`"clip"`, auto-load sources, extract once per image, and cache the result in
canonical metadata.

#### Scenario: First and repeat call

- **WHEN** no summary is cached
- **THEN** the model SHALL run, persist the summary, and return `cached: false`
- **WHEN** the summary is already cached
- **THEN** it SHALL return with `cached: true` and no model call

#### Scenario: Clipboard summary

- **WHEN** `"clip"` is summarized successively
- **THEN** current clipboard content SHALL be loaded each time

#### Scenario: clip_view

- **WHEN** `clip_view()` is called
- **THEN** it SHALL behave exactly as `summary(img="clip")`

#### Scenario: Summary shape

- **WHEN** extraction succeeds
- **THEN** the summary SHALL contain exactly `type`, `mode`, `colours`,
  `description`, and `content`

### Requirement: List loaded images

`image.list()` SHALL return metadata only for valid canonical entries and SHALL
not follow or report malformed or redirected metadata or content paths.

#### Scenario: Basic list

- **WHEN** valid images are loaded
- **THEN** their canonical handles and metadata SHALL return

#### Scenario: Invalid entry

- **WHEN** malformed filenames, symlinks, or inconsistent metadata exist
- **THEN** they SHALL not be followed or reported

#### Scenario: Empty store

- **WHEN** no valid entries exist
- **THEN** `[]` SHALL return

### Requirement: Delete a loaded image

`image.delete()` SHALL require a canonical public reference and remove only its
exact content path, metadata path, and cache entry.

#### Scenario: Successful delete

- **WHEN** a valid loaded reference is deleted
- **THEN** its exact files and cache entry SHALL be removed
- **AND** similarly prefixed files SHALL remain

#### Scenario: Invalid or unknown handle

- **WHEN** a reference is malformed or absent
- **THEN** an error SHALL return without deleting another path

### Requirement: Purge images by age

`image.purge()` SHALL delete valid canonical entries older than a positive
number of minutes, or every valid entry with `all=True`, without following
malformed, tampered, or symlink entries.

#### Scenario: Age and default

- **WHEN** positive `minutes` is passed
- **THEN** older valid entries SHALL be exactly deleted
- **WHEN** omitted
- **THEN** the threshold SHALL be 15 minutes

#### Scenario: Purge all

- **WHEN** `all=True`
- **THEN** every valid canonical entry and only those entries SHALL be deleted

#### Scenario: Invalid minutes

- **WHEN** minutes is zero or negative while `all` is false
- **THEN** `ValueError` SHALL be raised

### Requirement: Session cache is bounded

The session LRU cache SHALL retain exactly the configured positive number of
entries while leaving evicted originals on disk.

#### Scenario: Capacity one and positive capacity

- **WHEN** more than configured capacity is admitted
- **THEN** exactly the most recently used configured number SHALL remain,
  including exactly one when capacity is one

#### Scenario: Re-access after eviction

- **WHEN** an evicted canonical image is referenced
- **THEN** its exact content path SHALL be read and the cache repopulated

### Requirement: Configuration via `tools.image` block

The pack SHALL be configured under `tools.ot_image`.
`session_cache_size` SHALL be a positive integer, with hosted and standalone
configuration using the same typed field validation and pack-and-field failure
semantics.

#### Scenario: Non-positive cache size

- **WHEN** zero or a negative cache size is configured in either mode
- **THEN** configuration SHALL fail for `tools.ot_image.session_cache_size`

#### Scenario: Inherit LLM values

- **WHEN** image model or base URL is empty
- **THEN** top-level `llm` values SHALL be inherited
- **AND** the API key SHALL use `OPENAI_API_KEY` when present, otherwise
  `OT_LLM_API_KEY`

#### Scenario: Model required for vision

- **WHEN** no image or top-level model is configured
- **THEN** `ask` and `summary` SHALL return a model-setting error

#### Scenario: max_edge override

- **WHEN** `tools.ot_image.max_edge` is configured
- **THEN** model-upload resizing SHALL honor it
