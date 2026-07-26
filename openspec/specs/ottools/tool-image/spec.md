# tool-image Specification

## Purpose

Defines the `ot_image` pack providing image loading, querying, and lifecycle management for AI agents. Images are stored in `.onetool/images/`, accessed via stable content-hash handles, and queried using a configurable vision model. A session-scoped LRU cache avoids re-reading files on repeated access.

## Requirements

### Requirement: Supported image formats

`image.load()` SHALL accept images in the following formats: PNG, JPEG, GIF, WebP, TIFF, HEIC, and AVIF.

- TIFF is supported natively via Pillow (no extra dependency).
- HEIC, HEIF, and AVIF require `pillow-heif` to be installed; if it is missing, `load()` SHALL return an `{"error": ...}` dict with a clear message directing the user to `pip install pillow-heif`.
- SVG is supported via rasterisation with `resvg-py`; if it is missing, `load()` SHALL return an `{"error": ...}` dict with a clear message directing the user to `pip install resvg-py`.

#### Scenario: Supported raster format loads
- **WHEN** `image.load(img="photo.png")` is called for a supported raster image
- **THEN** the image SHALL be accepted and stored

#### Scenario: Missing optional decoder
- **WHEN** `image.load(...)` is called for a HEIC, HEIF, AVIF, SVG, or clipboard source and a required optional dependency is missing
- **THEN** it SHALL return an `{"error": ...}` dict (not raise) whose message names the missing dependency and install requirement

---

### Requirement: Load a single image into session storage

`image.load()` SHALL accept a single image source, save the original verbatim to
`.onetool/images/` under a filename whose extension matches the detected source
format, populate the session LRU cache, and return a dict with handle
and image metadata.

#### Scenario: Load from file path

- **WHEN** `image.load(img="~/screenshots/ui.png")` is called
- **THEN** it SHALL return `{"handle": "#img_<8hexchars>", "source": "<path>", "dims": [W, H], "resized": bool, "dedup": false}`
- **AND** the original file SHALL be saved verbatim to `.onetool/images/img_<hash>.<ext>` where `<ext>` matches the detected source format
- **AND** `img_<hash>.meta.json` SHALL be created with `source`, `hash`,
  `original_dims`, `model_dims`, `resized`, `max_edge`, `original_format`,
  `file` (the stored content filename, e.g. `"img_<hash>.jpg"`),
  `created_at`, and `summary: null`
- **AND** if `model` is configured, a background daemon thread SHALL be spawned
  to call `extract_summary()` and persist the result via `save_summary()` — the
  `load()` call SHALL NOT block on this

#### Scenario: Stored extension matches detected format

- **WHEN** `image.load(img="~/photo.jpeg")` is called with JPEG content
- **THEN** the original SHALL be stored as `img_<hash>.jpg` (not `.png`)
- **AND** the extension SHALL be derived from content detection, per this mapping: PNG→`.png`, JPEG→`.jpg`, GIF→`.gif`, WebP→`.webp`, TIFF→`.tiff`, HEIC→`.heic`, AVIF→`.avif`, SVG→`.svg`
- **AND** clipboard captures (re-encoded PNG bytes) SHALL be stored as `.png`

#### Scenario: Legacy `.png`-named entries remain readable

- **GIVEN** a pre-existing entry stored as `{handle}.png` whose `meta.json` has no `file` key
- **WHEN** `image.ask()`, `image.summary()`, or `image.delete()` is called for that handle
- **THEN** the content file SHALL be resolved by extension-insensitive lookup and the operation SHALL succeed

#### Scenario: Background summary skipped when no vision model
- **WHEN** `image.load()` is called and `model` is not configured (empty string)
- **THEN** no background thread SHALL be spawned for auto-summary

#### Scenario: Load from clipboard

- **WHEN** `image.load(img="clip")` is called on Windows or macOS with an image in
  the clipboard
- **THEN** it SHALL capture the clipboard image, save it, and return a result dict
- **AND** `source` in `meta.json` SHALL be `"clipboard"`

#### Scenario: Load from URL

- **WHEN** `image.load(img="https://...")` is called
- **THEN** it SHALL download the image, save it, and return a result dict
- **AND** `source` in `meta.json` SHALL be the URL string

#### Scenario: Named handle

- **WHEN** `image.load(img="~/ui.png", handle="vscode")` is called
- **THEN** the `handle` key in the returned dict SHALL be `"#vscode"`
- **AND** the files SHALL be saved as `vscode.<ext>` (extension matching the detected source format) and `vscode.meta.json`

#### Scenario: Dedup — same content loaded twice (auto-handle)

- **GIVEN** `image.load(img="~/a.png")` has been called and returned `{"handle": "#img_a3f7b2c4", ...}`
- **WHEN** `image.load(img="~/a.png")` is called again without a `handle=` parameter
- **THEN** it SHALL return a dict with `handle: "#img_a3f7b2c4"` and `dedup: true` without writing new files

#### Scenario: Named handle bypasses content dedup

- **WHEN** `image.load(img="~/a.png", handle="ref")` is called for content already stored under an auto-handle
- **THEN** it SHALL create a new entry `"#ref"` — deduplication does NOT apply to named handles
- **AND** the tool docstring SHALL document this limitation

#### Scenario: Named handle collision with different content

- **GIVEN** `image.load(img="~/a.png", handle="vscode")` has been called
- **WHEN** `image.load(img="~/b.png", handle="vscode")` is called with different content
- **THEN** it SHALL return `{"error": "handle #vscode already exists with different content..."}`

#### Scenario: Glob rejected by `load()`

- **WHEN** `image.load(img="~/screenshots/*.png")` is called
- **THEN** it SHALL return `{"error": "...use load_batch()..."}`

#### Scenario: Linux clipboard not supported

- **WHEN** `image.load(img="clip")` is called on Linux
- **THEN** it SHALL return `{"error": "...Linux clipboard is not yet supported..."}`

#### Scenario: Image resize

- **GIVEN** `max_edge=1568` (default)
- **WHEN** an image with longest edge > 1568px is loaded
- **THEN** the original file SHALL be saved at full resolution
- **AND** only the in-memory model-upload bytes SHALL be resized — no resized file
  written to disk
- **AND** `meta.json` SHALL record both `original_dims` and `model_dims`

---

### Requirement: Load multiple images in batch

`image.load_batch()` SHALL accept a glob pattern or a list of source strings, load each,
and return a list of result dicts (same format as `image.load()`).

#### Scenario: Glob load

- **WHEN** `image.load_batch(img="~/screenshots/*.png")` is called
- **THEN** it SHALL return a `list[dict]` of result dicts, one per matched file
- **AND** each image SHALL be loaded as if `image.load()` were called individually

#### Scenario: List of sources

- **WHEN** `image.load_batch(img=["~/a.png", "~/b.png", "https://..."])` is called
- **THEN** it SHALL return a `list[dict]` of result dicts in input order

#### Scenario: Empty glob

- **WHEN** `image.load_batch(img="~/screenshots/*.xyz")` matches no files
- **THEN** it SHALL return an empty list `[]`

---

### Requirement: Ask questions about a loaded image

`image.ask()` SHALL send one or more images and one or more questions to the configured vision model and return answers. The `img` parameter SHALL accept a single image reference (string) or a list of image references; each reference may be a handle (`"#name"` or bare `"name"`), file path, URL, or `"clip"`.

#### Scenario: Single question

- **WHEN** `image.ask(img="#img_a3f7b2c4", q="What framework is shown?")` is called
- **THEN** it SHALL return `{"result": [{"question": "What framework is shown?", "answer": "<answer text>"}], "handle": "#img_a3f7b2c4"}`

#### Scenario: Batch questions — structured single call

- **WHEN** `image.ask(img="#img_a3f7b2c4", q=["Extract text", "Is this dark mode?"])`
  is called
- **THEN** it SHALL send all questions in a single model call requesting a JSON response of the form `{"answers": [...]}` with exactly one answer string per question
- **AND** it SHALL return `{"result": [{"question": "Extract text", "answer": "<answer1>"}, {"question": "Is this dark mode?", "answer": "<answer2>"}], "handle": "#img_a3f7b2c4"}`
- **AND** result entries SHALL be in the same order as the input list

#### Scenario: Batch answer parsing falls back to per-question calls

- **GIVEN** a batched multi-question call whose model response cannot be parsed
  as JSON with exactly one answer per question
- **WHEN** `image.ask(img="#h", q=["q1", "q2"])` processes that response
- **THEN** it SHALL fall back to one model call per question, in input order
- **AND** each returned `answer` SHALL be the complete answer to its own question — answers SHALL NOT be truncated, merged across questions, or silently replaced with empty strings due to response formatting

#### Scenario: Multi-image ask

- **GIVEN** handles `"#before"` and `"#after"` are loaded
- **WHEN** `image.ask(img=["#before", "#after"], q="What changed between these screenshots?")` is called
- **THEN** it SHALL send both images in a single model call, each preceded by a positional label (`"Image 1"`, `"Image 2"`, ...) in list order
- **AND** it SHALL return `{"result": [{"question": ..., "answer": ...}], "handles": ["#before", "#after"]}`

#### Scenario: Multi-image response shape keyed by input type

- **WHEN** `image.ask(img=["#only"], q="...")` is called with a single-element list
- **THEN** the response SHALL contain `handles: ["#only"]` (a list), not `handle`
- **WHEN** `image.ask(img="#only", q="...")` is called with a plain string
- **THEN** the response SHALL contain `handle: "#only"` (a string), not `handles`

#### Scenario: Multi-image list entries accept any reference form

- **WHEN** `image.ask(img=["#h1", "~/b.png", "https://example.org/c.png"], q="...")` is called
- **THEN** each entry SHALL be resolved as `image.load()` would resolve it (handles pass through; paths and URLs are auto-loaded with hash dedup)

#### Scenario: Multi-image resolution failure fails fast

- **WHEN** `image.ask(img=["#h1", "#missing"], q="...")` is called and `"#missing"` cannot be resolved
- **THEN** it SHALL return `{"error": "...", "handle": "#missing"}` identifying the failing reference
- **AND** it SHALL NOT make a vision model call

#### Scenario: Empty image list

- **WHEN** `image.ask(img=[], q="...")` is called
- **THEN** it SHALL return an `{"error": ...}` dict stating the list is empty
- **AND** it SHALL NOT make a vision model call

#### Scenario: Multi-image cap

- **WHEN** `image.ask(img=[...], q="...")` is called with more than 8 image references
- **THEN** it SHALL return an `{"error": ...}` dict naming the 8-image limit
- **AND** it SHALL NOT make a vision model call

#### Scenario: `"clip"` shorthand — auto-load

- **WHEN** `image.ask(img="clip", q="What is this?")` is called with no prior clipboard
  load this session
- **THEN** it SHALL auto-load the clipboard image, then proceed with the question
- **AND** the returned handle SHALL match what `image.load(img="clip")` would return

#### Scenario: `"clip"` shorthand — refresh clipboard each call

- **GIVEN** `image.load(img="clip")` or `image.ask(img="clip", ...)` was called
  earlier this session
- **WHEN** `image.ask(img="clip", q="What is this?")` is called again
- **THEN** it SHALL read current clipboard bytes again before answering
- **AND** if clipboard bytes are unchanged, it SHALL return the existing handle via hash dedup
- **AND** if clipboard bytes changed, it SHALL return the handle for the new clipboard image

#### Scenario: Unknown handle

- **WHEN** `image.ask(img="#notexist", q="...")` is called
- **THEN** it SHALL return `{"error": "Error: handle #notexist not found", "handle": "#notexist"}`

#### Scenario: Bare handle name (without # prefix)

- **WHEN** `image.ask(img="img_a3f7b2c4", q="...")` is called (no `#` prefix)
- **AND** a handle named `"img_a3f7b2c4"` exists in storage
- **THEN** it SHALL resolve to that handle and proceed normally

#### Scenario: Vision model not configured

- **WHEN** `image.ask()` is called and no `model` is set in config
- **THEN** it SHALL return `{"error": "Error: ...", "handle": "..."}` where `error` starts with `"Error:"`
- **AND** it SHALL NOT raise an exception

---

### Requirement: Extract and cache a structured image summary

`image.summary()` SHALL run a generic extraction prompt once per image, cache the result
in `meta.json`, and return immediately on repeat calls.

#### Scenario: First call — triggers model

- **WHEN** `image.summary(img="#img_a3f7b2c4")` is called and `summary` is `null` in
  `meta.json`
- **THEN** it SHALL call the vision model with the extraction prompt
- **AND** return `{"summary": {"type": ..., "mode": ..., "colours": [...], "description": ..., "content": ...}, "handle": "#img_a3f7b2c4", "cached": false}`
- **AND** write the `summary` dict into `meta.json`

#### Scenario: Repeat call — cached, no model call

- **GIVEN** `image.summary(img="#img_a3f7b2c4")` has been called once
- **WHEN** `image.summary(img="#img_a3f7b2c4")` is called again
- **THEN** it SHALL return the cached summary with `"cached": true`
- **AND** SHALL NOT make a vision model API call

#### Scenario: `"clip"` summary — refresh clipboard each call

- **GIVEN** `image.load(img="clip")`, `image.ask(img="clip", ...)`, or `image.summary(img="clip")`
  was called earlier this session
- **WHEN** `image.summary(img="clip")` is called again
- **THEN** it SHALL read current clipboard bytes again before summarising
- **AND** if clipboard bytes are unchanged, it SHALL return the existing handle via hash dedup
- **AND** if clipboard bytes changed, it SHALL return the handle for the new clipboard image

#### Scenario: `clip_view()` delegates to clipboard summary

- **WHEN** `image.clip_view()` is called
- **THEN** it SHALL behave exactly like `image.summary(img="clip")`
- **AND** it SHALL return the same response shape as `image.summary()`

#### Scenario: Summary JSON keys

- **WHEN** a summary is returned
- **THEN** it SHALL contain exactly the keys: `type`, `mode`, `colours`, `description`, `content`
- **AND** `mode` SHALL be one of `"dark"`, `"light"`, `"unknown"`
- **AND** `content` SHALL be an empty string (not null) if no text is visible

---

### Requirement: List loaded images

`image.list()` SHALL return metadata for all images currently in the session images directory.

#### Scenario: Basic list

- **WHEN** `image.list()` is called after loading two images
- **THEN** it SHALL return a list of dicts, one per image
- **AND** each dict SHALL contain: `handle`, `source`, `dims`, `resized`,
  `created_at`, `summary` (bool), `type` (null if summary not called)

#### Scenario: Empty store

- **WHEN** `image.list()` is called with no images loaded
- **THEN** it SHALL return an empty list `[]`

---

### Requirement: Delete a loaded image

`image.delete()` SHALL remove the stored content file (whatever its extension), `meta.json`, and session cache entry for a given handle.

#### Scenario: Successful delete

- **GIVEN** handle `"#img_a3f7b2c4"` is loaded with a stored content file `img_a3f7b2c4.<ext>`
- **WHEN** `image.delete(handle="#img_a3f7b2c4")` is called
- **THEN** it SHALL delete the content file and `img_a3f7b2c4.meta.json` from the session images directory, regardless of the content file's extension
- **AND** remove the entry from the session LRU cache
- **AND** return a confirmation string

#### Scenario: Delete unknown handle

- **WHEN** `image.delete(handle="#notexist")` is called
- **THEN** it SHALL return an error string indicating the handle was not found

### Requirement: Purge images by age

`image.purge()` SHALL delete images older than a given number of minutes, or all images when `all=True`.

#### Scenario: Purge with minutes

- **WHEN** `image.purge(minutes=120)` is called
- **THEN** it SHALL delete all image files and meta.json pairs whose `created_at`
  is more than 120 minutes ago
- **AND** return `{"purged": N, "bytes_freed": N}`

#### Scenario: Purge default (no argument)

- **WHEN** `image.purge()` is called with no arguments
- **THEN** it SHALL delete images older than 15 minutes (the default)
- **AND** return `{"purged": N, "bytes_freed": N}`

#### Scenario: Purge all

- **WHEN** `image.purge(all=True)` is called
- **THEN** it SHALL delete all images in the session images directory regardless of age
- **AND** return `{"purged": N, "bytes_freed": N}`

#### Scenario: Zero or negative minutes raises

- **WHEN** `image.purge(minutes=0)` or `image.purge(minutes=-1)` is called
- **THEN** it SHALL raise `ValueError`

---

### Requirement: Session cache is bounded

The in-memory session LRU cache SHALL enforce a maximum entry count to prevent unbounded
memory growth.

#### Scenario: Eviction at limit

- **GIVEN** `session_cache_size=10` (default)
- **WHEN** an 11th distinct image is loaded
- **THEN** the least-recently-used entry SHALL be evicted from the in-memory cache
- **AND** the evicted image's file SHALL remain on disk unaffected

#### Scenario: Re-access after eviction

- **GIVEN** an image was evicted from the session cache
- **WHEN** `image.ask()` is called with its handle
- **THEN** it SHALL re-read the file from disk and re-encode for the model call

---

### Requirement: Configuration via `tools.image` block

The `ot_image` pack SHALL be configurable via `onetool.yaml` under
`tools.ot_image`. Its `llm` selection SHALL control generation for `image.ask()` and
`image.summary()`, while image processing settings SHALL remain pack-level fields.

#### Scenario: model required for ask and summary

- **WHEN** no model is supplied by the call, `tools.ot_image.llm`, or top-level `llm`
- **AND** `image.ask()` is called or `image.summary()` requires generation on a cache miss
- **THEN** it SHALL return an error string, not raise, indicating a generation model is required

#### Scenario: Inherit generation selection from top-level llm config

- **WHEN** a generation field is not set under `tools.ot_image.llm`
- **THEN** `image` SHALL inherit that field from the top-level `llm` configuration
- **AND** a CLIProxyAPI route SHALL use its inference client credential without requiring `OPENAI_API_KEY`

#### Scenario: Per-call model and effort override

- **WHEN** `image.ask()` is called, or `image.summary()` requires generation on a cache miss, with `model="terra"` and `effort="high"`
- **THEN** the operation SHALL resolve `terra` from the shared registry and request high effort
- **AND** the selected model SHALL be validated for image input before network I/O

#### Scenario: Cached summary does not resolve overrides

- **GIVEN** an image already has a cached summary
- **WHEN** `image.summary()` is called with any model or effort override
- **THEN** it SHALL return the cached summary without resolving a generation route
- **AND** it SHALL NOT make a network request
- **AND** model or effort changes SHALL NOT implicitly invalidate the cache

#### Scenario: max_edge override

- **WHEN** `tools.ot_image.max_edge: 800` is set in config
- **AND** `image.load(img="~/large.png")` is called with a 2000×1500px image
- **THEN** the model-upload bytes SHALL be resized to fit within 800px on the long edge
