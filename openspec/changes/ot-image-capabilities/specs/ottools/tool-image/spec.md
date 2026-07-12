# tool-image Delta Specification

## MODIFIED Requirements

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
