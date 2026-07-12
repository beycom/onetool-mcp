# Design: ot-image-capabilities

## Context

The `ot_image` pack (`src/ottools/ot_image.py` facade + `src/ottools/_image/` implementation) loads images into `.onetool/images/` under stable content-hash handles and queries them with an OpenAI-compatible vision model. Three deferred gaps remain after the bug-fix commits (b45c29a6, 60ceaa8b):

1. `ask()` (`_image/tools.py`) takes exactly one image reference — no way to ask comparison questions across images.
2. `save_image()` (`_image/store.py:46-61`) always writes `{handle}.png` even though the bytes are saved verbatim in their source format; `load_raw_bytes()`, `delete_handle_files()` and the main spec all hard-code `.png`.
3. `ask_questions()` (`_image/vision.py:109-163`) batches questions as a numbered list and re-splits the response with regex `^\s*(?:[#*]+\s*)?(\d+)[.)]\s*` — headings, bold numbering, or answers containing numbered lists corrupt the split, and misses are silently padded with empty strings.

Constraints: no new dependencies, no config schema changes, strict mypy/ruff, existing single-image call sites and stored `.png` files must keep working.

## Goals / Non-Goals

**Goals:**
- `ask()` accepts multiple image references and sends them in one vision call.
- Stored originals keep their source format extension; all read/delete paths resolve the content file regardless of extension.
- Batched answers are recovered via a structured JSON contract with a lossless per-question fallback — a question never gets another question's answer or a silent empty string.

**Non-Goals:**
- Linux clipboard support (Linux is not a supported platform for this pack).
- A separate `compare()` tool — `ask(img=[...])` covers comparison.
- Multi-image `summary()` / `load()` shape changes beyond the `file` meta key.
- Transcoding originals (bytes remain verbatim; only the filename changes).
- Switching the vision client to structured-output APIs (`response_format`) — see Decisions.

## Decisions

### D1: Multi-image via `ask(img=[...])`, not a new tool

`ask()` signature becomes `ask(*, img: str | list[str], q: str | list[str], max_edge: int = 1568)`. Each list entry is resolved through the existing `_resolve_handle_name()` (handles, bare names, paths, URLs, `"clip"` all work). Alternative — a dedicated `compare()` tool — rejected: it would duplicate resolution/return plumbing and grow the facade for what is the same operation with N images.

Response shape is keyed by input type: `img` as `str` returns `{"result": [...], "handle": "#a"}` exactly as today; `img` as `list` returns `{"result": [...], "handles": ["#a", "#b", ...]}` — even for a single-element list, so callers can rely on the shape from the type they passed. On any per-entry resolution failure, return `{"error": ..., "handle": "<failing ref>"}` immediately (fail fast, no partial vision call).

Limits: empty list → `{"error": "img list is empty"}`; more than 8 entries → error naming the cap (providers commonly cap images per request; 8 keeps payloads sane at max_edge 1568).

Vision layer: `call_vision()` and `ask_questions()` take `images: list[bytes]` (single-image callers pass a one-element list — internal API, all call sites updated in this change). For multi-image calls the message content interleaves a text label before each image block (`"Image 1:"`, image, `"Image 2:"`, image, …, prompt) so questions can reference "image 1" / "image 2" unambiguously.

`clip_ask()` is unchanged (single clipboard image).

### D2: Format-preserving originals via extension map + `file` meta key

`load()` already calls `validate_image_bytes()` (magic-byte detection, `_image/sources.py:31`) but discards its return. Capture it and map to an extension: `PNG→png, JPEG→jpg, GIF→gif, WEBP→webp, TIFF→tiff, HEIC→heic, AVIF→avif, SVG→svg`. Do not use `prepare_for_model().original_format` for this — SVG is rasterised before Pillow sees it, so Pillow reports PNG.

- `save_image(raw_bytes, handle_name, meta, *, ext)` writes `{handle}.{ext}`; the stored filename is recorded as `meta["file"]` (e.g. `"img_a3f7b2c4.jpg"`) before serialisation.
- `load_raw_bytes()` resolves the content file from `meta["file"]` when present; otherwise falls back to globbing `{handle}.*` excluding `.meta.json` and `.tmp` — this keeps pre-change `.png` entries (whose meta lacks `file`) readable. Alternative — one-shot migration renaming old files — rejected: session storage is short-lived (default purge 15 min) and the glob fallback is two lines.
- `delete_handle_files()` unlinks everything matching `{handle}.*` (content file, `meta.json`, stray `.tmp`) instead of the two hard-coded names. Handle names cannot collide across the dot boundary, so the glob is exact.
- `list_images()` / `purge_images()` iterate `*.meta.json` and delegate deletion to `delete_handle_files()` — no changes beyond inheriting the new behavior.
- Clipboard captures are re-encoded PNG bytes, so they naturally store as `.png`.

### D3: JSON answer contract with per-question fallback (no `response_format`)

For multi-question batches, the prompt instructs the model to return only `{"answers": ["<answer 1>", ..., "<answer N>"]}` with exactly N strings, in question order. Parsing reuses a shared helper `parse_json_payload(text)` factored out of `extract_summary()`'s existing fence-strip + `json.loads` + embedded-object-regex logic (`vision.py:186-202`); `extract_summary()` is refactored onto the same helper.

Validation: payload parses, `answers` is a list of exactly N entries (entries coerced via `str()`). If the batched call returns an API error (`"Error:"` prefix) → return `[error]` as today (fallback would fail identically). If the call succeeds but validation fails → fall back to one `call_vision()` per question, sequentially, preserving order; the fallback is recorded on the LogSpan (`fallback=per_question`).

Alternatives rejected:
- Keep regex, harden patterns — the failure class (model formatting drift) is open-ended; padding-with-empty-string stays silently lossy.
- `response_format={"type": "json_object"}` — many OpenAI-compatible endpoints (local gateways, non-OpenAI providers) reject the parameter; prompt-level JSON plus fallback works everywhere.
- Always per-question calls — N× latency/cost on the happy path for no benefit.

Single-question calls stay plain text (no JSON round-trip, no behavior change).

## Risks / Trade-offs

- [Multi-image payload size: 8 images × ~1568px PNG can be large] → cap at 8, images already resized to `max_edge` before encoding; documented in the `ask()` docstring.
- [Fallback doubles latency when the model ignores the JSON contract] → rare with `temperature=0.1`; fallback is logged via LogSpan so drift is observable.
- [Glob resolution could match unexpected files] → glob excludes `.meta.json`/`.tmp`, and `meta["file"]` short-circuits the glob for all new entries.
- [Internal `ask_questions`/`call_vision` signature change] → all callers live in `_image/` (`tools.py`); updated atomically in this change, no external surface.
- [Old meta.json without `file` key] → glob fallback covers; no migration needed for short-lived session storage.

## Migration Plan

Single-release change, no flags. Existing `.png`-named entries remain readable/deletable via the glob fallback; new loads write format-true extensions. Rollback = revert the commit (old code reads `.png` only, so non-PNG entries loaded under the new code would need a `purge(all=True)` after rollback — acceptable for session-scoped storage).

## Open Questions

None.
