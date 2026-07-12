# Tasks: ot-image-capabilities

## 1. Format-preserving originals (store.py)

- [x] 1.1 Add a module-level format→extension map in `src/ottools/_image/store.py` (PNG→png, JPEG→jpg, GIF→gif, WEBP→webp, TIFF→tiff, HEIC→heic, AVIF→avif, SVG→svg) and an `ext_for_format(fmt: str) -> str` helper defaulting to `png` for unknown values
- [x] 1.2 Change `save_image()` to take the detected format (or extension), write `{handle}.{ext}` instead of hard-coded `.png`, and set `meta["file"] = "{handle}.{ext}"` before serialising meta.json
- [x] 1.3 Rework `load_raw_bytes()` to resolve the content file via `meta["file"]` when present, else glob `{handle}.*` excluding `.meta.json` and `.tmp` (legacy `.png` fallback)
- [x] 1.4 Rework `delete_handle_files()` to unlink all files matching `{handle}.*` (content file, meta.json, stray tmp) and return `(found, bytes_freed)` as before
- [x] 1.5 In `load()` (`src/ottools/_image/tools.py`), capture the return of the existing `validate_image_bytes()` call and pass the detected format through to `save_image()`; do NOT use `prep.original_format` (SVG rasterises to PNG before Pillow)
- [x] 1.6 Unit tests in `tests/ottools/unit/tools/test_image.py`: JPEG bytes stored as `.jpg` with `file` key in meta; SVG stored as `.svg`; legacy `{handle}.png` without `file` key still resolved by `load_raw_bytes()` and deleted by `delete_handle_files()`; `purge()`/`delete()` free non-`.png` content files

## 2. Vision layer: multi-image + JSON answer contract (vision.py)

- [x] 2.1 Factor a `parse_json_payload(text: str) -> dict | None` helper out of `extract_summary()`'s fence-strip + `json.loads` + embedded-object fallback; refactor `extract_summary()` to use it (behavior unchanged)
- [x] 2.2 Change `call_vision()` to accept `images: list[bytes]`; build message content as interleaved text labels + image blocks (`"Image 1:"`, image1, `"Image 2:"`, image2, …, prompt) when `len(images) > 1`, single image block + prompt otherwise
- [x] 2.3 Change `ask_questions()` to accept `images: list[bytes]`; replace the numbered-list prompt with a JSON contract prompt (return only `{"answers": [...]}` with exactly N answer strings in question order); delete the `_num_pat` regex splitting and empty-string padding
- [x] 2.4 Parse the batched response with `parse_json_payload()`; validate `answers` is a list of exactly N entries (coerce entries via `str()`); on API error (`"Error:"` result) return `[error]` unchanged; on parse/count failure fall back to one `call_vision()` per question in order, recording `fallback=per_question` on the LogSpan
- [x] 2.5 Keep the single-question path as a plain-text call (no JSON round-trip)
- [x] 2.6 Unit tests: batched JSON response parsed into ordered answers; fenced/preambled JSON handled; malformed response triggers per-question fallback with correct per-question answers; answer-count mismatch triggers fallback; API error short-circuits without fallback; `extract_summary()` still parses via the shared helper

## 3. Multi-image ask (tools.py + facade)

- [x] 3.1 Change `ask()` signature in `src/ottools/_image/tools.py` to `ask(*, img: str | list[str], q: str | list[str], max_edge: int = 1568)`; normalise `img` to a list plus an `is_multi` flag from the input type
- [x] 3.2 Guard clauses before any model call: empty list → `{"error": "img list is empty"}`; more than 8 entries → error naming the 8-image cap
- [x] 3.3 Resolve each entry via `_resolve_handle_name()`; on first failure return `{"error": ..., "handle": "<failing ref>"}` without calling the model; verify each resolved handle's meta and model bytes as the single-image path does today
- [x] 3.4 Call `ask_questions(images, questions, config)` with all resolved model bytes; return `{"result": pairs, "handle": "#name"}` for string input and `{"result": pairs, "handles": ["#a", ...]}` for list input (including single-element lists)
- [x] 3.5 Update the `ask()` docstring (multi-image usage, response shape by input type, 8-image cap, comparison example) — the facade `src/ottools/ot_image.py` re-exports it unchanged
- [x] 3.6 Unit tests: two-handle ask returns `handles` list and passes both byte payloads to the vision layer in order; single-element list returns `handles` not `handle`; string input still returns `handle`; empty list and 9-entry list error without a model call; unresolvable entry fails fast identifying the reference
- [x] 3.7 Integration test in `tests/integration/tools/test_image.py`: `ask(img=[h1, h2], q="what differs?")` against two small fixture images returns one answer and both handles

## 4. Verification

- [x] 4.1 Run `uv run pytest -m "unit and tools" tests/ottools/unit/tools/test_image.py` — all pass
- [x] 4.2 Run `just lint` and `uv run mypy src/ottools` (or the project's mypy invocation) — clean
- [x] 4.3 Confirm delta scenarios in `openspec/changes/ot-image-capabilities/specs/ottools/tool-image/spec.md` each map to a passing test (multi-image shapes, cap, fallback, extension preservation, legacy `.png` compatibility)
