# Proposal: ot-image-capabilities

## Why

The `ot_image` pack has three deferred capability gaps from the ot-image fixes issue (bug fixes already landed in b45c29a6/60ceaa8b): agents cannot ask comparison questions across multiple loaded images, originals are silently re-labelled as `.png` on disk regardless of source format (a JPEG source is stored byte-verbatim under a misleading `.png` name), and batched `ask()` answers are recovered from the model response with a fragile numbered-list regex that breaks whenever the model deviates from the expected numbering format.

## What Changes

- **Multi-image ask**: `image.ask()` accepts `img` as a list of image references (handles, paths, URLs) in addition to a single string. All referenced images are sent in one vision call, enabling comparison questions ("what changed between these two screenshots?"). Multi-image responses include a `handles` list instead of a single `handle`.
- **Format-preserving originals**: `image.load()` stores the original file under its detected format extension (`img_<hash>.jpg`, `vscode.webp`, …) instead of always `.png`. `meta.json` gains a `file` key recording the stored filename; read/delete/purge paths resolve the content file via meta or extension glob, remaining backward compatible with existing `.png`-named entries.
- **Robust batch-answer parsing**: the numbered-answer regex in `_image/vision.py` is replaced by a JSON-structured response contract (model returns `{"answers": [...]}`); on parse failure or answer-count mismatch, the pack falls back to one model call per question so no question ever receives another question's answer or a silent empty string.

No breaking changes: single-image `ask()` calls, existing handles, and stored `.png` files continue to work unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ottools/tool-image`:
  - "Ask questions about a loaded image" — accepts a list of image references; multi-image response shape (`handles`); batch-question answering contract changes from "single model call with numbered parsing" to "JSON-structured single call with per-question fallback".
  - "Load a single image into session storage" — stored original filename preserves the source format extension; `meta.json` records the stored filename.
  - "Delete a loaded image" — deletes the content file whatever its extension, plus `meta.json`.

## Impact

- `src/ottools/_image/tools.py` — `ask()` signature (`img: str | list[str]`), multi-handle resolution, response shape.
- `src/ottools/_image/vision.py` — `ask_questions()` accepts multiple image byte payloads; JSON answer contract; per-question fallback; shared JSON-response parsing helper reused by `extract_summary()`.
- `src/ottools/_image/store.py` — `save_image()` extension mapping, `load_raw_bytes()` / `delete_handle_files()` content-file resolution, `file` key in meta.
- `src/ottools/_image/sources.py` — no behavior change (`validate_image_bytes()` already returns the detected format used for the extension mapping).
- `src/ottools/ot_image.py` — docstring/facade untouched except `ask` doc updates via re-export.
- Tests: `tests/ottools/unit/tools/test_image.py` (new cases), `tests/integration/tools/test_image.py` (multi-image ask).
- No new dependencies; no config schema changes.
